from __future__ import annotations

import math
import re
from typing import Any

import pandas as pd


SEGMENT_META = {
    "gold": {"label": "黄金", "color": "#f59e0b"},
    "copper": {"label": "铜", "color": "#b45309"},
    "lithium": {"label": "碳酸锂", "color": "#8b5cf6"},
    "other": {"label": "其他业务", "color": "#94a3b8"},
    "total": {"label": "总营收", "color": "#2563eb"},
}

SUPPLY_COMMODITY_LABELS = {
    "gold": "黄金",
    "copper": "铜",
    "lithium": "锂",
}

SUPPLY_STATUS_LABELS = {
    "quantified": "三年量化",
    "partial": "部分披露",
    "undisclosed": "未完整披露",
}


def as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def format_period_label(period: str) -> str:
    if len(period) != 8 or not period.isdigit():
        return period
    if period.endswith("1231"):
        return period[:4] + "A"
    if period.endswith("0630"):
        return period[:4] + "H1"
    if period.endswith("0331"):
        return period[:4] + "Q1"
    if period.endswith("0930"):
        return period[:4] + "Q3"
    return period[:4] + "-" + period[4:6]


def period_to_quarter_label(period: str) -> str | None:
    if len(period) != 8 or not period.isdigit():
        return None
    suffix_map = {"0331": "Q1", "0630": "Q2", "0930": "Q3", "1231": "Q4"}
    suffix = suffix_map.get(period[4:])
    if suffix is None:
        return None
    return f"{period[:4]}{suffix}"


def shift_quarter_label(label: str, offset: int) -> str:
    year = int(label[:4])
    quarter = int(label[-1])
    serial = year * 4 + (quarter - 1) + offset
    next_year, next_quarter_idx = divmod(serial, 4)
    return f"{next_year}Q{next_quarter_idx + 1}"


def quarterly_average_price_map(df: pd.DataFrame) -> dict[str, float]:
    if df.empty or "trade_date" not in df.columns or "close" not in df.columns:
        return {}
    sample = df.copy()
    sample["trade_date"] = pd.to_datetime(sample["trade_date"], errors="coerce")
    sample["close"] = pd.to_numeric(sample["close"], errors="coerce")
    sample = sample.dropna(subset=["trade_date", "close"])
    if sample.empty:
        return {}
    grouped = (
        sample.assign(
            quarter=sample["trade_date"].dt.year.astype(str)
            + "Q"
            + sample["trade_date"].dt.quarter.astype(str)
        )
        .groupby("quarter", as_index=False)
        .agg(close=("close", "mean"))
    )
    return {str(row["quarter"]): float(row["close"]) for _, row in grouped.iterrows()}


def quarterly_income_map(income_df: pd.DataFrame) -> dict[str, float]:
    if income_df.empty or "end_date" not in income_df.columns or "revenue" not in income_df.columns:
        return {}
    sample = income_df.copy()
    sample["end_date"] = sample["end_date"].astype(str)
    sample["revenue"] = pd.to_numeric(sample["revenue"], errors="coerce")
    sample = sample.dropna(subset=["revenue"]).sort_values("end_date").drop_duplicates("end_date", keep="last")
    result: dict[str, float] = {}
    for year, sub in sample.groupby(sample["end_date"].str[:4]):
        year_rows = {period_to_quarter_label(item["end_date"]): float(item["revenue"]) for _, item in sub.iterrows()}
        if f"{year}Q1" in year_rows:
            result[f"{year}Q1"] = year_rows[f"{year}Q1"]
        if f"{year}Q2" in year_rows and f"{year}Q1" in year_rows:
            result[f"{year}Q2"] = year_rows[f"{year}Q2"] - year_rows[f"{year}Q1"]
        if f"{year}Q3" in year_rows and f"{year}Q2" in year_rows:
            result[f"{year}Q3"] = year_rows[f"{year}Q3"] - year_rows[f"{year}Q2"]
        if f"{year}Q4" in year_rows and f"{year}Q3" in year_rows:
            result[f"{year}Q4"] = year_rows[f"{year}Q4"] - year_rows[f"{year}Q3"]
    return result


