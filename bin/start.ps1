<#
.SYNOPSIS
  AI Personal Finance Advisor - Windows Single-Port Start Script
.DESCRIPTION
  Starts the unified FastAPI + static frontend server on a single port (default: 8787),
  or starts the single-container Docker Compose service with -Docker.
#>
param(
    [switch]$Docker,
    [switch]$Restart,
    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 8787
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $RepoRoot

if ($Docker) {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Write-Error "Docker not found. Install Docker Desktop for Windows first."
    }
    New-Item -ItemType Directory -Force -Path (Join-Path $RepoRoot "data"), (Join-Path $RepoRoot "output") | Out-Null
    docker compose up -d --build app
    Write-Host "✓ App running at http://localhost:8787" -ForegroundColor Green
    Write-Host "  Default login: user / password"
    exit 0
}

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Error "uv not found. Install uv (https://docs.astral.sh/uv/) or run .\bin\start.ps1 -Docker"
}

$conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($conns) {
    $pids = $conns | Select-Object -ExpandProperty OwningProcess -Unique
    if ($Restart) {
        Write-Host "Stopping existing process(es) on port $Port (PID: $($pids -join ', '))..."
        foreach ($p in $pids) {
            Stop-Process -Id $p -Force -ErrorAction SilentlyContinue
        }
        Start-Sleep -Seconds 1
    } else {
        Write-Error "Port $Port is already in use (PID: $($pids -join ', ')). Run '.\bin\start.ps1 -Restart' or '.\bin\stop.ps1'."
    }
}

if (-not (Test-Path (Join-Path $RepoRoot ".venv"))) {
    uv sync --no-install-project --no-dev
}

Write-Host "Starting AI Personal Finance Advisor at http://${HostAddress}:${Port} (default login: user / password) ..." -ForegroundColor Green
uv run --no-sync uvicorn scripts.server:app --host $HostAddress --port "$Port"
