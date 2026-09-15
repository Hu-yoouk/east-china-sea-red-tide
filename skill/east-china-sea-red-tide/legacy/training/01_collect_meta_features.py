# -*- coding: utf-8 -*-
"""Step 5.1: Collect Meta-Features from All Expert Models
- LightGBM OOF predictions + SHAP values (top 3 features)
- TCN model predictions (regional time series)
- Spatial CNN model predictions
- Builds meta-feature dataset with model predictions, confidence, entropy, SHAP
- Handles class imbalance with SMOTE/class weights
"""
import os, sys, warnings
import numpy as np
import pandas as pd
warnings.filterwarnings('ignore')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import rcParams
rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
rcParams['axes.unicode_minus'] = False

# scikit-learn / lightgbm / shap
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler
import lightgbm as lgb
from imblearn.over_sampling import SMOTE

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(BASE, '05_Stacking融合模型', 'output_stacking')
os.makedirs(OUT_DIR, exist_ok=True)

# ===== Parameters =====
VAR_NAMES = ['sst', 'chlorophyll', 'wind_speed', 'pressure',
             'solar_radiation', 'precipitation', 'salinity',
             'nitrate', 'phosphate', 'silicate']
TRAIN_YEARS = list(range(2004, 2018))
VAL_YEARS = list(range(2018, 2020))
TEST_YEARS = list(range(2020, 2024))
SEED = 42

# =====================================================================
# 1. Load cleaned data (for LightGBM OOF)
# =====================================================================
print('[1/5] Loading cleaned data...')
csv_path = os.path.join(BASE, '01_数据预处理', 'cleaned_red_tide_data.csv')
df = pd.read_csv(csv_path)
df['time_key'] = df['year'].astype(str) + '-' + df['month'].astype(str).str.zfill(2)
print('  Raw shape:', df.shape)

# Aggregate to monthly level (all models predict per month)
df_monthly = df.groupby(['year', 'month', 'time_key']).agg(
    red_tide_label=('red_tide_label', 'first'),
    **{v: (v, 'mean') for v in VAR_NAMES}
).reset_index()
print('  Monthly shape:', df_monthly.shape)
print('  Label distribution:', df_monthly['red_tide_label'].value_counts().to_dict())

# =====================================================================
# 2. LightGBM OOF Predictions + SHAP
# =====================================================================
print('[2/5] Generating LightGBM OOF predictions...')
X = df_monthly[VAR_NAMES].values.astype(np.float32)
y = df_monthly['red_tide_label'].values

skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
lgb_oof_preds = np.full(len(y), np.nan, dtype=np.float32)
lgb_top3_shap = np.full((len(y), 3), np.nan, dtype=np.float32)

for fold, (train_idx, val_idx) in enumerate(skf.split(X, y)):
    X_train_f, X_val_f = X[train_idx], X[val_idx]
    y_train_f, y_val_f = y[train_idx], y[val_idx]

    model = lgb.LGBMClassifier(
        n_estimators=200, max_depth=5, num_leaves=16,
        learning_rate=0.05, class_weight='balanced',
        random_state=SEED, verbose=-1, n_jobs=-1
    )
    model.fit(X_train_f, y_train_f, eval_set=[(X_val_f, y_val_f)],
              callbacks=[lgb.early_stopping(10), lgb.log_evaluation(0)])
    lgb_oof_preds[val_idx] = model.predict_proba(X_val_f)[:, 1]

    # SHAP (TreeExplainer)
    try:
        import shap
        explainer = shap.TreeExplainer(model)
        shap_vals = explainer.shap_values(X_val_f)
        if isinstance(shap_vals, list):
            shap_vals = shap_vals[1]  # for binary, class 1
        # Top 3 features by |SHAP| per sample
        top3_indices = np.argsort(-np.abs(shap_vals), axis=1)[:, :3]
        for i, idx_in_val in enumerate(val_idx):
            lgb_top3_shap[idx_in_val] = shap_vals[i, top3_indices[i]]
    except Exception as e:
        print('  SHAP failed:', e)

valid_mask = ~np.isnan(lgb_oof_preds)
print('  OOF AUC: %.4f' % roc_auc_score(np.array(y)[valid_mask], lgb_oof_preds[valid_mask]))

# =====================================================================
# 3. Load TCN predictions
# =====================================================================
print('[3/5] Loading TCN predictions...')
tcn_pred_path = os.path.join(BASE, '03_时序特征工程', 'output_tcn_regional', 'test_predictions.npz')
try:
    tcn_data = np.load(tcn_pred_path)
    tcn_preds = tcn_data['preds']
    tcn_labels = tcn_data['labels']
    print('  TCN test predictions:', len(tcn_preds))

    # TCN test predictions are for 2020-2023. Build mapping to monthly dataframe.
    tcn_preds_mapped = np.full(len(df_monthly), np.nan, dtype=np.float32)
    test_mask_lgb = df_monthly['year'].isin(TEST_YEARS)
    tcn_indices = np.where(test_mask_lgb)[0]
    for i, idx in enumerate(tcn_indices):
        if i < len(tcn_preds):
            tcn_preds_mapped[idx] = tcn_preds[i]
    print('  Mapped %d TCN predictions' % np.sum(~np.isnan(tcn_preds_mapped)))
