$ErrorActionPreference = "SilentlyContinue"

$RootDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PidDir = Join-Path $RootDir "dashboard_storage\pids"

function Stop-FromPidFile($PidFile, $Name) {
  if (-not (Test-Path $PidFile)) {
    Write-Host "$Name not running (no pid file)"
    return
  }
  $pid = Get-Content $PidFile | Select-Object -First 1
  if ($pid) {
    try {
      Stop-Process -Id $pid -Force
      Write-Host "Stopped $Name (pid $pid)"
    } catch {
      Write-Host "$Name not running"
    }
  }
  Remove-Item $PidFile -Force
}

Stop-FromPidFile (Join-Path $PidDir "dashboard.pid") "dashboard"
Stop-FromPidFile (Join-Path $PidDir "opencode.pid") "opencode"
