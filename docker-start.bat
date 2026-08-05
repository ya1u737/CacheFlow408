@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ==============================================
echo    KnowMate-408 Docker 一键启动
echo ==============================================
echo.

REM ---- 1. 检查 docker 命令 ----
where docker >nul 2>nul
if %errorlevel% neq 0 (
    echo [错误] 未找到 docker 命令，请先启动 Docker Desktop。
    pause
    exit /b 1
)

REM ---- 2. 检查 Docker 引擎是否就绪 ----
docker info >nul 2>nul
if %errorlevel% neq 0 (
    echo [..] Docker 引擎未就绪，等待 Docker Desktop 启动...
    start "" "D:\desktop\Docker Desktop.lnk"
    timeout /t 20 /nobreak >nul
)

docker info >nul 2>nul
if %errorlevel% neq 0 (
    echo [错误] Docker 引擎仍未就绪，请手动打开 Docker Desktop 后重试。
    pause
    exit /b 1
)
echo [OK] Docker 引擎已就绪

REM ---- 3. 构建并启动（优先 GPU 配置；无 NVIDIA 显卡请改用 docker-compose.cpu.yml）----
echo [..] 构建镜像并启动服务（首次构建约 10-20 分钟）...
echo.
echo 请选择运行模式：
echo   1. GPU 模式（推荐，有 NVIDIA 显卡）
echo   2. CPU 模式（无显卡，关闭 rerank/查询改写）
set /p MODE=请输入 1 或 2（默认 1）:
if "%MODE%"=="2" (
    docker compose -f docker-compose.cpu.yml up -d --build
) else (
    docker compose up -d --build
)
if %errorlevel% neq 0 (
    echo [错误] 启动失败，请查看上方日志。
    pause
    exit /b 1
)

REM ---- 4. 等待后端就绪后打开浏览器 ----
echo [..] 等待服务就绪（首次启动需拉取模型，可能较久）...
powershell -NoProfile -Command ^
  "$ok=$false; for($i=0;$i -lt 120;$i++){ try{ $r=Invoke-WebRequest -UseBasicParsing 'http://localhost:8000/api/status' -TimeoutSec 2; if($r.StatusCode -eq 200){ $ok=$true; break } }catch{}; Start-Sleep 2 }; if($ok){ Start-Process 'http://localhost:5173' } else { Write-Host '[警告] 后端未在 4 分钟内就绪，请查看: docker compose logs backend' }"

echo.
echo [OK] 浏览器已打开。
echo   前端：http://localhost:5173
echo   后端：http://localhost:8000
echo   停止：docker compose down      （保留数据）
echo   彻底清除：docker compose down -v （删除向量库/模型缓存）
pause
