@echo off
chcp 65001 >nul
cd /d "G:\ComfyUI"
setlocal enabledelayedexpansion

echo.
echo   ==============================================
echo     StyleForge Creative Studio
echo     Qwen Image + Wan 2.1 ^| RTX 4060 8GB
echo   ==============================================
echo.

set "PY=G:\ComfyUI\comfy_env\Scripts\python.exe"
if not exist "%PY%" (
    echo   [ERROR] Python not found
    pause & exit /b 1
)
if not exist "G:\ComfyUI\main.py" (
    echo   [ERROR] ComfyUI main.py not found
    pause & exit /b 1
)

:: Start ComfyUI backend
echo   [1/2] Starting ComfyUI backend...
start "ComfyUI" /MIN "%PY%" -s "G:\ComfyUI\main.py" --port 8188 --listen 127.0.0.1 --lowvram

:: Wait for ComfyUI (up to 120s)
echo   Waiting for backend to be ready...
for /L %%i in (1,1,60) do (
    powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8188/system_stats' -TimeoutSec 3 -ErrorAction Stop; if ($r.StatusCode -eq 200) { exit 0 } } catch {} exit 1" >nul 2>&1
    if !errorlevel! equ 0 goto comfy_ready
    >nul ping -n 3 127.0.0.1
)
echo   [WARNING] ComfyUI may still be loading...

:comfy_ready
echo   Backend ready (port 8188).
echo.

:: Start WebUI
echo   [2/2] Starting StyleForge WebUI...
start "StyleForge" /MIN "%PY%" -s "G:\ComfyUI\styleforge_webui.py"

:: Wait for WebUI
echo   Waiting for WebUI to be ready...
for /L %%i in (1,1,30) do (
    powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:7860' -TimeoutSec 3 -ErrorAction Stop; if ($r.StatusCode -eq 200) { exit 0 } } catch {} exit 1" >nul 2>&1
    if !errorlevel! equ 0 goto webui_ready
    >nul ping -n 3 127.0.0.1
)

:webui_ready
echo   WebUI ready (port 7860).

:: Open browser
start "" http://127.0.0.1:7860

echo.
echo   ==============================================
echo     All services running!
echo.
echo     Web UI:  http://127.0.0.1:7860
echo     Backend: http://127.0.0.1:8188
echo.
echo     Close this window to stop.
echo   ==============================================
echo.

:loop
>nul ping -n 11 127.0.0.1
goto loop