except Exception as e:
    print('  TCN load failed:', e)
    tcn_preds_mapped = np.full(len(df_monthly), np.nan, dtype=np.float32)

# =====================================================================
# 4. Load Spatial CNN predictions
# =====================================================================
print('[4/5] Loading Spatial CNN predictions...')
cnn_pred_path = os.path.join(BASE, '04_空间CNN模型', 'output_cnn', 'test_predictions.npz')
try:
    cnn_data = np.load(cnn_pred_path)
    cnn_keys = cnn_data.files
    if "cnn_combined" in cnn_keys:
        cnn_preds = cnn_data["cnn_combined"]
    elif "preds" in cnn_keys:
        cnn_preds = cnn_data["preds"]
    else:
        cnn_preds = cnn_data["lgb_prob"][:] + cnn_data["delta"][:]
    cnn_time_keys = list(cnn_data["time_keys"]) if "time_keys" in cnn_keys else None
    print("  CNN test predictions:", len(cnn_preds))
    cnn_preds_mapped = np.full(len(df_monthly), np.nan, dtype=np.float32)
    if cnn_time_keys is not None:
        for i, tk in enumerate(cnn_time_keys):
            mask = df_monthly["time_key"] == tk
            if mask.any() and i < len(cnn_preds):
                cnn_preds_mapped[mask] = cnn_preds[i]
    else:
        test_mask = df_monthly["year"].isin(TEST_YEARS)
        test_indices = np.where(test_mask)[0]
        for i, idx in enumerate(test_indices):
            if i < len(cnn_preds):
                cnn_preds_mapped[idx] = cnn_preds[i]
    print("  Mapped %d CNN predictions" % np.sum(~np.isnan(cnn_preds_mapped)))
except Exception as e:
    print("  CNN load failed:", e)
    cnn_preds_mapped = np.full(len(df_monthly), np.nan, dtype=np.float32)

# =====================================================================
# 5. Build Meta-Feature Dataset
# =====================================================================================================================================
# 5. Build Meta-Feature Dataset
# =====================================================================
print('[5/5] Building meta-feature dataset...')
meta = pd.DataFrame()
meta['year'] = df_monthly['year']
meta['month'] = df_monthly['month']
meta['time_key'] = df_monthly['time_key']
meta['true_label'] = df_monthly['red_tide_label']

# Model predictions (use OOF for train/val, direct for test)
# For LGB OOF predictions, they cover all samples
meta['p_lgb'] = lgb_oof_preds
meta['p_tcn'] = tcn_preds_mapped
meta['p_cnn'] = cnn_preds_mapped

# Fill missing TCN/CNN predictions with LGB prediction (interpolation)
for col in ['p_tcn', 'p_cnn']:
    mask = meta[col].isna()
    if mask.any():
        meta.loc[mask, col] = meta.loc[mask, 'p_lgb']
        print('  Filled %d NaN in %s with LGB pred' % (mask.sum(), col))

# Meta-features
meta['p_max'] = meta[['p_lgb', 'p_tcn', 'p_cnn']].max(axis=1)
meta['p_min'] = meta[['p_lgb', 'p_tcn', 'p_cnn']].min(axis=1)
meta['p_std'] = meta[['p_lgb', 'p_tcn', 'p_cnn']].std(axis=1)

# Entropy: -sum(p*log(p+1e-8)) normalized by log(3)
eps = 1e-8
p_arr = meta[['p_lgb', 'p_tcn', 'p_cnn']].values
q_arr = np.stack([p_arr, 1 - p_arr], axis=-1)   # (N, 3, 2) -> prob of class 0/1 per model
# Entropy across models: for each sample, entropy = -mean(sum_k(p_k*log(p_k)))
entropy_per_model = -np.sum(q_arr * np.log(q_arr + eps), axis=-1) / np.log(2)  # (N, 3)
meta['entropy'] = np.mean(entropy_per_model, axis=1)
meta['confidence'] = 1 - meta['entropy']

# SHAP interaction features
meta['shap_top1'] = lgb_top3_shap[:, 0]
meta['shap_top2'] = lgb_top3_shap[:, 1]
meta['shap_top3'] = lgb_top3_shap[:, 2]

# Agreement flags
meta['all_agree'] = ((meta['p_lgb'] > 0.5) & (meta['p_tcn'] > 0.5) & (meta['p_cnn'] > 0.5)) |                     ((meta['p_lgb'] < 0.5) & (meta['p_tcn'] < 0.5) & (meta['p_cnn'] < 0.5))
meta['majority_rt'] = ((meta[['p_lgb', 'p_tcn', 'p_cnn']] > 0.5).sum(axis=1) >= 2).astype(int)

