"""面向用户和 Agent 的统一命令行入口。"""

import argparse
import html
import json
import sys
from pathlib import Path

from .core import NAMES, history, predict, read_monthly, save_json, train


def feature_label(name):
    if name == "target_month_sin":
        return "目标月份季节项（正弦）"
    if name == "target_month_cos":
        return "目标月份季节项（余弦）"
    variable, operation = name.split("__", 1)
    title = "叶绿素观测覆盖率" if variable == "chlorophyll_coverage" else NAMES[variable]
    suffix = {"last": "最后月", "mean3": "最近三月均值", "mean12": "最近十二月均值",
              "change3": "最后月与前两月之差"}[operation]
    return f"{title}：{suffix}"


def write_report(result, destination):
    escape = html.escape
    probability = result["probability"]
    baseline = result["seasonal_baseline"]
    warnings = "\n".join(f"- {item}" for item in result["warnings"])
    text = (f"# 东海研究区下一月预测\n\n"
            f"数据截至 **{result['forecast_origin']}**，预测目标为 **{result['target_month']}**。\n\n"
            f"模型输出概率 **{probability:.1%}**；历年同月基准 **{baseline:.1%}**。"
            f"{result['classification']}（固定阈值 0.5，非官方预警等级）。\n\n"
            f"研究范围：{result['scope']}。\n\n"
            f"这是实际加载 `{result['model_id']}` 权重计算的结果；不是网站规则评分。\n\n"
            f"## 解释与建议\n\n" + "\n".join(f"- {item}" for item in result["suggestions"]) +
            f"\n\n{result['explanation_note']}\n\n## 适用条件\n\n{warnings}\n\n"
            f"完整贡献、输入校验值和独立测试指标见同目录 `prediction.json`。\n")
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "report.md").write_text(text, encoding="utf-8")
    items = "".join(f"<li>{escape(item)}</li>" for item in result["warnings"])
    rows = "".join(f"<tr><td>{escape(feature_label(item['feature']))}</td>"
                   f"<td>{item['log_odds_contribution']:+.4f}</td></tr>" for item in result["local_contributions"])
    test = result["test_evaluation"]
    page = f"""<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>东海研究区下一月预测</title><style>
body{{font:16px/1.7 system-ui,sans-serif;background:#f2f6fa;color:#183245;margin:0}}
main{{max-width:900px;margin:40px auto;padding:32px;background:white;border-radius:16px}}
h1{{font-size:28px}}.bar{{height:26px;background:#137c95;color:white;min-width:55px;padding:2px 8px;box-sizing:border-box}}
table{{border-collapse:collapse;width:100%}}td,th{{padding:8px;border-bottom:1px solid #dde4ea;text-align:left}}
.note{{background:#fff5dd;padding:16px;border-radius:8px}}code{{overflow-wrap:anywhere}}
@media(max-width:600px){{main{{margin:12px;padding:18px}}}}</style><main>
<p>真实模型推理 · 研究演示</p><h1>东海研究区下一月预测</h1>
<p>数据截至 <b>{result['forecast_origin']}</b> → 预测 <b>{result['target_month']}</b></p>
<p>{escape(result['scope'])}</p><h2>预测与季节参考</h2>
<p>模型输出概率（未经校准）</p><div class="bar" style="width:{probability*100:.3f}%">{probability:.1%}</div>
<p>训练期历年同月基准</p><div class="bar" style="width:{baseline*100:.3f}%;background:#738598">{baseline:.1%}</div>
<p>{result['classification']}；固定分类阈值 0.5，非业务预警等级。</p>
<h2>独立测试：2020—2023 年</h2><table><tr><th>指标</th><th>模型</th><th>同月基准</th></tr>
<tr><td>AUC</td><td>{test['model']['auc']:.3f}</td><td>{test['seasonal_baseline']['auc']:.3f}</td></tr>
<tr><td>Brier（越小越好）</td><td>{test['model']['brier']:.3f}</td><td>{test['seasonal_baseline']['brier']:.3f}</td></tr></table>
<h2>模型局部贡献</h2><table><tr><th>派生特征</th><th>对数几率贡献</th></tr>{rows}</table>
<p>{escape(result['explanation_note'])}</p><h2>建议</h2><ul>
{''.join('<li>'+escape(item)+'</li>' for item in result['suggestions'])}</ul>
<h2>适用条件</h2><ul class="note">{items}</ul>
<p>模型版本：<code>{escape(result['model_id'])}</code></p>
<p>输入 SHA256：<code>{result['input_sha256']}</code></p>
<p>完整结果：<a href="prediction.json">prediction.json</a> · <a href="report.md">中文报告</a></p></main></html>"""
    (destination / "report.html").write_text(page, encoding="utf-8")


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="东海研究区整体下一月赤潮风险研判")
    commands = parser.add_subparsers(dest="command", required=True)
    for name, description in [("validate", "校验月度输入"), ("train", "训练并评估下一月模型"),
                              ("predict", "加载真实模型预测下一月"), ("history", "查询历史月度标签")]:
        sub = commands.add_parser(name, help=description)
        sub.add_argument("--input", required=True, type=Path, help="月度 CSV 路径")
        if name in ("train", "predict"):
            sub.add_argument("--model-dir", required=True, type=Path, help="模型目录")
        if name in ("predict", "history"):
            sub.add_argument("--output", required=True, type=Path, help="输出目录")
        if name == "history":
            sub.add_argument("--year", type=int, help="筛选年份")
            sub.add_argument("--month", type=int, choices=range(1, 13), help="筛选月份")
    args = parser.parse_args()
    try:
        if args.command == "validate":
            frame = read_monthly(args.input)
            if len(frame) < 12:
                raise ValueError("用于预测时需要至少连续 12 个月数据")
            result = {"valid": True, "rows": len(frame), "forecast_origin": str(frame.iloc[-1].period)}
        elif args.command == "train":
            result = train(args.input, args.model_dir)["evaluation"]
        elif args.command == "predict":
            result = predict(args.input, args.model_dir)
            save_json(args.output / "prediction.json", result)
            write_report(result, args.output)
        else:
            result = history(args.input, args.year, args.month)
            save_json(args.output / "history.json", result)
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    except (ValueError, OSError, KeyError) as error:
        parser.exit(2, f"运行失败：{error}\n")
