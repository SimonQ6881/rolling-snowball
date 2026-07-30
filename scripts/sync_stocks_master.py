#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.rolling_snowball.db import bootstrap_database
from src.rolling_snowball.master_sync import sync_stocks_master
from src.rolling_snowball.settings import PostgresSettings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="同步 rolling_snowball 的股票主档表。")
    parser.add_argument("--limit", type=int, default=None, help="仅同步前 N 条股票记录，用于调试。")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    settings = PostgresSettings.from_env()
    bootstrap_database(settings)
    synced = sync_stocks_master(settings, limit=args.limit)
    print(f"Synced {synced} stock master records into {settings.dbname}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
