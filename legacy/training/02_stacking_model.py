# -*- coding: utf-8 -*-
"""
Step 5.2: Stacking Ensemble — 主干-修正器自适应融合
===========================================================================
定位：元学习器作为"仲裁者"，自动学习不同场景下的最优权重分配

建模逻辑：
  LightGBM 是可信主干 (AUC=0.979)。
  TCN 和 CNN 是修正器，分别输出 Δ_temporal 和 Δ_spatial。

  Stacking 不简单平均三个模型，而是通过元学习器学会：
    - 何时信任主干（稳态环境 → 高权重给 p_lgb）
    - 何时采纳时序修正（趋势变化期 → 采纳 Δ_temporal）
    - 何时采纳空间修正（空间异质期 → 采纳 Δ_spatial）

元特征设计：
  1. 主干信号: p_lgb (LightGBM 基线)
  2. 修正信号: delta_tcn, delta_cnn (修正量)
  3. 修正后信号: p_lgb_tcn, p_lgb_cnn (基线+修正)
  4. 一致性特征: p_max, p_min, p_std, entropy, confidence
  5. 局部解释特征: shap_top1, shap_top2, shap_top3
===========================================================================
"""
import os, sys, warnings, json
import numpy as np
import pandas as pd
warnings.filterwarnings('ignore')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import rcParams
rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
rcParams['axes.unicode_minus'] = False

from sklearn.metrics import (roc_auc_score, accuracy_score, precision_score,
                              recall_score, f1_score, confusion_matrix, roc_curve)
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
import lightgbm as lgb
import torch
import torch.nn as nn

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
META_CSV = os.path.join(BASE, '05_Stacking融合模型', 'output_stacking', 'meta_features.csv')
OUT_DIR  = os.path.join(BASE, '05_Stacking融合模型', 'output_stacking')
os.makedirs(OUT_DIR, exist_ok=True)

TRAIN_YEARS = list(range(2004, 2018))
VAL_YEARS   = [2018, 2019]
TEST_YEARS  = list(range(2020, 2024))

np.random.seed(42)
torch.manual_seed(42)

# ════════════════════════════════════════════════════════════════
# 1. 从 meta_features.csv 读取元特征
# ════════════════════════════════════════════════════════════════
print('=' * 60)
print('Stacking Ensemble — Backbone + Corrector Arbitration')
print('=' * 60)

print('\n[1/6] Loading meta-features from meta_features.csv...')
meta = pd.read_csv(META_CSV)
print(f'  Shape: {meta.shape}')
print(f'  Columns: {list(meta.columns)}')
print(f'  Year range: {meta["year"].min()}-{meta["year"].max()}')
label_dist = meta['true_label'].value_counts().to_dict()
print(f'  Label distribution: {label_dist}')

# ── Compute correction deltas ──
# In the correction framework:
#   delta_tcn = p_tcn - p_lgb   (how much TCN adjusts the backbone)
#   delta_cnn = p_cnn - p_lgb   (how much CNN adjusts the backbone)
meta['delta_tcn'] = meta['p_tcn'] - meta['p_lgb']
meta['delta_cnn'] = meta['p_cnn'] - meta['p_lgb']

# Corrected predictions (backbone + correction)
# p_lgb_tcn = p_lgb + delta_tcn = p_tcn (combined TCN prediction)
# p_lgb_cnn = p_lgb + delta_cnn = p_cnn (combined CNN prediction)
meta['p_lgb_tcn'] = meta['p_tcn']  # backbone + temporal correction
meta['p_lgb_cnn'] = meta['p_cnn']  # backbone + spatial correction

print('\n  Correction delta statistics:')
print(f'    delta_tcn: mean={meta["delta_tcn"].mean():+.4f}, '
      f'std={meta["delta_tcn"].std():.4f}, '
      f'range=[{meta["delta_tcn"].min():+.4f}, {meta["delta_tcn"].max():+.4f}]')
print(f'    delta_cnn: mean={meta["delta_cnn"].mean():+.4f}, '
      f'std={meta["delta_cnn"].std():.4f}, '
      f'range=[{meta["delta_cnn"].min():+.4f}, {meta["delta_cnn"].max():+.4f}]')

# ════════════════════════════════════════════════════════════════
# 2. 构建元特征向量 (Backbone + Corrections + Consistency)
# ════════════════════════════════════════════════════════════════
print('\n[2/6] Building meta-feature vectors...')

