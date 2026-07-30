#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "[legacy] run_report_server.sh 属于历史日报预览服务，不是当前 rolling-snowball 控制台主入口。" >&2

python3 "$ROOT/src/report_server.py" "$@"
