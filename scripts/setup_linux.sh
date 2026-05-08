#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$ROOT_DIR/.venv"

echo "=== OpenCode Ad Dashboard Setup ==="
echo

echo "[1/6] Checking Python 3.10+"
if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 not found. Install Python 3.10+ first: https://www.python.org/downloads/"
  exit 1
fi
python3 --version

echo
echo "[2/6] Creating virtual environment"
if [[ ! -d "$VENV_DIR" ]]; then
  python3 -m venv "$VENV_DIR"
  echo "Created .venv/"
else
  echo "Using existing .venv/"
fi

echo
echo "[3/6] Installing Python dependencies"
"$VENV_DIR/bin/pip" install -q -r "$ROOT_DIR/requirements-dashboard.txt"

echo
echo "[4/6] Installing OpenCode CLI"
if command -v opencode >/dev/null 2>&1; then
  echo "OpenCode already installed: $(opencode --version 2>/dev/null || echo 'ok')"
else
  echo "Installing OpenCode via official installer..."
  curl -fsSL https://opencode.ai/install | bash
  if [[ -f "$HOME/bin/opencode" ]]; then
    export PATH="$HOME/bin:$PATH"
  fi
fi
opencode --version

echo
echo "[5/6] Creating storage directories"
mkdir -p "$ROOT_DIR/dashboard_storage"/{pids,logs,runs}

echo
echo "[6/6] Verifying setup"
if opencode models >/dev/null 2>&1; then
  echo "OpenCode providers: $(opencode providers list 2>/dev/null | grep -c '●' || echo '0') configured"
else
  echo "WARNING: OpenCode has no providers configured. Run: opencode providers login"
fi

echo
echo "=== Setup complete! ==="
echo
echo "Start dashboard:"
echo "  bash scripts/start_dashboard_stack.sh"
echo
echo "Or manually:"
echo "  bash scripts/run_dashboard.sh   # dashboard only"
echo "  opencode serve                  # headless OpenCode"
echo
echo "Stop:"
echo "  bash scripts/stop_dashboard_stack.sh"
