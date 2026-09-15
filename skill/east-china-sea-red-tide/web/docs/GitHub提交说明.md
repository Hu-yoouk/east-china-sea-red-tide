# GitHub 提交说明

如果要把本部署包更新到 GitHub 仓库 `webredrisk`，建议按以下方式提交。

## 1. 推荐提交内容

应提交：

- `src/`
- `public/`
- `scripts/`
- `nginx/`
- `docs/`
- `package.json`
- `package-lock.json`
- `vite.config.ts`
- `tsconfig*.json`
- `tailwind.config.js`
- `postcss.config.js`
- `eslint.config.js`
- `index.html`
- `Dockerfile`
- `Dockerfile.build`
- `docker-compose.yml`
- `.dockerignore`
- `README.md`
- `README_服务器部署.md`
- `部署检查清单.md`

可选提交：

- `dist/`

如果希望老师下载后不运行构建命令也能直接部署，建议保留 `dist/`。

不应提交：

- `node_modules/`
- `.git/`
- `.Rhistory`
- `npm-debug.log`
- 本机临时截图或缓存文件

## 2. 提交流程

```bash
git add .
git commit -m "docs: update red tide risk system architecture and deployment package"
git push
```

## 3. 仓库首页建议

GitHub 仓库首页会优先展示 `README.md`，因此本次已经将 README 改为项目总览型说明。更详细的架构、功能和模型口径放在 `docs/` 目录下，避免首页过长。
