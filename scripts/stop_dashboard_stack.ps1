<#
.SYNOPSIS
    Stops the OpenCode Ad Dashboard stack.
.DESCRIPTION
    Stops both the OpenCode headless AI server and the FastAPI dashboard
    by reading their PIDs from the pid files.
.EXAMPLE
    .\scripts\stop_dashboard_stack.ps1
#>

$ErrorActionPreference = "SilentlyContinue"

$RootDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PidDir = Join-Path $RootDir "dashboard_storage\pids"

function Stop-FromPidFile($PidFile, $Name) {
    if (-not (Test-Path $PidFile)) {
        Write-Host "$Name: not running (no pid file)" -ForegroundColor Gray
        return
    }

    $pidStr = Get-Content $PidFile | Select-Object -First 1
    if (-not $pidStr) {
        Write-Host "$Name: empty pid file" -ForegroundColor Gray
        Remove-Item $PidFile -Force
        return
    }

    $pid = [int]$pidStr
    try {
        $proc = Get-Process -Id $pid -ErrorAction Stop
        Stop-Process -Id $pid -Force
        Write-Host "$Name: stopped (pid $pid)" -ForegroundColor Green
    } catch {
        Write-Host "$Name: not running (pid $pid not found)" -ForegroundColor Gray
    }

    Remove-Item $PidFile -Force
}

Write-Host "Stopping dashboard stack..." -ForegroundColor Yellow
Write-Host ""

Stop-FromPidFile (Join-Path $PidDir "dashboard.pid") "Dashboard"
Stop-FromPidFile (Join-Path $PidDir "opencode.pid") "OpenCode"

Write-Host ""
Write-Host "Dashboard stack stopped." -ForegroundColor Green
