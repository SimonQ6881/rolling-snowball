#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STATE_DIR="$ROOT/data/dev-console"
BACKEND_PID_FILE="$STATE_DIR/backend.pid"
FRONTEND_PID_FILE="$STATE_DIR/frontend.pid"

stop_by_pid_file() {
  local label="$1"
  local pid_file="$2"

  if [ ! -f "$pid_file" ]; then
    echo "$label 未运行。"
    return 0
  fi

  local pid
  pid="$(cat "$pid_file" 2>/dev/null || true)"
  if [ -z "$pid" ]; then
    rm -f "$pid_file"
    echo "$label PID 文件为空，已清理。"
    return 0
  fi

  if kill -0 "$pid" >/dev/null 2>&1; then
    kill "$pid"
    echo "已停止 $label，PID=$pid"
  else
    echo "$label 进程不存在，已清理 PID 文件。"
  fi

  rm -f "$pid_file"
}

stop_by_pid_file "后端" "$BACKEND_PID_FILE"
stop_by_pid_file "前端" "$FRONTEND_PID_FILE"