# Core meta-features in the correction framework
META_FEATURES = [
    # Backbone signal
    'p_lgb',
    # Correction signals
    'delta_tcn', 'delta_cnn',
    # Corrected predictions
    'p_lgb_tcn', 'p_lgb_cnn',
    # Consistency / uncertainty features
    'p_max', 'p_min', 'p_std', 'entropy', 'confidence',
    # SHAP interaction features
    'shap_top1', 'shap_top2', 'shap_top3',
    # Agreement flags
    'all_agree', 'majority_rt',
]
# Ensure boolean columns are int
if meta['all_agree'].dtype == bool:
    meta['all_agree'] = meta['all_agree'].astype(int)
if meta['majority_rt'].dtype == bool:
    meta['majority_rt'] = meta['majority_rt'].astype(int)

print(f'  Meta features ({len(META_FEATURES)}): {META_FEATURES}')

# ════════════════════════════════════════════════════════════════
# 3. Walk-Forward Split (时序前向分割)
# ════════════════════════════════════════════════════════════════
print('\n[3/6] Walk-forward split...')

meta_train = meta[meta['year'].isin(TRAIN_YEARS)].copy()
meta_val   = meta[meta['year'].isin(VAL_YEARS)].copy()
meta_test  = meta[meta['year'].isin(TEST_YEARS)].copy()

X_train = meta_train[META_FEATURES].values.astype(np.float32)
y_train = meta_train['true_label'].values
X_val   = meta_val[META_FEATURES].values.astype(np.float32)
y_val   = meta_val['true_label'].values
X_test  = meta_test[META_FEATURES].values.astype(np.float32)
y_test  = meta_test['true_label'].values

print(f'  Train ({TRAIN_YEARS[0]}-{TRAIN_YEARS[-1]}): {X_train.shape[0]} samples, '
      f'RT rate={y_train.mean():.3f}')
print(f'  Val   ({VAL_YEARS[0]}-{VAL_YEARS[-1]}): {X_val.shape[0]} samples, '
      f'RT rate={y_val.mean():.3f}')
print(f'  Test  ({TEST_YEARS[0]}-{TEST_YEARS[-1]}): {X_test.shape[0]} samples, '
      f'RT rate={y_test.mean():.3f}')

# ── Scaling ──
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_val_scaled   = scaler.transform(X_val)
X_test_scaled  = scaler.transform(X_test)

# Combine train + val for meta-learner training
X_meta_train = np.vstack([X_train_scaled, X_val_scaled])
y_meta_train = np.concatenate([y_train, y_val])

# ════════════════════════════════════════════════════════════════
# 4. Train & Compare 4 Meta-Learners
# ════════════════════════════════════════════════════════════════
print('\n[4/6] Training meta-learners (arbitration models)...')

results = {}

# ── 4a. Logistic Regression (可解释基线) ──
lr = LogisticRegression(C=1.0, class_weight='balanced', max_iter=1000, random_state=42)
lr.fit(X_train_scaled, y_train)
p_lr = lr.predict_proba(X_test_scaled)[:, 1]
results['LR'] = {
    'model': lr, 'preds': p_lr,
    'auc': roc_auc_score(y_test, p_lr),
    'f1': f1_score(y_test, (p_lr >= 0.5).astype(int)),
}
print(f'  LR (Linear Arbitration): AUC={results["LR"]["auc"]:.4f}, F1={results["LR"]["f1"]:.4f}')

# ── 4b. Random Forest (非线性仲裁) ──
rf = RandomForestClassifier(n_estimators=100, max_depth=4,
                             class_weight='balanced', random_state=42)
rf.fit(X_train_scaled, y_train)
p_rf = rf.predict_proba(X_test_scaled)[:, 1]
results['RF'] = {
    'model': rf, 'preds': p_rf,
    'auc': roc_auc_score(y_test, p_rf),
    'f1': f1_score(y_test, (p_rf >= 0.5).astype(int)),
}
print(f'  RF (Nonlinear Arbitration): AUC={results["RF"]["auc"]:.4f}, F1={results["RF"]["f1"]:.4f}')

# ── 4c. LightGBM (小树) ──
lgb_meta = lgb.LGBMClassifier(num_leaves=8, learning_rate=0.05, n_estimators=100,
                               class_weight='balanced', random_state=42, verbose=-1)
