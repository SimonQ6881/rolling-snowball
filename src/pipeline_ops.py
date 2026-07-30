from __future__ import annotations

import json
from dataclasses import fields, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


def safe_slug(value: str) -> str:
    chars = []
    for ch in value:
        if ch.isalnum() or ch in ("_", "-"):
            chars.append(ch)
        else:
            chars.append("_")
    return "".join(chars).strip("_") or "dataset"


def current_trade_date(now: datetime) -> str:
    return now.strftime("%Y%m%d")


def default_dataset_key(records: list[dict[str, Any]]) -> list[str]:
    if not records:
        return []
    sample = records[0]
    key_sets = (
        ("record_id",),
        ("record_key",),
        ("trade_date",),
        ("date", "title"),
        ("ann_date", "title"),
        ("datetime", "title"),
        ("month_label", "title"),
        ("title",),
    )
    for candidate_set in key_sets:
        if all(candidate in sample for candidate in candidate_set):
            return list(candidate_set)
    return []


def validate_records(name: str, records: list[dict[str, Any]]) -> dict[str, Any]:
    dataset_keys = default_dataset_key(records)
    seen: set[str] = set()
    duplicate_count = 0
    missing_count = 0
    for row in records:
        if not any(str(value).strip() for value in row.values() if value is not None):
            missing_count += 1
            continue
        if not dataset_keys:
            continue
        key_parts = [str(row.get(dataset_key, "")).strip() for dataset_key in dataset_keys]
        if not all(key_parts):
            missing_count += 1
            continue
        key = "||".join(key_parts)
        if key in seen:
            duplicate_count += 1
        else:
            seen.add(key)
    return {
        "dataset": name,
        "rows": len(records),
        "key": ",".join(dataset_keys),
        "missing_count": missing_count,
        "duplicate_count": duplicate_count,
        "valid": missing_count == 0 and duplicate_count == 0,
    }


def serialize_value(value: Any) -> Any:
    if isinstance(value, pd.DataFrame):
        return value.to_dict(orient="records")
    if isinstance(value, list):
        return [serialize_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): serialize_value(item) for key, item in value.items()}
    if is_dataclass(value):
        return {field.name: serialize_value(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, (datetime, pd.Timestamp)):
        return value.isoformat()
    return value


def serialize_report_data(data: Any) -> dict[str, Any]:
    if is_dataclass(data):
        return {field.name: serialize_value(getattr(data, field.name)) for field in fields(data)}
    raise TypeError("data 必须是 dataclass")


def build_archive_manifest(payload: dict[str, Any], status_rows: list[dict[str, Any]]) -> dict[str, Any]:
    datasets: list[dict[str, Any]] = []
    for key, value in payload.items():
        if isinstance(value, list) and (not value or isinstance(value[0], dict)):
            datasets.append(validate_records(key, value))
        elif isinstance(value, dict):
            for child_key, child_value in value.items():
                if isinstance(child_value, list) and (not child_value or isinstance(child_value[0], dict)):
                    datasets.append(validate_records(f"{key}.{child_key}", child_value))
    ok = all(item["valid"] for item in datasets)
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "datasets": datasets,
        "status_rows": status_rows,
        "integrity_ok": ok,
        "invalid_datasets": [item["dataset"] for item in datasets if not item["valid"]],
    }


def archive_exists(archive_root: Path, trade_date: str) -> bool:
    folder = archive_root / trade_date[:4] / trade_date[4:6] / trade_date[6:8]
    return (folder / f"trading_snapshot_{trade_date}.json").exists()


def archive_trading_snapshot(
    archive_root: Path,
    trade_date: str,
    report_data: Any,
    status_rows: list[dict[str, Any]],
) -> tuple[Path, Path]:
    folder = archive_root / trade_date[:4] / trade_date[4:6] / trade_date[6:8]
    folder.mkdir(parents=True, exist_ok=True)
    payload = {
        "trade_date": trade_date,
        "archived_at": datetime.now().isoformat(timespec="seconds"),
        "report_data": serialize_report_data(report_data),
    }
    manifest = build_archive_manifest(payload["report_data"], status_rows)
    if not manifest["integrity_ok"]:
        raise ValueError(f"归档校验失败: {','.join(manifest['invalid_datasets'])}")
    data_path = folder / f"trading_snapshot_{trade_date}.json"
    manifest_path = folder / f"trading_snapshot_{trade_date}.manifest.json"
    data_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return data_path, manifest_path


def is_trading_day(calendar_df: pd.DataFrame, now: datetime) -> bool:
    if calendar_df.empty:
        return now.weekday() < 5
    sample = calendar_df.copy()
    if "is_open" not in sample.columns:
        return now.weekday() < 5
    latest = sample.iloc[-1]
    return str(latest.get("is_open", "0")) in {"1", "True", "true"}


def should_run_hourly_update(now: datetime, trading_day: bool) -> bool:
    if not trading_day:
        return False
    return 9 <= now.hour <= 15


def should_archive_after_close(now: datetime, trading_day: bool) -> bool:
    if not trading_day:
        return False
    return now.hour >= 16