def parse_quantity_text(text: str) -> float | None:
    if not text:
        return None
    match = re.search(r"(\d+(?:\.\d+)?)", str(text))
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def annual_average_price(df: pd.DataFrame, year: int) -> float | None:
    if df.empty or "trade_date" not in df.columns or "close" not in df.columns:
        return None
    sample = df.copy()
    sample["trade_date"] = pd.to_datetime(sample["trade_date"], errors="coerce")
    sample["close"] = pd.to_numeric(sample["close"], errors="coerce")
    sample = sample.dropna(subset=["trade_date", "close"])
    sample = sample[sample["trade_date"].dt.year == year]
    if sample.empty:
        return None
    return float(sample["close"].mean())


def monthly_average_frame(df: pd.DataFrame, months: int = 12) -> pd.DataFrame:
    if df.empty or "trade_date" not in df.columns or "close" not in df.columns:
        return pd.DataFrame(columns=["month", "month_end", "close", "mom_pct"])
    sample = df.copy()
    sample["trade_date"] = pd.to_datetime(sample["trade_date"], errors="coerce")
    sample["close"] = pd.to_numeric(sample["close"], errors="coerce")
    sample = sample.dropna(subset=["trade_date", "close"]).sort_values("trade_date")
    if sample.empty:
        return pd.DataFrame(columns=["month", "month_end", "close", "mom_pct"])
    monthly = (
        sample.assign(month=sample["trade_date"].dt.to_period("M").astype(str))
        .groupby("month", as_index=False)
        .agg(month_end=("trade_date", "max"), close=("close", "mean"))
    )
    monthly = monthly.tail(months).reset_index(drop=True)
    monthly["mom_pct"] = monthly["close"].pct_change() * 100
    return monthly


def turning_point_rows(monthly: pd.DataFrame, label: str) -> list[list[str]]:
    if len(monthly) < 3:
        return []
    rows: list[dict[str, Any]] = []
    closes = monthly["close"].tolist()
    months = monthly["month"].tolist()
    for idx in range(1, len(closes) - 1):
        prev_delta = closes[idx] - closes[idx - 1]
        next_delta = closes[idx + 1] - closes[idx]
        tone = ""
        if prev_delta > 0 and next_delta < 0:
            tone = "阶段高点"
        elif prev_delta < 0 and next_delta > 0:
            tone = "阶段低点"
        if not tone:
            continue
        rows.append(
            {
                "month": months[idx],
                "label": label,
                "price": closes[idx],
                "tone": tone,
                "swing": abs(as_float(monthly.iloc[idx]["mom_pct"]) or 0.0),
            }
        )
    if not rows:
        return []
    rows = sorted(rows, key=lambda item: item["swing"], reverse=True)[:3]
    return [
        [
            item["label"],
            item["month"],
            item["tone"],
            f"{item['price']:.2f}",
            f"{item['swing']:.2f}%",
        ]
        for item in rows
    ]


def turning_point_markers(monthly: pd.DataFrame, series_key: str) -> list[dict[str, Any]]:
    if len(monthly) < 3:
        return []
    markers: list[dict[str, Any]] = []
    closes = monthly["close"].tolist()
    months = monthly["month"].tolist()
    base = closes[0] if closes and closes[0] else None
    if base in (None, 0):
        return []
    for idx in range(1, len(closes) - 1):
        prev_delta = closes[idx] - closes[idx - 1]
        next_delta = closes[idx + 1] - closes[idx]
        label = ""
        if prev_delta > 0 and next_delta < 0:
            label = "高点"
        elif prev_delta < 0 and next_delta > 0:
            label = "低点"
        if not label:
            continue
        markers.append(
            {
                "x_label": months[idx],
                "series_key": series_key,
                "value": closes[idx] / base * 100,
                "label": label,
            }
        )
    return markers[:4]


