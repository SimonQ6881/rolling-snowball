#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.rolling_snowball.scoring_pipeline import ScoringPipeline
from src.rolling_snowball.settings import PostgresSettings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="运行 rolling_snowball 评分流水线的首版闭环。")
    parser.add_argument(
        "--data-version",
        default=datetime.now().strftime("%Y%m%d"),
        help="本次运行使用的数据版本标识。",
    )
    parser.add_argument("--limit", type=int, default=None, help="仅同步前 N 条股票记录，用于调试。")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    pipeline = ScoringPipeline(PostgresSettings.from_env())
    result = pipeline.run_bootstrap_flow(data_version=args.data_version, limit=args.limit)
    print(
        "Bootstrap scoring flow completed: "
        f"run_id={result['run_id']} "
        f"total_stocks={result['total_stocks']} "
        f"passed_filter_count={result['passed_filter_count']} "
        f"key_watch_count={result['key_watch_count']} "
        f"watch_count={result['watch_count']} "
        f"upserted_count={result['upserted_count']} "
        f"rule_version={result['rule_version']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
