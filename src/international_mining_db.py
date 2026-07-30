from __future__ import annotations

import argparse
import json
import math
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_SUPPLY_PATH = ROOT / "data" / "cache" / "commodity_supply_plans.json"
OUTPUT_DATA_DIR = ROOT / "data" / "international_mining"
OUTPUT_REPORT_DIR = ROOT / "reports" / "international_mining"

COMMODITY_LABELS = {
    "gold": "黄金",
    "copper": "铜",
    "lithium": "锂",
}

STATUS_LABELS = {
    "quantified": "三年量化",
    "partial": "部分披露",
    "undisclosed": "未完整披露",
}

COUNTRY_ALIASES = {
    "china": "China",
    "united states": "United States",
    "usa": "United States",
    "us": "United States",
    "uk": "United Kingdom",
    "u.k.": "United Kingdom",
    "south africa": "South Africa",
    "peru": "Peru",
    "mexico": "Mexico",
    "australia": "Australia",
    "canada": "Canada",
    "chile": "Chile",
}

REGION_MAP = {
    "China": "Asia",
    "Australia": "Oceania",
    "Canada": "North America",
    "United States": "North America",
    "United Kingdom": "Europe",
    "South Africa": "Africa",
    "Chile": "South America",
    "Peru": "South America",
    "Mexico": "North America",
    "Argentina": "South America",
    "Mongolia": "Asia",
}

MISSING_MARKERS = {"", "未单列披露", "未披露", "n/a", "na", "情景口径，未单列披露"}


@dataclass
class ParsedProduction:
    raw_text: str
    disclosed: bool
    comparable: bool
    basis: str | None
    display_unit: str | None
    standardized_unit: str | None
    value_min: float | None
    value_max: float | None
    value_mid: float | None
    scale_reference_value: float | None


def load_json_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, list) else []


def normalize_whitespace(value: str) -> str:
    return " ".join(str(value).strip().split())


def is_missing_text(value: Any) -> bool:
    text = normalize_whitespace(str(value or ""))
    return text.lower() in MISSING_MARKERS


def normalize_country_list(raw_country: str) -> list[str]:
    text = normalize_whitespace(raw_country)
    if not text:
        return ["Unknown"]
    for sep in ("/", ",", ";", "|", "、"):
        text = text.replace(sep, "|")
    tokens = [token.strip() for token in text.split("|") if token.strip()]
    normalized: list[str] = []
    for token in tokens:
        mapped = COUNTRY_ALIASES.get(token.lower(), token)
        normalized.append(mapped)
    return normalized or ["Unknown"]


def infer_regions(countries: list[str]) -> list[str]:
    regions = []
    for country in countries:
        regions.append(REGION_MAP.get(country, "Other"))
    deduped: list[str] = []
    for item in regions:
        if item not in deduped:
            deduped.append(item)
    return deduped


def normalize_source_date(raw_value: str) -> str:
    text = normalize_whitespace(raw_value)
    if not text:
        return "未披露"
    digits = "".join(ch for ch in text if ch.isdigit())
    if len(digits) >= 6:
        return f"{digits[:4]}-{digits[4:6]}"
    if len(digits) == 4:
        return digits
    return text


def source_domain(url: str) -> str:
    parsed = urlparse(url or "")
    return parsed.netloc or "unknown"


def _parse_number(text: str) -> float:
    return float(text.replace(",", ""))


def _extract_range_with_unit(text: str, units: list[str]) -> tuple[float, float, str] | None:
    lowered = text.lower()
    ordered_units = sorted(units, key=len, reverse=True)
    for unit in ordered_units:
        unit_pattern = unit.replace(" ", r"\s+")
        range_pattern = rf"(?<![A-Za-z])(\d+(?:,\d{{3}})*(?:\.\d+)?)\s*-\s*(\d+(?:,\d{{3}})*(?:\.\d+)?)\s*({unit_pattern})"
        range_match = pd.Series([lowered]).str.extract(range_pattern).iloc[0].tolist()
        if isinstance(range_match[0], str) and range_match[0]:
            return _parse_number(range_match[0]), _parse_number(range_match[1]), unit
        single_pattern = rf"(?<![A-Za-z])(\d+(?:,\d{{3}})*(?:\.\d+)?)\s*({unit_pattern})"
        single_match = pd.Series([lowered]).str.extract(single_pattern).iloc[0].tolist()
        if isinstance(single_match[0], str) and single_match[0]:
            value = _parse_number(single_match[0])
            return value, value, unit
    return None


