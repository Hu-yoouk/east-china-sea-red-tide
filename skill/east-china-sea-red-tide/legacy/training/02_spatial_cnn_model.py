# -*- coding: utf-8 -*-
"""
Step 4.2: Spatial-CNN 空间修正模块
======================================================================
定位：LightGBM为主干 空间邻域修正机制

建模逻辑：
  LightGBM 逐网格点独立预测，完全不考虑空间邻域信息。
  但赤潮具有"成片爆发"特征——邻近网格的环境条件（SST梯度、
  叶绿素斑块结构）是重要的空间上下文信号。

  Spatial-CNN 在此不试图"超越" LightGBM，而是作为 空间修正器：
    - 输入：逐月 15×13 空间栅格（10个环境通道 + LightGBM基线通道）
    - 目标：残差 (residual = label − LightGBM_prob)
    - 输出：空间修正量 Δ_spatial, 最终预测 = LightGBM_prob + Δ_spatial
    - 注意力可视化揭示哪些空间区域驱动修正

架构：2层Conv2D + GAP + FC
  Conv1: 11→16 (3×3, padding=1)
  Conv2: 16→32 (3×3, padding=1)
  GAP + FC(32→1)
"""

import os, sys, warnings, numpy as np, pandas as pd
warnings.filterwarnings("ignore")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import rcParams
rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "DejaVu Sans"]
rcParams["axes.unicode_minus"] = False

from sklearn.metrics import (roc_auc_score, accuracy_score, precision_score,
                             recall_score, f1_score, roc_curve)
import torch, torch.nn as nn, torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import lightgbm as lgb

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TENSOR_PATH = os.path.join(BASE, "04_空间CNN模型", "output_cnn", "spatial_tensor.npz")
RAW_DATA   = os.path.join(BASE, "01_数据预处理", "cleaned_red_tide_data.csv")
OUT_DIR    = os.path.join(BASE, "04_空间CNN模型", "output_cnn")
os.makedirs(OUT_DIR, exist_ok=True)
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Device: {DEVICE}")

# ── Parameters ─────────────────────────────────
BATCH_SIZE = 16
MAX_EPOCHS = 200
LR = 1e-3
WD = 1e-4
PATIENCE = 20
N_VARS = 10
H, W = 15, 13

LGB_PARAMS = {
    "objective": "binary", "metric": "auc", "boosting_type": "gbdt",
    "num_leaves": 31, "learning_rate": 0.05,
    "feature_fraction": 0.8, "bagging_fraction": 0.8, "bagging_freq": 5,
    "min_data_in_leaf": 50, "lambda_l1": 0.1, "lambda_l2": 1.0,
    "verbose": -1, "random_state": 42,
}
RAW_FEATURES = ["sst","chlorophyll","wind_speed","pressure",
                "solar_radiation","precipitation","salinity",
                "nitrate","phosphate","silicate"]

# ════════════════════════════════════════════════
# 1. 加载数据 & 生成 LightGBM 空间基线
# ════════════════════════════════════════════════
print("=" * 60)
print("Spatial-CNN Correction Module")
print("  Role: Correct LightGBM residual using spatial context")
print("=" * 60)

print("\n[1/7] Loading spatial tensor...")
data = np.load(TENSOR_PATH, allow_pickle=True)
tensor = data["tensor"].astype(np.float32)        # (T, C, H, W)
labels = data["labels"].astype(np.float32)          # (T,)
time_keys = data["time_keys"]                       # (T,)
var_names = list(data["var_names"])                 # [C]
train_mask = data["train_mask"]                     # (T,) bool
val_mask = data["val_mask"]
test_mask = data["test_mask"]

T_total = len(labels)
print(f"  Tensor: {tensor.shape}  Labels: {labels.shape}  "
      f"Train={train_mask.sum()}  Val={val_mask.sum()}  Test={test_mask.sum()}")

# ── Build LightGBM spatial baseline ──
# For each month, train LightGBM on per-grid features and average predictions
# across the spatial domain to get a monthly spatial-pooled baseline
print("\n[Generating LightGBM spatial baseline...]")
df_raw = pd.read_csv(RAW_DATA)
df_raw = df_raw.sort_values(["longitude","latitude","year","month"]).reset_index(drop=True)

# Generate monthly LightGBM predictions for the full domain
# Use temporal split to avoid future leakage
years = df_raw["year"].unique()
train_yrs = [y for y in years if y <= 2017]
val_yrs   = [2018, 2019]
test_yrs  = [y for y in years if y >= 2020]

tr = df_raw["year"].isin(train_yrs)
va = df_raw["year"].isin(val_yrs)
te = df_raw["year"].isin(test_yrs)

