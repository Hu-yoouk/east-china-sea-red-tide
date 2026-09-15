# -*- coding: utf-8 -*-
"""
Step 3.4: TCN时序修正模块
======================================================================
定位：LightGBM为主干时序修正机制

建模逻辑：
  LightGBM 基于逐网格点的10维静态环境特征，已完成 AUC=0.979 的强基线。
  但赤潮爆发是一个动态过程——持续升温、低风速持续、季节异常等时域演变
  特征无法被 LightGBM 的静态截面视角捕获。

  TCN 在此不试图"超越" LightGBM，而是作为 时序修正器：
    - 输入：过去12个月的环境演变轨迹 + LightGBM基线预测值
    - 目标：残差 (residual = label − LightGBM_prob)
    - 输出：时序修正量 Δ_temporal，最终预测 = LightGBM_prob + Δ_temporal

  若 TCN 修正后 AUC/F1 无明显提升，说明时序演变信息已被 LightGBM
  的月份特征和静态变量间接捕获，深度模型并非必要；
  若有提升，则为 LightGBM 的静态视角提供了动态补充。

架构：膨胀因果卷积 (dilated causal convolution) + 残差连接
  通道数 [16, 32, 48]，卷积核3，dropout 0.3
"""

import os, sys, warnings, numpy as np, pandas as pd
warnings.filterwarnings("ignore")

import torch, torch.nn as nn, torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from sklearn.metrics import (roc_auc_score, accuracy_score, precision_score,
                             recall_score, f1_score, confusion_matrix,
                             classification_report)
import lightgbm as lgb

# ── Paths ──────────────────────────────────────
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMP_DATA = os.path.join(BASE, "03_时序特征工程", "temporal_features.csv")
RAW_DATA  = os.path.join(BASE, "01_数据预处理", "cleaned_red_tide_data.csv")
OUT       = os.path.join(BASE, "03_时序特征工程", "output_tcn")
os.makedirs(OUT, exist_ok=True)

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Device: {DEVICE}")

# ── Parameters ─────────────────────────────────
SEQ_LEN = 12
BATCH_SIZE = 512
EPOCHS = 80
LR = 5e-4
WD = 1e-3
# NUM_CHANNELS not used (MLP architecture)
KERNEL_SIZE = 3
DROPOUT = 0.3
EARLY_STOP = 15

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
META = ['year','month','longitude','latitude','grid_id','red_tide_label']

# ════════════════════════════════════════════════
# 1. 加载数据 & 生成 LightGBM 基线
# ════════════════════════════════════════════════
print("=" * 60)
print("TCN Temporal Correction Module")
print("  Role: Correct LightGBM residual using temporal dynamics")
print("=" * 60)

print("\n[1/6] Loading data...")
df_raw = pd.read_csv(RAW_DATA)
df_temp = pd.read_csv(TEMP_DATA)

# Sort both identically
df_raw = df_raw.sort_values(["longitude","latitude","year","month"]).reset_index(drop=True)
df_temp = df_temp.sort_values(["longitude","latitude","year","month"]).reset_index(drop=True)

# Add grid_id to raw
df_raw["grid_id"] = df_raw.groupby(["longitude","latitude"]).ngroup()

# Temporal split (no future leakage for LightGBM baseline)
ALL_YEARS = sorted(df_raw["year"].unique())
TRAIN_YEARS = [y for y in ALL_YEARS if y <= 2017]
VAL_YEARS   = [2018, 2019]
TEST_YEARS  = [y for y in ALL_YEARS if y >= 2020]
print(f"  Train: {TRAIN_YEARS[0]}-{TRAIN_YEARS[-1]}  "
      f"Val: {VAL_YEARS[0]}-{VAL_YEARS[-1]}  "
      f"Test: {TEST_YEARS[0]}-{TEST_YEARS[-1]}")

