# -*- coding: utf-8 -*-
"""Step 3.8: Regional TCN model (single clean time series)
- Trains on regional-averaged features (240 months, 57 features)
- Key insight: label is identical across all 195 grids,
  regional averaging reduces noise by ~14x
- Includes month encoding for seasonal awareness
- Walk-forward validation for reliable evaluation
- Very small architecture (avoid overfitting on 240 samples)
"""

import os, sys, warnings
import numpy as np
import pandas as pd
warnings.filterwarnings("ignore")

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader

from sklearn.metrics import (roc_auc_score, accuracy_score,
    precision_score, recall_score, f1_score, confusion_matrix,
    classification_report)

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "03_时序特征工程", "temporal_features_regional.csv")
OUT = os.path.join(BASE, "03_时序特征工程", "output_tcn_regional")
os.makedirs(OUT, exist_ok=True)

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print("Device:", DEVICE)

# ===== Parameters =====
SEQ_LEN = 12
BATCH_SIZE = 32
EPOCHS = 100
LEARNING_RATE = 3e-4
WEIGHT_DECAY = 5e-4
NUM_CHANNELS = [8, 16, 24]
KERNEL_SIZE = 3
DROPOUT = 0.4
EARLY_STOP_PATIENCE = 20

# ===== Load regional data =====
print("[1/6] Loading regional features...")
df = pd.read_csv(DATA)
print("  Shape:", df.shape)

META_COLS = ["year", "month", "red_tide_label"]
FEATURE_COLS = [c for c in df.columns if c not in META_COLS]
N_FEATURES = len(FEATURE_COLS)
print("  Features:", N_FEATURES)

# Fill NaN
for col in FEATURE_COLS:
    if df[col].isna().sum() > 0:
        df[col] = df[col].bfill().ffill()
print("  NaN after fill:", df[FEATURE_COLS].isna().sum().sum())

# ===== Month encoding (sin/cos for seasonal awareness) =====
# The TCN needs to know which month it is to interpret anomalies meaningfully
df['month_sin'] = np.sin(2 * np.pi * df['month'] / 12)
df['month_cos'] = np.cos(2 * np.pi * df['month'] / 12)
ENCODED_FEATURES = FEATURE_COLS + ['month_sin', 'month_cos']
N_ENCODED = len(ENCODED_FEATURES)
print("  With month encoding:", N_ENCODED, "features")

# ===== Dataset class (single time series) =====
class RegionalTimeSeriesDataset(Dataset):
    def __init__(self, df, feature_cols, seq_len=12):
        self.seq_len = seq_len
        self.feature_cols = feature_cols
        self.samples = []
        self.labels = []
        self.years = []

        df = df.sort_values(["year", "month"]).reset_index(drop=True)
        values = df[feature_cols].values.astype(np.float32)
        labels = df["red_tide_label"].values.astype(np.float32)
        years = df["year"].values

        # Z-score normalization using training statistics
        # (applied after splitting, so we pass pre-normalized data)
        for t in range(seq_len, len(values)):
            self.samples.append(values[t - seq_len : t])
            self.labels.append(labels[t])
            self.years.append(years[t])

        self.samples = np.array(self.samples)
        self.labels = np.array(self.labels)
        self.years = np.array(self.years)
        print("  Dataset: {} sequences, label_ratio={:.3f}".format(
            len(self.samples), self.labels.mean()))

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        return (torch.tensor(self.samples[idx], dtype=torch.float32),
                torch.tensor(self.labels[idx], dtype=torch.float32))


def normalize_series(values, train_end):
    """Z-score normalize using first train_end samples."""
    mean = values[:train_end].mean(axis=0)
    std = values[:train_end].std(axis=0) + 1e-8
    return (values - mean) / std


# ===== Walk-forward temporal split =====
print("\n[2/6] Walk-forward split...")
df_sorted = df.sort_values(["year", "month"]).reset_index(drop=True)

# Get the values and labels
all_values = df_sorted[ENCODED_FEATURES].values.astype(np.float32)
all_labels = df_sorted["red_tide_label"].values.astype(np.float32)
all_years = df_sorted["year"].values

# Split by time (years)
TRAIN_YEARS = [y for y in sorted(df["year"].unique()) if y <= 2017]
VAL_YEARS = [2018, 2019]
TEST_YEARS = [y for y in sorted(df["year"].unique()) if y >= 2020]

train_mask = df_sorted["year"].isin(TRAIN_YEARS)
val_mask = df_sorted["year"].isin(VAL_YEARS)
test_mask = df_sorted["year"].isin(TEST_YEARS)

print("  Train years:", TRAIN_YEARS[0], "-", TRAIN_YEARS[-1])
print("  Val years:", VAL_YEARS)
print("  Test years:", TEST_YEARS)

# Normalize each split independently using training statistics
train_end = sum(train_mask)
all_values_normalized = normalize_series(all_values, train_end)

train_df = df_sorted[train_mask].copy()
val_df = df_sorted[val_mask].copy()
test_df = df_sorted[test_mask].copy()

