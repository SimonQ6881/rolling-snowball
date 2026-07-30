#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

echo "[legacy] run_stock_evaluation_server.sh 属于旧版股票评估原型，不是当前 rolling-snowball 控制台主入口。" >&2

python3 src/stock_evaluation_server.py "$@"
