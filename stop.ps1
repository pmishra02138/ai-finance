<#
.SYNOPSIS
  AI Personal Finance Advisor - Windows Stop Script
.DESCRIPTION
  Stops Docker Compose services (if running) and frees local ports (default: 3000, 8787).
.EXAMPLE
  .\stop.ps1
  .\stop.ps1 -Port 3001 -ApiPort 8788
#>
param(
    [int]$Port = 3000,
    [int]$ApiPort = 8787
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

if (Get-Command docker -ErrorAction SilentlyContinue) {
    try {
        docker info *> $null
        if ($LASTEXITCODE -eq 0 -and (Test-Path (Join-Path $ScriptDir "docker-compose.yml"))) {
            docker compose down --remove-orphans *> $null
            Write-Host "✓ Stopped Docker Compose services (if any)" -ForegroundColor Green
        }
    } catch {
        # Docker daemon not running; ignore
    }
}

function Free-LocalPort {
    param([int]$TargetPort, [string]$Label)
    $conns = Get-NetTCPConnection -LocalPort $TargetPort -State Listen -ErrorAction SilentlyContinue
    if ($conns) {
        $pids = $conns | Select-Object -ExpandProperty OwningProcess -Unique
        Write-Host "Stopping $Label on port $TargetPort (PID: $($pids -join ', '))..."
        foreach ($p in $pids) {
            Stop-Process -Id $p -Force -ErrorAction SilentlyContinue
        }
        Write-Host "✓ Freed port $TargetPort" -ForegroundColor Green
    } else {
        Write-Host "✓ Port $TargetPort ($Label) is already free" -ForegroundColor Green
    }
}

Free-LocalPort -TargetPort $Port -Label "Node.js frontend"
Free-LocalPort -TargetPort $ApiPort -Label "FastAPI backend"
