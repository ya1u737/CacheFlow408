@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 停止 KnowMate-408 容器（数据保留）...
docker compose down
echo [提示] 若曾使用 CPU 模式启动，请执行：docker compose -f docker-compose.cpu.yml down
echo [OK] 已停止
pause
