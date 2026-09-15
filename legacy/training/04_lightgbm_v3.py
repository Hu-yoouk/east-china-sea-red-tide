# -*- coding: utf-8 -*-
"""LightGBM v3 - 新数据集 (ERA5 + nutrients + salinity) + 空间 GroupKFold"""
import sqlite3, os, warnings, json
warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib import rcParams
rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "DejaVu Sans"]
rcParams["axes.unicode_minus"] = False

import lightgbm as lgb
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    roc_auc_score, accuracy_score, precision_score, recall_score,
    f1_score, confusion_matrix, classification_report, roc_curve
)
import shap

np.random.seed(42)

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.normpath(os.path.join(BASE, "..", "..", "integrated_database.db"))
OUT = os.path.join(BASE, "output_lightgbm_v3")
os.makedirs(OUT, exist_ok=True)

print("=" * 70)
print("LightGBM v3 - ERA5 + Nutrients + Spatial GroupKFold")
print("=" * 70)

# ============================================================
# 1. 数据加载
# ============================================================
print("\n[1/6] Loading data from integrated_database.db ...")
conn = sqlite3.connect(DB)
df = pd.read_sql_query("""
    SELECT year, month, longitude, latitude,
           sst, chlorophyll, wind_speed, pressure,
           solar_radiation, precipitation, red_tide_label,
           salinity, nitrate, phosphate, silicate
    FROM integrated_data
""", conn)
conn.close()
print(f"Records: {len(df)}  |  Positive: {df.red_tide_label.sum()} ({df.red_tide_label.mean()*100:.1f}%)")

# ============================================================
# 2. 特征工程
# ============================================================
print("\n[2/6] Feature engineering ...")
df["season"] = df["month"].apply(lambda x: 1 if x in [3,4,5] else 2 if x in [6,7,8] else 3 if x in [9,10,11] else 4)
df["month_sin"] = np.sin(2 * np.pi * df["month"] / 12)
df["month_cos"] = np.cos(2 * np.pi * df["month"] / 12)
df["weather_index"] = (df["wind_speed"] * df["precipitation"] * 100) / (df["pressure"] / 1000)
df["sst_chl"] = df["sst"] * df["chlorophyll"]
df["nutrient_index"] = df["nitrate"] * df["phosphate"] * df["silicate"]
df["n_p_ratio"] = df["nitrate"] / (df["phosphate"] + 0.01)
df["si_n_ratio"] = df["silicate"] / (df["nitrate"] + 0.01)

# 不含经纬度和年份 (避免空间/时间标识符泄漏)
FEATURES = [
    "month_sin", "month_cos", "season",
    "sst", "chlorophyll", "salinity",
    "nitrate", "phosphate", "silicate",
    "wind_speed", "pressure", "solar_radiation", "precipitation",
    "weather_index", "sst_chl", "nutrient_index", "n_p_ratio", "si_n_ratio"
]
LABEL = "red_tide_label"

X_raw = df[FEATURES].values
y = df[LABEL].values

scaler = StandardScaler()
X = scaler.fit_transform(X_raw)

# 空间分组
grid_ids = df[["longitude", "latitude"]].drop_duplicates().reset_index(drop=True)
grid_ids["grid_id"] = range(len(grid_ids))
df_grid = df.merge(grid_ids, on=["longitude", "latitude"], how="left")
groups = df_grid["grid_id"].values

print(f"Features: {len(FEATURES)}  |  Grids: {len(grid_ids)}")

# ============================================================
# 3. Spatial GroupKFold Cross-Validation
# ============================================================
print("\n[3/6] Spatial GroupKFold CV (5-fold) ...")
cv = GroupKFold(n_splits=5)

params = {
    "objective": "binary",
    "metric": "auc",
    "boosting_type": "gbdt",
    "num_leaves": 31,
    "learning_rate": 0.05,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "bagging_freq": 5,
    "min_data_in_leaf": 50,
    "lambda_l1": 0.1,
    "lambda_l2": 1.0,
    "verbose": -1,
    "random_state": 42,
}

cv_scores = {"auc": [], "accuracy": [], "precision": [], "recall": [], "f1": []}
oof_preds = np.zeros(len(y))
feature_importances_gain = np.zeros(len(FEATURES))
feature_importances_split = np.zeros(len(FEATURES))

