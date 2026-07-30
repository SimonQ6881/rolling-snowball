from __future__ import annotations

import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

from .settings import ROOT


RULE_VERSION = "v1.0"
RULE_NAME = "首版通用选股规则"
RULE_SNAPSHOT_PATH = ROOT / "config" / "rule_versions" / "stock_selection_v1.json"


@lru_cache(maxsize=1)
def load_rule_snapshot(path: Path = RULE_SNAPSHOT_PATH) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("rule_version") != RULE_VERSION:
        raise ValueError(f"规则快照版本不匹配: {payload.get('rule_version')} != {RULE_VERSION}")
    return payload


def clone_rule_snapshot(snapshot: dict[str, Any] | None = None) -> dict[str, Any]:
    return deepcopy(snapshot or load_rule_snapshot())


def write_rule_snapshot(snapshot: dict[str, Any], path: Path = RULE_SNAPSHOT_PATH) -> None:
    if snapshot.get("rule_version") != RULE_VERSION:
        raise ValueError(f"规则快照版本不匹配: {snapshot.get('rule_version')} != {RULE_VERSION}")
    path.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    load_rule_snapshot.cache_clear()