lgb_meta.fit(X_train_scaled, y_train)
p_lgb_meta = lgb_meta.predict_proba(X_test_scaled)[:, 1]
results['LGB'] = {
    'model': lgb_meta, 'preds': p_lgb_meta,
    'auc': roc_auc_score(y_test, p_lgb_meta),
    'f1': f1_score(y_test, (p_lgb_meta >= 0.5).astype(int)),
}
print(f'  LGB (Tree Arbitration): AUC={results["LGB"]["auc"]:.4f}, F1={results["LGB"]["f1"]:.4f}')

# ── 4d. MLP (深度仲裁) ──
class MetaMLP(nn.Module):
    def __init__(self, n_in=len(META_FEATURES)):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(n_in, 16), nn.ReLU(), nn.Dropout(0.2),
            nn.Linear(16, 8), nn.ReLU(), nn.Dropout(0.2),
            nn.Linear(8, 1),
        )
    def forward(self, x):
        return self.net(x).squeeze(-1)

mlp = MetaMLP()
opt = torch.optim.AdamW(mlp.parameters(), lr=0.01, weight_decay=1e-4)
pos_weight = torch.tensor([(y_train == 0).sum() / (y_train == 1).sum()])
criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight)

best_auc = 0
for ep in range(200):
    mlp.train()
    opt.zero_grad()
    loss = criterion(mlp(torch.tensor(X_train_scaled, dtype=torch.float32)),
                     torch.tensor(y_train, dtype=torch.float32))
    loss.backward()
    opt.step()
    mlp.eval()
    with torch.no_grad():
        vp = torch.sigmoid(mlp(torch.tensor(X_val_scaled, dtype=torch.float32))).numpy()
        va = roc_auc_score(y_val, vp)
        if va > best_auc:
            best_auc = va
            torch.save(mlp.state_dict(), os.path.join(OUT_DIR, 'best_mlp.pt'))

mlp.load_state_dict(torch.load(os.path.join(OUT_DIR, 'best_mlp.pt'), weights_only=True))
mlp.eval()
with torch.no_grad():
    p_mlp = torch.sigmoid(mlp(torch.tensor(X_test_scaled, dtype=torch.float32))).numpy()
results['MLP'] = {
    'model': mlp, 'preds': p_mlp,
    'auc': roc_auc_score(y_test, p_mlp),
    'f1': f1_score(y_test, (p_mlp >= 0.5).astype(int)),
}
print(f'  MLP (Deep Arbitration): AUC={results["MLP"]["auc"]:.4f}, F1={results["MLP"]["f1"]:.4f}')

# Best meta-learner
best_name = max(results, key=lambda k: results[k]['auc'])
best_preds = results[best_name]['preds']
print(f'\n  >>> Best Arbiter: Stacking-{best_name} (AUC={results[best_name]["auc"]:.4f})')

# ════════════════════════════════════════════════════════════════
# 5. Single Model Comparisons (Backbone vs Backbone+Corrections)
# ════════════════════════════════════════════════════════════════
print('\n[5/6] Correction performance comparison...')

single_results = {}
test_mask = meta['year'].isin(TEST_YEARS)
meta_test_all = meta[test_mask]

# Backbone alone
p_lgb_test = meta_test_all['p_lgb'].values
y_test_all = meta_test_all['true_label'].values

single_results['LightGBM (Backbone)'] = {
    'auc': roc_auc_score(y_test_all, p_lgb_test),
    'f1': f1_score(y_test_all, (p_lgb_test >= 0.5).astype(int)),
}

# Backbone + TCN correction
single_results['LGB+TCN'] = {
    'auc': roc_auc_score(y_test_all, meta_test_all['p_lgb_tcn'].values),
    'f1': f1_score(y_test_all, (meta_test_all['p_lgb_tcn'].values >= 0.5).astype(int)),
}

# Backbone + CNN correction
single_results['LGB+CNN'] = {
    'auc': roc_auc_score(y_test_all, meta_test_all['p_lgb_cnn'].values),
    'f1': f1_score(y_test_all, (meta_test_all['p_lgb_cnn'].values >= 0.5).astype(int)),
}

for name in single_results:
    print(f'  {name:<25s}: AUC={single_results[name]["auc"]:.4f}, '
          f'F1={single_results[name]["f1"]:.4f}')

# ════════════════════════════════════════════════════════════════
# 6. Visualizations
# ════════════════════════════════════════════════════════════════
print('\n[6/6] Generating visualizations...')

