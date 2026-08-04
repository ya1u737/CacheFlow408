@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ==============================================
echo    KnowMate-408 一键启动
echo ==============================================
echo.

REM ---- 0. 环境检查 ----
if not exist "D:\miniconda\envs\408rag\python.exe" (
    echo [错误] 未找到 Python 环境：D:\miniconda\envs\408rag
    echo 请先安装 conda 环境 408rag（见 README.md）。
    pause
    exit /b 1
)

REM ---- 1. 确保 Ollama 在运行 ----
tasklist /FI "IMAGENAME eq ollama.exe" 2>nul | find /I "ollama.exe" >nul
if %errorlevel%==0 (
    echo [OK] Ollama 已在运行
) else (
    echo [..] 启动 Ollama ...
    start "" "C:\Users\李炳树\AppData\Local\Programs\Ollama\ollama.exe" serve
    timeout /t 5 /nobreak >nul
)

REM ---- 2. 启动后端（FastAPI :8000）----
echo [..] 启动后端服务（http://localhost:8000）...
start "KnowMate-Backend" cmd /k "D:\miniconda\envs\408rag\python.exe -m uvicorn backend.api:app --port 8000"

REM ---- 3. 启动前端（Vite :5173）----
echo [..] 启动前端服务（http://localhost:5173）...
start "KnowMate-Frontend" cmd /k "cd /d frontend && npm run dev"

REM ---- 4. 等待后端就绪后打开浏览器 ----
echo [..] 等待服务就绪...
powershell -NoProfile -Command ^
  "$ok=$false; for($i=0;$i -lt 40;$i++){ try{ $r=Invoke-WebRequest -UseBasicParsing 'http://localhost:8000/api/status' -TimeoutSec 1; if($r.StatusCode -eq 200){ $ok=$true; break } }catch{}; Start-Sleep 1 }; if(-not $ok){ Write-Host '[警告] 后端未在 40 秒内就绪，请查看后端窗口日志' }"
timeout /t 3 /nobreak >nul
start http://localhost:5173

echo.
echo [OK] 浏览器已打开。停止服务：关闭两个黑色窗口即可。
echo 前端：http://localhost:5173   后端：http://localhost:8000
pause
