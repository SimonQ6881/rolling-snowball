#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "[legacy] run_daily_report.sh 属于历史日报链路，不是当前 rolling-snowball 控制台主入口。" >&2

if [ -f "$ROOT/.env" ]; then
  set -a
  source "$ROOT/.env"
  set +a
fi

python3 "$ROOT/src/zijin_daily_report.py" --config "$ROOT/config/portfolio.json" "$@"