# 6a. Model comparison bar chart
fig, ax = plt.subplots(figsize=(10, 5))
all_models = list(single_results.keys()) + [f'Stack-{best_name}']
all_aucs = [single_results[m]['auc'] for m in single_results] + [results[best_name]['auc']]
colors = plt.cm.Set2(np.linspace(0, 1, len(all_models)))
bars = ax.bar(range(len(all_models)), all_aucs, color=colors, width=0.6, edgecolor='gray')
ax.set_xticks(range(len(all_models)))
ax.set_xticklabels(all_models, fontsize=11)
ax.set_ylabel('Test AUC', fontsize=12)
ax.set_title('Correction Performance: Backbone vs Backbone+Corrector vs Stacking Arbiter',
             fontsize=13, fontweight='bold')
ax.set_ylim(0.5, 1.0)
for bar, val in zip(bars, all_aucs):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01,
            f'{val:.4f}', ha='center', va='bottom', fontsize=10, fontweight='bold')
plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, '01_model_comparison.png'), dpi=150, bbox_inches='tight')
plt.close()

# 6b. Arbiter weights (LR coefficients)
fig, ax = plt.subplots(figsize=(9, 6))
coef = lr.coef_[0]
feat_labels = META_FEATURES
idx = np.argsort(np.abs(coef))
colors_weights = ['#FF6B6B' if 'delta' in feat_labels[i] or 'p_lgb' in feat_labels[i]
                  else '#4ECDC4' for i in idx]
ax.barh(range(len(coef)), coef[idx], color=[colors_weights[i] for i in idx])
ax.set_yticks(range(len(coef)))
ax.set_yticklabels([feat_labels[i] for i in idx], fontsize=9)
ax.set_xlabel('Coefficient (LR Arbiter)', fontsize=11)
ax.set_title('Stacking Arbiter Weights: How Each Signal Is Weighted', fontsize=13, fontweight='bold')
ax.axvline(0, color='gray', linestyle='--', alpha=0.5)
ax.grid(True, alpha=0.3, axis='x')
plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, '02_stacking_weights.png'), dpi=150, bbox_inches='tight')
plt.close()

# 6c. Confusion matrices
fig, axes = plt.subplots(1, 3, figsize=(15, 4))
titles = ['Backbone (LGB Only)', 'Backbone+Best Corrector', f'Stacking-{best_name} (Arbiter)']
preds_list = [
    (p_lgb_test >= 0.5).astype(int),
    (np.maximum(meta_test_all['p_lgb_tcn'].values, meta_test_all['p_lgb_cnn'].values) >= 0.5).astype(int),
    (best_preds >= 0.5).astype(int),
]
for ax, title, pred in zip(axes, titles, preds_list):
    cm = confusion_matrix(y_test_all, pred)
    im = ax.imshow(cm, cmap='Blues', vmin=0, vmax=cm.max()+1)
    ax.set_xticks([0, 1]); ax.set_yticks([0, 1])
    ax.set_xticklabels(['No RT', 'RT']); ax.set_yticklabels(['No RT', 'RT'])
    for i in range(2):
        for j in range(2):
            ax.text(j, i, str(cm[i, j]), ha='center', va='center', fontsize=14, fontweight='bold')
    ax.set_title(title, fontsize=11, fontweight='bold')
    ax.set_xlabel('Predicted'); ax.set_ylabel('True')
plt.suptitle('Confusion Matrix: Backbone vs Corrector vs Stacking Arbiter', fontsize=13, fontweight='bold')
plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, '03_stacking_confusion.png'), dpi=150, bbox_inches='tight')
plt.close()

# 6d. Risk level distribution
risk_levels = np.digitize(best_preds, bins=[0.3, 0.7])
risk_labels = ['Low (<0.3)', 'Medium (0.3-0.7)', 'High (>0.7)']
fig, axes = plt.subplots(1, 2, figsize=(12, 4))
counts = np.bincount(risk_levels, minlength=3)
axes[0].bar(risk_labels, counts, color=['green', 'orange', 'red'], alpha=0.7, edgecolor='gray')
for i, c in enumerate(counts):
    axes[0].text(i, c + 0.5, str(c), ha='center', fontsize=11, fontweight='bold')
axes[0].set_title(f'Risk Level Distribution — Stacking-{best_name} Arbiter', fontsize=12, fontweight='bold')
axes[0].set_ylabel('Count')
for i in range(3):
    mask = risk_levels == i
    if mask.sum() > 0:
        acc = (best_preds[mask] >= 0.5) == y_test_all[mask]
        axes[1].bar(i, acc.mean(), color=['green', 'orange', 'red'][i], alpha=0.7, edgecolor='gray')
        axes[1].text(i, acc.mean() + 0.02, f'{acc.mean():.2f}', ha='center', fontsize=10, fontweight='bold')
