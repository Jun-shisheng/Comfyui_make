# StyleForge ComfyUI Launcher for RTX 4060 (8GB)
# Usage: .\launch.ps1 [-mode comfyui|webui|download|all] [-port 8188] [-webui_port 7860]

param(
    [string]$mode = "all",
    [int]$port = 8188,
    [int]$webui_port = 7860
)

$ErrorActionPreference = "Stop"
$comfyDir = $PSScriptRoot
$python = "$comfyDir\comfy_env\Scripts\python.exe"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  StyleForge Creative Studio Launcher" -ForegroundColor Cyan
Write-Host "  Qwen Image + Wan 2.1 | RTX 4060 8GB" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

if (!(Test-Path $python)) {
    Write-Host "ERROR: Python not found at $python" -ForegroundColor Red
    exit 1
}

if (!(Test-Path "$comfyDir\main.py")) {
    Write-Host "ERROR: ComfyUI main.py not found in $comfyDir" -ForegroundColor Red
    exit 1
}

function Start-ComfyUI {
    Write-Host "[ComfyUI] Starting server..." -ForegroundColor Yellow
    Write-Host "  Port: $port | VRAM: 8GB optimized" -ForegroundColor Gray

    $env:HF_HOME = "G:\ComfyUI\hf_cache"
    $env:HUGGINGFACE_HUB_CACHE = "G:\ComfyUI\hf_cache\hub"
    $env:TORCH_FORCE_WEIGHTS_ONLY_LOAD = "0"
    $env:http_proxy = ""
    $env:https_proxy = ""

    $mainPy = Join-Path $comfyDir "main.py"
    $argList = @(
        "-s", $mainPy,
        "--port", $port,
        "--listen", "127.0.0.1",
        "--reserve-vram", "1.0",
        "--highvram"
    )

    Start-Process -FilePath $python -ArgumentList $argList -NoNewWindow

    Write-Host "  Waiting for ComfyUI..." -ForegroundColor Gray
    $retries = 0
    while ($retries -lt 60) {
        try {
            $response = Invoke-WebRequest -Uri "http://127.0.0.1:$port/system_stats" -TimeoutSec 2 -ErrorAction Stop
            if ($response.StatusCode -eq 200) {
                Write-Host "  ComfyUI READY: http://127.0.0.1:$port" -ForegroundColor Green
                return $true
            }
        } catch {}
        Start-Sleep -Seconds 2
        $retries++
    }
    Write-Host "  WARNING: May not be ready yet" -ForegroundColor Yellow
    return $true
}

function Start-WebUI {
    Write-Host "[WebUI] Starting StyleForge WebUI..." -ForegroundColor Yellow
    Write-Host "  Simple MJ/SD-like interface at http://127.0.0.1:$webui_port" -ForegroundColor Gray

    $webuiPy = Join-Path $comfyDir "styleforge_webui.py"
    Start-Process -FilePath $python -ArgumentList @("-s", $webuiPy) -NoNewWindow
    Write-Host "  WebUI: http://127.0.0.1:$webui_port" -ForegroundColor Green
}

function Start-Download {
    Write-Host "Starting model downloads..." -ForegroundColor Yellow
    $dlScript = Join-Path $comfyDir "download_wan_models.py"
    & $python $dlScript
}

switch ($mode.ToLower()) {
    "comfyui" {
        Start-ComfyUI
        Write-Host "ComfyUI: http://127.0.0.1:$port" -ForegroundColor Green
        Write-Host "Workflows in: workflows/ directory" -ForegroundColor Gray
        while ($true) { Start-Sleep -Seconds 5 }
    }
    "webui" {
        Start-WebUI
        Write-Host "WebUI: http://127.0.0.1:$webui_port" -ForegroundColor Green
        while ($true) { Start-Sleep -Seconds 5 }
    }
    "download" {
        Start-Download
    }
    "all" {
        Write-Host "Launching full StyleForge stack" -ForegroundColor Cyan
        Start-ComfyUI
        Start-Sleep -Seconds 5
        Start-WebUI
        Write-Host ""
        Write-Host ("=" * 60)
        Write-Host "ComfyUI Backend: http://127.0.0.1:$port" -ForegroundColor Green
        Write-Host "StyleForge UI:  http://127.0.0.1:$webui_port" -ForegroundColor Green
        Write-Host ("=" * 60)
        Write-Host ""
        Write-Host "Use StyleForge UI for simple MJ/SD-like operation." -ForegroundColor Gray
        Write-Host "Press Ctrl+C to stop all services" -ForegroundColor Gray
        while ($true) { Start-Sleep -Seconds 5 }
    }
    default {
        Write-Host "Usage: .\launch.ps1 [-mode comfyui|webui|download|all]" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "  comfyui  - Start ComfyUI backend only"
        Write-Host "  webui    - Start the simple MJ/SD-like interface only"
        Write-Host "  all      - Start both ComfyUI + Simple WebUI (default)"
        Write-Host "  download - Download all required models"
    }
}