for fold, (train_idx, val_idx) in enumerate(cv.split(X, y, groups)):
    X_tr, X_val = X[train_idx], X[val_idx]
    y_tr, y_val = y[train_idx], y[val_idx]

    dtrain = lgb.Dataset(X_tr, label=y_tr)
    dval = lgb.Dataset(X_val, label=y_val, reference=dtrain)

    model = lgb.train(
        params, dtrain, num_boost_round=500,
        valid_sets=[dtrain, dval],
        callbacks=[lgb.early_stopping(50), lgb.log_evaluation(0)]
    )

    y_prob = model.predict(X_val)
    y_pred = (y_prob >= 0.5).astype(int)
    oof_preds[val_idx] = y_prob

    cv_scores["auc"].append(roc_auc_score(y_val, y_prob))
    cv_scores["accuracy"].append(accuracy_score(y_val, y_pred))
    cv_scores["precision"].append(precision_score(y_val, y_pred))
    cv_scores["recall"].append(recall_score(y_val, y_pred))
    cv_scores["f1"].append(f1_score(y_val, y_pred))

    fi_g = model.feature_importance(importance_type="gain")
    fi_s = model.feature_importance(importance_type="split")
    feature_importances_gain += fi_g
    feature_importances_split += fi_s

    print(f"  Fold {fold+1}: AUC={cv_scores['auc'][-1]:.4f}  F1={cv_scores['f1'][-1]:.4f}  "
          f"best_iter={model.best_iteration}")

feature_importances_gain /= 5
feature_importances_split /= 5

print(f"\nCV Summary:")
for m in ["auc", "accuracy", "precision", "recall", "f1"]:
    print(f"  {m}: {np.mean(cv_scores[m]):.4f} +/- {np.std(cv_scores[m]):.4f}")

# ============================================================
# 4. 全量训练 + Holdout 评估
# ============================================================
print("\n[4/6] Final model + Holdout evaluation ...")

fold_iter = list(cv.split(X, y, groups))
train_idx, test_idx = fold_iter[-1]
X_tr, X_te = X[train_idx], X[test_idx]
y_tr, y_te = y[train_idx], y[test_idx]

dtrain_final = lgb.Dataset(X_tr, label=y_tr)
dval_final = lgb.Dataset(X_te, label=y_te, reference=dtrain_final)

final_model = lgb.train(
    params, dtrain_final, num_boost_round=500,
    valid_sets=[dtrain_final, dval_final],
    callbacks=[lgb.early_stopping(50), lgb.log_evaluation(100)]
)

y_prob_te = final_model.predict(X_te)
y_pred_te = (y_prob_te >= 0.5).astype(int)

holdout_auc = roc_auc_score(y_te, y_prob_te)
holdout_f1 = f1_score(y_te, y_pred_te)
holdout_acc = accuracy_score(y_te, y_pred_te)
holdout_prec = precision_score(y_te, y_pred_te)
holdout_rec = recall_score(y_te, y_pred_te)
holdout_cm = confusion_matrix(y_te, y_pred_te)

print(f"\nHoldout Results (spatial fold, {len(y_te)} samples, {y_te.sum()} positive):")
print(f"  AUC={holdout_auc:.4f}  F1={holdout_f1:.4f}  Acc={holdout_acc:.4f}")
print(f"  Precision={holdout_prec:.4f}  Recall={holdout_rec:.4f}")
print(f"  Best Iterations: {final_model.best_iteration}")
print(classification_report(y_te, y_pred_te, target_names=["No Red Tide", "Red Tide"]))

# ============================================================
# 5. 图表输出
# ============================================================
print("\n[5/6] Generating figures ...")

# 5a. Feature importance
fig, axes = plt.subplots(1, 2, figsize=(16, 7))
for ax, f_imp, title, cmap in [
    (axes[0], feature_importances_gain, "Gain Importance", "Reds"),
    (axes[1], feature_importances_split, "Split Importance", "Blues"),
]:
    sorted_idx = np.argsort(f_imp)
    ax.barh(range(len(FEATURES)), f_imp[sorted_idx],
            color=plt.cm.get_cmap(cmap)(np.linspace(0.35, 0.9, len(FEATURES))),
            edgecolor="white", height=0.6)
    ax.set_yticks(range(len(FEATURES)))
    ax.set_yticklabels([FEATURES[i] for i in sorted_idx])
    ax.set_title(f"LightGBM v3 - {title}", fontsize=13, fontweight="bold")