print('  Meta features shape:', meta.shape)
print('  Columns:', list(meta.columns))
print('  Label distribution:')
print('    ', meta['true_label'].value_counts().to_dict())
print('  Stats:')
print('    p_lgb mean=%.4f std=%.4f' % (meta['p_lgb'].mean(), meta['p_lgb'].std()))
print('    p_tcn mean=%.4f std=%.4f' % (meta['p_tcn'].mean(), meta['p_tcn'].std()))
print('    p_cnn mean=%.4f std=%.4f' % (meta['p_cnn'].mean(), meta['p_cnn'].std()))
print('    entropy mean=%.4f' % meta['entropy'].mean())
print('    confidence mean=%.4f' % meta['confidence'].mean())
print('    all agree: %d / %d' % (meta['all_agree'].sum(), len(meta)))

# ===== Handle class imbalance =====
print('Handling class imbalance...')
meta_train = meta[meta['year'].isin(TRAIN_YEARS)].copy()
meta_test = meta[meta['year'].isin(TEST_YEARS)].copy()

# Apply SMOTE to training data
FEATURE_COLS = ['p_lgb', 'p_tcn', 'p_cnn', 'p_max', 'p_min', 'p_std',
                'entropy', 'confidence', 'shap_top1', 'shap_top2', 'shap_top3',
                'all_agree', 'majority_rt']
# Convert boolean to int
meta_train['all_agree'] = meta_train['all_agree'].astype(int)
meta_test['all_agree'] = meta_test['all_agree'].astype(int)

X_train_meta = meta_train[FEATURE_COLS].values.astype(np.float32)
y_train_meta = meta_train['true_label'].values
X_test_meta = meta_test[FEATURE_COLS].values.astype(np.float32)
y_test_meta = meta_test['true_label'].values

# SMOTE
try:
    smote = SMOTE(random_state=SEED)
    X_train_res, y_train_res = smote.fit_resample(X_train_meta, y_train_meta)
    print('  SMOTE: %d -> %d samples' % (len(X_train_meta), len(X_train_res)))
except Exception as e:
    print('  SMOTE failed, using original:', e)
    X_train_res, y_train_res = X_train_meta, y_train_meta

# Also include validation set (2018-2019)
meta_val = meta[meta['year'].isin(VAL_YEARS)].copy()
meta_val['all_agree'] = meta_val['all_agree'].astype(int)
X_val_meta = meta_val[FEATURE_COLS].values.astype(np.float32)
y_val_meta = meta_val['true_label'].values

# ===== Save =====
print('Saving outputs...')
meta.to_csv(os.path.join(OUT_DIR, 'meta_features.csv'), index=False, encoding='utf-8')

np.savez_compressed(os.path.join(OUT_DIR, 'meta_data.npz'),
    X_train=X_train_res, y_train=y_train_res,
    X_val=X_val_meta, y_val=y_val_meta,
    X_test=X_test_meta, y_test=y_test_meta,
    feature_names=np.array(FEATURE_COLS, dtype=object),
    train_indices=meta[meta['year'].isin(TRAIN_YEARS)].index.values,
    val_indices=meta[meta['year'].isin(VAL_YEARS)].index.values,
    test_indices=meta[meta['year'].isin(TEST_YEARS)].index.values)

# Report
lines = []
lines.append('=' * 60)
lines.append('Meta-Feature Collection Report')
lines.append('=' * 60)
lines.append('')
lines.append('Data: %d months (%d-%d)' % (len(meta), meta['year'].min(), meta['year'].max()))
lines.append('  Train (%d-%d): %d samples' % (TRAIN_YEARS[0], TRAIN_YEARS[-1], len(meta_train)))
lines.append('  Val   (%d-%d): %d samples' % (VAL_YEARS[0], VAL_YEARS[-1], len(meta_val)))
lines.append('  Test  (%d-%d): %d samples' % (TEST_YEARS[0], TEST_YEARS[-1], len(meta_test)))
lines.append('')
lines.append('Meta Features:')
for c in FEATURE_COLS:
    lines.append('  %-20s: mean=%.4f  std=%.4f' % (c, meta[c].mean(), meta[c].std()))
lines.append('')
lines.append('LightGBM OOF AUC: %.4f' % roc_auc_score(
    y[~np.isnan(lgb_oof_preds)],
    lgb_oof_preds[~np.isnan(lgb_oof_preds)]))
lines.append('')
lines.append('Label Distribution:')
lines.append('  Train: %s' % meta_train['true_label'].value_counts().to_dict())
lines.append('  Val:   %s' % meta_val['true_label'].value_counts().to_dict())
lines.append('  Test:  %s' % meta_test['true_label'].value_counts().to_dict())
lines.append('')
lines.append('After SMOTE:')
lines.append('  Train: %s' % pd.Series(y_train_res).value_counts().to_dict())
lines.append('=' * 60)

with open(os.path.join(OUT_DIR, 'meta_features_report.txt'), 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))
print('Done. Output in:', OUT_DIR)



