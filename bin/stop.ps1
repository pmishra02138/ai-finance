<#
.SYNOPSIS
  AI Personal Finance Advisor - Windows Stop Script
.DESCRIPTION
  Stops Docker Compose services (if running) and frees the app port (default: 8787).
#>
param(
    [int]$Port = 8787
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $RepoRoot

if (Get-Command docker -ErrorAction SilentlyContinue) {
    try {
        docker info *> $null
        if ($LASTEXITCODE -eq 0 -and (Test-Path (Join-Path $RepoRoot "docker-compose.yml"))) {
            docker compose down --remove-orphans *> $null
            Write-Host "✓ Stopped Docker Compose services (if any)" -ForegroundColor Green
        }
    } catch {
        # Docker daemon not running; ignore
    }
}

$conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($conns) {
    $pids = $conns | Select-Object -ExpandProperty OwningProcess -Unique
    Write-Host "Stopping server on port $Port (PID: $($pids -join ', '))..."
    foreach ($p in $pids) {
        Stop-Process -Id $p -Force -ErrorAction SilentlyContinue
    }
    Write-Host "✓ Freed port $Port" -ForegroundColor Green
} else {
    Write-Host "✓ Port $Port is already free" -ForegroundColor Green
}
