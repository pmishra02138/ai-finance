<#
.SYNOPSIS
  AI Personal Finance Advisor - Windows Start Script
.DESCRIPTION
  Starts both the FastAPI + SQLite backend (default port 8787) and the Node.js frontend (default port 3000),
  or starts the Docker Compose stack with -Docker.
.EXAMPLE
  .\start.ps1
  .\start.ps1 -Restart
  .\start.ps1 -Docker
#>
param(
    [switch]$Docker,
    [switch]$Restart,
    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 3000,
    [int]$ApiPort = 8787
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

if ($Docker) {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Write-Error "Docker CLI not found. Install Docker Desktop for Windows first."
    }
    docker compose up -d --build
    Write-Host "✓ Unified app running at http://localhost:3000 (API docs: http://localhost:8787/docs)" -ForegroundColor Green
    Write-Host "  Default login: user / password"
    exit 0
}

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Error "uv not found. Install uv (https://docs.astral.sh/uv/) or run .\start.ps1 -Docker"
}
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Error "node not found. Install Node.js 18+ or run .\start.ps1 -Docker"
}

function Test-Or-FreePort {
    param([int]$TargetPort, [string]$Label)
    $conns = Get-NetTCPConnection -LocalPort $TargetPort -State Listen -ErrorAction SilentlyContinue
    if ($conns) {
        $pids = $conns | Select-Object -ExpandProperty OwningProcess -Unique
        if ($Restart) {
            Write-Host "Stopping existing $Label process(es) on port $TargetPort (PID: $($pids -join ', '))..."
            foreach ($p in $pids) {
                Stop-Process -Id $p -Force -ErrorAction SilentlyContinue
            }
            Start-Sleep -Seconds 1
        } else {
            Write-Error "$Label port $TargetPort is already in use (PID: $($pids -join ', ')). Run '.\start.ps1 -Restart' or use '.\stop.ps1'."
        }
    }
}

Test-Or-FreePort -TargetPort $ApiPort -Label "FastAPI backend"
Test-Or-FreePort -TargetPort $Port -Label "Node.js frontend"

if (-not (Test-Path (Join-Path $ScriptDir ".venv"))) {
    uv sync --no-install-project --no-dev
}

Write-Host "Starting FastAPI backend at http://${HostAddress}:${ApiPort} ..." -ForegroundColor Cyan
$apiProc = Start-Process -FilePath "uv" -ArgumentList @("run", "--no-sync", "uvicorn", "scripts.server:app", "--host", $HostAddress, "--port", "$ApiPort") -PassThru -NoNewWindow

try {
    $env:HOST = $HostAddress
    $env:PORT = "$Port"
    $env:BACKEND_URL = "http://${HostAddress}:${ApiPort}"
    Write-Host "Starting Node.js frontend at http://${HostAddress}:${Port} (default login: user / password) ..." -ForegroundColor Green
    node (Join-Path $ScriptDir "frontend\server.js")
} finally {
    if ($apiProc -and -not $apiProc.HasExited) {
        Stop-Process -Id $apiProc.Id -Force -ErrorAction SilentlyContinue
    }
}
