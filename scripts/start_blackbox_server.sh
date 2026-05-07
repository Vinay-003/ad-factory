#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_DIR="$ROOT_DIR/dashboard_storage/pids"
LOG_DIR="$ROOT_DIR/dashboard_storage/logs"

BLACKBOX_HOST="127.0.0.1"
BLACKBOX_PORT="4091"
BLACKBOX_API_KEY="${BLACKBOX_API_KEY:-sk-r5EM_uLQNKnct30sEnkSYQ}"
BLACKBOX_PASSWORD="${BLACKBOX_SERVER_PASSWORD:-blackbox-local-pass}"

mkdir -p "$PID_DIR" "$LOG_DIR"

BLACKBOX_PID_FILE="$PID_DIR/blackbox.pid"
BLACKBOX_LOG="$LOG_DIR/blackbox.log"

is_pid_running() {
  local pid_file="$1"
  if [[ ! -f "$pid_file" ]]; then
    return 1
  fi
  local pid
  pid="$(cat "$pid_file")"
  if [[ -z "$pid" ]]; then
    return 1
  fi
  if kill -0 "$pid" >/dev/null 2>&1; then
    return 0
  fi
  return 1
}

start_blackbox_server() {
  if is_pid_running "$BLACKBOX_PID_FILE"; then
    echo "Blackbox server already running (pid $(cat "$BLACKBOX_PID_FILE"))"
    return
  fi
  echo "Starting Blackbox server on $BLACKBOX_HOST:$BLACKBOX_PORT"
  
  export BLACKBOX_API_KEY="$BLACKBOX_API_KEY"
  
  nohup python3 "$ROOT_DIR/dashboard_storage/blackbox_config/blackbox_server.py" >"$BLACKBOX_LOG" 2>&1 &
  echo $! >"$BLACKBOX_PID_FILE"
  echo "Blackbox server started with pid $(cat "$BLACKBOX_PID_FILE")"
}

wait_for_url() {
  local url="$1"
  local name="$2"
  local retries=30
  local delay=0.5
  for _ in $(seq 1 "$retries"); do
    if curl -fsS -u "user:$BLACKBOX_PASSWORD" "$url" >/dev/null 2>&1; then
      echo "$name is ready"
      return 0
    fi
    sleep $delay
  done
  echo "Warning: $name did not become ready at $url"
  return 1
}

start_blackbox_server

wait_for_url "http://$BLACKBOX_HOST:$BLACKBOX_PORT/v1/models" "Blackbox Server"

echo
echo "Blackbox Server URL: http://$BLACKBOX_HOST:$BLACKBOX_PORT"
echo "Blackbox password: $BLACKBOX_PASSWORD"
echo "Blackbox log: $BLACKBOX_LOG"
echo "API Key: ${BLACKBOX_API_KEY:0:10}..."