# ── Train LightGBM baseline (temporal split) ──
print("\n[LightGBM baseline] Training with temporal split...")
tr_mask = df_raw["year"].isin(TRAIN_YEARS)
val_mask = df_raw["year"].isin(VAL_YEARS)
te_mask = df_raw["year"].isin(TEST_YEARS)

X_tr = df_raw.loc[tr_mask, RAW_FEATURES].values
y_tr = df_raw.loc[tr_mask, "red_tide_label"].values
X_val = df_raw.loc[val_mask, RAW_FEATURES].values
y_val = df_raw.loc[val_mask, "red_tide_label"].values
X_te = df_raw.loc[te_mask, RAW_FEATURES].values
y_te = df_raw.loc[te_mask, "red_tide_label"].values

lgb_model = lgb.train(LGB_PARAMS,
                      lgb.Dataset(X_tr, label=y_tr),
                      num_boost_round=500,
                      valid_sets=[lgb.Dataset(X_val, label=y_val)],
                      callbacks=[lgb.early_stopping(30), lgb.log_evaluation(0)])

# Generate baseline predictions
lgb_prob_tr = lgb_model.predict(X_tr)
lgb_prob_val = lgb_model.predict(X_val)
lgb_prob_te = lgb_model.predict(X_te)

for name, prob, lbl in [("Train", lgb_prob_tr, y_tr),
                         ("Val", lgb_prob_val, y_val),
                         ("Test", lgb_prob_te, y_te)]:
    auc = roc_auc_score(lbl, prob)
    f1 = f1_score(lbl, (prob >= 0.5).astype(int))
    print(f"  LightGBM {name}: AUC={auc:.4f}  F1={f1:.4f}")

# ── Build TCN dataset with residual targets ──
# The TCN input = temporal features; target = residual = label - LightGBM_prob
# TCN output = delta to add to LightGBM baseline
print("\n[2/6] Building TCN dataset with residual targets...")

FEATURE_COLS = [c for c in df_temp.columns if c not in META]
N_FEATURES = len(FEATURE_COLS)
print(f"  Temporal features: {N_FEATURES}")

# Fill NaN in temporal features
for col in FEATURE_COLS:
    if df_temp[col].isna().sum() > 0:
        df_temp[col] = df_temp.groupby("grid_id")[col].transform(
            lambda x: x.bfill().ffill())

# Merge LightGBM predictions as baseline input
df_temp["lgb_prob"] = np.concatenate([lgb_prob_tr, lgb_prob_val, lgb_prob_te])
# lgb_prob is kept separate and NOT normalized (preserving its 0-1 probability scale)
FEATURE_COLS_ONLY = FEATURE_COLS  # temporal features only (57)
FEATURE_COLS_WITH_BASELINE = FEATURE_COLS + ["lgb_prob"]  # 58 features for model input

