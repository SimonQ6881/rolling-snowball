from __future__ import annotations

from src.rolling_snowball.rules import RULE_VERSION, load_rule_snapshot
from src.rolling_snowball.settings import PostgresSettings


def test_postgres_settings_connect_kwargs_excludes_empty_password() -> None:
    settings = PostgresSettings(
        host="/tmp/postgres-run",
        port=5432,
        dbname="rolling_snowball",
        user="tester",
        password=None,
    )

    kwargs = settings.connect_kwargs()

    assert kwargs == {
        "host": "/tmp/postgres-run",
        "port": 5432,
        "dbname": "rolling_snowball",
        "user": "tester",
    }


def test_rule_snapshot_version_matches_constant() -> None:
    snapshot = load_rule_snapshot()

    assert snapshot["rule_version"] == RULE_VERSION
    assert snapshot["top_level_weights"]["biz_quality"] == 0.3
    assert snapshot["pool_thresholds"]["key_watch_min_score"] == 80.0
