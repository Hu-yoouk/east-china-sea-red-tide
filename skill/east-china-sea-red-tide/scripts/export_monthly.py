"""从项目数据库和原始叶绿素观测生成可复现的区域月度数据。"""

import argparse
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

from red_tide.core import UNITS, VARIABLES, save_json, sha256


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--chlorophyll", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    database = args.database.resolve(strict=True)
    connection = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)
    try:
        frame = pd.read_sql_query(
            "SELECT year,month,longitude,latitude," + ",".join(VARIABLES) +
            ",red_tide_label FROM integrated_data", connection)
    finally:
        connection.close()
    keys = ["year", "month", "longitude", "latitude"]
    if frame.duplicated(keys).any():
        raise ValueError("数据库存在重复时空键")
    grid_counts = frame.groupby(["year", "month"]).size()
    if not grid_counts.eq(195).all():
        raise ValueError("每月必须包含完整的 195 个研究区网格")
    expected = {(120.5 + i * 0.25, 29.0 + j * 0.25) for i in range(13) for j in range(15)}
    for _, group in frame.groupby(["year", "month"]):
        if set(zip(group.longitude, group.latitude)) != expected:
            raise ValueError("存在不属于固定研究区的网格")
    if not frame.red_tide_label.isin([0, 1]).all():
        raise ValueError("标签必须为 0 或 1")
    if not frame.groupby(["year", "month"]).red_tide_label.nunique().eq(1).all():
        raise ValueError("此导出入口仅处理旧版统一区域标签，不会自动将空间标签转换成区域标签")
    observed = pd.read_csv(args.chlorophyll)
    if observed.duplicated(keys).any():
        raise ValueError("原始叶绿素文件存在重复时空键")
    frame = frame.drop(columns="chlorophyll").merge(observed[keys + ["chlorophyll"]],
                                                   on=keys, how="left", validate="one_to_one")
    if (frame.chlorophyll.dropna() < 0).any():
        raise ValueError("原始叶绿素包含负数，需要先核对缺测编码")
    if frame[[v for v in VARIABLES if v != "chlorophyll"]].isna().any(axis=None):
        raise ValueError("除原始叶绿素外出现缺失，需先核验数据来源")
    grouped = frame.groupby(["year", "month"])
    monthly = grouped[VARIABLES].mean()
    monthly["chlorophyll_coverage"] = grouped.chlorophyll.count() / 195
    monthly["red_tide_label"] = grouped.red_tide_label.first().astype(int)
    monthly = monthly.reset_index()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    monthly.to_csv(args.output, index=False, float_format="%.12g")
    save_json(args.output.with_suffix(".provenance.json"), {
        "database_file": database.name, "database_sha256": sha256(database),
        "chlorophyll_file": args.chlorophyll.name, "chlorophyll_sha256": sha256(args.chlorophyll),
        "output_sha256": sha256(args.output), "monthly_rows": len(monthly),
        "positive_months": int(monthly.red_tide_label.sum()), "units": UNITS,
        "aggregation": "固定 195 个规则网格等权均值；叶绿素仅对非缺测原始观测取均值，另记覆盖率。",
        "label": "项目旧数据库每月统一标签，仅代表项目整理的区域月度口径，未重核原始事件。",
        "chlorophyll": "替换数据库中的机器学习插补值；新预测流程不会使用跨全年份拟合的叶绿素插补。",
        "missing_chlorophyll_months": int(monthly.chlorophyll.isna().sum()),
        "environment_provenance_limit": "其余环境字段沿用现有处理结果；原产品单位转换与可用时间尚未全面重核。",
        "redistribution": "派生数据来源分别追溯到原产品；不以代码许可证替代上游数据条款。",
    })
    examples = args.output.parent.parent / "examples"
    examples.mkdir(parents=True, exist_ok=True)
    for year in (2019, 2023):
        sample = monthly[monthly.year == year].drop(columns="red_tide_label")
        sample.to_csv(examples / f"observations_{year}.csv", index=False, float_format="%.12g")
    invalid = monthly[monthly.year == 2019].drop(columns=["red_tide_label", "pressure"])
    invalid.to_csv(examples / "invalid_missing_pressure.csv", index=False, float_format="%.12g")
    print(f"已导出 {len(monthly)} 个月，区域阳性月份 {monthly.red_tide_label.sum()} 个；"
          f"叶绿素完全缺测月份 {monthly.chlorophyll.isna().sum()} 个。")


if __name__ == "__main__":
    main()
