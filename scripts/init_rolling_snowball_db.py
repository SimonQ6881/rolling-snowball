#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.rolling_snowball.db import bootstrap_database
from src.rolling_snowball.settings import PostgresSettings


def main() -> int:
    settings = PostgresSettings.from_env()
    bootstrap_database(settings)
    print(f"Initialized rolling_snowball database schema on {settings.dbname}@{settings.host}:{settings.port}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
