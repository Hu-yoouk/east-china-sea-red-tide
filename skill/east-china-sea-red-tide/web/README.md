# 原项目历史展示网站

此目录保留项目历史数据、图表和前端规则评分，供评委了解原研究流程。页面顶部已标注其与新下一月真实模型的区别。

本仓库真实预测入口在上级目录的 `SKILL.md` 和 `src/red_tide/`，真实预测会生成独立 HTML 报告。不要把本网站中的概率、风险图或旧模型指标当作新预测结果。

## 本地启动

需要满足 Vite 8 要求的 Node.js 版本；建议使用 Node.js 22.12 或以上的 22 系列版本。

```bash
npm ci
npm run build
npm run preview -- --host 127.0.0.1 --port 4173
```

浏览器访问终端显示的地址，并包含 `/red-tide-risk/` 路径。

服务器也可在本目录运行 `docker compose up -d --build`。当前 Compose 使用 `Dockerfile.build` 从源码构建，不需要预先提供 `dist`。Docker 方式尚未在本机验证。

数据导出仅在需要更新历史展示时运行：`node scripts/export-data.cjs 数据库路径`。前端数据 JSON 已附带，默认不需要数据库。

`docs/` 为原项目说明，可能含旧部署方式或研究口径；新预测以仓库根目录文档和模型卡为准。原网站许可证见本目录 `LICENSE`。