lgb_model = lgb.train(LGB_PARAMS,
                      lgb.Dataset(df_raw.loc[tr, RAW_FEATURES].values,
                                  label=df_raw.loc[tr, "red_tide_label"].values),
                      num_boost_round=500,
                      valid_sets=[lgb.Dataset(df_raw.loc[va, RAW_FEATURES].values,
                                              label=df_raw.loc[va, "red_tide_label"].values)],
                      callbacks=[lgb.early_stopping(30), lgb.log_evaluation(0)])

# Get per-grid predictions for all months
df_raw["lgb_prob"] = lgb_model.predict(df_raw[RAW_FEATURES].values)

# Aggregate to monthly domain averages: for each month, average across all 195 grid points
monthly_lgb = df_raw.groupby(["year","month"])["lgb_prob"].mean().reset_index()
monthly_lgb.columns = ["year","month","lgb_prob"]

# Also get monthly true labels (presence/absence at domain level)
monthly_true = df_raw.groupby(["year","month"])["red_tide_label"].max().reset_index()
monthly_true.columns = ["year","month","label_domain"]

# ── Align with spatial tensor time indices ──
# Extract year,month from time_keys
lgb_baseline = np.zeros(T_total, dtype=np.float32)
lgb_monthly_labels = np.zeros(T_total, dtype=np.float32)
for i, tk in enumerate(time_keys):
    # time_keys can be like '2004-01', '2004_01', or numpy scalar array
    tk_str = str(tk).replace('_', '-')
    parts = tk_str.split('-')
    yr, mo = int(parts[0]), int(parts[1])
    row = monthly_lgb[(monthly_lgb["year"]==yr) & (monthly_lgb["month"]==mo)]
    if len(row) > 0:
        lgb_baseline[i] = row["lgb_prob"].values[0]
    true_row = monthly_true[(monthly_true["year"]==yr) & (monthly_true["month"]==mo)]
    if len(true_row) > 0:
        lgb_monthly_labels[i] = true_row["label_domain"].values[0]

# LightGBM baseline AUC
lgb_auc_full = roc_auc_score(labels, lgb_baseline)
print(f"  LightGBM spatial-pooled AUC: {lgb_auc_full:.4f}")

# ── Compute residual targets ──
residuals = lgb_monthly_labels - lgb_baseline  # target = true - baseline
print(f"  Residual: mean={residuals.mean():.4f}, std={residuals.std():.4f}")

# Add LightGBM baseline as an additional channel (channel index 10)
# Shape: (T, 1, H, W) - same LightGBM value for all grid points in a month
lgb_channel = lgb_baseline[:, np.newaxis, np.newaxis, np.newaxis]  # (T, 1, 1, 1)
lgb_channel = np.broadcast_to(lgb_channel, (T_total, 1, H, W))
tensor_with_lgb = np.concatenate([tensor, lgb_channel], axis=1)   # (T, 11, H, W)

# ════════════════════════════════════════════════
# 2. Dataset with residual targets
# ════════════════════════════════════════════════
class ResidualSpatialDataset(Dataset):
    def __init__(self, tensor, residuals, mask):
        idx = np.where(mask)[0]
        self.tensor = torch.from_numpy(tensor[idx])
        self.residuals = torch.from_numpy(residuals[idx]).float()
    def __len__(self):
        return len(self.residuals)
    def __getitem__(self, i):
        return self.tensor[i], self.residuals[i]

print(f"\n[2/7] Building dataset with residual targets...")
train_ds = ResidualSpatialDataset(tensor_with_lgb, residuals, train_mask)
val_ds   = ResidualSpatialDataset(tensor_with_lgb, residuals, val_mask)
test_ds  = ResidualSpatialDataset(tensor_with_lgb, residuals, test_mask)
train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True)
val_loader   = DataLoader(val_ds, batch_size=BATCH_SIZE)
test_loader  = DataLoader(test_ds, batch_size=BATCH_SIZE)

# ════════════════════════════════════════════════
# 3. 模型: 空间修正器
# ════════════════════════════════════════════════
class SpatialCorrector(nn.Module):
    """
    空间修正器: 输入空间栅格, 输出 Δ_spatial
    最终预测 = LightGBM_baseline + Δ_spatial
    """
    def __init__(self, in_channels=11):  # 10 env + 1 LightGBM
        super().__init__()
        self.conv1 = nn.Conv2d(in_channels, 16, kernel_size=3, padding=1)
        self.bn1 = nn.BatchNorm2d(16)
        self.conv2 = nn.Conv2d(16, 32, kernel_size=3, padding=1)
        self.bn2 = nn.BatchNorm2d(32)
        self.pool = nn.AdaptiveAvgPool2d(1)
        self.fc = nn.Linear(32, 1)

    def forward(self, x):
        # x: (B, C, H, W)
        x = torch.relu(self.bn1(self.conv1(x)))
        x = torch.relu(self.bn2(self.conv2(x)))
        x = self.pool(x).squeeze(-1).squeeze(-1)
        delta = self.fc(x).squeeze(-1)
        return delta