def build_price_analysis(price_frames: dict[str, pd.DataFrame], events: list[dict[str, str]]) -> dict[str, Any]:
    labels: list[str] = []
    normalized_series: list[dict[str, Any]] = []
    point_markers: list[dict[str, Any]] = []
    overview_rows: list[list[str]] = []
    turning_rows: list[list[str]] = []
    monthly_tables: dict[str, list[list[str]]] = {}

    for key, meta in (("gold", SEGMENT_META["gold"]), ("copper", SEGMENT_META["copper"]), ("lithium", SEGMENT_META["lithium"])):
        frame = price_frames.get(key, pd.DataFrame())
        monthly = monthly_average_frame(frame, months=12)
        if monthly.empty:
            continue
        if not labels:
            labels = monthly["month"].tolist()
        base = as_float(monthly.iloc[0]["close"])
        if base not in (None, 0):
            normalized_series.append(
                {
                    "label": meta["label"],
                    "key": meta["label"],
                    "color": meta["color"],
                    "values": [round(float(value) / base * 100, 2) for value in monthly["close"].tolist()],
                }
            )
            point_markers.extend(turning_point_markers(monthly, meta["label"]))

        latest_daily = None
        if not frame.empty:
            latest_sample = frame.copy()
            latest_sample["trade_date"] = latest_sample["trade_date"].astype(str)
            latest_sample["close"] = pd.to_numeric(latest_sample["close"], errors="coerce")
            latest_sample = latest_sample.dropna(subset=["close"]).sort_values("trade_date")
            if not latest_sample.empty:
                latest_daily = latest_sample.iloc[-1]

        annual_change = None
        if len(monthly) >= 2:
            start_value = as_float(monthly.iloc[0]["close"])
            end_value = as_float(monthly.iloc[-1]["close"])
            if start_value not in (None, 0) and end_value is not None:
                annual_change = (end_value / start_value - 1.0) * 100

        monthly_tables[meta["label"]] = [
            [
                row["month"],
                f"{row['close']:.2f}",
                "N/A" if pd.isna(row["mom_pct"]) else f"{row['mom_pct']:+.2f}%",
            ]
            for _, row in monthly.iterrows()
        ]
        turning_rows.extend(turning_point_rows(monthly, meta["label"]))
        overview_rows.append(
            [
                meta["label"],
                str(latest_daily["trade_date"]) if latest_daily is not None else monthly.iloc[-1]["month"],
                f"{as_float(latest_daily['close']) or monthly.iloc[-1]['close']:.2f}",
                f"{monthly.iloc[-1]['close']:.2f}",
                "N/A" if annual_change is None else f"{annual_change:+.2f}%",
            ]
        )

    event_markers = [{"x_label": item.get("month", ""), "label": item.get("title", "")} for item in events]
    event_rows = [[item.get("month", ""), item.get("title", ""), item.get("detail", "")] for item in events]
    return {
        "labels": labels,
        "normalized_series": normalized_series,
        "point_markers": point_markers,
        "event_markers": event_markers,
        "overview_rows": overview_rows,
        "turning_rows": turning_rows,
        "monthly_tables": monthly_tables,
        "event_rows": event_rows,
        "note": "黄金/铜采用上期所连续主力日线聚合月均；碳酸锂采用广期所 LC.GFE 主力映射连续序列聚合月均。",
    }


def _supply_sort_key(item: dict[str, Any]) -> tuple[int, str]:
    commodity_rank = {"gold": 0, "copper": 1, "lithium": 2}
    return commodity_rank.get(str(item.get("commodity", "")), 99), str(item.get("company", ""))


def _missing_supply_fields(item: dict[str, Any]) -> str:
    missing: list[str] = []
    for year in ("production_2026", "production_2027", "production_2028"):
        value = str(item.get(year, "")).strip()
        if not value or value in {"未单列披露", "未披露", "N/A"}:
            missing.append(year.replace("production_", ""))
    return "、".join(missing) if missing else "无"