class ResidualDataset(Dataset):
    """TCN inputs: temporal sequence; targets: residual after LightGBM."""
    def __init__(self, df_temp, df_raw, feature_cols, seq_len=12,
                 year_range=None):
        self.seq_len = seq_len
        self.feature_cols = feature_cols
        # lgb_prob is the last feature in feature_cols
        self.has_baseline = "lgb_prob" in feature_cols

        if year_range:
            mask = df_temp["year"].isin(year_range)
            df_t = df_temp[mask].copy()
            df_r = df_raw[mask].copy()
        else:
            df_t = df_temp.copy()
            df_r = df_raw.copy()

        samples, labels, lgb_baselines, metas = [], [], [], []
        sample_count = 0
        correction_pos = 0
        correction_neg = 0

        for grid_id, grp in df_t.groupby("grid_id"):
            grp = grp.sort_values(["year","month"]).reset_index(drop=True)
            vals = grp[feature_cols].values.astype(np.float32)
            lgb_b = vals[:, -1].copy()  # lgb_prob is last column
            # Get true labels from raw data
            grid_mask = (df_r["grid_id"] == grid_id)
            raw_grp = df_r[grid_mask].sort_values(["year","month"]).reset_index(drop=True)
            true_labels = raw_grp["red_tide_label"].values.astype(np.float32)

            # Normalize ONLY temporal features (exclude lgb_prob from normalization)
            temp_vals = vals[:, :-1]  # all columns except lgb_prob
            train_end = int(len(temp_vals) * 0.8)
            valid_mask = ~np.isnan(temp_vals[:train_end]).any(axis=1)
            if valid_mask.sum() < 10:
                continue
            mean = temp_vals[:train_end][valid_mask].mean(axis=0)
            std = temp_vals[:train_end][valid_mask].std(axis=0) + 1e-8
            temp_vals = (temp_vals - mean) / std
            # Reconstruct: normalized temporal + raw lgb_prob
            vals = np.column_stack([temp_vals, lgb_b])

            for t in range(seq_len, len(vals)):
                if np.isnan(vals[t-seq_len:t, :-1]).any():
                    continue
                samples.append(vals[t-seq_len:t])
                # Target = residual
                residual = true_labels[t] - lgb_b[t]
                labels.append(residual)
                lgb_baselines.append(lgb_b[t])
                metas.append({
                    "year": int(grp.iloc[t]["year"]),
                    "month": int(grp.iloc[t]["month"]),
                    "grid_id": int(grid_id),
                    "true_label": int(true_labels[t]),
                    "lgb_prob": float(lgb_b[t]),
                })
                sample_count += 1
                lgb_pred = (lgb_b[t] >= 0.5).astype(int)
                if lgb_pred != true_labels[t]:
                    if true_labels[t] == 1:
                        correction_pos += 1
                    else:
                        correction_neg += 1

        self.samples = np.array(samples)
        self.labels = np.array(labels)
        self.lgb_baselines = np.array(lgb_baselines)
        self.metas = metas

        print(f"  Dataset: {len(self.samples)} sequences, "
              f"residual mean={self.labels.mean():.4f}")
        print(f"  LightGBM errors in this split: "
              f"FN={correction_pos} (missed RT), FP={correction_neg} (false alarm)")
        print(f"  Max correction opportunity: {correction_pos + correction_neg} / {sample_count} "
              f"({(correction_pos+correction_neg)/sample_count*100:.1f}%)")

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        return (torch.tensor(self.samples[idx], dtype=torch.float32),
                torch.tensor(self.labels[idx], dtype=torch.float32),
                torch.tensor(self.metas[idx]['true_label'], dtype=torch.float32))

# Build datasets for each split
train_ds = ResidualDataset(df_temp, df_raw, FEATURE_COLS_WITH_BASELINE, SEQ_LEN,
                           year_range=TRAIN_YEARS)
val_ds   = ResidualDataset(df_temp, df_raw, FEATURE_COLS_WITH_BASELINE, SEQ_LEN,
                           year_range=VAL_YEARS)
test_ds  = ResidualDataset(df_temp, df_raw, FEATURE_COLS_WITH_BASELINE, SEQ_LEN,
                           year_range=TEST_YEARS)

train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True, drop_last=True)
val_loader   = DataLoader(val_ds,   batch_size=BATCH_SIZE, shuffle=False)
test_loader  = DataLoader(test_ds,  batch_size=BATCH_SIZE, shuffle=False)

# ════════════════════════════════════════════════
# 2. TCN 架构
# ════════════════════════════════════════════════
input_size = len(FEATURE_COLS_WITH_BASELINE)