print(f"\n[3/7] Initializing Spatial Corrector...")
model = SpatialCorrector(in_channels=11).to(DEVICE)
n_params = sum(p.numel() for p in model.parameters())
print(f"  Architecture: 11 -> Conv(16) -> Conv(32) -> GAP -> FC(1)")
print(f"  Parameters: {n_params:,}")

criterion = nn.MSELoss()
optimizer = optim.AdamW(model.parameters(), lr=LR, weight_decay=WD)
scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode="min",
                                                   factor=0.5, patience=8)

# ════════════════════════════════════════════════
# 4. 训练
# ════════════════════════════════════════════════
print("\n[4/7] Training (predicting spatial residual)...")
best_val_loss = float("inf")
best_state = None
best_epoch = 0
counter = 0
train_hist, val_hist = [], []

for epoch in range(1, MAX_EPOCHS + 1):
    model.train()
    loss_sum = 0.0
    for bx, by in train_loader:
        bx, by = bx.to(DEVICE), by.to(DEVICE)
        optimizer.zero_grad()
        delta = model(bx)
        loss = criterion(delta, by)
        loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()
        loss_sum += loss.item()

    model.eval()
    vloss = 0.0
    with torch.no_grad():
        for bx, by in val_loader:
            vloss += criterion(model(bx.to(DEVICE)), by.to(DEVICE)).item()

    train_hist.append(loss_sum / len(train_loader))
    val_hist.append(vloss / len(val_loader))
    scheduler.step(val_hist[-1])

    if val_hist[-1] < best_val_loss:
        best_val_loss = val_hist[-1]
        best_state = model.state_dict()
        best_epoch = epoch
        counter = 0
    else:
        counter += 1

    if epoch % 10 == 0 or epoch == 1:
        print(f"  Epoch {epoch:3d}: train_loss={train_hist[-1]:.6f}  "
              f"val_loss={val_hist[-1]:.6f}  (best={best_val_loss:.6f} @ {best_epoch})")
    if counter >= PATIENCE:
        print(f"  Early stopping at epoch {epoch}")
        break

model.load_state_dict(best_state)
torch.save(model.state_dict(), os.path.join(OUT_DIR, "cnn_corrector.pt"))
np.savez(os.path.join(OUT_DIR, "training_history.npz"),
         train_losses=np.array(train_hist), val_losses=np.array(val_hist))

# ════════════════════════════════════════════════
# 5. 评估
# ════════════════════════════════════════════════
print("\n[5/7] Evaluating spatial correction...")

def eval_correction(model, loader, lgb_baseline_subset, device):
    model.eval()
    all_delta = []
    with torch.no_grad():
        for bx, _ in loader:
            all_delta.extend(model(bx.to(device)).cpu().numpy())
    all_delta = np.array(all_delta)
    # Combined = LightGBM + spatial correction
    lgb_sub = lgb_baseline_subset[:len(all_delta)]
    combined = np.clip(lgb_sub + all_delta, 0, 1)
    return combined, lgb_sub, all_delta

# Test set
test_indices = np.where(test_mask)[0]
lgb_test = lgb_baseline[test_indices]
combined, lgb_test_sub, deltas = eval_correction(model, test_loader, lgb_test, DEVICE)
true_test = labels[test_indices]

lgb_auc = roc_auc_score(true_test, lgb_test_sub)
cnn_auc = roc_auc_score(true_test, combined)
lgb_f1 = f1_score(true_test, (lgb_test_sub >= 0.5).astype(int))
cnn_f1 = f1_score(true_test, (combined >= 0.5).astype(int))

# Correction analysis
lgb_wrong = ((lgb_test_sub >= 0.5).astype(int) != true_test)
corrected = lgb_wrong & ((combined >= 0.5).astype(int) == true_test)
worsened = ~lgb_wrong & ((combined >= 0.5).astype(int) != true_test)

