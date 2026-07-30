from __future__ import annotations

import json
from pathlib import Path

import psycopg

from .rules import RULE_NAME, RULE_VERSION, load_rule_snapshot
from .settings import ROOT, PostgresSettings


SCHEMA_PATH = ROOT / "sql" / "postgres" / "001_init_schema.sql"


def connect(settings: PostgresSettings | None = None, *, autocommit: bool = False) -> psycopg.Connection:
    pg_settings = settings or PostgresSettings.from_env()
    conn = psycopg.connect(**pg_settings.connect_kwargs())
    conn.autocommit = autocommit
    return conn


def apply_schema(settings: PostgresSettings | None = None, schema_path: Path = SCHEMA_PATH) -> None:
    sql = schema_path.read_text(encoding="utf-8")
    with connect(settings, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)


def upsert_rule_version(
    settings: PostgresSettings | None = None,
    *,
    rule_version: str = RULE_VERSION,
    rule_name: str = RULE_NAME,
    is_active: bool = True,
) -> None:
    snapshot = load_rule_snapshot()
    sql = """
        INSERT INTO rule_versions (rule_version, rule_name, rule_snapshot, is_active)
        VALUES (%s, %s, %s::jsonb, %s)
        ON CONFLICT (rule_version) DO UPDATE
        SET rule_name = EXCLUDED.rule_name,
            rule_snapshot = EXCLUDED.rule_snapshot,
            is_active = EXCLUDED.is_active,
            updated_at = now();
    """
    deactivate_sql = """
        UPDATE rule_versions
        SET is_active = false,
            updated_at = now()
        WHERE rule_version <> %s AND is_active = true;
    """
    with connect(settings) as conn:
        with conn.cursor() as cur:
            if is_active:
                cur.execute(deactivate_sql, (rule_version,))
            cur.execute(sql, (rule_version, rule_name, json.dumps(snapshot, ensure_ascii=False), is_active))
        conn.commit()


def bootstrap_database(settings: PostgresSettings | None = None) -> None:
    apply_schema(settings)
    upsert_rule_version(settings)
