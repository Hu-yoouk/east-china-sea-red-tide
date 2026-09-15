# 东海赤潮风险研判技能

让 Agent 查询历史资料，并读取连续 12 个月的新环境数据，调用真实 LightGBM 模型预测研究区整体下一月风险。面向评委提供可执行、可追溯的演示。

**整个仓库就是完整 Skill 包，入口为 [SKILL.md](SKILL.md)。** 本地训练、推理和独立 Agent 验收已完成。不要只复制技能说明文件。

开源仓库：[Hu-yoouk/east-china-sea-red-tide](https://github.com/Hu-yoouk/east-china-sea-red-tide)。可下载完整仓库，或运行 `git clone https://github.com/Hu-yoouk/east-china-sea-red-tide.git`。

## 快速运行

安装 **Python 3.12**，在仓库根目录打开终端，先执行 `python --version` 确认版本；有多个 Python 时使用 3.12 的实际解释器路径。

Windows：

```bat
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.venv\Scripts\python.exe -m pip install --no-build-isolation --no-deps -e .
.venv\Scripts\python.exe -m red_tide predict --input examples/observations_2019.csv --model-dir models/regional_v1 --output outputs/demo
```

macOS / Linux：

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-lock.txt
.venv/bin/python -m pip install --no-build-isolation --no-deps -e .
.venv/bin/python -m red_tide predict --input examples/observations_2019.csv --model-dir models/regional_v1 --output outputs/demo
```

LightGBM 需要 OpenMP 运行库；macOS 缺库时安装 `libomp`，Linux 缺 `libgomp.so.1` 时安装对应系统包。本机 Windows 已验证，Linux 与 macOS 工作流尚未实际运行。

打开 `outputs/demo/report.html` 查看结果。首次安装需要联网，推理和报告可离线使用。Windows 安装后也可双击 `演示.cmd`。

样例是 **2019 年历史输入预测 2020 年 1 月**，概率约 **17.22%**，季节基准约 **13.33%**；不是当前实测预报。

## 在不同 Agent 中调用

将完整仓库放到平台可读取的目录，注册为一个技能；不支持自动发现技能的平台，可以直接告诉 Agent：

> 请读取这个仓库的 SKILL.md，按其规范校验我的数据，再调用真实程序预测并返回结果文件。不要用语言模型猜测概率。

Agent 需要文件读取和终端执行能力。纯聊天平台可解释外部程序生成的 JSON，但不能自行执行本地预测。

可以提问：“2021 年有多少个月出现赤潮标签？”“这份数据覆盖固定研究区，请预测下一月。”“为什么新模型指标与论文不同？”

## 模型证据

新模型是重新训练的下一月 LightGBM 基线，不是原论文融合模型。训练为 2005—2017 年的 156 个月，验证为 2018—2019 年的 24 个月，独立测试为 2020—2023 年的 48 个月。

| 独立测试指标 | 新模型 | 历年同月基准 |
|---|---:|---:|
| AUC | 0.7571 | 0.7393 |
| 平均精确率 | 0.6540 | 0.6241 |
| Brier，越小越好 | 0.1983 | 0.2133 |
| F1，固定阈值 0.5 | 0.5556 | 0.5556 |

改进有限，未检验统计显著性。概率未经独立校准，不是官方预警等级。仅支持 120.5°E—123.5°E、29.0°N—32.5°N 研究区整体下一月预测。

## 已发现的关键差异

原始数据库同一月份所有网格标签相同，不能作为已验证的网格事件标签。空间重建数据库有 67 个正例，其中 2020—2023 年只有 1 个正例。原模型主要使用同期环境预测同期标签，不能把原评估指标直接迁移到下一月预测。

详见 [模型与数据审计](docs/模型与数据审计.md) 和 [机器可读审计结果](docs/data_audit.json)。

## 复现与查询

在已安装环境中运行，或把 `python` 换成虚拟环境解释器：

```bash
python -m unittest discover -s tests -v
python -m red_tide train --input data/monthly.csv --model-dir outputs/retrained_model
python scripts/check_reproduction.py --reference models/regional_v1 --candidate outputs/retrained_model
python -m red_tide history --input data/monthly.csv --year 2021 --output outputs/history_2021
```

从原始材料重新导出月度数据：

```bash
python scripts/export_monthly.py --database /数据路径/integrated_database.db --chlorophyll /数据路径/chlorophyll_grid_data.csv --output outputs/source_export/monthly.csv
```

日常推理与重训使用随包月度 CSV，不需要原始大型数据库。`scripts/audit_data.py` 可只读审计源数据库。

## 目录与交付

| 路径 | 用途 |
|---|---|
| SKILL.md | 技能入口 |
| src/red_tide/ | 校验、训练、推理与报告 |
| models/regional_v1/ | 权重、版本、独立测试 |
| data/、examples/ | 月度数据、来源校验、输入与结果示例 |
| docs/、references/ | 规范、审计、研究结论与演示说明 |
| tests/、evals/ | 程序及独立 Agent 验收 |
| web/ | 原项目历史网站 |
| legacy/ | 原报告及选定训练代码 |

当前为本地开源交付候选。代码沿用原项目木兰宽松许可证第 2 版，第三方数据与依赖授权单独处理；见 [材料与来源](docs/材料与来源.md)。验收边界见 [复现验收](docs/复现验收.md)，演示步骤见 [评委演示流程](docs/评委演示流程.md)。
