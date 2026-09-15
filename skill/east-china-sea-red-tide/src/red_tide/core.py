"""统一输入规范、因果特征和真实模型推理；不使用网站规则评分。"""

import hashlib
import json
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd


VARIABLES = ["sst", "chlorophyll", "wind_speed", "pressure", "solar_radiation",
             "precipitation", "salinity", "nitrate", "phosphate", "silicate"]
UNITS = {"sst": "℃", "chlorophyll": "mg/m³", "wind_speed": "m/s", "pressure": "Pa",
         "solar_radiation": "W/m²", "precipitation": "mm/day", "salinity": "实用盐度",
         "nitrate": "μmol/L", "phosphate": "μmol/L", "silicate": "μmol/L"}
NAMES = {"sst": "海表温度", "chlorophyll": "叶绿素", "wind_speed": "风速", "pressure": "气压",
         "solar_radiation": "太阳辐射", "precipitation": "降水", "salinity": "盐度",
         "nitrate": "硝酸盐", "phosphate": "磷酸盐", "silicate": "硅酸盐"}
SCOPE = "120.5°E—123.5°E、29.0°N—32.5°N 研究区整体；不提供网格级预测"


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def save_json(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(content, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                    encoding="utf-8")


def read_monthly(path, labelled=False):
    """输入为固定研究区的月均值；叶绿素允许缺测，必须提供观测覆盖率。"""
    frame = pd.read_csv(path)
    required = ["year", "month", "chlorophyll_coverage"] + VARIABLES
    if labelled:
        required.append("red_tide_label")
    absent = sorted(set(required) - set(frame.columns))
    if absent:
        raise ValueError("缺少字段：" + "、".join(absent))
    for column in required:
        try:
            frame[column] = pd.to_numeric(frame[column], errors="raise")
        except (ValueError, TypeError) as error:
            raise ValueError(f"字段 {column} 包含非数值内容") from error
    if frame.empty:
        raise ValueError("输入文件没有数据")
    for column, lower, upper in [("year", 1900, 2200), ("month", 1, 12)]:
        values = frame[column]
        if not (values.notna() & values.between(lower, upper) & (values % 1 == 0)).all():
            raise ValueError(f"{column} 必须为 {lower}—{upper} 范围内的整数")
        frame[column] = values.astype(int)
    if frame.duplicated(["year", "month"]).any():
        raise ValueError("同一月份出现多行；此入口需要研究区月度汇总，不接受逐网格行")
    frame = frame.sort_values(["year", "month"]).reset_index(drop=True)
    frame["period"] = pd.PeriodIndex.from_fields(year=frame.year, month=frame.month, freq="M")
    if not np.all(np.diff(frame.period.astype("int64")) == 1):
        raise ValueError("月份不连续，请补齐缺少月份；程序不会用未来数据回填")
    ranges = {"sst": (-3, 45), "chlorophyll": (0, 10000), "wind_speed": (0, 100),
              "pressure": (80000, 120000), "solar_radiation": (0, 1500),
              "precipitation": (0, 2000), "salinity": (0, 50),
              "nitrate": (0, 10000), "phosphate": (0, 10000), "silicate": (0, 10000),
              "chlorophyll_coverage": (0, 1)}
    for column, (lower, upper) in ranges.items():
        values = frame[column]
        valid = np.isfinite(values) & values.between(lower, upper)
        if column == "chlorophyll":
            valid |= values.isna()
        if not valid.all():
            raise ValueError(f"{column} 必须在 {lower}—{upper} 内；单位为 {UNITS.get(column, '比例')}，"
                             "除叶绿素外不接受缺测值")
    if not (frame.chlorophyll.isna() == (frame.chlorophyll_coverage == 0)).all():
        raise ValueError("叶绿素缺测时覆盖率必须为 0；有观测值时覆盖率必须大于 0")
    if labelled and not frame.red_tide_label.isin([0, 1]).all():
        raise ValueError("训练标签必须为 0 或 1")
    return frame


def window_features(window):
    """仅使用预测起点及之前的 12 个月；目标月只提供已知日历信息。"""
    if len(window) != 12:
        raise ValueError("预测需要连续 12 个月的数据")
    target = window.iloc[-1].period + 1
    result = {"target_month_sin": np.sin(2 * np.pi * target.month / 12),
              "target_month_cos": np.cos(2 * np.pi * target.month / 12)}
    for variable in VARIABLES + ["chlorophyll_coverage"]:
        values = window[variable]
        result[f"{variable}__last"] = values.iloc[-1]
        result[f"{variable}__mean3"] = values.iloc[-3:].mean()
        result[f"{variable}__mean12"] = values.mean()
        result[f"{variable}__change3"] = values.iloc[-1] - values.iloc[-3]
    return result


def supervised(frame):
    """第 t 月结束时的窗口对应第 t+1 月标签，不包含目标月环境或标签特征。"""
    if len(frame) < 13:
        raise ValueError("训练数据至少需要 13 个月")
    features, labels, targets = [], [], []
    for index in range(11, len(frame) - 1):
        features.append(window_features(frame.iloc[index - 11:index + 1]))
        labels.append(int(frame.iloc[index + 1].red_tide_label))
        targets.append(frame.iloc[index + 1].period)
    return pd.DataFrame(features), np.asarray(labels), pd.PeriodIndex(targets, freq="M")


def train(data_path, model_dir):
    from sklearn.metrics import average_precision_score, brier_score_loss, f1_score, log_loss, roc_auc_score

    frame = read_monthly(data_path, labelled=True)
    features, labels, targets = supervised(frame)
    train_mask = targets <= pd.Period("2017-12", freq="M")
    valid_mask = (targets >= pd.Period("2018-01", freq="M")) & (targets <= pd.Period("2019-12", freq="M"))
    test_mask = (targets >= pd.Period("2020-01", freq="M")) & (targets <= pd.Period("2023-12", freq="M"))
    for name, mask in [("训练", train_mask), ("验证", valid_mask), ("测试", test_mask)]:
        if mask.sum() == 0 or len(np.unique(labels[mask])) != 2:
            raise ValueError(f"{name}集缺少样本或不包含两种标签，不能进行当前时间划分的评估")
    medians = features.loc[train_mask].median()
    if medians.isna().any():
        raise ValueError("部分特征在训练期全部缺失，不能拟合预处理")
    filled = features.fillna(medians)
    params = dict(objective="binary", metric="binary_logloss", num_leaves=4, max_depth=3,
                  min_data_in_leaf=15, learning_rate=0.03, lambda_l2=5.0,
                  verbosity=-1, seed=42, num_threads=1, deterministic=True, force_col_wise=True)
    model = lgb.train(params, lgb.Dataset(filled.loc[train_mask], label=labels[train_mask]),
                      num_boost_round=250,
                      valid_sets=[lgb.Dataset(filled.loc[valid_mask], label=labels[valid_mask])],
                      callbacks=[lgb.early_stopping(30, verbose=False)])
    # 平滑的历年同月基准，仅使用训练期的目标标签。
    seasonal = {}
    for month in range(1, 13):
        chosen = train_mask & (targets.month == month)
        seasonal[str(month)] = float((labels[chosen].sum() + 1) / (chosen.sum() + 2))
    threshold = 0.5

    def metrics(truth, probability):
        return {"n": len(truth), "positive": int(truth.sum()),
                "auc": float(roc_auc_score(truth, probability)),
                "average_precision": float(average_precision_score(truth, probability)),
                "brier": float(brier_score_loss(truth, probability)),
                "log_loss": float(log_loss(truth, probability, labels=[0, 1])),
                "f1_at_0_5": float(f1_score(truth, probability >= threshold, zero_division=0))}

    evaluation = {}
    for name, mask in [("train", train_mask), ("validation", valid_mask), ("test", test_mask)]:
        prediction = model.predict(filled.loc[mask])
        baseline = np.asarray([seasonal[str(month)] for month in targets[mask].month])
        evaluation[name] = {"first_target": str(targets[mask][0]), "last_target": str(targets[mask][-1]),
                            "model": metrics(labels[mask], prediction),
                            "seasonal_baseline": metrics(labels[mask], baseline)}
    model_dir = Path(model_dir)
    model_dir.mkdir(parents=True, exist_ok=True)
    model_file = model_dir / "model.txt"
    # 由 Python 读写 UTF-8 路径，避免底层库在 Windows 中文路径上打开失败。
    model_file.write_text(model.model_to_string(), encoding="utf-8")
    meta = {"model_id": "regional-next-month-lightgbm-v1", "scope": SCOPE,
            "model_type": "重新训练的 LightGBM 下一月基线；不是原论文融合模型",
            "horizon_months": 1, "window_months": 12, "features": list(features.columns),
            "medians": medians.to_dict(), "feature_min": features.loc[train_mask].min().to_dict(),
            "feature_max": features.loc[train_mask].max().to_dict(),
            "threshold": threshold, "threshold_note": "固定 0.5 分类阈值，非业务预警标准",
            "seasonal_baseline": seasonal, "evaluation": evaluation,
            "training_data_sha256": sha256(data_path), "model_sha256": sha256(model_file),
            "best_iteration": model.best_iteration, "parameters": params,
            "calibrated": False,
            "limitations": ["仅 240 个月历史数据，独立测试期 48 个月。",
                            "标签沿用项目整理的区域月度记录，未重新核验原始事件清单。",
                            "使用历史环境产品回溯评估，不等于实况业务预报；需核对数据发布延迟。",
                            "未验证网格级预测、其他海域或跨多月递推预测。",
                            "模型概率未经独立校准，不提供置信区间或官方预警等级。"]}
    save_json(model_dir / "metadata.json", meta)
    save_json(model_dir / "evaluation.json", evaluation)
    out = pd.DataFrame({"target_month": targets[test_mask].astype(str),
                        "true_label": labels[test_mask],
                        "probability": model.predict(filled.loc[test_mask]),
                        "seasonal_baseline": [seasonal[str(m)] for m in targets[test_mask].month]})
    out.to_csv(model_dir / "test_predictions.csv", index=False)
    return meta


def predict(data_path, model_dir):
    frame = read_monthly(data_path)
    if len(frame) < 12:
        raise ValueError(f"需要连续 12 个月，当前只有 {len(frame)} 个月；请补齐历史环境数据")
    model_dir = Path(model_dir)
    meta = json.loads((model_dir / "metadata.json").read_text(encoding="utf-8"))
    if sha256(model_dir / "model.txt") != meta["model_sha256"]:
        raise ValueError("模型文件校验失败，权重与版本说明不一致")
    window = frame.iloc[-12:]
    raw = pd.DataFrame([window_features(window)])[meta["features"]]
    values = raw.fillna(pd.Series(meta["medians"]))
    model = lgb.Booster(model_str=(model_dir / "model.txt").read_text(encoding="utf-8"))
    probability = float(model.predict(values)[0])
    contributions = model.predict(values, pred_contrib=True)[0]
    top = np.argsort(-np.abs(contributions[:-1]))[:5]
    target = window.iloc[-1].period + 1
    out_of_range = [name for name in meta["features"] if pd.notna(raw.iloc[0][name]) and
                    not meta["feature_min"][name] <= raw.iloc[0][name] <= meta["feature_max"][name]]
    test = meta["evaluation"]["test"]
    warnings = list(meta["limitations"])
    if test["model"]["brier"] >= test["seasonal_baseline"]["brier"]:
        warnings.append("独立测试 Brier 分数未优于同月历史基准，不应宣称优于季节性参考。")
    if target > pd.Period("2023-12", freq="M"):
        warnings.append("预测目标超出已有测试期；没有该时段的实测验证，需关注分布变化。")
    if out_of_range:
        warnings.append(f"{len(out_of_range)} 项派生特征超出训练范围，结果需重点复核。")
    if raw.isna().any(axis=None):
        warnings.append("存在缺测叶绿素派生特征，已使用仅从训练期拟合的中位数。")
    if (window.chlorophyll_coverage < 0.5).any():
        warnings.append("部分月份叶绿素观测覆盖不足 50%，区域均值代表性有限。")
    return {"model_id": meta["model_id"], "scope": SCOPE,
            "input_sha256": sha256(data_path), "model_sha256": meta["model_sha256"],
            "input_first_month": str(window.iloc[0].period), "forecast_origin": str(window.iloc[-1].period),
            "target_month": str(target), "horizon_months": 1, "probability": probability,
            "probability_note": "模型输出概率，未经独立校准，不是确定发生率",
            "classification": "模型判为阳性" if probability >= meta["threshold"] else "模型判为阴性",
            "threshold": meta["threshold"], "threshold_note": meta["threshold_note"],
            "seasonal_baseline": meta["seasonal_baseline"][str(target.month)],
            "test_evaluation": test, "warnings": warnings, "out_of_range_features": out_of_range,
            "local_contributions": [{"feature": meta["features"][i],
                                     "log_odds_contribution": float(contributions[i])} for i in top],
            "explanation_note": "局部贡献为模型对数几率贡献，不代表因果关系或独立生态阈值。",
            "suggestions": ["结合近期现场监测核对叶绿素、水温及营养盐变化。",
                            "此结果用于研究区整体筛查，具体巡查点位需要空间观测支持。"]}


def history(data_path, year=None, month=None):
    frame = read_monthly(data_path, labelled=True)
    selected = frame
    if year is not None:
        selected = selected[selected.year == year]
    if month is not None:
        selected = selected[selected.month == month]
    if selected.empty:
        raise ValueError("指定时段没有记录；现有资料覆盖 2004—2023 年")
    return {"source_sha256": sha256(data_path), "scope": SCOPE,
            "months": len(selected), "positive_months": int(selected.red_tide_label.sum()),
            "positive_month_fraction": float(selected.red_tide_label.mean()),
            "interpretation": "区域月度标签比例，不是网格发生率，也不是未来概率。",
            "records": selected.drop(columns="period").replace({np.nan: None}).to_dict(orient="records")}