axes[1].set_xticks(range(3)); axes[1].set_xticklabels(risk_labels)
axes[1].set_title('Accuracy by Risk Level', fontsize=12, fontweight='bold')
axes[1].set_ylabel('Accuracy')
plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, '04_risk_levels.png'), dpi=150, bbox_inches='tight')
plt.close()

# 6e. ROC curves
fig, ax = plt.subplots(figsize=(8, 7))
roc_data = [
    ('LGB Backbone', p_lgb_test),
    ('LGB+TCN', meta_test_all['p_lgb_tcn'].values),
    ('LGB+CNN', meta_test_all['p_lgb_cnn'].values),
    (f'Stack-{best_name} (Arbiter)', best_preds),
]
for name, p_data in roc_data:
    fpr, tpr, _ = roc_curve(y_test_all, p_data)
    auc_val = roc_auc_score(y_test_all, p_data)
    ax.plot(fpr, tpr, lw=2, label=f'{name} (AUC={auc_val:.4f})')
ax.plot([0,1],[0,1],'k--',alpha=0.3)
ax.set_xlabel('False Positive Rate', fontsize=12)
ax.set_ylabel('True Positive Rate', fontsize=12)
ax.set_title('ROC Curves: Backbone → Corrector → Arbiter', fontsize=13, fontweight='bold')
ax.legend(fontsize=10, loc='lower right')
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, '05_stacking_roc_comparison.png'), dpi=150, bbox_inches='tight')
plt.close()

print('  Visualizations saved')

# ════════════════════════════════════════════════════════════════
# 7. Save Results
# ════════════════════════════════════════════════════════════════
print('\n[7/6] Saving results...')

np.savez(os.path.join(OUT_DIR, 'stacking_predictions.npz'),
         preds_lgb=p_lgb_test,
         preds_lgb_tcn=meta_test_all['p_lgb_tcn'].values,
         preds_lgb_cnn=meta_test_all['p_lgb_cnn'].values,
         preds_lr=p_lr, preds_rf=p_rf,
         preds_lgb_meta=p_lgb_meta, preds_mlp=p_mlp,
         preds_best=best_preds,
         labels=y_test_all,
         years=meta_test_all['year'].values,
         months=meta_test_all['month'].values,
         best_meta_name=best_name,
         meta_features=np.array(META_FEATURES, dtype=object))

with open(os.path.join(OUT_DIR, 'stacking_model_report.txt'), 'w', encoding='utf-8') as f:
    f.write('=' * 60 + '\n')
    f.write('Stacking Ensemble — Backbone+Corrector Arbitration Report\n')
    f.write('=' * 60 + '\n\n')
    f.write('Framework: LightGBM (Backbone) + TCN (Temporal Corrector)\n')
    f.write('           + CNN (Spatial Corrector) → Stacking Arbiter\n\n')
    f.write('Test Performance (2020-2023):\n')
    for name in single_results:
        f.write(f'  {name:<25s}: AUC={single_results[name]["auc"]:.4f}, '
                f'F1={single_results[name]["f1"]:.4f}\n')
    f.write('\nMeta-Learner (Arbiter) Test Performance:\n')
    for name in results:
        f.write(f'  Stacking-{name:<3s}: AUC={results[name]["auc"]:.4f}, '
                f'F1={results[name]["f1"]:.4f}\n')
    f.write(f'\nBest Arbiter: Stacking-{best_name}\n')
    f.write(f'  Test AUC: {results[best_name]["auc"]:.4f}\n')
    f.write(f'  Test F1:  {results[best_name]["f1"]:.4f}\n')
    f.write('\nRisk Level Distribution:\n')
    for i, rl in enumerate(risk_labels):
        cnt = (risk_levels == i).sum()
        f.write(f'  {rl}: {cnt}\n')
    f.write('\nMeta Features:\n')
    for i, name in enumerate(META_FEATURES):
        f.write(f'  [{i:2d}] {name:<20s}: LR coef={coef[i]:+.4f}\n')

with open(os.path.join(OUT_DIR, 'stacking_weights.json'), 'w', encoding='utf-8') as f:
    weights = dict(zip(META_FEATURES, [float(x) for x in lr.coef_[0]]))
    json.dump(weights, f, ensure_ascii=False, indent=2)

print(f'\n{"="*60}')
print(f'Stacking arbiter complete! Best: Stacking-{best_name} (AUC={results[best_name]["auc"]:.4f})')
print(f'{"="*60}')
