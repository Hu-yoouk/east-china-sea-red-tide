@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo 尚未安装本项目环境，请先按照 README.md 的 Windows 步骤安装。
  pause
  exit /b 1
)
set PYTHONUTF8=1
echo 正在调用真实模型，以历史留出样例预测 2020 年 1 月……
".venv\Scripts\python.exe" -m red_tide predict --input examples/observations_2019.csv --model-dir models/regional_v1 --output outputs/demo
if errorlevel 1 (
  echo 运行失败，请查看上方错误。
  pause
  exit /b 1
)
start "" "%~dp0outputs\demo\report.html"
echo 报告已生成。此为历史留出样例，不是当前实测预报。
pause