def parse_production_text(text: Any, commodity: str) -> ParsedProduction:
    raw_text = normalize_whitespace(str(text or ""))
    if is_missing_text(raw_text):
        return ParsedProduction(raw_text, False, False, None, None, None, None, None, None, None)

    lowered = raw_text.lower()
    value_range: tuple[float, float, str] | None = None

    if commodity == "gold":
        value_range = _extract_range_with_unit(lowered, ["moz", "koz", "万吨", "吨"])
        if not value_range:
            return ParsedProduction(raw_text, True, False, None, None, None, None, None, None, None)
        value_min, value_max, unit = value_range
        if unit == "moz":
            factor = 31.1034768
            display_unit = "Moz"
        elif unit == "koz":
            factor = 0.0311034768
            display_unit = "koz"
        elif unit == "万吨":
            factor = 10000.0
            display_unit = "万吨"
        else:
            factor = 1.0
            display_unit = "吨"
        converted_min = value_min * factor
        converted_max = value_max * factor
        return ParsedProduction(
            raw_text,
            True,
            True,
            "gold_tonnes",
            display_unit,
            "吨",
            converted_min,
            converted_max,
            (converted_min + converted_max) / 2,
            (converted_min + converted_max) / 2,
        )

    if commodity == "copper":
        value_range = _extract_range_with_unit(lowered, ["bn lb", "ktpa", "kt", "万吨", "吨"])
        if not value_range:
            return ParsedProduction(raw_text, True, False, None, None, None, None, None, None, None)
        value_min, value_max, unit = value_range
        if unit == "bn lb":
            factor = 453.59237
            display_unit = "bn lb"
        elif unit in {"kt", "ktpa"}:
            factor = 1.0
            display_unit = unit
        elif unit == "万吨":
            factor = 10.0
            display_unit = "万吨"
        else:
            factor = 0.001
            display_unit = "吨"
        converted_min = value_min * factor
        converted_max = value_max * factor
        return ParsedProduction(
            raw_text,
            True,
            True,
            "copper_kt",
            display_unit,
            "kt",
            converted_min,
            converted_max,
            (converted_min + converted_max) / 2,
            (converted_min + converted_max) / 2,
        )

    if commodity == "lithium":
        lce_hint = any(token in lowered for token in ("lce", "碳酸锂"))
        hydroxide_hint = any(token in lowered for token in ("hydroxide", "氢氧化锂"))
        spodumene_hint = any(token in lowered for token in ("spodumene", "sc6"))
        value_range = _extract_range_with_unit(lowered, ["mtpa", "ktpa", "kt", "万吨", "吨"])
        if not value_range:
            return ParsedProduction(raw_text, True, False, None, None, None, None, None, None, None)
        value_min, value_max, unit = value_range
        if unit == "mtpa":
            factor = 1000.0
            display_unit = "Mtpa"
        elif unit in {"kt", "ktpa"}:
            factor = 1.0
            display_unit = unit
        elif unit == "万吨":
            factor = 10.0
            display_unit = "万吨"
        else:
            factor = 0.001
            display_unit = "吨"
        converted_min = value_min * factor
        converted_max = value_max * factor
        if lce_hint:
            basis = "lithium_lce_kt"
            standardized_unit = "kt LCE"
        elif hydroxide_hint:
            basis = "lithium_hydroxide_kt"
            standardized_unit = "kt LiOH"
        elif spodumene_hint or "ktpa" in lowered or "mtpa" in lowered:
            basis = "lithium_spodumene_kt"
            standardized_unit = "kt SC6"
        else:
            return ParsedProduction(raw_text, True, False, None, display_unit, None, None, None, None, None)
        return ParsedProduction(
            raw_text,
            True,
            True,
            basis,
            display_unit,
            standardized_unit,
            converted_min,
            converted_max,
            (converted_min + converted_max) / 2,
            (converted_min + converted_max) / 2,
        )

    return ParsedProduction(raw_text, True, False, None, None, None, None, None, None, None)