def build_supply_plan_analysis(records: list[dict[str, Any]], target_company_count: int = 50) -> dict[str, Any]:
    if not records:
        return {
            "supply_company_coverage": f"0/{target_company_count}",
            "supply_quantified_company_count": 0,
            "supply_partial_company_count": 0,
            "supply_source_count": 0,
            "supply_summary_rows": [],
            "supply_plan_rows": [],
            "supply_source_rows": [],
            "supply_gap_rows": [],
            "supply_note": "尚未录入全球矿企未来三年产量/产能规划事实库。",
        }

    normalized: list[dict[str, Any]] = []
    for raw in records:
        company = str(raw.get("company", "")).strip()
        commodity = str(raw.get("commodity", "")).strip().lower()
        if not company or commodity not in SUPPLY_COMMODITY_LABELS:
            continue
        item = {
            "company": company,
            "commodity": commodity,
            "company_type": str(raw.get("company_type", "")).strip(),
            "country": str(raw.get("country", "")).strip(),
            "status": str(raw.get("status", "partial")).strip().lower() or "partial",
            "production_2026": str(raw.get("production_2026", "")).strip() or "未单列披露",
            "production_2027": str(raw.get("production_2027", "")).strip() or "未单列披露",
            "production_2028": str(raw.get("production_2028", "")).strip() or "未单列披露",
            "current_capacity": str(raw.get("current_capacity", "")).strip() or "未披露",
            "commissioning": str(raw.get("commissioning", "")).strip() or "未披露",
            "capacity_addition": str(raw.get("capacity_addition", "")).strip() or "未披露",
            "source_date": str(raw.get("source_date", "")).strip() or "未披露",
            "source_title": str(raw.get("source_title", "")).strip() or "官方披露",
            "source_url": str(raw.get("source_url", "")).strip(),
            "assumptions": str(raw.get("assumptions", "")).strip() or "以公司公告/年报披露条件为准",
        }
        normalized.append(item)

    if not normalized:
        return {
            "supply_company_coverage": f"0/{target_company_count}",
            "supply_quantified_company_count": 0,
            "supply_partial_company_count": 0,
            "supply_source_count": 0,
            "supply_summary_rows": [],
            "supply_plan_rows": [],
            "supply_source_rows": [],
            "supply_gap_rows": [],
            "supply_note": "事实库文件存在，但未识别到有效矿企规划记录。",
        }

    normalized = sorted(normalized, key=_supply_sort_key)
    covered_companies = sorted({item["company"] for item in normalized})
    quantified_companies = sorted({item["company"] for item in normalized if item["status"] == "quantified"})
    partial_companies = sorted({item["company"] for item in normalized if item["status"] != "quantified"})

    commodity_summary_rows: list[list[str]] = []
    for commodity in ("gold", "copper", "lithium"):
        rows = [item for item in normalized if item["commodity"] == commodity]
        if not rows:
            continue
        company_set = {item["company"] for item in rows}
        quantified_set = {item["company"] for item in rows if item["status"] == "quantified"}
        partial_set = {item["company"] for item in rows if item["status"] != "quantified"}
        commodity_summary_rows.append(
            [
                SUPPLY_COMMODITY_LABELS[commodity],
                str(len(company_set)),
                str(len(quantified_set)),
                str(len(partial_set)),
                "官方年报/季报/技术研究/项目公告",
            ]
        )

    supply_plan_rows = [
        [
            SUPPLY_COMMODITY_LABELS[item["commodity"]],
            item["company"],
            item["production_2026"],
            item["production_2027"],
            item["production_2028"],
            item["current_capacity"],
            item["capacity_addition"],
            SUPPLY_STATUS_LABELS.get(item["status"], item["status"]),
        ]
        for item in normalized
    ]

    seen_sources: set[tuple[str, str, str, str]] = set()
    supply_source_rows: list[list[str]] = []
    for item in normalized:
        source_key = (item["company"], item["commodity"], item["source_date"], item["source_url"])
        if source_key in seen_sources:
            continue
        seen_sources.add(source_key)
        supply_source_rows.append(
            [
                item["company"],
                SUPPLY_COMMODITY_LABELS[item["commodity"]],
                item["source_date"],
                item["source_title"],
                item["source_url"] or "N/A",
                item["assumptions"],
            ]
        )

    supply_gap_rows = [
        [
            SUPPLY_COMMODITY_LABELS[item["commodity"]],
            item["company"],
            SUPPLY_STATUS_LABELS.get(item["status"], item["status"]),
            _missing_supply_fields(item),
            item["commissioning"],
        ]
        for item in normalized
        if item["status"] != "quantified"
    ]

    return {
        "supply_company_coverage": f"{len(covered_companies)}/{target_company_count}",
        "supply_quantified_company_count": len(quantified_companies),
        "supply_partial_company_count": len(partial_companies),
        "supply_source_count": len(supply_source_rows),
        "supply_summary_rows": commodity_summary_rows,
        "supply_plan_rows": supply_plan_rows,
        "supply_source_rows": supply_source_rows,
        "supply_gap_rows": supply_gap_rows,
        "supply_note": (
            "仅纳入企业官网、年报、业绩发布、监管披露和官方项目公告中的金/铜/锂三年规划口径。"
            "已显式区分“三年量化”“部分披露”“未完整披露”，避免把项目级描述误写为年度产量指引。"
        ),
    }