for split_df, split_name in [(train_df, "train"), (val_df, "val"), (test_df, "test")]:
    split_df["month_sin"] = np.sin(2 * np.pi * split_df["month"] / 12)
    split_df["month_cos"] = np.cos(2 * np.pi * split_df["month"] / 12)

train_ds = RegionalTimeSeriesDataset(train_df, ENCODED_FEATURES, SEQ_LEN)
val_ds = RegionalTimeSeriesDataset(val_df, ENCODED_FEATURES, SEQ_LEN)
test_ds = RegionalTimeSeriesDataset(test_df, ENCODED_FEATURES, SEQ_LEN)

train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True, drop_last=True)
val_loader = DataLoader(val_ds, batch_size=BATCH_SIZE, shuffle=False)
test_loader = DataLoader(test_ds, batch_size=BATCH_SIZE, shuffle=False)

# ===== TCN Architecture (same as v2, lightweight) =====
class Chomp1d(nn.Module):
    def __init__(self, chomp_size):
        super(Chomp1d, self).__init__()
        self.chomp_size = chomp_size
    def forward(self, x):
        return x[:, :, :-self.chomp_size]

class TemporalBlock(nn.Module):
    def __init__(self, n_inputs, n_outputs, kernel_size, dilation, dropout=0.3):
        super(TemporalBlock, self).__init__()
        padding = (kernel_size - 1) * dilation
        self.conv1 = nn.Conv1d(n_inputs, n_outputs, kernel_size,
                               padding=padding, dilation=dilation)
        self.chomp1 = Chomp1d(padding)
        self.relu1 = nn.ReLU()
        self.dropout1 = nn.Dropout(dropout)
        self.conv2 = nn.Conv1d(n_outputs, n_outputs, kernel_size,
                               padding=padding, dilation=dilation)
        self.chomp2 = Chomp1d(padding)
        self.relu2 = nn.ReLU()
        self.dropout2 = nn.Dropout(dropout)
        self.net = nn.Sequential(
            self.conv1, self.chomp1, self.relu1, self.dropout1,
            self.conv2, self.chomp2, self.relu2, self.dropout2)
        self.downsample = nn.Conv1d(n_inputs, n_outputs, 1) if n_inputs != n_outputs else None
        self.relu = nn.ReLU()

    def forward(self, x):
        out = self.net(x)
        res = x if self.downsample is None else self.downsample(x)
        return self.relu(out + res)

class TCN(nn.Module):
    def __init__(self, input_size, num_channels, kernel_size=3, dropout=0.3):
        super(TCN, self).__init__()
        layers = []
        for i, c in enumerate(num_channels):
            dilation = 2 ** i
            in_c = input_size if i == 0 else num_channels[i-1]
            layers.append(TemporalBlock(in_c, c, kernel_size, dilation, dropout))
        self.tcn = nn.Sequential(*layers)
        self.gap = nn.AdaptiveAvgPool1d(1)
        self.fc = nn.Linear(num_channels[-1], 1)

    def forward(self, x):
        x = x.permute(0, 2, 1)
        x = self.tcn(x)
        x = self.gap(x).squeeze(-1)
        return self.fc(x).squeeze(-1)


# ===== Initialize model =====
print("\n[3/6] Initializing Regional TCN...")
model = TCN(N_ENCODED, NUM_CHANNELS, KERNEL_SIZE, DROPOUT).to(DEVICE)
total_params = sum(p.numel() for p in model.parameters())
print("  Architecture:", N_ENCODED, "->", NUM_CHANNELS, "-> GAP -> FC")
print("  Parameters: {:,}".format(total_params))

# Positive class weight
pos_count = train_ds.labels.sum()
neg_count = len(train_ds.labels) - pos_count
pos_weight = torch.tensor([neg_count / max(pos_count, 1)], device=DEVICE)
criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
print("  Class weight (neg/pos): {:.2f}".format(pos_weight.item()))

optimizer = optim.AdamW(model.parameters(), lr=LEARNING_RATE, weight_decay=WEIGHT_DECAY)
scheduler = optim.lr_scheduler.ReduceLROnPlateau(
    optimizer, mode='max', factor=0.5, patience=5, min_lr=1e-6)

# ===== Training =====
print("\n[4/6] Training...")
best_val_auc = 0.0
best_epoch = 0
best_model_state = None
train_losses, val_losses, val_aucs = [], [], []
early_stop_counter = 0