def infer_operating_stage(current_capacity: str, commissioning: str, capacity_addition: str) -> str:
    text = " ".join([current_capacity, commissioning, capacity_addition]).lower()
    if any(token in text for token in ("care and maintenance", "停产", "暂停", "检修", "收缩")):
        return "维护收缩"
    if any(token in text for token in ("爬坡", "投产", "首产", "commercial", "机械完工", "恢复出矿", "复产", "放量")):
        return "投产爬坡"
    if any(token in text for token in ("开发阶段", "开发", "推进", "审批", "fid", "建设中", "待建", "前阶段")):
        return "开发建设"
    if any(token in text for token in ("稳定运营", "稳定维持", "稳定", "运营", "组合运营", "maintain")):
        return "成熟运营"
    return "待识别"


def infer_status(raw_status: str, disclosed_years: int) -> str:
    normalized = normalize_whitespace(raw_status).lower()
    if normalized in STATUS_LABELS:
        return normalized
    if disclosed_years >= 3:
        return "quantified"
    if disclosed_years >= 1:
        return "partial"
    return "undisclosed"


def deduplicate_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered: dict[tuple[str, str], dict[str, Any]] = {}
    for item in records:
        company = normalize_whitespace(item.get("company", ""))
        commodity = normalize_whitespace(item.get("commodity", "")).lower()
        if not company or commodity not in COMMODITY_LABELS:
            continue
        key = (company, commodity)
        item_date = normalize_source_date(str(item.get("source_date", "")))
        existing = ordered.get(key)
        if not existing:
            ordered[key] = item
            continue
        existing_date = normalize_source_date(str(existing.get("source_date", "")))
        if item_date >= existing_date:
            ordered[key] = item
    return list(ordered.values())


def scale_bucket_labels(length: int, rank: int) -> str:
    if length <= 1:
        return "头部"
    third = max(1, math.ceil(length / 3))
    if rank <= third:
        return "头部"
    if rank <= third * 2:
        return "中型"
    return "尾部"