def _segment_sales(sub: pd.DataFrame, segment: str) -> float | None:
    if sub.empty:
        return None
    sub = sub.copy()
    sub["bz_item"] = sub["bz_item"].astype(str)
    sub["bz_sales"] = pd.to_numeric(sub["bz_sales"], errors="coerce")

    if segment == "gold":
        mined_gold = sub.loc[sub["bz_item"] == "矿山产金", "bz_sales"].sum()
        if mined_gold == 0:
            mined_gold = sub.loc[sub["bz_item"].isin(["金锭", "金精矿"]), "bz_sales"].sum()
        return mined_gold if mined_gold > 0 else None

    if segment == "copper":
        copper_concentrate = sub.loc[sub["bz_item"] == "铜精矿", "bz_sales"].sum()
        mined_copper = sub.loc[sub["bz_item"] == "矿山产铜", "bz_sales"].sum()
        if mined_copper == 0:
            mined_copper = sub.loc[sub["bz_item"] == "电解铜与电积铜", "bz_sales"].sum()
        if mined_copper == 0:
            mined_copper = sub.loc[sub["bz_item"].isin(["矿山产电解铜", "矿山产电积铜"]), "bz_sales"].sum()
        total = copper_concentrate + mined_copper
        return total if total > 0 else None

    return None