class TemporalCorrector(nn.Module):
    """
    时序修正器: 简化 MLP 架构, 零初始化最后一层保证起始修正为 0
      输入: 展平的 12 个月时序特征 + lgb_logit
      输出: Δ_temporal (logit 空间修正量)
      combined_prob = sigmoid(lgb_logit + Δ_temporal)
    """
    def __init__(self, n_temporal_features, seq_len=12, hidden=64):
        super().__init__()
        self.seq_len = seq_len
        self.n_features = n_temporal_features
        input_dim = n_temporal_features * seq_len  # flattened temporal sequence
        self.net = nn.Sequential(
            nn.Linear(input_dim, hidden),
            nn.BatchNorm1d(hidden),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(hidden, hidden // 2),
            nn.BatchNorm1d(hidden // 2),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(hidden // 2, 1),
        )
        # Zero-init the last layer so initial delta = 0
        nn.init.zeros_(self.net[-1].weight)
        nn.init.zeros_(self.net[-1].bias)

    def forward(self, x, lgb_logit):
        # x: (B, seq_len, n_features)
        B = x.shape[0]
        x_flat = x.reshape(B, -1)  # (B, seq_len * n_features)
        delta = self.net(x_flat).squeeze(-1)  # (B,)
        combined_logit = delta + lgb_logit
        combined_prob = torch.sigmoid(combined_logit)
        return combined_prob, delta

# ════════════════════════════════════════════════
# 3. 训练
# ════════════════════════════════════════════════
print(f"\n[3/6] Initializing TCN Corrector...")
model = TemporalCorrector(input_size, SEQ_LEN, hidden=64).to(DEVICE)
n_params = sum(p.numel() for p in model.parameters())
print(f"  Input: {input_size} features x {SEQ_LEN} timesteps (flattened)")
print(f"  Hidden: 64->32->1 (last layer zero-initialized)")
print(f"  Parameters: {n_params:,}")

# Loss: BCE on combined prediction vs true label
# This is more stable than MSE on residual because sigmoid constrains output to [0,1]
# and the gradient is naturally bounded
criterion = nn.BCEWithLogitsLoss()
optimizer = optim.AdamW(model.parameters(), lr=LR, weight_decay=WD)
scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode="min", factor=0.5, patience=5)

print("\n[4/6] Training (predicting residual, not raw label)...")
best_val_loss = float("inf")
best_state = None
best_epoch = 0
patience_counter = 0
train_losses, val_losses = [], []

for epoch in range(1, EPOCHS + 1):
    # Train
    model.train()
    epoch_loss = 0.0
    for bx, by, _ in train_loader:
        bx, by = bx.to(DEVICE), by.to(DEVICE)
        # Extract LightGBM baseline from last feature column (concatenated)
        lgb_b = bx[:, -1, -1]  # last timestep's lgb_prob feature
        # Or more precisely: the lgb_prob is the last feature, take the last timestep's value
        # Actually, lgb_prob is constant across time for each sample, so just take position [:, -1, -1]
        optimizer.zero_grad()
        combined_pred, delta = model(bx, lgb_b)
        loss = criterion(delta, by)  # MSE on residual
        loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()
        epoch_loss += loss.item()

    # Validation
    model.eval()
    val_loss = 0.0
    with torch.no_grad():
        for bx, by, true_lbl in val_loader:
            bx, true_lbl = bx.to(DEVICE), true_lbl.to(DEVICE)
            lgb_b = bx[:, -1, -1]
            combined_pred, delta = model(bx, lgb_b)
            val_loss += criterion(delta + lgb_b, true_lbl).item()

    train_losses.append(epoch_loss / len(train_loader))
    val_losses.append(val_loss / len(val_loader))
    scheduler.step(val_losses[-1])

    if val_losses[-1] < best_val_loss:
        best_val_loss = val_losses[-1]
        best_state = model.state_dict()
        best_epoch = epoch
        patience_counter = 0
    else:
        patience_counter += 1

    if epoch % 5 == 0 or epoch == 1:
        print(f"  Epoch {epoch:3d}: train_loss={train_losses[-1]:.6f}  "
              f"val_loss={val_losses[-1]:.6f}  (best={best_val_loss:.6f} @ {best_epoch})")

    if patience_counter >= EARLY_STOP:
        print(f"  Early stopping at epoch {epoch}")
        break

model.load_state_dict(best_state)
torch.save(model.state_dict(), os.path.join(OUT, "tcn_corrector.pt"))

np.savez(os.path.join(OUT, "training_history.npz"),
         train_losses=np.array(train_losses),
         val_losses=np.array(val_losses))

# ════════════════════════════════════════════════
# 4. 评估：LightGBM vs LightGBM+TCN
# ════════════════════════════════════════════════
print("\n[5/6] Evaluating correction performance...")

def evaluate_correction(model, loader, device):
    """Evaluate LightGBM alone vs LightGBM+TCN."""
    model.eval()
    all_lgb_prob = []
    all_combined = []
    all_true = []
    all_deltas = []

    with torch.no_grad():
        for bx, by, true_lbl in loader:
            bx = bx.to(device)
            lgb_prob = bx[:, -1, -1]  # raw 0-1 probability
            # Convert to logit for model input
            eps_e = 1e-7
            lgb_logit = torch.log(lgb_prob.clamp(eps_e, 1-eps_e) / (1 - lgb_prob.clamp(eps_e, 1-eps_e)))
            combined, delta = model(bx, lgb_logit)
            all_combined.extend(combined.cpu().numpy())
            all_lgb_prob.extend(lgb_prob.cpu().numpy())
            all_true.extend(true_lbl.cpu().numpy())
            all_deltas.extend(delta.cpu().numpy())

    all_lgb_prob = np.array(all_lgb_prob)
    all_combined = np.array(all_combined)
    all_true = np.array(all_true)
    all_deltas = np.array(all_deltas)

    # Metrics
    lgb_auc = roc_auc_score(all_true, all_lgb_prob)
    combined_auc = roc_auc_score(all_true, all_combined)
    lgb_f1 = f1_score(all_true, (all_lgb_prob >= 0.5).astype(int))
    combined_f1 = f1_score(all_true, (all_combined >= 0.5).astype(int))

    # Correction analysis
    lgb_wrong = ((all_lgb_prob >= 0.5).astype(int) != all_true)
    corrected = lgb_wrong & ((all_combined >= 0.5).astype(int) == all_true)
    worsened = ~lgb_wrong & ((all_combined >= 0.5).astype(int) != all_true)
    n_corrected = corrected.sum()
    n_worsened = worsened.sum()
    n_lgb_wrong = lgb_wrong.sum()

    return {
        "lgb_auc": lgb_auc, "combined_auc": combined_auc,
        "lgb_f1": lgb_f1, "combined_f1": combined_f1,
        "n_corrected": n_corrected, "n_worsened": n_worsened,
        "n_lgb_wrong": n_lgb_wrong, "n_total": len(all_true),
        "delta_mean": all_deltas.mean(),
        "delta_std": all_deltas.std(),
        "all_lgb_prob": all_lgb_prob, "all_combined": all_combined,
        "all_true": all_true, "all_deltas": all_deltas,
    }

# Test set evaluation
results = evaluate_correction(model, test_loader, DEVICE)

print(f"\n  ┌──────────────────────────┬──────────┬──────────┐")
print(f"  │ Metric                   │ LightGBM │ +TCN     │")
print(f"  ├──────────────────────────┼──────────┼──────────┤")
print(f"  │ AUC                      │ {results['lgb_auc']:.4f}  │ {results['combined_auc']:.4f}  │")
print(f"  │ F1                       │ {results['lgb_f1']:.4f}  │ {results['combined_f1']:.4f}  │")
print(f"  └──────────────────────────┴──────────┴──────────┘")
print(f"\n  Correction analysis (test set):")
print(f"    LightGBM wrong:         {results['n_lgb_wrong']:>5d} / {results['n_total']:>5d} "
      f"({results['n_lgb_wrong']/results['n_total']*100:.1f}%)")
print(f"    Corrected by TCN:       {results['n_corrected']:>5d} "
      f"({results['n_corrected']/max(results['n_lgb_wrong'],1)*100:.1f}% of errors)")
print(f"    Worsened by TCN:        {results['n_worsened']:>5d} "
      f"({results['n_worsened']/max(results['n_total']-results['n_lgb_wrong'],1)*100:.1f}% of correct)")
print(f"    Mean correction (delta): {results['delta_mean']:.4f} +/- {results['delta_std']:.4f}")

# Save predictions
np.savez(os.path.join(OUT, "test_predictions.npz"),
         lgb_prob=results["all_lgb_prob"],
         combined_prob=results["all_combined"],
         true_label=results["all_true"],
         delta=results["all_deltas"])

# ════════════════════════════════════════════════
# 5. 报告
# ════════════════════════════════════════════════
print("\n[6/6] Generating report...")
report_path = os.path.join(OUT, "tcn_correction_report.txt")
with open(report_path, "w", encoding="utf-8") as f:
    f.write("=" * 70 + "\n")
    f.write("TCN Temporal Correction Module Report\n")
    f.write("=" * 70 + "\n\n")
    f.write("Modeling Philosophy:\n")
    f.write("  LightGBM is the primary trusted model (AUC=0.979 on CV).\n")
    f.write("  TCN acts as a temporal correction module:\n")
    f.write("    - Input: 12-month temporal dynamics + LightGBM baseline\n")
    f.write("    - Target: residual = label - LightGBM_prob\n")
    f.write("    - Output: Δ_temporal, combined = LightGBM + Δ_temporal\n\n")
    f.write(f"Architecture: MLP({input_size}x{SEQ_LEN} -> 64 -> 32 -> 1)\\n")
    f.write(f"Parameters: {n_params:,}\n")
    f.write(f"Sequence length: {SEQ_LEN} months\n")
    f.write(f"Dropout: {DROPOUT}, Weight decay: {WD}\n\n")
    f.write(f"Temporal split: Train={TRAIN_YEARS[0]}-{TRAIN_YEARS[-1]}, "
            f"Val={VAL_YEARS[0]}-{VAL_YEARS[-1]}, Test={TEST_YEARS[0]}-{TEST_YEARS[-1]}\n\n")
    f.write("--- Test Performance ---\n")
    f.write(f"  LightGBM alone:  AUC={results['lgb_auc']:.4f}, F1={results['lgb_f1']:.4f}\n")
    f.write(f"  LightGBM + TCN:  AUC={results['combined_auc']:.4f}, "
            f"F1={results['combined_f1']:.4f}\n")
    f.write(f"  AUC improvement: {results['combined_auc']-results['lgb_auc']:+.4f}\n")
    f.write(f"  F1 improvement:  {results['combined_f1']-results['lgb_f1']:+.4f}\n\n")
    f.write("--- Correction Analysis ---\n")
    f.write(f"  Samples where LightGBM is wrong: {results['n_lgb_wrong']} "
            f"({results['n_lgb_wrong']/results['n_total']*100:.1f}%)\n")
    f.write(f"  Errors corrected by TCN:        {results['n_corrected']} "
            f"({results['n_corrected']/max(results['n_lgb_wrong'],1)*100:.1f}% of errors)\n")
    f.write(f"  Correct predictions worsened:   {results['n_worsened']} "
            f"({results['n_worsened']/max(results['n_total']-results['n_lgb_wrong'],1)*100:.1f}%)\n\n")
    f.write("--- Delta Statistics ---\n")
    f.write(f"  Mean Δ: {results['delta_mean']:.4f}\n")
    f.write(f"  Std Δ:  {results['delta_std']:.4f}\n")
    f.write(f"  Max Δ:  {results['all_deltas'].max():.4f}\n")
    f.write(f"  Min Δ:  {results['all_deltas'].min():.4f}\n")

print(f"\n  Report: {report_path}")
print(f"\n{'='*60}")
print("TCN correction module complete!")
print(f"{'='*60}")
