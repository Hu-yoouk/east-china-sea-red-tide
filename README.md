# 东海赤潮风险研判技能

任何人都可以下载本公开仓库，查询已封装的历史数据与研究结论，并按技能规范获得有依据的解释和建议。具备文件访问与终端执行能力的 Agent，还可对符合要求的新环境数据运行真实 LightGBM 模型，预测固定研究区整体下一月风险。

## 直接安装技能

完整技能位于 **[skill/east-china-sea-red-tide/](skill/east-china-sea-red-tide/)**。

```text
east-china-sea-red-tide/         仓库
├── README.md                   本说明
├── .github/workflows/          跨系统验证
└── skill/
    └── east-china-sea-red-tide/ ← 把这个文件夹整体移入 Agent 的技能目录
        ├── SKILL.md            技能入口
        ├── README.md           环境安装与使用说明
        ├── src/                真实预测程序
        ├── models/             已训练模型
        ├── data/               月度历史数据
        ├── references/         原研究结论
        ├── examples/           输入与结果示例
        ├── docs/               输入规范与模型边界
        └── web/                原项目历史展示网站
```

1. 下载本仓库，取出 `skill/east-china-sea-red-tide/`；也可从 [v0.1.1 版本发布页](https://github.com/Hu-yoouk/east-china-sea-red-tide/releases/tag/v0.1.1) 下载技能专用 ZIP，解压后直接得到 `east-china-sea-red-tide/`。
2. 将整个 `east-china-sea-red-tide` 文件夹移入你的 Agent 支持的技能目录，保留文件夹名称。例如目标平台约定的目录为 `skills`，最终应为 `skills/east-china-sea-red-tide/SKILL.md`，不要额外套一层 `skill`。
3. 在该技能目录中，按 [技能安装说明](skill/east-china-sea-red-tide/README.md) 创建 Python 3.12 虚拟环境并安装依赖。移动文件夹后再安装环境，避免搬运已有虚拟环境导致路径失效。
4. 按目标平台要求重新加载技能。不同平台的目录和发现机制不同；不支持自动发现时，可直接让 Agent 读取该文件夹内的 `SKILL.md`。

**复制文件夹不等于依赖已安装。** 模型、数据和代码都随包提供；首次安装依赖需要联网，安装后推理可以离线运行。不必启动历史网站。

## 可以怎样提问

- “2021 年有多少个月出现赤潮标签？请给出依据。”
- “解释项目中融合模型的研究结论和局限。”
- “这份 CSV 覆盖固定研究区，请校验数据并预测下一月，生成报告。”

纯聊天平台可以阅读结论，但无法自行执行本地预测。技能不会自动收集最新海洋观测；真实预测需要用户提供连续至少 12 个月、符合字段和单位要求的区域环境数据。

## 能力与验证

新预测程序是区域下一月 LightGBM 基线，历史资料覆盖 2004—2023 年；原论文融合模型结论另行保留。示例使用 2019 年输入预测 2020 年 1 月，输出概率约 17.22%，不是当前实测预报。概率未经独立校准，不支持网格级或日尺度预报，也不替代官方预警。

- [技能入口](skill/east-china-sea-red-tide/SKILL.md)
- [安装、运行和复现](skill/east-china-sea-red-tide/README.md)
- [输入与模型说明](skill/east-china-sea-red-tide/docs/输入与模型说明.md)
- [复现验收记录](skill/east-china-sea-red-tide/docs/复现验收.md)
- [GitHub 自动测试](https://github.com/Hu-yoouk/east-china-sea-red-tide/actions)

代码沿用木兰宽松许可证第 2 版。第三方数据与依赖的许可独立处理，见 [材料与来源](skill/east-china-sea-red-tide/docs/材料与来源.md)。