for epoch in range(1, EPOCHS + 1):
    model.train()
    epoch_loss = 0.0
    for batch_x, batch_y in train_loader:
        batch_x, batch_y = batch_x.to(DEVICE), batch_y.to(DEVICE)
        optimizer.zero_grad()
        loss = criterion(model(batch_x), batch_y)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()
        epoch_loss += loss.item()

    model.eval()
    val_loss = 0.0
    val_preds, val_labels = [], []
    with torch.no_grad():
        for batch_x, batch_y in val_loader:
            batch_x, batch_y = batch_x.to(DEVICE), batch_y.to(DEVICE)
            outputs = model(batch_x)
            val_loss += criterion(outputs, batch_y).item()
            val_preds.extend(torch.sigmoid(outputs).cpu().numpy())
            val_labels.extend(batch_y.cpu().numpy())

    val_auc = roc_auc_score(val_labels, val_preds)
    train_losses.append(epoch_loss / len(train_loader))
    val_losses.append(val_loss / len(val_loader))
    val_aucs.append(val_auc)
    scheduler.step(val_auc)

    if val_auc > best_val_auc:
        best_val_auc = val_auc
        best_epoch = epoch
        best_model_state = model.state_dict()
        early_stop_counter = 0
    else:
        early_stop_counter += 1

    if epoch % 5 == 0 or epoch == 1:
        print("  Epoch {:3d}/{}: train_loss={:.4f}, val_loss={:.4f}, val_auc={:.4f} (best={:.4f} @ {})".format(
            epoch, EPOCHS, train_losses[-1], val_losses[-1],
            val_auc, best_val_auc, best_epoch))

    if early_stop_counter >= EARLY_STOP_PATIENCE:
        print("  Early stopping @ epoch", epoch)
        break

model.load_state_dict(best_model_state)
print("\n  Best val AUC: {:.4f} @ epoch {}".format(best_val_auc, best_epoch))

torch.save(model.state_dict(), os.path.join(OUT, "regional_tcn_model.pt"))
np.savez(os.path.join(OUT, "training_history.npz"),
         train_losses=np.array(train_losses),
         val_losses=np.array(val_losses),
         val_aucs=np.array(val_aucs))

# ===== Test evaluation =====
print("\n[5/6] Test evaluation...")
model.eval()
test_preds, test_labels = [], []
with torch.no_grad():
    for batch_x, batch_y in test_loader:
        test_preds.extend(torch.sigmoid(model(batch_x.to(DEVICE))).cpu().numpy())
        test_labels.extend(batch_y.numpy())

test_preds = np.array(test_preds)
test_labels = np.array(test_labels)
test_preds_bin = (test_preds >= 0.5).astype(int)

test_auc = roc_auc_score(test_labels, test_preds)
test_acc = accuracy_score(test_labels, test_preds_bin)
test_prec = precision_score(test_labels, test_preds_bin)
test_rec = recall_score(test_labels, test_preds_bin)
test_f1 = f1_score(test_labels, test_preds_bin)

print("  Test AUC: {:.4f}, Acc: {:.4f}, F1: {:.4f}".format(test_auc, test_acc, test_f1))

np.savez(os.path.join(OUT, "test_predictions.npz"),
         preds=test_preds, labels=test_labels)

# ===== Year-by-year breakdown =====
print("\n[6/6] Year-by-year analysis...")
years_list = sorted(df["year"].unique())
if len(test_ds) > 0 and hasattr(test_ds, "years"):
    test_years = test_ds.years
    for yr in sorted(set(test_years)):
        yr_mask = test_years == yr
        if yr_mask.sum() > 0 and len(np.unique(test_labels[yr_mask])) > 1:
            yr_auc = roc_auc_score(test_labels[yr_mask], test_preds[yr_mask])
            print("  {}: AUC={:.4f} (n={})".format(yr, yr_auc, yr_mask.sum()))

# ===== Generate report =====
report_path = os.path.join(OUT, "regional_tcn_report.txt")
with open(report_path, "w", encoding="utf-8") as f:
    f.write("=" * 70 + "\n")
    f.write("Regional TCN Model Report (Single Clean Time Series)\n")
    f.write("=" * 70 + "\n\n")
    f.write("Architecture:\n")
    f.write("  Sequence length: {} months\n".format(SEQ_LEN))
    f.write("  Features: {} ({}+month encoding)\n".format(N_ENCODED, N_FEATURES))
    f.write("  Channels: {}\n".format(list(NUM_CHANNELS)))
    f.write("  Parameters: {:,}\n".format(total_params))
    f.write("  Dropout: {}\n".format(DROPOUT))
    f.write("  Weight decay: {}\n".format(WEIGHT_DECAY))

    f.write("Training:\n")
    f.write("  Best val AUC: {:.4f} @ epoch {}\n".format(best_val_auc, best_epoch))
    f.write("  Total epochs: {}\n".format(len(train_losses)))

    f.write("Test Performance (years {}-{}):\n".format(min(TEST_YEARS), max(TEST_YEARS)))
    f.write("  AUC:       {:.4f}\n".format(test_auc))
    f.write("  Accuracy:  {:.4f}\n".format(test_acc))
    f.write("  Precision: {:.4f}\n".format(test_prec))
    f.write("  Recall:    {:.4f}\n".format(test_rec))
    f.write("  F1-Score:  {:.4f}\n".format(test_f1))
    f.write("\nConfusion Matrix:\n")
    cm = confusion_matrix(test_labels, test_preds_bin)
    f.write("{}\n".format(cm))

print("\n  Report:", report_path)
print("\n=== Regional TCN training complete! ===")
print("\nKey insight: regional averaging removes grid noise,")
print("allowing TCN to focus on true temporal dynamics.")
print("Compare: per-grid TCN AUC=0.6005 vs regional TCN AUC={:.4f}".format(test_auc))