def build_revenue_analysis(
    mainbiz_df: pd.DataFrame,
    income_df: pd.DataFrame,
    lithium_price_df: pd.DataFrame,
    production_targets: list[dict[str, str]],
) -> dict[str, Any]:
    if mainbiz_df.empty or income_df.empty:
        return {
            "current_rows": [],
            "current_slices": [],
            "trend_labels": [],
            "trend_series": [],
            "period_labels": [],
            "period_series": [],
            "growth_rows": [],
            "note": "主营构成或利润表缺失，无法生成营收结构分析。",
        }

    mainbiz = mainbiz_df.copy()
    mainbiz["end_date"] = mainbiz["end_date"].astype(str)
    mainbiz["bz_sales"] = pd.to_numeric(mainbiz["bz_sales"], errors="coerce")
    income = income_df.copy()
    income["end_date"] = income["end_date"].astype(str)
    income["revenue"] = pd.to_numeric(income["revenue"], errors="coerce")
    income = income.dropna(subset=["revenue"]).sort_values("end_date").drop_duplicates("end_date", keep="last")

    annual_periods = sorted(item for item in mainbiz["end_date"].unique() if item.endswith("1231"))[-5:]
    latest_annual = annual_periods[-1]

    lithium_output_map = {int(item[:4]): 0.0 for item in annual_periods}
    for item in production_targets:
        if str(item.get("product")) == "碳酸锂":
            base_value = parse_quantity_text(str(item.get("actual_2025", "")))
            if base_value is not None:
                lithium_output_map[2025] = base_value

    annual_rows: list[dict[str, Any]] = []
    for period in annual_periods:
        year = int(period[:4])
        income_row = income[income["end_date"] == period]
        total_revenue = as_float(income_row.iloc[-1]["revenue"]) if not income_row.empty else None
        sub = mainbiz[mainbiz["end_date"] == period]
        gold_revenue = _segment_sales(sub, "gold")
        copper_revenue = _segment_sales(sub, "copper")
        lithium_revenue = None
        lithium_output = lithium_output_map.get(year, 0.0)
        lithium_avg_price = annual_average_price(lithium_price_df, year)
        if lithium_output and lithium_avg_price is not None:
            lithium_revenue = lithium_output * 10000 * lithium_avg_price / 1e8
        annual_rows.append(
            {
                "period": period,
                "year": year,
                "total_revenue": total_revenue,
                "gold": gold_revenue / 1e8 if gold_revenue is not None else None,
                "copper": copper_revenue / 1e8 if copper_revenue is not None else None,
                "lithium": lithium_revenue,
            }
        )

    latest_row = next((item for item in annual_rows if item["period"] == latest_annual), None)
    previous_row = annual_rows[-2] if len(annual_rows) >= 2 else None
    current_slices: list[dict[str, Any]] = []
    current_rows: list[list[str]] = []
    growth_rows: list[list[str]] = []
    if latest_row and latest_row["total_revenue"]:
        known_sum = 0.0
        for segment in ("gold", "copper", "lithium"):
            value = as_float(latest_row.get(segment))
            if value is None:
                continue
            known_sum += value
        other_value = max((latest_row["total_revenue"] / 1e8) - known_sum, 0.0)

        slice_values = {
            "gold": as_float(latest_row.get("gold")) or 0.0,
            "copper": as_float(latest_row.get("copper")) or 0.0,
            "lithium": as_float(latest_row.get("lithium")) or 0.0,
            "other": other_value,
        }
        for segment in ("gold", "copper", "lithium", "other"):
            value = slice_values[segment]
            share = value / (latest_row["total_revenue"] / 1e8) * 100 if latest_row["total_revenue"] else 0.0
            current_slices.append(
                {
                    "label": SEGMENT_META[segment]["label"],
                    "value": value,
                    "share": share,
                    "color": SEGMENT_META[segment]["color"],
                }
            )

        for segment in ("gold", "copper", "lithium"):
            current_value = slice_values[segment]
            prev_value = as_float(previous_row.get(segment)) if previous_row else None
            yoy = None
            if prev_value not in (None, 0):
                yoy = (current_value / prev_value - 1.0) * 100
            qoq_note = "同比按2024A对比；2025H1仅披露粗分类，环比不可比" if latest_annual == "20251231" else "按同口径可比"
            basis = "年报矿山产品口径" if segment in {"gold", "copper"} else "披露产量×广期所年均价估算"
            current_rows.append(
                [
                    SEGMENT_META[segment]["label"],
                    f"{current_value:.2f}",
                    f"{slice_values[segment] / (latest_row['total_revenue'] / 1e8) * 100:.2f}%",
                    "N/A" if yoy is None else f"{yoy:+.2f}%",
                    qoq_note,
                    basis,
                ]
            )
            growth_rows.append(
                [
                    SEGMENT_META[segment]["label"],
                    f"{current_value:.2f}",
                    "N/A" if yoy is None else f"{yoy:+.2f}%",
                    qoq_note,
                ]
            )

    trend_labels = [str(item["year"]) for item in annual_rows]
    trend_series = []
    for segment in ("gold", "copper", "lithium", "other"):
        values: list[float | None] = []
        for item in annual_rows:
            total = as_float(item.get("total_revenue"))
            if total in (None, 0):
                values.append(None)
                continue
            if segment == "other":
                known = sum(as_float(item.get(key)) or 0.0 for key in ("gold", "copper", "lithium"))
                value = max(total / 1e8 - known, 0.0)
            else:
                value = as_float(item.get(segment))
            values.append(None if value is None else value / (total / 1e8) * 100)
        trend_series.append(
            {
                "label": SEGMENT_META[segment]["label"],
                "key": SEGMENT_META[segment]["label"],
                "color": SEGMENT_META[segment]["color"],
                "values": values,
            }
        )

    period_labels: list[str] = []
    period_series = []
    latest_periods = sorted(mainbiz["end_date"].unique())[-8:]
    period_values: dict[str, list[float | None]] = {"gold": [], "copper": [], "lithium": []}
    for period in latest_periods:
        period_labels.append(format_period_label(period))
        sub = mainbiz[mainbiz["end_date"] == period]
        gold_value = _segment_sales(sub, "gold")
        copper_value = _segment_sales(sub, "copper")
        lithium_value = None
        if period == latest_annual and latest_row is not None:
            lithium_value = as_float(latest_row.get("lithium"))
        period_values["gold"].append(None if gold_value is None else gold_value / 1e8)
        period_values["copper"].append(None if copper_value is None else copper_value / 1e8)
        period_values["lithium"].append(lithium_value)

    for segment in ("gold", "copper", "lithium"):
        period_series.append(
            {
                "label": SEGMENT_META[segment]["label"],
                "key": SEGMENT_META[segment]["label"],
                "color": SEGMENT_META[segment]["color"],
                "values": period_values[segment],
            }
        )

    return {
        "current_rows": current_rows,
        "current_slices": current_slices,
        "trend_labels": trend_labels,
        "trend_series": trend_series,
        "period_labels": period_labels,
        "period_series": period_series,
        "growth_rows": growth_rows,
        "annual_rows": annual_rows,
        "note": "黄金、铜按年报主营构成中的矿山产品口径拆分，不纳入冶炼加工金/冶炼产铜收入；2024H1/2025H1仅披露“矿产品/冶炼产品”等粗分类，8期柱状图对不可比期间保留空档；碳酸锂收入按已披露产量与广期所年均价估算。",
    }


