#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FRONTEND_DIR="$ROOT/frontend-console"
STATE_DIR="$ROOT/data/dev-console"
BACKEND_PID_FILE="$STATE_DIR/backend.pid"
FRONTEND_PID_FILE="$STATE_DIR/frontend.pid"
BACKEND_LOG="$STATE_DIR/backend.log"
FRONTEND_LOG="$STATE_DIR/frontend.log"
BACKEND_HOST="127.0.0.1"
BACKEND_PORT="8780"
FRONTEND_HOST="127.0.0.1"
FRONTEND_PORT="4178"
OPEN_BROWSER="0"
DRY_RUN="0"

mkdir -p "$STATE_DIR"

find_node() {
  if command -v node >/dev/null 2>&1; then
    command -v node
    return 0
  fi

  for candidate in /opt/homebrew/bin/node /usr/local/bin/node; do
    if [ -x "$candidate" ]; then
      echo "$candidate"
      return 0
    fi
  done

  return 1
}

is_pid_running() {
  local pid_file="$1"
  if [ ! -f "$pid_file" ]; then
    return 1
  fi

  local pid
  pid="$(cat "$pid_file" 2>/dev/null || true)"
  if [ -z "$pid" ]; then
    return 1
  fi

  kill -0 "$pid" >/dev/null 2>&1
}

start_backend() {
  if is_pid_running "$BACKEND_PID_FILE"; then
    echo "后端已在运行，PID=$(cat "$BACKEND_PID_FILE")"
    return 0
  fi

  local command=(python3 "$ROOT/scripts/run_console_server.py" --host "$BACKEND_HOST" --port "$BACKEND_PORT")
  echo "启动后端: ${command[*]}"
  if [ "$DRY_RUN" = "1" ]; then
    return 0
  fi

  "${command[@]}" >"$BACKEND_LOG" 2>&1 &
  echo $! >"$BACKEND_PID_FILE"
}

start_frontend() {
  if is_pid_running "$FRONTEND_PID_FILE"; then
    echo "前端已在运行，PID=$(cat "$FRONTEND_PID_FILE")"
    return 0
  fi

  local node_bin
  node_bin="$(find_node)" || {
    echo "未找到 node，可先把 node 加入 PATH，或安装到 /opt/homebrew/bin/node /usr/local/bin/node。"
    exit 1
  }

  local vite_entry="$FRONTEND_DIR/node_modules/vite/bin/vite.js"
  if [ ! -f "$vite_entry" ]; then
    echo "未找到 $vite_entry，请先安装前端依赖。"
    exit 1
  fi

  local command=("$node_bin" "$vite_entry" --host "$FRONTEND_HOST" --port "$FRONTEND_PORT")
  echo "启动前端: ${command[*]}"
  if [ "$DRY_RUN" = "1" ]; then
    return 0
  fi

  (
    cd "$FRONTEND_DIR"
    "${command[@]}"
  ) >"$FRONTEND_LOG" 2>&1 &
  echo $! >"$FRONTEND_PID_FILE"
}

for arg in "$@"; do
  case "$arg" in
    --open)
      OPEN_BROWSER="1"
      ;;
    --dry-run)
      DRY_RUN="1"
      ;;
    *)
      echo "不支持的参数: $arg"
      echo "可用参数: --open --dry-run"
      exit 1
      ;;
  esac
done

start_backend
start_frontend

if [ "$DRY_RUN" = "1" ]; then
  exit 0
fi

echo
echo "控制台已启动。"
echo "前端地址: http://$FRONTEND_HOST:$FRONTEND_PORT"
echo "后端地址: http://$BACKEND_HOST:$BACKEND_PORT"
echo "后端日志: $BACKEND_LOG"
echo "前端日志: $FRONTEND_LOG"
echo "停止服务: bash scripts/stop_console_stack.sh"

if [ "$OPEN_BROWSER" = "1" ]; then
  open "http://$FRONTEND_HOST:$FRONTEND_PORT"
fi
