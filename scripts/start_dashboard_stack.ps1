$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$VenvDir = Join-Path $RootDir ".venv"
$StorageDir = Join-Path $RootDir "dashboard_storage"
$PidDir = Join-Path $StorageDir "pids"
$LogDir = Join-Path $StorageDir "logs"
$RunsDir = Join-Path $StorageDir "runs"

$OpenCodeHost = "127.0.0.1"
$OpenCodePort = "4090"
$DashboardHost = "127.0.0.1"
$DashboardPort = "8787"
$OpenCodePassword = if ($env:OPENCODE_SERVER_PASSWORD) { $env:OPENCODE_SERVER_PASSWORD } else { [guid]::NewGuid().ToString() }

$OpenCodePidFile = Join-Path $PidDir "opencode.pid"
$DashboardPidFile = Join-Path $PidDir "dashboard.pid"
$OpenCodeLog = Join-Path $LogDir "opencode.log"
$DashboardLog = Join-Path $LogDir "dashboard.log"

New-Item -ItemType Directory -Force -Path $PidDir, $LogDir, $RunsDir | Out-Null

function Test-PidRunning($pidFile) {
  if (-not (Test-Path $pidFile)) { return $false }
  $pid = Get-Content $pidFile | Select-Object -First 1
  if (-not $pid) { return $false }
  try { $proc = Get-Process -Id $pid -ErrorAction SilentlyContinue; return $null -ne $proc } catch { return $false }
}

Write-Host "Starting OpenCode server on $OpenCodeHost`:$OpenCodePort"
$env:OPENCODE_SERVER_PASSWORD = $OpenCodePassword
$openCodeArgs = "serve --hostname $OpenCodeHost --port $OpenCodePort --cors http://$DashboardHost`:$DashboardPort"
$openCodeProc = Start-Process -FilePath "opencode" -ArgumentList $openCodeArgs -PassThru -WindowStyle Hidden -RedirectStandardOutput $OpenCodeLog -RedirectStandardError $OpenCodeLog
$openCodeProc.Id | Set-Content -Path $OpenCodePidFile
Write-Host "OpenCode started with pid $($openCodeProc.Id)"

Write-Host "Starting dashboard API/UI on $DashboardHost`:$DashboardPort"
$UvicornExe = Join-Path $VenvDir "Scripts\uvicorn.exe"
$uvicornArgs = "dashboard.backend.app:app --host $DashboardHost --port $DashboardPort --app-dir `"$RootDir`""
$dashboardProc = Start-Process -FilePath $UvicornExe -ArgumentList $uvicornArgs -PassThru -WindowStyle Hidden -WorkingDirectory $RootDir -RedirectStandardOutput $DashboardLog -RedirectStandardError $DashboardLog
$dashboardProc.Id | Set-Content -Path $DashboardPidFile
Write-Host "Dashboard started with pid $($dashboardProc.Id)"

Write-Host "Waiting for dashboard..."
$DashboardReady = $false
for ($i = 0; $i -lt 60; $i++) {
  try {
    $r = Invoke-WebRequest -Uri "http://$DashboardHost`:$DashboardPort/api/defaults" -TimeoutSec 2 -ErrorAction SilentlyContinue
    if ($r.StatusCode -eq 200) {
      Write-Host "Dashboard is ready" -ForegroundColor Green
      $DashboardReady = $true
      break
    }
  } catch { }
  Start-Sleep -Milliseconds 200
}
if (-not $DashboardReady) {
  Write-Host "Warning: Dashboard did not become ready at http://$DashboardHost`:$DashboardPort/api/defaults" -ForegroundColor Yellow
}

Write-Host
Write-Host "Dashboard URL: http://$DashboardHost`:$DashboardPort"
Write-Host "OpenCode URL:  http://$OpenCodeHost`:$OpenCodePort"
Write-Host "OpenCode password: $OpenCodePassword"
Write-Host "Dashboard log: $DashboardLog"
Write-Host "OpenCode log:  $OpenCodeLog"

Start-Process "http://$DashboardHost`:$DashboardPort"