def build_forecast_analysis(
    revenue_analysis: dict[str, Any],
    price_frames: dict[str, pd.DataFrame],
    production_targets: list[dict[str, str]],
    income_df: pd.DataFrame | None = None,
) -> dict[str, Any]:
    annual_rows = revenue_analysis.get("annual_rows") or []
    latest_row = annual_rows[-1] if annual_rows else None
    if not latest_row or not latest_row.get("total_revenue"):
        return {
            "labels": [],
            "series": [],
            "range_rows": [],
            "assumption_rows": [],
            "timeline_labels": [],
            "timeline_series": [],
            "timeline_event_markers": [],
            "note": "缺少营收基础数据，无法构建预测模型。",
        }

    actual_map: dict[str, float] = {}
    target_map: dict[str, float] = {}
    product_map = {"矿产金": "gold", "矿产铜": "copper", "碳酸锂": "lithium"}
    for item in production_targets:
        segment = product_map.get(str(item.get("product")))
        if not segment:
            continue
        actual_value = parse_quantity_text(str(item.get("actual_2025", "")))
        target_value = parse_quantity_text(str(item.get("target_2026", "")))
        if actual_value is not None:
            actual_map[segment] = actual_value
        if target_value is not None:
            target_map[segment] = target_value

    labels = ["2026Q3", "2026Q4"]
    pressure_band = {"gold": 0.06, "copper": 0.08, "lithium": 0.15, "other": 0.03}
    series_values = {key: [] for key in ("gold", "copper", "lithium", "total")}
    range_rows: list[list[str]] = []
    assumption_rows: list[list[str]] = []

    annual_total = latest_row["total_revenue"] / 1e8
    annual_gold = as_float(latest_row.get("gold")) or 0.0
    annual_copper = as_float(latest_row.get("copper")) or 0.0
    annual_lithium = as_float(latest_row.get("lithium")) or 0.0
    annual_other = max(annual_total - annual_gold - annual_copper - annual_lithium, 0.0)

    annual_segment_map = {
        "gold": annual_gold,
        "copper": annual_copper,
        "lithium": annual_lithium,
        "other": annual_other,
    }

    ratio_cache: dict[str, float] = {}
    for segment in ("gold", "copper", "lithium"):
        frame = price_frames.get(segment, pd.DataFrame())
        if frame.empty:
            ratio_cache[segment] = 1.0
            continue
        latest_close = as_float(frame.sort_values("trade_date").iloc[-1]["close"])
        monthly = monthly_average_frame(frame, months=12)
        trailing_avg = as_float(monthly["close"].mean()) if not monthly.empty else None
        if latest_close is None or trailing_avg in (None, 0):
            ratio_cache[segment] = 1.0
        else:
            ratio_cache[segment] = latest_close / trailing_avg

    quarter_factors = {
        "2026Q3": {},
        "2026Q4": {},
    }
    for segment in ("gold", "copper", "lithium"):
        actual_value = actual_map.get(segment)
        target_value = target_map.get(segment)
        if actual_value in (None, 0) or target_value is None:
            quarter_factors["2026Q3"][segment] = 1.0
            quarter_factors["2026Q4"][segment] = 1.0
            continue
        target_ratio = target_value / actual_value
        quarter_factors["2026Q3"][segment] = (1.0 + target_ratio) / 2.0
        quarter_factors["2026Q4"][segment] = target_ratio

    assumption_rows = [
        [
            SEGMENT_META[segment]["label"],
            f"{ratio_cache.get(segment, 1.0):.2f}x",
            f"{quarter_factors['2026Q3'].get(segment, 1.0):.2f}x",
            f"{quarter_factors['2026Q4'].get(segment, 1.0):.2f}x",
            f"±{int(pressure_band.get(segment, 0.0) * 100)}%",
        ]
        for segment in ("gold", "copper", "lithium")
    ]

    for quarter in labels:
        quarter_total = 0.0
        quarter_low = 0.0
        quarter_high = 0.0
        for segment in ("gold", "copper", "lithium"):
            base_value = annual_segment_map[segment] / 4.0
            forecast_value = base_value * ratio_cache.get(segment, 1.0) * quarter_factors[quarter].get(segment, 1.0)
            series_values[segment].append(round(forecast_value, 2))
            band = pressure_band.get(segment, 0.0)
            quarter_total += forecast_value
            quarter_low += forecast_value * (1.0 - band)
            quarter_high += forecast_value * (1.0 + band)
        other_value = annual_segment_map["other"] / 4.0
        quarter_total += other_value
        quarter_low += other_value * (1.0 - pressure_band["other"])
        quarter_high += other_value * (1.0 + pressure_band["other"])
        series_values["total"].append(round(quarter_total, 2))
        range_rows.append([quarter, f"{quarter_low:.2f}", f"{quarter_total:.2f}", f"{quarter_high:.2f}"])

    latest_actual_quarter = None
    income_quarters = quarterly_income_map(income_df if income_df is not None else pd.DataFrame())
    if income_quarters:
        latest_actual_quarter = sorted(income_quarters)[-1]
    else:
        latest_actual_quarter = f"{latest_row['year']}Q4"

    actual_labels = [shift_quarter_label(latest_actual_quarter, offset) for offset in range(-3, 1)]
    future_labels = [shift_quarter_label(latest_actual_quarter, offset) for offset in range(1, 5)]
    timeline_labels = actual_labels + future_labels

    quarter_price_maps = {
        segment: quarterly_average_price_map(price_frames.get(segment, pd.DataFrame()))
        for segment in ("gold", "copper", "lithium")
    }
    annual_quarters = [f"{latest_row['year']}Q1", f"{latest_row['year']}Q2", f"{latest_row['year']}Q3", f"{latest_row['year']}Q4"]

    history_weights: dict[str, dict[str, float]] = {}
    for segment in ("gold", "copper", "lithium"):
        price_map = quarter_price_maps[segment]
        scores = {
            quarter: price_map.get(quarter, sum(price_map.values()) / len(price_map) if price_map else 1.0)
            for quarter in annual_quarters
        }
        total_score = sum(scores.values()) or 1.0
        history_weights[segment] = {quarter: score / total_score for quarter, score in scores.items()}

    target_ratio_map = {}
    for segment in ("gold", "copper", "lithium"):
        actual_value = actual_map.get(segment)
        target_value = target_map.get(segment)
        if actual_value in (None, 0) or target_value is None:
            target_ratio_map[segment] = 1.0
        else:
            target_ratio_map[segment] = target_value / actual_value

    future_factor_steps = {
        future_labels[0]: 0.40,
        future_labels[1]: 0.60,
        future_labels[2]: 0.80,
        future_labels[3]: 1.00,
    }

    timeline_segment_values: dict[str, list[float | None]] = {key: [] for key in ("gold", "copper", "lithium")}
    for quarter in timeline_labels:
        for segment in ("gold", "copper", "lithium"):
            annual_value = annual_segment_map[segment]
            if annual_value in (None, 0):
                timeline_segment_values[segment].append(None)
                continue

            if quarter.startswith(str(latest_row["year"])):
                value = annual_value * history_weights[segment].get(quarter, 0.25)
            else:
                price_map = quarter_price_maps[segment]
                quarter_avg = price_map.get(quarter)
                trailing_avg = sum(price_map.values()) / len(price_map) if price_map else None
                price_ratio = 1.0 if quarter_avg is None or trailing_avg in (None, 0) else quarter_avg / trailing_avg
                ramp = future_factor_steps.get(quarter, 1.0)
                growth_ratio = 1.0 + (target_ratio_map.get(segment, 1.0) - 1.0) * ramp
                value = annual_value / 4.0 * price_ratio * growth_ratio
            timeline_segment_values[segment].append(round(value, 2))

    timeline_series = [
        {
            "label": SEGMENT_META[segment]["label"],
            "key": SEGMENT_META[segment]["label"],
            "color": SEGMENT_META[segment]["color"],
            "values": timeline_segment_values[segment],
        }
        for segment in ("gold", "copper", "lithium")
    ]
    timeline_event_markers = [{"x_label": future_labels[0], "label": "未来12个月预测起点"}]

    series = [
        {
            "label": SEGMENT_META[key]["label"],
            "key": SEGMENT_META[key]["label"],
            "color": SEGMENT_META[key]["color"],
            "values": values,
        }
        for key, values in series_values.items()
    ]
    return {
        "labels": labels,
        "series": series,
        "range_rows": range_rows,
        "assumption_rows": assumption_rows,
        "timeline_labels": timeline_labels,
        "timeline_series": timeline_series,
        "timeline_event_markers": timeline_event_markers,
        "note": "模型以2025年矿山业务口径营收为分板块基准，过去12个月按最近4个季度的公开财务周期与季度价格分布回推金、铜、锂营收曲线，未来12个月按当前价格相对近12个月均价的偏离和2026产量指引推导；其他业务按2025审计收入的季度均值平推，总营收为两部分合计。",
    }