def standardize_mining_records(records: list[dict[str, Any]]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    cleaned = deduplicate_records(records)
    as_of = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")

    company_rows: list[dict[str, Any]] = []
    production_rows: list[dict[str, Any]] = []

    for idx, raw in enumerate(cleaned, start=1):
        company = normalize_whitespace(raw.get("company", ""))
        commodity = normalize_whitespace(raw.get("commodity", "")).lower()
        country_list = normalize_country_list(str(raw.get("country", "")))
        region_list = infer_regions(country_list)
        current_capacity = normalize_whitespace(raw.get("current_capacity", "未披露"))
        commissioning = normalize_whitespace(raw.get("commissioning", "未披露"))
        capacity_addition = normalize_whitespace(raw.get("capacity_addition", "未披露"))

        year_payload: dict[int, ParsedProduction] = {}
        disclosed_years = 0
        comparable_years = 0
        for year in (2026, 2027, 2028):
            parsed = parse_production_text(raw.get(f"production_{year}", ""), commodity)
            year_payload[year] = parsed
            if parsed.disclosed:
                disclosed_years += 1
            if parsed.comparable:
                comparable_years += 1
            production_rows.append(
                {
                    "record_id": idx,
                    "company": company,
                    "commodity": commodity,
                    "commodity_label": COMMODITY_LABELS[commodity],
                    "year": year,
                    "raw_text": parsed.raw_text,
                    "disclosed": int(parsed.disclosed),
                    "comparable": int(parsed.comparable),
                    "basis": parsed.basis,
                    "display_unit": parsed.display_unit,
                    "standardized_unit": parsed.standardized_unit,
                    "value_min": parsed.value_min,
                    "value_max": parsed.value_max,
                    "value_mid": parsed.value_mid,
                }
            )

        current_capacity_parsed = parse_production_text(current_capacity, commodity)
        capacity_addition_parsed = parse_production_text(capacity_addition, commodity)
        status = infer_status(str(raw.get("status", "")), disclosed_years)

        if year_payload[2026].comparable:
            scale_value = year_payload[2026].scale_reference_value
            scale_basis = year_payload[2026].basis
            scale_source = "production_2026"
        elif current_capacity_parsed.comparable:
            scale_value = current_capacity_parsed.scale_reference_value
            scale_basis = current_capacity_parsed.basis
            scale_source = "current_capacity"
        elif capacity_addition_parsed.comparable:
            scale_value = capacity_addition_parsed.scale_reference_value
            scale_basis = capacity_addition_parsed.basis
            scale_source = "capacity_addition"
        else:
            scale_value = None
            scale_basis = None
            scale_source = None

        company_rows.append(
            {
                "record_id": idx,
                "company": company,
                "commodity": commodity,
                "commodity_label": COMMODITY_LABELS[commodity],
                "company_type": normalize_whitespace(raw.get("company_type", "unknown")) or "unknown",
                "country_primary": country_list[0],
                "country_list": json.dumps(country_list, ensure_ascii=False),
                "region_list": json.dumps(region_list, ensure_ascii=False),
                "status": status,
                "status_label": STATUS_LABELS[status],
                "disclosed_years": disclosed_years,
                "comparable_years": comparable_years,
                "operating_stage": infer_operating_stage(current_capacity, commissioning, capacity_addition),
                "scale_reference_value": scale_value,
                "scale_reference_basis": scale_basis,
                "scale_reference_source": scale_source,
                "production_2026_raw": year_payload[2026].raw_text or "未单列披露",
                "production_2027_raw": year_payload[2027].raw_text or "未单列披露",
                "production_2028_raw": year_payload[2028].raw_text or "未单列披露",
                "current_capacity": current_capacity,
                "commissioning": commissioning,
                "capacity_addition": capacity_addition,
                "source_date": normalize_source_date(str(raw.get("source_date", ""))),
                "source_title": normalize_whitespace(raw.get("source_title", "官方披露")) or "官方披露",
                "source_url": normalize_whitespace(raw.get("source_url", "")),
                "source_domain": source_domain(str(raw.get("source_url", ""))),
                "assumptions": normalize_whitespace(raw.get("assumptions", "")) or "以公司官方披露为准",
                "last_cleaned_at": as_of,
            }
        )

    company_df = pd.DataFrame(company_rows).sort_values(["commodity", "company"]).reset_index(drop=True)
    production_df = pd.DataFrame(production_rows).sort_values(["commodity", "company", "year"]).reset_index(drop=True)

    if not company_df.empty:
        company_df["scale_bucket"] = "未量化"
        company_df["rank_within_basis"] = None
        for (commodity, basis), group in company_df.dropna(subset=["scale_reference_basis", "scale_reference_value"]).groupby(
            ["commodity", "scale_reference_basis"]
        ):
            ranking = group.sort_values("scale_reference_value", ascending=False)
            for rank, row in enumerate(ranking.itertuples(index=False), start=1):
                mask = company_df["record_id"] == row.record_id
                company_df.loc[mask, "rank_within_basis"] = rank
                company_df.loc[mask, "scale_bucket"] = scale_bucket_labels(len(ranking), rank)

    inventory_df = pd.DataFrame(
        [
            {
                "dataset_name": "commodity_supply_plans",
                "dataset_path": str(RAW_SUPPLY_PATH.relative_to(ROOT)),
                "record_count": len(records),
                "deduplicated_record_count": len(company_df),
                "unique_company_count": int(company_df["company"].nunique()) if not company_df.empty else 0,
                "countries_covered": int(company_df["country_primary"].nunique()) if not company_df.empty else 0,
                "commodity_types": int(company_df["commodity"].nunique()) if not company_df.empty else 0,
                "update_frequency": "按公司财报/运营更新节奏手动维护，可按月重跑",
                "source_type": "企业官网/年报/季报/技术报告/项目公告",
                "notes": "当前项目中的国际矿企事实库主文件",
            }
        ]
    )
    return inventory_df, company_df, production_df


def _competition_rows(
    company_df: pd.DataFrame, production_df: pd.DataFrame
) -> tuple[dict[str, list[list[str]]], dict[str, dict[str, float | int | None]]]:
    tables: dict[str, list[list[str]]] = {}
    metrics: dict[str, dict[str, float | int | None]] = {}
    if company_df.empty or production_df.empty:
        return tables, metrics

    production_2026 = production_df[(production_df["year"] == 2026) & (production_df["comparable"] == 1)].copy()
    if production_2026.empty:
        return tables, metrics

    merged = production_2026.merge(
        company_df[
            [
                "record_id",
                "company",
                "country_primary",
                "status_label",
                "operating_stage",
                "scale_bucket",
            ]
        ],
        on=["record_id", "company"],
        how="left",
    )
    for (commodity_label, basis), group in merged.groupby(["commodity_label", "basis"]):
        ordered = group.sort_values("value_mid", ascending=False).reset_index(drop=True)
        key = f"{commodity_label}-{basis}"
        tables[key] = []
        total = float(ordered["value_mid"].sum()) if not ordered.empty else 0.0
        shares = []
        for rank, row in enumerate(ordered.itertuples(index=False), start=1):
            share = (float(row.value_mid) / total * 100) if total else 0.0
            shares.append(share)
            tables[key].append(
                [
                    str(rank),
                    row.company,
                    row.country_primary,
                    f"{float(row.value_mid):.2f}",
                    row.standardized_unit or "",
                    row.status_label,
                    row.operating_stage,
                    row.scale_bucket,
                    f"{share:.2f}%",
                ]
            )
        cr3 = sum(shares[:3]) if shares else None
        hhi = sum((share / 100) ** 2 for share in shares) * 10000 if shares else None
        metrics[key] = {
            "company_count": int(len(ordered)),
            "total_value": round(total, 4) if total else None,
            "cr3": round(cr3, 2) if cr3 is not None else None,
            "hhi": round(hhi, 2) if hhi is not None else None,
        }
    return tables, metrics


def _markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    output = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        output.append("| " + " | ".join(row) + " |")
    return "\n".join(output)


def build_analysis_markdown(
    inventory_df: pd.DataFrame,
    company_df: pd.DataFrame,
    production_df: pd.DataFrame,
) -> tuple[str, str]:
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    coverage_rows: list[list[str]] = []
    if not company_df.empty:
        for commodity, group in company_df.groupby("commodity_label"):
            coverage_rows.append(
                [
                    commodity,
                    str(group["company"].nunique()),
                    str(int((group["status"] == "quantified").sum())),
                    str(int((group["status"] == "partial").sum())),
                    str(int((group["status"] == "undisclosed").sum())),
                    str(int(group["country_primary"].nunique())),
                ]
            )

    operating_rows = [
        [stage, str(count)]
        for stage, count in company_df["operating_stage"].value_counts(dropna=False).items()
    ]
    country_rows = [
        [country, str(count)]
        for country, count in company_df["country_primary"].value_counts(dropna=False).head(12).items()
    ]
    region_rows = [
        [region, str(count)]
        for region, count in Counter(
            region
            for payload in company_df.get("region_list", pd.Series(dtype=str)).tolist()
            for region in json.loads(payload or "[]")
        ).most_common()
    ]
    scale_rows = [
        [bucket, str(count)]
        for bucket, count in company_df["scale_bucket"].value_counts(dropna=False).items()
    ]
    gap_rows = []
    for row in company_df[company_df["status"] != "quantified"].head(12).itertuples(index=False):
        missing_years = []
        for year in (2026, 2027, 2028):
            raw_text = getattr(row, f"production_{year}_raw")
            if is_missing_text(raw_text):
                missing_years.append(str(year))
        gap_rows.append(
            [
                row.company,
                row.commodity_label,
                row.status_label,
                "、".join(missing_years) if missing_years else "无",
                row.operating_stage,
                row.source_title,
            ]
        )

    competition_tables, competition_metrics = _competition_rows(company_df, production_df)

    parts = [
        "# 国际矿企多维分析报告",
        "",
        f"- 生成时间：`{generated_at}`",
        f"- 原始事实库：`{RAW_SUPPLY_PATH.relative_to(ROOT)}`",
        f"- 去重后公司-矿种记录数：`{len(company_df)}`",
        f"- 唯一矿企数：`{company_df['company'].nunique() if not company_df.empty else 0}`",
        "",
        "## 1. 数据归集范围",
        "",
        _markdown_table(
            ["数据集", "路径", "原始记录数", "去重后记录数", "唯一矿企数", "覆盖国家数", "矿种数", "更新方式"],
            [
                [
                    str(item["dataset_name"]),
                    str(item["dataset_path"]),
                    str(item["record_count"]),
                    str(item["deduplicated_record_count"]),
                    str(item["unique_company_count"]),
                    str(item["countries_covered"]),
                    str(item["commodity_types"]),
                    str(item["update_frequency"]),
                ]
                for _, item in inventory_df.iterrows()
            ],
        ),
        "",
        "## 2. 标准化清洗规则",
        "",
        "1. 以 `company + commodity` 为唯一键去重，保留最新 `source_date` 记录。",
        "2. 国家字段统一拆分并标准化为 `country_primary + country_list + region_list`。",
        "3. 产量/产能字段统一拆解为长表，逐年识别 `是否披露/是否可比/单位/标准化数值`。",
        "4. 黄金统一折算为 `吨`，铜统一折算为 `kt`，锂按 `LCE / SC6 / LiOH` 不同基准分别标准化，避免误把不同产品形态直接横比。",
        "5. 经营状况通过 `current_capacity + commissioning + capacity_addition` 关键词归类为 `成熟运营 / 投产爬坡 / 开发建设 / 维护收缩 / 待识别`。",
        "6. 产能规模采用 2026 指引优先、当前产能次之的原则，按矿种与可比基准分组后进行头部/中型/尾部划分。",
        "",
        "## 3. 行业发展趋势",
        "",
        "### 3.1 覆盖与披露完整度",
        "",
        _markdown_table(["矿种", "矿企数", "三年量化", "部分披露", "未完整披露", "覆盖国家数"], coverage_rows or [["暂无数据", "0", "0", "0", "0", "0"]]),
        "",
        "### 3.2 经营阶段分布",
        "",
        _markdown_table(["经营阶段", "记录数"], operating_rows or [["暂无数据", "0"]]),
        "",
        "### 3.3 产能规模分布",
        "",
        _markdown_table(["规模档", "记录数"], scale_rows or [["暂无数据", "0"]]),
        "",
        "## 4. 市场竞争格局",
        "",
    ]

    if not competition_tables:
        parts.extend(["暂无足够的可比 2026 指引数据用于竞争格局测算。", ""])
    else:
        for idx, (key, rows) in enumerate(competition_tables.items(), start=1):
            metric = competition_metrics.get(key, {})
            parts.extend(
                [
                    f"### 4.{idx} {key}",
                    "",
                    f"- 可比样本数：`{metric.get('company_count')}`",
                    f"- CR3：`{metric.get('cr3')}`",
                    f"- HHI：`{metric.get('hhi')}`",
                    "",
                    _markdown_table(
                        ["排名", "公司", "国家", "2026中值", "标准单位", "披露状态", "经营阶段", "规模档", "份额"],
                        rows,
                    ),
                    "",
                ]
            )

    parts.extend(
        [
            "## 5. 资源分布特征",
            "",
            "### 5.1 国家分布",
            "",
            _markdown_table(["国家", "记录数"], country_rows or [["暂无数据", "0"]]),
            "",
            "### 5.2 区域分布",
            "",
            _markdown_table(["区域", "记录数"], region_rows or [["暂无数据", "0"]]),
            "",
            "## 6. 数据缺口与后续更新重点",
            "",
            _markdown_table(["公司", "矿种", "披露状态", "缺失年份", "经营阶段", "来源"], gap_rows or [["暂无数据", "-", "-", "-", "-", "-"]]),
            "",
            "## 7. 结论摘要",
            "",
            "- 当前项目内国际矿企数据已具备按国家、矿种、规模、经营阶段进行统一建模的基础，但不同矿种的可比性仍受披露口径影响。",
            "- 黄金与铜的年度指引可比性相对更强，适合直接做头部竞争格局与集中度分析。",
            "- 锂板块存在 `LCE / SC6 / LiOH` 多基准并行的典型问题，必须分基准比较，不能直接横向混算。",
            "- `部分披露` 仍是当前事实库的主要类型，后续应优先补齐 2027-2028 年 guidance 与项目投放节奏。",
            "",
        ]
    )

    usage = [
        "# 国际矿企数据库使用说明",
        "",
        f"- 生成时间：`{generated_at}`",
        f"- 数据目录：`{OUTPUT_DATA_DIR.relative_to(ROOT)}`",
        "",
        "## 1. 产物清单",
        "",
        "- `raw_data_inventory.csv`：原始数据归集清单",
        "- `raw_supply_records.csv/json`：去重前原始事实库镜像",
        "- `standardized_company_dimensions.csv`：标准化后的公司-矿种维表",
        "- `standardized_production_guidance.csv`：标准化后的逐年产量/产能长表",
        "- `international_mining_analysis_summary.json`：分析摘要 JSON",
        "- `international_mining_companies.db`：SQLite 数据库",
        "- `国际矿企多维分析报告.md`：结构化分析报告",
        "",
        "## 2. 数据库表结构",
        "",
        "- `source_inventory`：记录原始数据集路径、条数、覆盖范围与更新方式",
        "- `raw_supply_records`：原始矿企事实库镜像",
        "- `company_dimensions`：标准化后的公司-矿种主表",
        "- `production_guidance`：按年份展开的产量/产能长表",
        "",
        "## 3. 运行方式",
        "",
        "```bash",
        "cd /Users/user/Documents/personal/rolling-snowball",
        "bash scripts/run_international_mining_pipeline.sh",
        "```",
        "",
        "## 4. 示例查询",
        "",
        "```sql",
        "-- 查询黄金矿企的 2026 年可比产量中值",
        "SELECT company, country_primary, value_mid, standardized_unit",
        "FROM production_guidance pg",
        "JOIN company_dimensions cd ON pg.record_id = cd.record_id",
        "WHERE cd.commodity = 'gold' AND pg.year = 2026 AND pg.comparable = 1",
        "ORDER BY value_mid DESC;",
        "",
        "-- 查询处于投产爬坡阶段的锂矿企",
        "SELECT company, country_primary, operating_stage, production_2026_raw, current_capacity",
        "FROM company_dimensions",
        "WHERE commodity = 'lithium' AND operating_stage = '投产爬坡';",
        "```",
        "",
        "## 5. 更新建议",
        "",
        "1. 先维护 `data/cache/commodity_supply_plans.json` 中的新增/修订记录。",
        "2. 重跑管道脚本，自动刷新 CSV / JSON / SQLite / Markdown 产物。",
        "3. 若新增矿种，补充 `COMMODITY_LABELS` 与对应单位转换规则。",
        "4. 若披露口径变化，优先扩展 `parse_production_text()` 里的单位识别逻辑。",
        "",
    ]

    return "\n".join(parts), "\n".join(usage)


def write_sqlite_database(
    db_path: Path,
    inventory_df: pd.DataFrame,
    raw_records: list[dict[str, Any]],
    company_df: pd.DataFrame,
    production_df: pd.DataFrame,
) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        inventory_df.to_sql("source_inventory", conn, if_exists="replace", index=False)
        pd.DataFrame(raw_records).to_sql("raw_supply_records", conn, if_exists="replace", index=False)
        company_df.to_sql("company_dimensions", conn, if_exists="replace", index=False)
        production_df.to_sql("production_guidance", conn, if_exists="replace", index=False)
    finally:
        conn.close()


def run_pipeline() -> dict[str, Any]:
    OUTPUT_DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_REPORT_DIR.mkdir(parents=True, exist_ok=True)

    raw_records = load_json_records(RAW_SUPPLY_PATH)
    inventory_df, company_df, production_df = standardize_mining_records(raw_records)
    analysis_markdown, usage_markdown = build_analysis_markdown(inventory_df, company_df, production_df)

    raw_json_path = OUTPUT_DATA_DIR / "raw_supply_records.json"
    raw_csv_path = OUTPUT_DATA_DIR / "raw_supply_records.csv"
    inventory_csv_path = OUTPUT_DATA_DIR / "raw_data_inventory.csv"
    company_csv_path = OUTPUT_DATA_DIR / "standardized_company_dimensions.csv"
    production_csv_path = OUTPUT_DATA_DIR / "standardized_production_guidance.csv"
    summary_json_path = OUTPUT_DATA_DIR / "international_mining_analysis_summary.json"
    db_path = OUTPUT_DATA_DIR / "international_mining_companies.db"
    report_path = OUTPUT_REPORT_DIR / "国际矿企多维分析报告.md"
    usage_path = OUTPUT_REPORT_DIR / "国际矿企数据库使用说明.md"

    raw_json_path.write_text(json.dumps(raw_records, ensure_ascii=False, indent=2), encoding="utf-8")
    pd.DataFrame(raw_records).to_csv(raw_csv_path, index=False, encoding="utf-8-sig")
    inventory_df.to_csv(inventory_csv_path, index=False, encoding="utf-8-sig")
    company_df.to_csv(company_csv_path, index=False, encoding="utf-8-sig")
    production_df.to_csv(production_csv_path, index=False, encoding="utf-8-sig")
    report_path.write_text(analysis_markdown, encoding="utf-8")
    usage_path.write_text(usage_markdown, encoding="utf-8")

    competition_tables, competition_metrics = _competition_rows(company_df, production_df)
    summary_payload = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "raw_record_count": len(raw_records),
        "deduplicated_record_count": int(len(company_df)),
        "unique_company_count": int(company_df["company"].nunique()) if not company_df.empty else 0,
        "countries_covered": int(company_df["country_primary"].nunique()) if not company_df.empty else 0,
        "commodity_types": int(company_df["commodity"].nunique()) if not company_df.empty else 0,
        "status_distribution": company_df["status_label"].value_counts().to_dict() if not company_df.empty else {},
        "operating_stage_distribution": company_df["operating_stage"].value_counts().to_dict() if not company_df.empty else {},
        "competition_metrics": competition_metrics,
        "competition_table_keys": list(competition_tables.keys()),
        "output_files": {
            "inventory_csv": str(inventory_csv_path.relative_to(ROOT)),
            "company_csv": str(company_csv_path.relative_to(ROOT)),
            "production_csv": str(production_csv_path.relative_to(ROOT)),
            "database": str(db_path.relative_to(ROOT)),
            "report_md": str(report_path.relative_to(ROOT)),
            "usage_md": str(usage_path.relative_to(ROOT)),
        },
    }
    summary_json_path.write_text(json.dumps(summary_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_sqlite_database(db_path, inventory_df, raw_records, company_df, production_df)
    return summary_payload


def main() -> None:
    parser = argparse.ArgumentParser(description="国际矿企数据库标准化与分析管道")
    parser.parse_args()
    summary = run_pipeline()
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