plt.tight_layout()
plt.savefig(f"{OUT}/feature_importance.png", dpi=150, bbox_inches="tight")
plt.close()
print("  -> feature_importance.png")

# 5b. ROC curve
fig, ax = plt.subplots(figsize=(8, 7))
fpr, tpr, _ = roc_curve(y_te, y_prob_te)
ax.plot(fpr, tpr, color="crimson", linewidth=2.5, label=f"AUC = {holdout_auc:.4f}")
ax.plot([0, 1], [0, 1], "k--", alpha=0.3, linewidth=1)
ax.fill_between(fpr, tpr, alpha=0.15, color="crimson")
ax.set_xlabel("False Positive Rate", fontsize=12)
ax.set_ylabel("True Positive Rate", fontsize=12)
ax.set_title(f"LightGBM v3 - ROC Curve (Spatial Holdout)  AUC={holdout_auc:.4f}", fontsize=14, fontweight="bold")
ax.legend(fontsize=12, loc="lower right")
ax.set_xlim(0, 1); ax.set_ylim(0, 1)
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig(f"{OUT}/roc_curve.png", dpi=150, bbox_inches="tight")
plt.close()
print("  -> roc_curve.png")

# 5c. Confusion Matrix
fig, ax = plt.subplots(figsize=(6, 5))
sns.heatmap(holdout_cm, annot=True, fmt="d", cmap="Blues", ax=ax,
            xticklabels=["No Red Tide", "Red Tide"], yticklabels=["No Red Tide", "Red Tide"],
            cbar_kws={"shrink": 0.8})
ax.set_title(f"LightGBM v3 - Confusion Matrix (Holdout)\nAcc={holdout_acc:.4f}  F1={holdout_f1:.4f}",
             fontsize=13, fontweight="bold")
ax.set_ylabel("True", fontsize=12)
ax.set_xlabel("Predicted", fontsize=12)
plt.tight_layout()
plt.savefig(f"{OUT}/confusion_matrix.png", dpi=150, bbox_inches="tight")
plt.close()
print("  -> confusion_matrix.png")

# 5d. SHAP
sample_idx = np.random.choice(len(y_tr), size=min(3000, len(y_tr)), replace=False)
X_sample = X_tr[sample_idx]

explainer = shap.TreeExplainer(final_model)
shap_values = explainer.shap_values(X_sample)

fig, ax = plt.subplots(figsize=(10, 7))
shap.summary_plot(shap_values, X_sample, feature_names=FEATURES, show=False)
plt.tight_layout()
plt.savefig(f"{OUT}/shap_summary.png", dpi=150, bbox_inches="tight")
plt.close()

fig, ax = plt.subplots(figsize=(10, 7))
shap.summary_plot(shap_values, X_sample, feature_names=FEATURES, plot_type="bar", show=False)
plt.tight_layout()
plt.savefig(f"{OUT}/shap_bar.png", dpi=150, bbox_inches="tight")
plt.close()

top4_idx = np.argsort(np.abs(shap_values).mean(0))[-4:][::-1]
top4_names = [FEATURES[i] for i in top4_idx]
fig, axes = plt.subplots(2, 2, figsize=(14, 11))
axes = axes.flatten()
for i, (feat_idx, feat_name) in enumerate(zip(top4_idx, top4_names)):
    shap.dependence_plot(feat_idx, shap_values, X_sample,
                         feature_names=FEATURES, ax=axes[i], show=False)
    axes[i].set_title(f"SHAP Dependence: {feat_name}", fontsize=12, fontweight="bold")
plt.tight_layout()
plt.savefig(f"{OUT}/shap_dependence.png", dpi=150, bbox_inches="tight")
plt.close()

