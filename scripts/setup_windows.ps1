param(
  [switch]$SkipInstallOpenCode
)

$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$VenvDir = Join-Path $RootDir ".venv"

Write-Host "=== OpenCode Ad Dashboard Setup ===" -ForegroundColor Cyan
Write-Host

Write-Host "[1/6] Checking Python 3.10+"
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
  Write-Host "ERROR: python not found. Install Python 3.10+ first: https://www.python.org/downloads/" -ForegroundColor Red
  exit 1
}
python --version

Write-Host
Write-Host "[2/6] Creating virtual environment"
if (-not (Test-Path $VenvDir)) {
  python -m venv $VenvDir
  Write-Host "Created .venv/"
} else {
  Write-Host "Using existing .venv/"
}

$Pip = Join-Path $VenvDir "Scripts\pip.exe"
$Python = Join-Path $VenvDir "Scripts\python.exe"

Write-Host
Write-Host "[3/6] Installing Python dependencies"
& $Pip install -q -r (Join-Path $RootDir "requirements-dashboard.txt")

Write-Host
Write-Host "[4/6] Installing OpenCode CLI"
if ($SkipInstallOpenCode) {
  Write-Host "Skipping OpenCode installation (--SkipInstallOpenCode)"
} elseif (Get-Command opencode -ErrorAction SilentlyContinue) {
  Write-Host "OpenCode already installed: $(opencode --version 2>$null)"
} else {
  Write-Host "Downloading OpenCode installer..."
  $tmp = [System.IO.Path]::GetTempFileName() + ".exe"
  try {
    Invoke-WebRequest -Uri "https://opencode.ai/install" -OutFile $tmp
    Start-Process -FilePath $tmp -Wait
  } finally {
    Remove-Item $tmp -Force -ErrorAction SilentlyContinue
  }
}

if (Get-Command opencode -ErrorAction SilentlyContinue) {
  opencode --version
} else {
  Write-Host "WARNING: OpenCode not found in PATH. Install manually: https://opencode.ai/docs/cli" -ForegroundColor Yellow
}

Write-Host
Write-Host "[5/6] Creating storage directories"
$StorageDir = Join-Path $RootDir "dashboard_storage"
foreach ($sub in @("pids", "logs", "runs")) {
  $dir = Join-Path $StorageDir $sub
  if (-not (Test-Path $dir)) {
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    Write-Host "  Created $sub/"
  }
}

Write-Host
Write-Host "[6/6] Verifying setup"
if (Get-Command opencode -ErrorAction SilentlyContinue) {
  opencode models 2>$null | Out-Null
  if ($LASTEXITCODE -eq 0) {
    Write-Host "OpenCode providers configured" -ForegroundColor Green
  } else {
    Write-Host "WARNING: Run 'opencode providers login' to configure providers" -ForegroundColor Yellow
  }
} else {
  Write-Host "WARNING: OpenCode CLI not available" -ForegroundColor Yellow
}

Write-Host
Write-Host "=== Setup complete! ===" -ForegroundColor Green
Write-Host
Write-Host "Start dashboard:" -ForegroundColor Cyan
Write-Host "  .\scripts\start_dashboard_stack.ps1"
Write-Host
Write-Host "Or manually:" -ForegroundColor Cyan
Write-Host "  .\.venv\Scripts\uvicorn.exe dashboard.backend.app:app --host 127.0.0.1 --port 8787 --reload --app-dir `"$RootDir`""
Write-Host "  opencode serve"
Write-Host
Write-Host "Stop:" -ForegroundColor Cyan
Write-Host "  .\scripts\stop_dashboard_stack.ps1"
