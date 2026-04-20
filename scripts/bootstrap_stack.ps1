$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$VenvDir = Join-Path $RootDir ".venv"

Write-Host "[1/6] Checking Python"
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
  Write-Host "python not found. Install Python 3.10+ first."
  exit 1
}

Write-Host "[2/6] Creating virtualenv if needed"
if (-not (Test-Path $VenvDir)) {
  python -m venv $VenvDir
}

$Pip = Join-Path $VenvDir "Scripts\pip.exe"
$Python = Join-Path $VenvDir "Scripts\python.exe"

Write-Host "[3/6] Installing dashboard dependencies"
& $Pip install -r (Join-Path $RootDir "requirements-dashboard.txt")

Write-Host "[4/6] Checking OpenCode CLI"
if (-not (Get-Command opencode -ErrorAction SilentlyContinue)) {
  if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Write-Host "npm not found. Install Node.js LTS first: https://nodejs.org/"
    exit 1
  }
  Write-Host "OpenCode not found. Installing via npm..."
  npm install -g opencode-cli
}

Write-Host "[5/6] Verifying OpenCode"
opencode --version

Write-Host "[6/6] Starting full stack"
$env:OPENCODE_SERVER_PASSWORD = if ($env:OPENCODE_SERVER_PASSWORD) { $env:OPENCODE_SERVER_PASSWORD } else { [guid]::NewGuid().ToString() }

$DashboardStorage = Join-Path $RootDir "dashboard_storage"
$PidDir = Join-Path $DashboardStorage "pids"
$LogDir = Join-Path $DashboardStorage "logs"
$RunsDir = Join-Path $DashboardStorage "runs"
New-Item -ItemType Directory -Force -Path $PidDir, $LogDir, $RunsDir | Out-Null

$OpenCodeLog = Join-Path $LogDir "opencode.log"
$DashboardLog = Join-Path $LogDir "dashboard.log"
$OpenCodePidFile = Join-Path $PidDir "opencode.pid"
$DashboardPidFile = Join-Path $PidDir "dashboard.pid"

$openCodeArgs = "serve --hostname 127.0.0.1 --port 4090 --cors http://127.0.0.1:8787"
$openCodeProc = Start-Process -FilePath "opencode" -ArgumentList $openCodeArgs -PassThru -WindowStyle Hidden -RedirectStandardOutput $OpenCodeLog -RedirectStandardError $OpenCodeLog
Set-Content -Path $OpenCodePidFile -Value $openCodeProc.Id

$uvicornArgs = "dashboard.backend.app:app --host 127.0.0.1 --port 8787 --app-dir `"$RootDir`""
$dashboardProc = Start-Process -FilePath (Join-Path $VenvDir "Scripts\uvicorn.exe") -ArgumentList $uvicornArgs -PassThru -WindowStyle Hidden -WorkingDirectory $RootDir -RedirectStandardOutput $DashboardLog -RedirectStandardError $DashboardLog
Set-Content -Path $DashboardPidFile -Value $dashboardProc.Id

Write-Host "Dashboard URL: http://127.0.0.1:8787"
Write-Host "OpenCode URL:  http://127.0.0.1:4090"
Write-Host "OpenCode password: $env:OPENCODE_SERVER_PASSWORD"
Write-Host "Dashboard log: $DashboardLog"
Write-Host "OpenCode log:  $OpenCodeLog"

Start-Process "http://127.0.0.1:8787"

Write-Host "Next steps:"
Write-Host "  1) Add provider: opencode providers login"
Write-Host "  2) Verify models: opencode models"