# Waterfall (one positive sample)
pos_samples = np.where(y_tr == 1)[0]
if len(pos_samples) > 0:
    sample_idx_wf = np.random.choice(pos_samples)
    shap_exp = explainer(X_tr[sample_idx_wf:sample_idx_wf+1])
    if hasattr(shap_exp, 'values') and len(shap_exp.values.shape) > 1:
        shap_exp = shap.Explanation(
            values=shap_exp.values[0],
            base_values=shap_exp.base_values[0] if hasattr(shap_exp.base_values, '__len__') and len(np.array(shap_exp.base_values).shape) > 0 else shap_exp.base_values,
            data=shap_exp.data[0],
            feature_names=FEATURES
        )
    fig = shap.plots.waterfall(shap_exp, show=False, max_display=10)
    plt.tight_layout()
    plt.savefig(f"{OUT}/shap_waterfall.png", dpi=150, bbox_inches="tight")
    plt.close()

print("  -> shap_summary.png, shap_bar.png, shap_dependence.png, shap_waterfall.png")

# ============================================================
# 6. 报告输出
# ============================================================
print("\n[6/6] Generating report ...")

shap_importance = np.abs(shap_values).mean(0)

report_lines = []
report_lines.append("=" * 70)
report_lines.append("LightGBM v3 - Red Tide Prediction Report")
report_lines.append("New Dataset: ERA5 + Nutrients + Salinity")
report_lines.append("=" * 70)
report_lines.append("")
report_lines.append(f"Date: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}")
report_lines.append(f"Features: {len(FEATURES)}  |  Samples: {len(y)}  |  Positive: {y.sum()} ({y.mean()*100:.1f}%)")
report_lines.append(f"Spatial Grids: {len(grid_ids)}  |  Time Span: {df.year.min()}-{df.year.max()}")
report_lines.append(f"Feature list: {', '.join(FEATURES)}")
report_lines.append("")
report_lines.append("-" * 70)
report_lines.append("Cross-Validation (5-Fold Spatial GroupKFold)")
report_lines.append("-" * 70)
for m in ["auc", "accuracy", "precision", "recall", "f1"]:
    report_lines.append(f"  {m}: {np.mean(cv_scores[m]):.4f} +/- {np.std(cv_scores[m]):.4f}")
report_lines.append("")
report_lines.append("-" * 70)
report_lines.append("Holdout Evaluation (1 spatial fold held out)")
report_lines.append("-" * 70)
report_lines.append(f"  AUC:       {holdout_auc:.4f}")
report_lines.append(f"  F1:        {holdout_f1:.4f}")
report_lines.append(f"  Accuracy:  {holdout_acc:.4f}")
report_lines.append(f"  Precision: {holdout_prec:.4f}")
report_lines.append(f"  Recall:    {holdout_rec:.4f}")
report_lines.append(f"  Best Iter: {final_model.best_iteration}")
report_lines.append(f"  TN={holdout_cm[0,0]}  FP={holdout_cm[0,1]}  FN={holdout_cm[1,0]}  TP={holdout_cm[1,1]}")
report_lines.append("")
report_lines.append("-" * 70)
report_lines.append("Feature Importance (Gain, avg across 5 folds)")
report_lines.append("-" * 70)
gain_sorted = sorted(zip(FEATURES, feature_importances_gain), key=lambda x: -x[1])
total_gain = sum(v for _, v in gain_sorted)
for name, val in gain_sorted:
    report_lines.append(f"  {name:<25s} {val:>10.1f}  ({val/total_gain*100:5.1f}%)")
report_lines.append("")
report_lines.append("-" * 70)
report_lines.append("SHAP Importance (mean |SHAP|)")
report_lines.append("-" * 70)
shap_sorted = sorted(zip(FEATURES, shap_importance), key=lambda x: -x[1])
for name, val in shap_sorted:
    report_lines.append(f"  {name:<25s} {val:>10.4f}")

report_text = "\n".join(report_lines)

with open(os.path.join(OUT, "model_report.txt"), "w", encoding="utf-8") as f:
    f.write(report_text)

print(report_text)

# Save model
import joblib
joblib.dump(final_model, os.path.join(OUT, "lightgbm_v3_model.pkl"))
joblib.dump(scaler, os.path.join(OUT, "lightgbm_v3_scaler.pkl"))
print("\nSaved: lightgbm_v3_model.pkl, lightgbm_v3_scaler.pkl")

print("\n" + "=" * 70)
print("LightGBM v3 COMPLETE!")
print("=" * 70)
