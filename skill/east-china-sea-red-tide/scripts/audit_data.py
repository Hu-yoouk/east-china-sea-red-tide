"""只读审计赤潮数据库：检查时空覆盖、标签口径与缺失字段。"""

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path


KEYS = ("year", "month", "longitude", "latitude")
ENVIRONMENT = (
    "sst", "chlorophyll", "wind_speed", "pressure", "solar_radiation",
    "precipitation", "salinity", "nitrate", "phosphate", "silicate",
)


def audit(path):
    path = Path(path).resolve(strict=True)
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    try:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(integrated_data)")}
        required = set(KEYS + ENVIRONMENT + ("red_tide_label",))
        missing = sorted(required - columns)
        if missing:
            raise ValueError("数据库缺少字段：" + "、".join(missing))
        records = connection.execute(
            "SELECT year,month,longitude,latitude,red_tide_label FROM integrated_data"
        ).fetchall()
        if not records:
            raise ValueError("数据库为空")
        months, grids, years = {}, set(), {}
        seen, duplicates, invalid = set(), 0, 0
        for year, month, longitude, latitude, label in records:
            key = (year, month, longitude, latitude)
            duplicates += key in seen
            seen.add(key)
            valid = (
                isinstance(year, int) and 1900 <= year <= 2200
                and isinstance(month, int) and 1 <= month <= 12
                and isinstance(longitude, (float, int)) and 120.5 <= longitude <= 123.5
                and isinstance(latitude, (float, int)) and 29 <= latitude <= 32.5
                and label in (0, 1)
            )
            if not valid:
                invalid += 1
                continue
            grids.add((longitude, latitude))
            period = f"{year:04d}-{month:02d}"
            bucket = months.setdefault(period, {"rows": 0, "positive": 0, "labels": set()})
            bucket["rows"] += 1
            bucket["positive"] += label
            bucket["labels"].add(label)
            annual = years.setdefault(str(year), {"rows": 0, "positive": 0})
            annual["rows"] += 1
            annual["positive"] += label
        missing_values = {
            col: connection.execute(
                f'SELECT COUNT(*) FROM integrated_data WHERE "{col}" IS NULL'
            ).fetchone()[0]
            for col in ENVIRONMENT
        }
        invalid_labels = connection.execute(
            "SELECT COUNT(*) FROM integrated_data "
            "WHERE red_tide_label IS NULL OR red_tide_label NOT IN (0,1)"
        ).fetchone()[0]
        result = {
            "file": path.name,
            "sha256": digest,
            "rows": len(records),
            "grids": len(grids),
            "months": len(months),
            "first_month": min(months) if months else None,
            "last_month": max(months) if months else None,
            "positive_rows": sum(item["positive"] for item in months.values()),
            "duplicate_keys": duplicates,
            "invalid_rows": invalid,
            "invalid_labels": invalid_labels,
            "uniform_label_months": sum(len(item["labels"]) == 1 for item in months.values()),
            "mixed_label_months": sum(len(item["labels"]) > 1 for item in months.values()),
            "missing_environment_values": missing_values,
            "annual_counts": years,
            "test_2020_2023": {
                field: sum(item[field] for year, item in years.items() if 2020 <= int(year) <= 2023)
                for field in ("rows", "positive")
            },
            "monthly_counts": {
                period: {"rows": item["rows"], "positive": item["positive"]}
                for period, item in sorted(months.items())
            },
            "interpretation": "标签为项目整理结果；零标签不能单独证明不存在未记录事件。",
        }
        return result
    finally:
        connection.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("databases", nargs="+", type=Path, help="待审计的 SQLite 数据库")
    parser.add_argument("--output", required=True, type=Path, help="审计结果 JSON")
    args = parser.parse_args()
    try:
        results = [audit(path) for path in args.databases]
    except (OSError, ValueError, sqlite3.Error) as error:
        parser.exit(2, f"审计失败：{error}\n")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for result in results:
        print(f"{result['file']}：{result['rows']} 条，{result['positive_rows']} 个正例，"
              f"测试期正例 {result['test_2020_2023']['positive']} 个")
    print(f"审计结果已保存：{args.output}")


if __name__ == "__main__":
    main()
