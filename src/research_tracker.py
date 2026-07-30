from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


@dataclass(frozen=True)
class ThemeRule:
    key: str
    label: str
    keywords: tuple[str, ...]


DEFAULT_THEME_RULES = (
    ThemeRule("precious_metals", "贵金属", ("黄金", "金价", "贵金属", "铜", "铜价", "锂", "矿业", "gold", "copper", "lithium")),
    ThemeRule("dollar_rates", "美元利率", ("美元", "美债", "利率", "收益率", "联储", "FOMC", "Treasury", "dollar", "yield", "rate")),
    ThemeRule("central_bank_gold", "央行购金", ("央行购金", "黄金储备", "官方储备", "央行", "gold reserves", "gold purchase", "central bank")),
)

SOURCE_CREDIBILITY = {
    "Tushare研报": "高",
    "中信证券": "高",
    "中金公司": "高",
    "华泰证券": "高",
    "国泰海通证券": "高",
    "国联民生证券": "高",
    "招商证券": "高",
    "兴业证券": "高",
    "华鑫证券": "中",
    "太平洋证券": "中",
    "国盛证券": "中",
    "中邮证券": "中",
    "财信证券": "中",
    "渤海证券": "中",
    "eastmoney": "中",
}


def score_theme(text: str, rule: ThemeRule) -> int:
    sample = normalize_text(text).lower()
    return sum(2 if len(keyword) >= 4 else 1 for keyword in rule.keywords if keyword.lower() in sample)


def classify_theme(item: dict[str, Any], theme_rules: tuple[ThemeRule, ...] = DEFAULT_THEME_RULES) -> tuple[str, int]:
    sample = " ".join(
        [
            str(item.get("title", "")),
            str(item.get("title_original", "")),
            str(item.get("summary", "")),
            str(item.get("summary_original", "")),
            " ".join(str(tag) for tag in item.get("tags", [])),
        ]
    )
    scored = [(rule.label, score_theme(sample, rule)) for rule in theme_rules]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    top_label, top_score = scored[0]
    return (top_label, top_score) if top_score > 0 else ("其他", 0)


def extract_summary(item: dict[str, Any]) -> str:
    summary = normalize_text(str(item.get("summary", "")))
    if summary:
        return summary[:180]
    title = normalize_text(str(item.get("title", "")))
    return title[:180]


def credibility_label(item: dict[str, Any]) -> str:
    source = str(item.get("institution") or item.get("org_name") or item.get("source") or "")
    return SOURCE_CREDIBILITY.get(source, SOURCE_CREDIBILITY.get(str(item.get("source", "")), "观察"))


def build_entry_id(item: dict[str, Any]) -> str:
    return "||".join(
        [
            str(item.get("core_theme", "")),
            str(item.get("date", "")),
            str(item.get("institution") or item.get("org_name") or item.get("source") or ""),
            str(item.get("title_original") or item.get("title") or ""),
        ]
    )


def filter_target_research(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    for item in entries:
        core_theme, score = classify_theme(item)
        if core_theme == "其他":
            continue
        out = dict(item)
        out["core_theme"] = core_theme
        out["theme_score"] = score
        out["credibility"] = credibility_label(out)
        out["updated_at"] = str(out.get("date", ""))
        out["core_view"] = extract_summary(out)
        out["record_id"] = build_entry_id(out)
        filtered.append(out)
    filtered.sort(key=lambda row: (str(row.get("date", "")), int(row.get("theme_score", 0))), reverse=True)
    return filtered


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"seen_ids": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"seen_ids": []}
    if not isinstance(data, dict):
        return {"seen_ids": []}
    seen_ids = data.get("seen_ids")
    return {"seen_ids": seen_ids if isinstance(seen_ids, list) else []}


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def track_research_updates(
    entries: list[dict[str, Any]],
    state_path: Path,
    alert_path: Path,
) -> list[dict[str, Any]]:
    state = load_state(state_path)
    seen_ids = set(str(item) for item in state.get("seen_ids", []))
    alerts: list[dict[str, Any]] = []
    for item in entries:
        record_id = str(item.get("record_id") or build_entry_id(item))
        if record_id in seen_ids:
            continue
        alerts.append(
            {
                "record_id": record_id,
                "date": item.get("date", ""),
                "core_theme": item.get("core_theme", ""),
                "title": item.get("title", ""),
                "institution": item.get("institution") or item.get("org_name") or item.get("source"),
                "credibility": item.get("credibility", "观察"),
                "core_view": item.get("core_view", ""),
            }
        )
        seen_ids.add(record_id)
    state["seen_ids"] = sorted(seen_ids)
    save_state(state_path, state)
    if alerts:
        alert_path.parent.mkdir(parents=True, exist_ok=True)
        alert_path.write_text(json.dumps(alerts, ensure_ascii=False, indent=2), encoding="utf-8")
    return alerts
