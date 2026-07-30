#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

HOURS="${1:-72}"
INTERVAL_SECONDS="${2:-3600}"
END_TS=$(( $(date +%s) + HOURS * 3600 ))
LOG_DIR="$ROOT/reports/testing"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/stability_$(date +%Y%m%d_%H%M%S).log"

echo "stability_hours=$HOURS interval_seconds=$INTERVAL_SECONDS" | tee -a "$LOG_FILE"

while [ "$(date +%s)" -lt "$END_TS" ]; do
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] run scheduled pipeline" | tee -a "$LOG_FILE"
  if bash "$ROOT/scripts/run_daily_report.sh" --mode scheduled >>"$LOG_FILE" 2>&1; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ok" | tee -a "$LOG_FILE"
  else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] failed" | tee -a "$LOG_FILE"
    exit 1
  fi
  sleep "$INTERVAL_SECONDS"
done

echo "stability test finished: $LOG_FILE"