print(f"\n  ┌──────────────────────────┬──────────┬──────────┐")
print(f"  │ Metric                   │ LightGBM │ +CNN     │")
print(f"  ├──────────────────────────┼──────────┼──────────┤")
print(f"  │ AUC                      │ {lgb_auc:.4f}  │ {cnn_auc:.4f}  │")
print(f"  │ F1                       │ {lgb_f1:.4f}  │ {cnn_f1:.4f}  │")
print(f"  └──────────────────────────┴──────────┴──────────┘")
print(f"\n  Correction analysis:")
print(f"    LightGBM wrong:       {lgb_wrong.sum():>4d} / {len(true_test)}")
print(f"    Corrected by CNN:     {corrected.sum():>4d}")
print(f"    Worsened by CNN:      {worsened.sum():>4d}")
print(f"    Mean delta:           {deltas.mean():.4f}")

# Save test predictions
np.savez(os.path.join(OUT_DIR, "test_predictions.npz"),
         lgb_prob=lgb_test_sub, cnn_combined=combined,
         true_label=true_test, delta=deltas)

# ════════════════════════════════════════════════
# 6. 通道重要性
# ════════════════════════════════════════════════
print("\n[6/7] Channel importance analysis...")
model.eval()
channel_names = var_names + ["LightGBM_baseline"]

# For each channel, zero it out and measure AUC drop
base_correct, base_lgb, _ = eval_correction(model, test_loader, lgb_test, DEVICE)
base_auc = roc_auc_score(true_test, base_correct)

channel_aucs = {}
for c in range(tensor_with_lgb.shape[1]):
    # Create modified tensor with channel c zeroed
    with torch.no_grad():
        tensor_ablated = tensor_with_lgb.copy()
        tensor_ablated[:, c] = 0.0
        ablated_ds = ResidualSpatialDataset(tensor_ablated, residuals, test_mask)
        ablated_loader = DataLoader(ablated_ds, batch_size=BATCH_SIZE)
        ablated, _, _ = eval_correction(model, ablated_loader,
                                         lgb_test, DEVICE)
        ablated_auc = roc_auc_score(true_test, ablated)
        channel_aucs[channel_names[c]] = base_auc - ablated_auc

# Plot
sorted_channels = sorted(channel_aucs.items(), key=lambda x: -abs(x[1]))
fig, ax = plt.subplots(figsize=(10, 5))
names = [s[0] for s in sorted_channels]
vals = [s[1] for s in sorted_channels]
colors = ["#FF6B6B" if "LightGBM" in n else "#2196F3" for n in names]
ax.barh(range(len(names)), vals, color=colors, edgecolor="white", height=0.6)
ax.set_yticks(range(len(names)))
ax.set_yticklabels(names, fontsize=9)
ax.set_xlabel("AUC Drop (channel zeroed)", fontsize=12)
ax.set_title("Spatial-CNN Channel Importance (AUC drop when channel removed)",
             fontsize=13, fontweight="bold")
ax.axvline(x=0, color="gray", alpha=0.3)
ax.invert_yaxis()
ax.grid(True, alpha=0.3, axis="x")
plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, "channel_importance.png"), dpi=150, bbox_inches="tight")
plt.close()
print("  Saved: channel_importance.png")

# ════════════════════════════════════════════════
# 7. 报告
# ════════════════════════════════════════════════
print("\n[7/7] Generating report...")
report_path = os.path.join(OUT_DIR, "cnn_correction_report.txt")
with open(report_path, "w", encoding="utf-8") as f:
    f.write("=" * 70 + "\n")
    f.write("Spatial-CNN Correction Module Report\n")
    f.write("=" * 70 + "\n\n")
    f.write("Modeling Philosophy:\n")
    f.write("  LightGBM is per-grid-point, ignores spatial context.\n")
    f.write("  CNN corrects LightGBM residual using spatial patterns.\n\n")
    f.write(f"Architecture: 11 -> Conv(16) -> Conv(32) -> GAP -> FC(1)\n")
    f.write(f"Parameters: {n_params:,}\n\n")
    f.write("--- Test Performance ---\n")
    f.write(f"  LightGBM alone:       AUC={lgb_auc:.4f}, F1={lgb_f1:.4f}\n")
    f.write(f"  LightGBM + CNN:       AUC={cnn_auc:.4f}, F1={cnn_f1:.4f}\n")
    f.write(f"  AUC improvement:      {cnn_auc-lgb_auc:+.4f}\n\n")
    f.write(f"  LightGBM wrong:       {lgb_wrong.sum()} / {len(true_test)}\n")
    f.write(f"  Corrected by CNN:     {corrected.sum()}\n")
    f.write(f"  Worsened by CNN:      {worsened.sum()}\n\n")
    f.write("--- Channel Importance ---\n")
    for name, val in sorted_channels:
        f.write(f"  {name:<20s}: AUC drop = {val:.4f}\n")

print(f"\n  Report: {report_path}")
print(f"\n{'='*60}")
print("Spatial-CNN correction module complete!")
print(f"{'='*60}")
