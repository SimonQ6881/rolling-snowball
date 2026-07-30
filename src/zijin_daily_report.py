#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import math
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

import pandas as pd
import tushare as ts

from commodity_insights import (
    build_forecast_analysis,
    build_price_analysis,
    build_revenue_analysis,
    build_supply_plan_analysis,
)
from central_bank_insights import build_central_bank_gold_analysis
from report_extra import (
    build_timeframe_map,
    cache_json_records,
    classify_tags,
    compute_support_resistance,
    fetch_boe_policy_events,
    fetch_boe_rate_history,
    fetch_fed_policy_events,
    fetch_fred_series,
    fetch_goldhub_gold_purchase_entries,
    fetch_boj_policy_events,
    fetch_treasury_curve,
    summarize_status_by_error,
)
from pipeline_ops import (
    archive_exists,
    archive_trading_snapshot,
    current_trade_date,
    is_trading_day,
    should_archive_after_close,
    should_run_hourly_update,
)
from research_tracker import filter_target_research, track_research_updates
from translation_service import TranslationConfig, translate_entries


ROOT = Path(__file__).resolve().parents[1]
SH_TZ = ZoneInfo("Asia/Shanghai")


@dataclass
class QueryResult:
    name: str
    ok: bool
    detail: str


@dataclass
class ReportData:
    zijin_df: pd.DataFrame
    realtime_quote: dict[str, Any]
    daily_basic: pd.DataFrame
    moneyflow: pd.DataFrame
    gold_proxy_df: pd.DataFrame
    future_frames: dict[str, pd.DataFrame]
    cn_index_rows: list[list[str]]
    global_index_rows: list[list[str]]
    global_index_frames: dict[str, pd.DataFrame]
    fx_df: pd.DataFrame
    shibor_df: pd.DataFrame
    yc_df: pd.DataFrame
    anns: pd.DataFrame
    holder_trade: pd.DataFrame
    forecast: pd.DataFrame
    express: pd.DataFrame
    disclosure: pd.DataFrame
    fina_indicator: pd.DataFrame
    income: pd.DataFrame
    cashflow: pd.DataFrame
    dividend: pd.DataFrame
    news_rows: list[list[str]]
    precious_frames: dict[str, pd.DataFrame]
    theme_frames: dict[str, pd.DataFrame]
    dollar_index_df: pd.DataFrame
    treasury_curve_df: pd.DataFrame
    research_entries: list[dict[str, Any]]
    research_alerts: list[dict[str, Any]]
    policy_entries: list[dict[str, Any]]
    central_bank_gold_entries: list[dict[str, Any]]
    boe_rate_df: pd.DataFrame
    mainbiz: pd.DataFrame
    official_commodity_frames: dict[str, pd.DataFrame]
    commodity_price_analysis: dict[str, Any]
    revenue_structure_analysis: dict[str, Any]
    revenue_forecast_analysis: dict[str, Any]
    central_bank_gold_analysis: dict[str, Any]


def load_config(config_path: Path) -> dict[str, Any]:
    with config_path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def load_json_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def load_translation_config(config: dict[str, Any]) -> TranslationConfig:
    section = config.get("external_sources", {}).get("translation", {})
    enabled = str(os.getenv("TRANSLATION_ENABLED", section.get("enabled", "false"))).lower() in {"1", "true", "yes"}
    return TranslationConfig(
        enabled=enabled,
        api_base_url=os.getenv("TRANSLATION_API_BASE_URL", str(section.get("api_base_url", "")).strip()),
        api_key=os.getenv("TRANSLATION_API_KEY", str(section.get("api_key_env_value", "")).strip()),
        model=os.getenv("TRANSLATION_MODEL", str(section.get("model", "gpt-4.1-mini")).strip()),
        timeout_seconds=int(section.get("timeout_seconds", 30)),
        max_retries=int(section.get("max_retries", 3)),
        glossary={str(key): str(value) for key, value in section.get("glossary", {}).items()},
    )


def today_str() -> str:
    return datetime.now(SH_TZ).strftime("%Y%m%d")


def now_text() -> str:
    return datetime.now(SH_TZ).strftime("%Y-%m-%d %H:%M:%S")


def days_ago_str(days: int, now: datetime | None = None) -> str:
    base = now or datetime.now(SH_TZ)
    return (base - timedelta(days=days)).strftime("%Y%m%d")


def hours_ago_text(hours: int, now: datetime | None = None) -> str:
    base = now or datetime.now(SH_TZ)
    return (base - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")


def ensure_dataframe(df: Any) -> pd.DataFrame:
    if df is None:
        return pd.DataFrame()
    if isinstance(df, pd.DataFrame):
        if "trade_date" in df.columns:
            df = df.sort_values("trade_date").reset_index(drop=True)
        return df
    return pd.DataFrame()


def normalize_trade_date(df: pd.DataFrame, column: str = "trade_date") -> pd.DataFrame:
    if df.empty or column not in df.columns:
        return df
    out = df.copy()
    out[column] = out[column].astype(str)
    out = out.sort_values(column).reset_index(drop=True)
    return out


def as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def fmt_num(value: Any, digits: int = 2, suffix: str = "") -> str:
    number = as_float(value)
    if number is None:
        return "N/A"
    return f"{number:,.{digits}f}{suffix}"


def fmt_pct(value: Any, digits: int = 2) -> str:
    number = as_float(value)
    if number is None:
        return "N/A"
    return f"{number:.{digits}f}%"


def fmt_signed_pct(value: Any, digits: int = 2) -> str:
    number = as_float(value)
    if number is None:
        return "N/A"
    return f"{number:+.{digits}f}%"


def fmt_money(value: Any, digits: int = 2) -> str:
    number = as_float(value)
    if number is None:
        return "N/A"
    return f"{number:,.{digits}f}"


def latest_row(df: pd.DataFrame) -> pd.Series | None:
    if df.empty:
        return None
    return df.iloc[-1]


def prev_row(df: pd.DataFrame) -> pd.Series | None:
    if len(df) < 2:
        return None
    return df.iloc[-2]


def compute_drawdown(close_series: pd.Series, window: int) -> float | None:
    if close_series.empty:
        return None
    sample = close_series.tail(window)
    if sample.empty:
        return None
    peak = sample.max()
    last = sample.iloc[-1]
    if peak == 0:
        return None
    return (last / peak - 1.0) * 100


def compute_return(close_series: pd.Series, periods: int) -> float | None:
    if len(close_series) <= periods:
        return None
    start = as_float(close_series.iloc[-periods - 1])
    end = as_float(close_series.iloc[-1])
    if start in (None, 0) or end is None:
        return None
    return (end / start - 1.0) * 100


def frame_rows(df: pd.DataFrame, limit: int, row_builder: Callable[[pd.Series], list[str]]) -> list[list[str]]:
    if df.empty:
        return []
    rows: list[list[str]] = []
    for _, item in df.head(limit).iterrows():
        rows.append(row_builder(item))
    return rows


class TushareFetcher:
    def __init__(self, token: str):
        self.pro = ts.pro_api(token)
        self.status: list[QueryResult] = []

    def _record(self, name: str, ok: bool, detail: str) -> None:
        self.status.append(QueryResult(name=name, ok=ok, detail=detail))

    def safe(self, name: str, func: Callable[..., Any], *args: Any, **kwargs: Any) -> pd.DataFrame:
        try:
            df = func(*args, **kwargs)
            df = ensure_dataframe(df)
            self._record(name, True, f"{len(df)} rows")
            return df
        except Exception as exc:  # noqa: BLE001
            self._record(name, False, str(exc))
            return pd.DataFrame()

    def bar(self, name: str, ts_code: str, asset: str, start_date: str, end_date: str) -> pd.DataFrame:
        df = self.safe(
            name,
            ts.pro_bar,
            ts_code=ts_code,
            asset=asset,
            start_date=start_date,
            end_date=end_date,
            freq="D",
        )
        df = ensure_dataframe(df)
        if not df.empty and "trade_date" in df.columns:
            df = normalize_trade_date(df, "trade_date")
        return df

    def query(self, name: str, api_name: str, **kwargs: Any) -> pd.DataFrame:
        method = getattr(self.pro, api_name, None)
        if callable(method):
            return self.safe(name, method, **kwargs)
        return self.safe(name, self.pro.query, api_name, **kwargs)

    def safe_any(self, name: str, func: Callable[..., Any], fallback: Any, *args: Any, **kwargs: Any) -> Any:
        try:
            value = func(*args, **kwargs)
            if isinstance(value, pd.DataFrame):
                detail = f"{len(value)} rows"
            elif isinstance(value, list):
                detail = f"{len(value)} items"
            elif isinstance(value, dict):
                detail = f"{len(value)} keys"
            else:
                detail = type(value).__name__
            self._record(name, True, detail)
            return value
        except Exception as exc:  # noqa: BLE001
            self._record(name, False, str(exc))
            return fallback


def normalize_realtime_quote(raw: Any, ts_code: str) -> dict[str, Any]:
    df = ensure_dataframe(raw)
    if df.empty:
        return {}
    if "TS_CODE" in df.columns:
        matched = df[df["TS_CODE"].astype(str) == ts_code]
        if not matched.empty:
            df = matched.reset_index(drop=True)
    row = df.iloc[0]

    def pick(*names: str) -> Any:
        for name in names:
            value = row.get(name)
            if value is None:
                continue
            text = str(value).strip()
            if not text or text.lower() == "nan":
                continue
            return value
        return None

    return {
        "name": str(pick("NAME", "name") or ""),
        "ts_code": str(pick("TS_CODE", "ts_code") or ts_code),
        "date": str(pick("DATE", "date") or ""),
        "time": str(pick("TIME", "time") or ""),
        "price": as_float(pick("PRICE", "price", "current")),
        "pre_close": as_float(pick("PRE_CLOSE", "pre_close")),
        "open": as_float(pick("OPEN", "open")),
        "high": as_float(pick("HIGH", "high")),
        "low": as_float(pick("LOW", "low")),
    }


def fetch_realtime_quote(ts_code: str) -> dict[str, Any]:
    return normalize_realtime_quote(ts.realtime_quote(ts_code=ts_code), ts_code)


def enrich_price_frame(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "close" not in df.columns:
        return df
    out = df.copy()
    out["close"] = pd.to_numeric(out["close"], errors="coerce")
    out["ma20"] = out["close"].rolling(20).mean()
    out["ma60"] = out["close"].rolling(60).mean()
    out["ma5"] = out["close"].rolling(5).mean()
    out["ret_5d"] = out["close"].pct_change(5) * 100
    out["ret_20d"] = out["close"].pct_change(20) * 100
    out["drawdown_20d"] = out["close"] / out["close"].rolling(20).max() - 1.0
    out["drawdown_60d"] = out["close"] / out["close"].rolling(60).max() - 1.0
    out["drawdown_20d"] = out["drawdown_20d"] * 100
    out["drawdown_60d"] = out["drawdown_60d"] * 100
    return out


def price_snapshot(label: str, df: pd.DataFrame) -> list[str] | None:
    if df.empty:
        return None
    row = latest_row(df)
    if row is None:
        return None
    return [
        label,
        str(row.get("trade_date", "N/A")),
        fmt_num(row.get("close")),
        fmt_signed_pct(row.get("pct_chg")),
        fmt_signed_pct(row.get("ret_5d")),
        fmt_signed_pct(row.get("ret_20d")),
    ]


def normalize_market_frame(df: pd.DataFrame, trade_date_column: str = "trade_date") -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    rename_map = {}
    if trade_date_column != "trade_date" and trade_date_column in out.columns:
        rename_map[trade_date_column] = "trade_date"
    if "pct_change" in out.columns and "pct_chg" not in out.columns:
        rename_map["pct_change"] = "pct_chg"
    if rename_map:
        out = out.rename(columns=rename_map)
    if "trade_date" in out.columns:
        out = normalize_trade_date(out, "trade_date")
    return enrich_price_frame(out)


def fetch_mapped_future_frame(
    fetcher: TushareFetcher,
    name: str,
    ts_code: str,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    mapping = fetcher.query(name, "fut_mapping", ts_code=ts_code)
    if mapping.empty:
        return pd.DataFrame()
    mapping = mapping.copy()
    mapping["trade_date"] = mapping["trade_date"].astype(str)
    mapping = mapping[(mapping["trade_date"] >= start_date) & (mapping["trade_date"] <= end_date)]
    mapping = mapping[["trade_date", "mapping_ts_code"]].drop_duplicates()
    if mapping.empty:
        return pd.DataFrame()

    frames: list[pd.DataFrame] = []
    for contract in sorted(mapping["mapping_ts_code"].dropna().astype(str).unique()):
        contract_df = fetcher.bar(f"{name}-{contract}", contract, "FT", start_date, end_date)
        if contract_df.empty:
            continue
        contract_df = contract_df.copy()
        contract_df["trade_date"] = contract_df["trade_date"].astype(str)
        contract_df["mapping_ts_code"] = contract
        frames.append(contract_df)
    if not frames:
        return pd.DataFrame()

    merged = mapping.merge(
        pd.concat(frames, ignore_index=True),
        on=["trade_date", "mapping_ts_code"],
        how="left",
    )
    merged["ts_code"] = ts_code
    return normalize_market_frame(merged)


def filter_news(df: pd.DataFrame) -> list[list[str]]:
    if df.empty:
        return []
    keywords = ("紫金", "黄金", "金价", "铜价", "锂", "美元", "美联储", "美债", "关税", "台海")
    rows: list[list[str]] = []
    for _, item in df.iterrows():
        title = str(item.get("title") or item.get("content") or "")
        if not any(keyword in title for keyword in keywords):
            continue
        rows.append(
            [
                str(item.get("datetime", "")),
                str(item.get("src", "news")),
                title[:72],
            ]
        )
        if len(rows) >= 8:
            break
    return rows


def latest_fx_row(df: pd.DataFrame) -> list[list[str]]:
    row = latest_row(df)
    if row is None:
        return [["美元兑离岸人民币", "N/A", "N/A", "接口无权限或无数据"]]
    close = row.get("bid_close") or row.get("ask_close")
    prev = prev_row(df)
    prev_close = None
    if prev is not None:
        prev_close = prev.get("bid_close") or prev.get("ask_close")
    delta = None
    if as_float(close) is not None and as_float(prev_close) is not None:
        delta = (as_float(close) - as_float(prev_close)) / as_float(prev_close) * 100
    return [[
        "美元兑离岸人民币",
        str(row.get("trade_date", "N/A")),
        fmt_num(close, 4),
        f"日变动 {fmt_signed_pct(delta)}",
    ]]


def latest_rate_rows(shibor_df: pd.DataFrame, yc_df: pd.DataFrame) -> list[list[str]]:
    rows = []
    sh = latest_row(shibor_df)
    if sh is not None:
        rows.append(["SHIBOR 3M", str(sh.get("date", "N/A")), fmt_pct(sh.get("3m"), 4), "国内利率参考"])
        rows.append(["SHIBOR 1Y", str(sh.get("date", "N/A")), fmt_pct(sh.get("1y"), 4), "长端资金成本参考"])
    else:
        rows.append(["SHIBOR", "N/A", "N/A", "接口无权限或无数据"])

    yc = latest_row(yc_df)
    if yc is not None:
        rows.append(
            [
                "中债10Y国债收益率",
                str(yc.get("trade_date", "N/A")),
                fmt_pct(yc.get("yield"), 4),
                "中国长端利率代理",
            ]
        )
    else:
        rows.append(["中债10Y", "N/A", "N/A", "单独权限接口，缺失时可手工补录美债观察"])
    return rows


def html_escape(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def css_change_class(value: Any) -> str:
    number = as_float(value)
    if number is None:
        return "neutral"
    if number > 0:
        return "positive"
    if number < 0:
        return "negative"
    return "neutral"


def html_table(headers: list[str], rows: list[list[str]]) -> str:
    if not rows:
        return '<div class="empty">暂无数据</div>'
    thead = "".join(f"<th>{html_escape(item)}</th>" for item in headers)
    trs: list[str] = []
    for row in rows:
        tds = "".join(f"<td>{html_escape(item)}</td>" for item in row)
        trs.append(f"<tr>{tds}</tr>")
    tbody = "".join(trs)
    return f"<table><thead><tr>{thead}</tr></thead><tbody>{tbody}</tbody></table>"


def html_list(items: list[str], checkable: bool = False) -> str:
    if not items:
        return '<div class="empty">暂无数据</div>'
    lis = []
    for item in items:
        prefix = "[ ] " if checkable else ""
        lis.append(f"<li>{html_escape(prefix + item)}</li>")
    return "<ul>" + "".join(lis) + "</ul>"


def stat_card(title: str, value: str, subtitle: str = "", tone: str = "neutral") -> str:
    subtitle_html = f'<div class="card-subtitle">{html_escape(subtitle)}</div>' if subtitle else ""
    return (
        f'<div class="card {tone}">'
        f'<div class="card-title">{html_escape(title)}</div>'
        f'<div class="card-value">{html_escape(value)}</div>'
        f"{subtitle_html}"
        "</div>"
    )


def format_date_label(date_str: Any) -> str:
    value = str(date_str or "")
    if len(value) == 8 and value.isdigit():
        return f"{value[4:6]}/{value[6:8]}"
    return value


def build_svg_line_chart(
    title: str,
    labels: list[str],
    series: list[dict[str, Any]],
    guides: list[dict[str, Any]] | None = None,
    event_markers: list[dict[str, Any]] | None = None,
    point_markers: list[dict[str, Any]] | None = None,
    chart_id: str | None = None,
    width: int = 920,
    height: int = 280,
) -> str:
    valid_values: list[float] = []
    for item in series:
        for value in item["values"]:
            number = as_float(value)
            if number is not None:
                valid_values.append(number)

    if len(labels) < 2 or not valid_values:
        return f'<div class="chart-card"><div class="chart-title">{html_escape(title)}</div><div class="empty">暂无图表数据</div></div>'

    min_value = min(valid_values)
    max_value = max(valid_values)
    if min_value == max_value:
        min_value -= 1
        max_value += 1

    left = 48
    right = 18
    top = 18
    bottom = 30
    inner_w = width - left - right
    inner_h = height - top - bottom

    def x_pos(idx: int) -> float:
        if len(labels) == 1:
            return left + inner_w / 2
        return left + inner_w * idx / (len(labels) - 1)

    def y_pos(value: float) -> float:
        return top + (max_value - value) / (max_value - min_value) * inner_h

    grid_lines = []
    for step in range(5):
        y = top + inner_h * step / 4
        v = max_value - (max_value - min_value) * step / 4
        grid_lines.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{width-right}" y2="{y:.1f}" class="grid-line" />'
            f'<text x="6" y="{y+4:.1f}" class="axis-label">{html_escape(fmt_num(v))}</text>'
        )

    x_labels = []
    x_steps = min(6, len(labels))
    for step in range(x_steps):
        idx = round((len(labels) - 1) * step / max(x_steps - 1, 1))
        x = x_pos(idx)
        x_labels.append(
            f'<text x="{x:.1f}" y="{height-8}" text-anchor="middle" class="axis-label">{html_escape(labels[idx])}</text>'
        )

    guide_lines = []
    for guide in guides or []:
        number = as_float(guide.get("value"))
        if number is None:
            continue
        y = y_pos(number)
        css_class = "guide-line support" if guide.get("tone") == "support" else "guide-line resistance"
        guide_lines.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{width-right}" y2="{y:.1f}" class="{css_class}" />'
            f'<text x="{width-right-2}" y="{y-4:.1f}" text-anchor="end" class="axis-label">{html_escape(guide.get("label", ""))} {html_escape(fmt_num(number))}</text>'
        )

    event_lines = []
    for item in event_markers or []:
        try:
            idx = labels.index(str(item.get("x_label", "")))
        except ValueError:
            continue
        x = x_pos(idx)
        event_lines.append(
            f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{height-bottom}" class="event-line" />'
            f'<text x="{min(x + 4, width - right - 40):.1f}" y="{top + 12:.1f}" class="event-label">{html_escape(item.get("label", ""))}</text>'
        )

    polylines = []
    legend = []
    series_map: dict[str, list[Any]] = {}
    for item in series:
        points = []
        raw_values = list(item.get("values", []))[: len(labels)]
        series_key = str(item.get("key", item["label"]))
        series_map[series_key] = raw_values
        for idx, raw in enumerate(raw_values):
            number = as_float(raw)
            if number is None:
                continue
            points.append(f"{x_pos(idx):.2f},{y_pos(number):.2f}")
        if not points:
            continue
        color = item["color"]
        series_key = html_escape(item.get("key", item["label"]))
        extra_attr = f' data-chart-id="{html_escape(chart_id)}" data-series-key="{series_key}"' if chart_id else ""
        polylines.append(
            f'<polyline fill="none" stroke="{color}" stroke-width="2.5" points="{" ".join(points)}"{extra_attr} />'
        )
        legend.append(
            f'<button type="button" class="legend-item legend-toggle" data-target-chart="{html_escape(chart_id or "")}" data-target-series="{series_key}"><span class="legend-dot" style="background:{color}"></span>{html_escape(item["label"])}</button>'
        )

    marker_nodes = []
    for item in point_markers or []:
        try:
            idx = labels.index(str(item.get("x_label", "")))
        except ValueError:
            continue
        series_key = str(item.get("series_key", ""))
        values = series_map.get(series_key)
        number = as_float(item.get("value"))
        if values is None and number is None:
            continue
        if number is None and values is not None:
            if idx >= len(values):
                continue
            number = as_float(values[idx])
        if number is None:
            continue
        marker_nodes.append(
            f'<circle cx="{x_pos(idx):.1f}" cy="{y_pos(number):.1f}" r="4" class="point-marker" />'
            f'<text x="{min(x_pos(idx) + 6, width - right - 54):.1f}" y="{max(y_pos(number) - 6, top + 12):.1f}" class="point-label">{html_escape(item.get("label", ""))}</text>'
        )

    svg = (
        f'<svg viewBox="0 0 {width} {height}" class="chart-svg">'
        f'{"".join(grid_lines)}'
        f'{"".join(guide_lines)}'
        f'{"".join(event_lines)}'
        f'{"".join(polylines)}'
        f'{"".join(marker_nodes)}'
        f'{"".join(x_labels)}'
        "</svg>"
    )
    return (
        '<div class="chart-card">'
        f'<div class="chart-title">{html_escape(title)}</div>'
        f'<div class="legend">{"".join(legend)}</div>'
        f"{svg}"
        "</div>"
    )


def build_svg_bar_chart(
    title: str,
    labels: list[str],
    series: list[dict[str, Any]],
    chart_id: str | None = None,
    width: int = 920,
    height: int = 300,
) -> str:
    valid_values = [as_float(value) for item in series for value in item.get("values", [])]
    valid_values = [value for value in valid_values if value is not None]
    if len(labels) < 1 or not valid_values:
        return f'<div class="chart-card"><div class="chart-title">{html_escape(title)}</div><div class="empty">暂无图表数据</div></div>'

    max_value = max(valid_values)
    if max_value <= 0:
        max_value = 1.0

    left = 48
    right = 18
    top = 18
    bottom = 36
    inner_w = width - left - right
    inner_h = height - top - bottom
    group_width = inner_w / max(len(labels), 1)
    bar_width = min(24.0, group_width / max(len(series) + 1, 2))

    def y_pos(value: float) -> float:
        return top + inner_h - value / max_value * inner_h

    grid_lines = []
    for step in range(5):
        y = top + inner_h * step / 4
        v = max_value - max_value * step / 4
        grid_lines.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{width-right}" y2="{y:.1f}" class="grid-line" />'
            f'<text x="6" y="{y+4:.1f}" class="axis-label">{html_escape(fmt_num(v))}</text>'
        )

    legend = []
    rects = []
    x_labels = []
    for idx, label in enumerate(labels):
        base_x = left + idx * group_width + group_width / 2
        x_labels.append(
            f'<text x="{base_x:.1f}" y="{height-10}" text-anchor="middle" class="axis-label">{html_escape(label)}</text>'
        )
        for s_idx, item in enumerate(series):
            values = item.get("values", [])
            if idx >= len(values):
                continue
            number = as_float(values[idx])
            if number is None:
                continue
            bar_x = left + idx * group_width + (s_idx + 0.35) * bar_width
            bar_y = y_pos(number)
            rects.append(
                f'<rect x="{bar_x:.1f}" y="{bar_y:.1f}" width="{bar_width:.1f}" height="{top + inner_h - bar_y:.1f}" rx="4" fill="{html_escape(item["color"])}"'
                + (f' data-chart-id="{html_escape(chart_id)}" data-series-key="{html_escape(item.get("key", item["label"]))}"' if chart_id else "")
                + " />"
            )
    for item in series:
        legend.append(
            f'<button type="button" class="legend-item legend-toggle" data-target-chart="{html_escape(chart_id or "")}" data-target-series="{html_escape(item.get("key", item["label"]))}"><span class="legend-dot" style="background:{html_escape(item["color"])}"></span>{html_escape(item["label"])}</button>'
        )

    svg = (
        f'<svg viewBox="0 0 {width} {height}" class="chart-svg">'
        f'{"".join(grid_lines)}'
        f'{"".join(rects)}'
        f'{"".join(x_labels)}'
        "</svg>"
    )
    return (
        '<div class="chart-card">'
        f'<div class="chart-title">{html_escape(title)}</div>'
        f'<div class="legend">{"".join(legend)}</div>'
        f"{svg}"
        "</div>"
    )


def build_svg_donut_chart(title: str, slices: list[dict[str, Any]], width: int = 920, height: int = 280) -> str:
    valid_slices = [item for item in slices if as_float(item.get("value")) not in (None, 0)]
    total = sum(as_float(item.get("value")) or 0.0 for item in valid_slices)
    if total <= 0:
        return f'<div class="chart-card"><div class="chart-title">{html_escape(title)}</div><div class="empty">暂无图表数据</div></div>'

    center_x = 180
    center_y = height / 2
    radius = 70
    circumference = 2 * math.pi * radius
    offset = 0.0
    circles = []
    legends = []
    for item in valid_slices:
        value = as_float(item.get("value")) or 0.0
        share = value / total
        dash = share * circumference
        circles.append(
            f'<circle cx="{center_x}" cy="{center_y:.1f}" r="{radius}" fill="none" stroke="{html_escape(item["color"])}" stroke-width="28" stroke-dasharray="{dash:.2f} {circumference - dash:.2f}" stroke-dashoffset="{-offset:.2f}" transform="rotate(-90 {center_x} {center_y:.1f})" />'
        )
        offset += dash
        legends.append(
            f'<div class="donut-legend-row"><span class="legend-dot" style="background:{html_escape(item["color"])}"></span><span>{html_escape(item["label"])}</span><span>{html_escape(fmt_num(item.get("value")))} 亿元 / {html_escape(fmt_pct(item.get("share")))} </span></div>'
        )
    svg = (
        f'<svg viewBox="0 0 {width} {height}" class="chart-svg">'
        f'<circle cx="{center_x}" cy="{center_y:.1f}" r="{radius}" fill="none" stroke="#e5e7eb" stroke-width="28" />'
        f'{"".join(circles)}'
        f'<text x="{center_x}" y="{center_y-4:.1f}" text-anchor="middle" class="donut-total">{html_escape(fmt_num(total))}</text>'
        f'<text x="{center_x}" y="{center_y+16:.1f}" text-anchor="middle" class="axis-label">亿元</text>'
        "</svg>"
    )
    return (
        '<div class="chart-card">'
        f'<div class="chart-title">{html_escape(title)}</div>'
        '<div class="donut-layout">'
        + svg
        + f'<div class="donut-legend">{"".join(legends)}</div>'
        + "</div></div>"
    )


def normalized_series(df: pd.DataFrame, column: str = "close") -> tuple[list[str], list[float]]:
    if df.empty or column not in df.columns:
        return [], []
    sample = df.tail(90).copy()
    if sample.empty:
        return [], []
    sample[column] = pd.to_numeric(sample[column], errors="coerce")
    sample = sample.dropna(subset=[column])
    if sample.empty:
        return [], []
    base = as_float(sample.iloc[0][column])
    if base in (None, 0):
        return [], []
    labels = [format_date_label(item) for item in sample["trade_date"].tolist()]
    values = [(as_float(item) or 0.0) / base * 100 for item in sample[column].tolist()]
    return labels, values


def price_chart_series(df: pd.DataFrame) -> tuple[list[str], list[dict[str, Any]]]:
    if df.empty:
        return [], []
    sample = df.tail(90).copy()
    labels = [format_date_label(item) for item in sample["trade_date"].tolist()]
    return labels, [
        {"label": "收盘价", "color": "#2563eb", "values": sample["close"].tolist()},
        {"label": "MA20", "color": "#f59e0b", "values": sample["ma20"].tolist()},
        {"label": "MA60", "color": "#10b981", "values": sample["ma60"].tolist()},
    ]


def sort_by_column(df: pd.DataFrame, column: str) -> pd.DataFrame:
    if df.empty or column not in df.columns:
        return df
    out = df.copy()
    out[column] = out[column].astype(str)
    return out.sort_values(column).reset_index(drop=True)


def sort_and_dedup_by_column(df: pd.DataFrame, column: str) -> pd.DataFrame:
    if df.empty or column not in df.columns:
        return df
    out = sort_by_column(df, column)
    return out.drop_duplicates(subset=[column], keep="last").reset_index(drop=True)


def extract_financial_trend(
    df: pd.DataFrame,
    label: str,
    value_column: str,
    date_column: str = "end_date",
    scale: float = 1.0,
) -> dict[str, Any] | None:
    if df.empty or value_column not in df.columns or date_column not in df.columns:
        return None
    sample = sort_by_column(df, date_column)[[date_column, value_column]].copy()
    sample[value_column] = pd.to_numeric(sample[value_column], errors="coerce")
    sample = sample.dropna(subset=[value_column]).drop_duplicates(subset=[date_column], keep="last").tail(8)
    if sample.empty:
        return None
    labels = [str(item)[2:4] + "-" + str(item)[4:6] for item in sample[date_column].tolist()]
    values = [float(item) / scale for item in sample[value_column].tolist()]
    return {"label": label, "labels": labels, "values": values}


def join_chart_labels(series_items: list[dict[str, Any]]) -> list[str]:
    for item in series_items:
        labels = item.get("labels") or []
        if labels:
            return labels
    return []


def list_card(title: str, summary: str, items: list[str]) -> str:
    return (
        '<div class="logic-card">'
        f'<div class="logic-title">{html_escape(title)}</div>'
        f'<div class="logic-summary">{html_escape(summary)}</div>'
        f"{html_list(items)}"
        "</div>"
    )


def render_data_health_cards(status: list[QueryResult]) -> str:
    ok = sum(1 for item in status if item.ok)
    fail = len(status) - ok
    return (
        '<div class="cards compact">'
        + stat_card("成功接口", str(ok), tone="positive" if ok else "neutral")
        + stat_card("失败接口", str(fail), tone="negative" if fail else "neutral")
        + stat_card("总接口数", str(len(status)))
        + "</div>"
    )


def render_timeframe_chart_panel(
    title: str,
    panel_id: str,
    frames: dict[str, pd.DataFrame],
    label: str,
    color: str,
    extra_series: list[tuple[str, dict[str, pd.DataFrame], str]] | None = None,
    guides: list[dict[str, Any]] | None = None,
) -> str:
    buttons = []
    charts = []
    for idx, timeframe in enumerate(("日", "周", "月", "年")):
        frame = frames.get(timeframe, pd.DataFrame())
        labels, values = normalized_series(frame)
        series = []
        if values:
            series.append({"label": label, "key": label, "color": color, "values": values})
        for extra_label, frame_map, extra_color in extra_series or []:
            _, extra_values = normalized_series(frame_map.get(timeframe, pd.DataFrame()))
            if extra_values:
                series.append({"label": extra_label, "key": extra_label, "color": extra_color, "values": extra_values})
        button_class = "time-btn active" if idx == 0 else "time-btn"
        panel_class = "time-panel active" if idx == 0 else "time-panel"
        buttons.append(
            f'<button type="button" class="{button_class}" data-time-panel="{html_escape(panel_id)}" data-timeframe="{html_escape(timeframe)}">{html_escape(timeframe)}</button>'
        )
        charts.append(
            f'<div class="{panel_class}" data-panel-id="{html_escape(panel_id)}" data-timeframe="{html_escape(timeframe)}">'
            + build_svg_line_chart(
                f"{title} · {timeframe}线",
                labels,
                series,
                guides=guides if timeframe == "日" else None,
                chart_id=f"{panel_id}-{timeframe}",
            )
            + "</div>"
        )
    return (
        '<div class="chart-switcher">'
        f'<div class="switcher-head"><div class="chart-title">{html_escape(title)}</div><div class="time-tabs">{"".join(buttons)}</div></div>'
        + "".join(charts)
        + "</div>"
    )


def render_research_cards(entries: list[dict[str, Any]], section_id: str) -> str:
    if not entries:
        return '<div class="empty">暂无研报与资讯数据</div>'
    cards = []
    for idx, item in enumerate(entries[:16]):
        tags = "".join(f'<span class="tag">{html_escape(tag)}</span>' for tag in item.get("tags", [])[:6])
        summary = html_escape(str(item.get("summary", ""))[:180])
        original_title = str(item.get("title_original", ""))
        original_summary = str(item.get("summary_original", ""))
        show_toggle = bool(original_title and original_title != str(item.get("title", "")))
        toggle_id = f"{section_id}-{idx}"
        extra_tags = []
        if item.get("core_theme"):
            extra_tags.append(f'<span class="tag">{html_escape(item.get("core_theme", ""))}</span>')
        if item.get("credibility"):
            extra_tags.append(f'<span class="tag">{html_escape(item.get("credibility", ""))}可信度</span>')
        if item.get("translation_ready"):
            extra_tags.append('<span class="tag">已翻译</span>')
        cards.append(
            '<article class="info-card"'
            f' data-filter-source="{html_escape(item.get("source", ""))}"'
            f' data-filter-date="{html_escape(item.get("date", ""))}"'
            f' data-filter-tags="{html_escape(" ".join(item.get("tags", []) + [str(item.get("core_theme", "")), str(item.get("credibility", ""))]))}">'
            f'<div class="info-head"><span class="info-source">{html_escape(item.get("source", ""))}</span><span class="muted">{html_escape(item.get("date", ""))}</span></div>'
            + (
                f'<button type="button" class="filter-clear translation-toggle" data-toggle-id="{html_escape(toggle_id)}">切换原文</button>'
                if show_toggle
                else ""
            )
            + f'<div class="info-title dual-text" data-toggle-id="{html_escape(toggle_id)}">'
            + f'<span class="text-primary">{html_escape(item.get("title", ""))}</span>'
            + (
                f'<span class="text-secondary">{html_escape(original_title)}</span>'
                if show_toggle
                else ""
            )
            + "</div>"
            + f'<div class="info-summary dual-text" data-toggle-id="{html_escape(toggle_id)}">'
            + f'<span class="text-primary">{summary}</span>'
            + (
                f'<span class="text-secondary">{html_escape(original_summary[:180])}</span>'
                if show_toggle
                else ""
            )
            + "</div>"
            + f'<div class="tag-row">{tags}{"".join(extra_tags)}</div>'
            + f'<div class="muted">机构：{html_escape(item.get("org_name", item.get("institution", "N/A")))} | 观点：{html_escape(item.get("core_view", ""))[:90]}</div>'
            + (f'<a class="info-link" href="{html_escape(item.get("link", ""))}" target="_blank">查看原文</a>' if item.get("link") else "")
            + "</article>"
        )
    return (
        f'<div class="filter-bar"><input id="{html_escape(section_id)}-search" class="filter-input" placeholder="按关键词 / 机构 / 标签检索" />'
        f'<button type="button" class="filter-clear" data-filter-reset="{html_escape(section_id)}">清空</button></div>'
        f'<div id="{html_escape(section_id)}" class="info-grid">{"".join(cards)}</div>'
    )


def render_policy_cards(entries: list[dict[str, Any]], section_id: str) -> str:
    if not entries:
        return '<div class="empty">暂无央行政策事件</div>'
    cards = []
    for idx, item in enumerate(entries[:18]):
        tags = "".join(f'<span class="tag">{html_escape(tag)}</span>' for tag in item.get("tags", [])[:6])
        original_title = str(item.get("title_original", ""))
        original_summary = str(item.get("summary_original", ""))
        show_toggle = bool(original_title and original_title != str(item.get("title", "")))
        toggle_id = f"{section_id}-{idx}"
        cards.append(
            '<article class="info-card"'
            f' data-filter-source="{html_escape(item.get("institution", ""))}"'
            f' data-filter-date="{html_escape(item.get("date", ""))}"'
            f' data-filter-tags="{html_escape(" ".join(item.get("tags", [])))}">'
            f'<div class="info-head"><span class="info-source">{html_escape(item.get("institution", ""))}</span><span class="muted">{html_escape(item.get("date", ""))}</span></div>'
            + (
                f'<button type="button" class="filter-clear translation-toggle" data-toggle-id="{html_escape(toggle_id)}">切换原文</button>'
                if show_toggle
                else ""
            )
            + f'<div class="info-title dual-text" data-toggle-id="{html_escape(toggle_id)}">'
            + f'<span class="text-primary">{html_escape(item.get("title", ""))}</span>'
            + (
                f'<span class="text-secondary">{html_escape(original_title)}</span>'
                if show_toggle
                else ""
            )
            + "</div>"
            + f'<div class="tag-row"><span class="tag action">{html_escape(item.get("action", "观察"))}</span><span class="tag">{html_escape(item.get("rate", "N/A"))}</span>{tags}</div>'
            + f'<div class="info-summary dual-text" data-toggle-id="{html_escape(toggle_id)}">'
            + f'<span class="text-primary">{html_escape(str(item.get("summary", ""))[:220])}</span>'
            + (
                f'<span class="text-secondary">{html_escape(original_summary[:220])}</span>'
                if show_toggle
                else ""
            )
            + "</div>"
            + (f'<a class="info-link" href="{html_escape(item.get("link", ""))}" target="_blank">查看原文</a>' if item.get("link") else "")
            + "</article>"
        )
    return (
        f'<div class="filter-bar"><input id="{html_escape(section_id)}-search" class="filter-input" placeholder="按央行 / 动作 / 关键词检索" />'
        f'<button type="button" class="filter-clear" data-filter-reset="{html_escape(section_id)}">清空</button></div>'
        f'<div id="{html_escape(section_id)}" class="info-grid">{"".join(cards)}</div>'
    )


def render_status_panel(status: list[QueryResult]) -> str:
    total = len(status)
    ok = sum(1 for item in status if item.ok)
    fail = total - ok
    success_rate = (ok / total * 100) if total else 0
    status_rows = [{"name": item.name, "ok": item.ok, "detail": item.detail} for item in status]
    error_rows = summarize_status_by_error(status_rows)
    recent_failures = [
        [item.name, "失败", item.detail[:120]]
        for item in status
        if not item.ok
    ][:12]
    return (
        '<div class="status-board">'
        '<div class="cards compact">'
        + stat_card("接口总数", str(total))
        + stat_card("成功率", fmt_pct(success_rate), tone="positive" if success_rate >= 80 else "negative")
        + stat_card("失败数", str(fail), tone="negative" if fail else "neutral")
        + stat_card("更新时间", now_text()[-8:])
        + "</div>"
        '<div class="grid-2">'
        + build_svg_line_chart(
            "接口抓取成败占比",
            ["成功", "失败"],
            [{"label": "数量", "key": "数量", "color": "#2563eb", "values": [ok, fail]}],
            chart_id="status-summary",
            width=560,
        )
        + '<div class="chart-card"><div class="chart-title">失败类型聚合</div>'
        + html_table(["失败类型", "次数"], error_rows)
        + "</div></div>"
        + '<details class="status-detail"><summary>展开异常明细与溯源</summary>'
        + html_table(["模块", "状态", "说明"], recent_failures if recent_failures else [["无", "成功", "当前无异常"]])
        + "</details></div>"
    )


def _parse_ratio_text(text: Any) -> tuple[int, int]:
    raw = str(text or "").strip()
    if "/" not in raw:
        return 0, 0
    left, right = raw.split("/", 1)
    try:
        return int(left), int(right)
    except ValueError:
        return 0, 0


def build_information_analysis(
    *,
    fetcher: TushareFetcher,
    current_price: float | None,
    current_price_subtitle: str,
    market_value: float | None,
    pnl: float | None,
    drawdown_20d: float | None,
    commodity_price_analysis: dict[str, Any],
    revenue_structure_analysis: dict[str, Any],
    revenue_forecast_analysis: dict[str, Any],
    central_bank_gold_analysis: dict[str, Any],
    research_entries: list[dict[str, Any]],
    research_alerts: list[dict[str, Any]],
    policy_entries: list[dict[str, Any]],
    central_bank_gold_entries: list[dict[str, Any]],
    ann_rows: list[list[str]],
    forecast_rows: list[list[str]],
    express_rows: list[list[str]],
    disclosure_rows: list[list[str]],
    quarter_rows: list[list[str]],
    research_recent_count: int,
) -> dict[str, Any]:
    supply_coverage_text = str(commodity_price_analysis.get("supply_company_coverage", "0/50"))
    covered_companies, target_companies = _parse_ratio_text(supply_coverage_text)
    total_modules = len(fetcher.status)
    failed_modules = [item for item in fetcher.status if not item.ok]
    failed_module_names = "、".join(item.name for item in failed_modules[:5]) if failed_modules else "无"
    success_modules = total_modules - len(failed_modules)
    success_rate = (success_modules / total_modules * 100) if total_modules else 0.0

    category_specs = [
        {
            "name": "持仓与交易",
            "sections": ["首页摘要", "每日持仓与交易结构", "每周与每季度复盘"],
            "tags": ["持仓", "盈亏", "均线", "资金流", "风控"],
            "focus": "收盘价、当前价、市值、盈亏、交易信号",
            "status": "关注" if current_price is None or (drawdown_20d is not None and drawdown_20d <= -10) else "正常",
        },
        {
            "name": "核心矿产与供给",
            "sections": ["微观三重支撑监控", "核心矿产品价格验证", "贵金属行情模块"],
            "tags": ["黄金", "铜", "锂", "价格验证", "供给规划"],
            "focus": "价格样本、拐点、矿企三年指引、供给缺口",
            "status": "关注" if covered_companies < target_companies else "正常",
        },
        {
            "name": "营收与预测",
            "sections": ["主营营收结构", "未来两季度营收预测"],
            "tags": ["营收结构", "季度预测", "产量假设", "估值"],
            "focus": "分板块营收占比、未来季度测算、假设区间",
            "status": "正常" if revenue_forecast_analysis.get("labels") else "关注",
        },
        {
            "name": "宏观与利率",
            "sections": ["趋势总览", "宏观四大逻辑监控", "宏观与风险偏好", "美元与美债行情模块"],
            "tags": ["美元", "利率", "美债", "风险偏好", "联动"],
            "focus": "黄金/美元/利率/指数联动与风险偏好切换",
            "status": "关注" if failed_modules else "正常",
        },
        {
            "name": "央行与黄金",
            "sections": ["全球央行货币政策追踪", "全球央行购金趋势跟踪"],
            "tags": ["央行购金", "货币政策", "黄金储备", "驱动因素"],
            "focus": "政策事件、购金轨迹、区域差异、业务传导",
            "status": "关注" if not policy_entries or not central_bank_gold_entries else "正常",
        },
        {
            "name": "研究与资讯",
            "sections": ["机构研报与资讯追踪"],
            "tags": ["研报", "资讯", "机构观点", "标签检索"],
            "focus": "研报条目、机构覆盖、主题分布、新增提醒",
            "status": "正常" if research_entries else "关注",
        },
        {
            "name": "公司事件与财务",
            "sections": ["公司事件与舆情"],
            "tags": ["公告", "股东", "业绩预告", "披露计划", "财务快照"],
            "focus": "公告、业绩、披露计划与季度财务快照",
            "status": "正常" if any([ann_rows, forecast_rows, express_rows, disclosure_rows, quarter_rows]) else "关注",
        },
        {
            "name": "数据质量与刷新",
            "sections": ["接口抓取状态统计面板", "刷新数据"],
            "tags": ["接口状态", "异常识别", "刷新", "数据完整性"],
            "focus": "抓取成功率、失败类型、刷新链路、降级提示",
            "status": "异常" if failed_modules else "正常",
        },
    ]

    tag_to_categories: dict[str, list[str]] = {}
    for spec in category_specs:
        for tag in spec["tags"]:
            tag_to_categories.setdefault(tag, []).append(spec["name"])

    category_rows = [
        [
            spec["name"],
            str(len(spec["sections"])),
            " / ".join(spec["sections"]),
            "、".join(spec["tags"]),
            spec["focus"],
            spec["status"],
        ]
        for spec in category_specs
    ]
    tag_rows = [
        [tag, str(len(categories)), "、".join(categories)]
        for tag, categories in sorted(tag_to_categories.items(), key=lambda item: (item[0]))
    ]

    key_rows = [
        [
            "持仓状态",
            f"当前价 {fmt_money(current_price)}，市值 {fmt_money(market_value)}，盈亏 {fmt_money(pnl)}",
            current_price_subtitle,
        ],
        [
            "矿产价格验证",
            f"价格样本 {len(commodity_price_analysis.get('overview_rows', []))} 个，关键拐点 {len(commodity_price_analysis.get('turning_rows', []))} 个，事件节点 {len(commodity_price_analysis.get('event_rows', []))} 个",
            "用于快速定位金、铜、锂价格变化与事件触发点",
        ],
        [
            "供给规划覆盖",
            f"矿企覆盖 {supply_coverage_text}，三年量化 {commodity_price_analysis.get('supply_quantified_company_count', 0)} 家，部分披露 {commodity_price_analysis.get('supply_partial_company_count', 0)} 家",
            f"未完整披露记录 {len(commodity_price_analysis.get('supply_gap_rows', []))} 条",
        ],
        [
            "营收与预测",
            f"营收结构板块 {len(revenue_structure_analysis.get('current_rows', []))} 个，预测季度 {len(revenue_forecast_analysis.get('labels', []))} 个",
            f"核心假设 {len(revenue_forecast_analysis.get('assumption_rows', []))} 条",
        ],
        [
            "央行与政策",
            f"政策事件 {len(policy_entries)} 条，购金月报 {len(central_bank_gold_entries)} 条",
            str(central_bank_gold_analysis.get("summary_text", "暂无最新央行购金摘要"))[:120],
        ],
        [
            "研究与舆情",
            f"研报/资讯 {len(research_entries)} 条，近30天新增 {research_recent_count} 条，本次新增提醒 {len(research_alerts)} 条",
            "支持按关键词 / 机构 / 标签检索",
        ],
        [
            "数据健康",
            f"接口成功 {success_modules}/{total_modules}，失败 {len(failed_modules)}，成功率 {fmt_pct(success_rate)}",
            f"异常模块：{failed_module_names}",
        ],
    ]

    anomaly_rows: list[list[str]] = []
    if failed_modules:
        error_rows = summarize_status_by_error(
            [{"name": item.name, "ok": item.ok, "detail": item.detail} for item in fetcher.status]
        )
        error_summary = "；".join(f"{name} {count} 次" for name, count in error_rows[:3]) if error_rows else "未归类"
        anomaly_rows.append(
            [
                "接口抓取异常",
                f"{len(failed_modules)} 个模块失败",
                error_summary,
                failed_module_names,
                "优先处理 SSL/证书与权限问题，避免宏观与央行板块长期缺数",
            ]
        )
    if current_price is None:
        anomaly_rows.append(
            [
                "实时行情降级",
                "当前价缺失",
                "页面已回退到收盘口径",
                "当前市值/浮盈展示会弱化盘中变化",
                "检查实时行情接口返回值与交易时段",
            ]
        )
    if covered_companies < target_companies:
        anomaly_rows.append(
            [
                "供给覆盖缺口",
                f"已覆盖 {covered_companies}/{target_companies} 家目标矿企",
                f"三年量化 {commodity_price_analysis.get('supply_quantified_company_count', 0)} 家，部分披露 {commodity_price_analysis.get('supply_partial_company_count', 0)} 家",
                f"仍有 {max(target_companies - covered_companies, 0)} 家未纳入事实库",
                "继续补官方年报、IR 指引与未上市头部矿企项目口径",
            ]
        )
    if commodity_price_analysis.get("supply_gap_rows"):
        anomaly_rows.append(
            [
                "口径不完整",
                f"{len(commodity_price_analysis.get('supply_gap_rows', []))} 条记录未形成完整三年分年指引",
                "以项目级扩产或中期路径替代了完整年度产量指引",
                "对市场份额、集中度测算存在下偏误风险",
                "保持 partial 状态，不把项目产能直接当成年产量",
            ]
        )
    if not policy_entries or not central_bank_gold_entries:
        anomaly_rows.append(
            [
                "宏观链路缺口",
                f"政策事件 {len(policy_entries)} 条，购金月报 {len(central_bank_gold_entries)} 条",
                "央行与宏观板块存在外部抓取缺口",
                "趋势判断和联动分析的证据链会变短",
                "补抓官方页面或修复外部抓取证书链",
            ]
        )
    if drawdown_20d is not None and drawdown_20d <= -10:
        anomaly_rows.append(
            [
                "市场波动预警",
                f"近20日回撤 {fmt_signed_pct(drawdown_20d)}",
                "已进入重点观察区",
                "需要结合均线、资金流与金铜价格联动复核",
                "优先看反弹力度和60日线趋势变化",
            ]
        )
    if not anomaly_rows:
        anomaly_rows.append(["未识别显著异常", "N/A", "当前页面信息链路完整", "无显著阻断", "继续按日刷新与核验"])

    info_cards = (
        '<div class="cards compact">'
        + stat_card("信息分类", str(len(category_specs)))
        + stat_card("结构化标签", str(len(tag_rows)))
        + stat_card("关键提要", str(len(key_rows)))
        + stat_card("异常识别", str(len(anomaly_rows)), tone="negative" if len(anomaly_rows) else "neutral")
        + stat_card("接口成功", str(success_modules), tone="positive" if success_modules else "neutral")
        + stat_card("接口失败", str(len(failed_modules)), tone="negative" if failed_modules else "neutral")
        + "</div>"
    )
    return {
        "cards_html": info_cards,
        "category_rows": category_rows,
        "tag_rows": tag_rows,
        "key_rows": key_rows,
        "anomaly_rows": anomaly_rows,
        "note": "对当前页面全部信息按主题、来源与用途进行结构化归类，并在服务端完成统计、提要和异常识别，不新增额外接口请求。",
    }


def load_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def load_csv_frame(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:  # noqa: BLE001
        return pd.DataFrame()


def save_csv_frame(path: Path, df: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def parse_pct_text(text: Any) -> float | None:
    value = str(text or "").strip().replace("%", "").replace("+", "")
    if value in {"", "N/A"}:
        return None
    return as_float(value)


def clip_text(value: Any, limit: int = 48) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text or "N/A"
    return text[: limit - 1] + "…"


def parse_list_text(text: Any) -> list[str]:
    raw = str(text or "").strip()
    if not raw:
        return []
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        payload = None
    if isinstance(payload, list):
        return [str(item).strip() for item in payload if str(item).strip()]
    cleaned = raw.replace("[", "").replace("]", "").replace('"', "")
    return [item.strip() for item in cleaned.split(",") if item.strip()]


def annualized_volatility(df: pd.DataFrame, column: str = "close", window: int = 60) -> float | None:
    if df.empty or column not in df.columns:
        return None
    sample = sort_by_column(df, "trade_date").tail(window + 1).copy()
    sample[column] = pd.to_numeric(sample[column], errors="coerce")
    sample = sample.dropna(subset=[column])
    if len(sample) < 10:
        return None
    returns = sample[column].pct_change().dropna()
    if returns.empty:
        return None
    return float(returns.std() * math.sqrt(252) * 100)


def compute_correlation(
    left_df: pd.DataFrame,
    right_df: pd.DataFrame,
    left_col: str = "close",
    right_col: str = "close",
    window: int = 60,
) -> float | None:
    if left_df.empty or right_df.empty or left_col not in left_df.columns or right_col not in right_df.columns:
        return None
    left = sort_by_column(left_df, "trade_date")[["trade_date", left_col]].copy().rename(columns={left_col: "left_value"})
    right = sort_by_column(right_df, "trade_date")[["trade_date", right_col]].copy().rename(columns={right_col: "right_value"})
    left["left_value"] = pd.to_numeric(left["left_value"], errors="coerce")
    right["right_value"] = pd.to_numeric(right["right_value"], errors="coerce")
    merged = left.merge(right, on="trade_date", how="inner").dropna().tail(window + 1)
    if len(merged) < 10:
        return None
    left_ret = merged["left_value"].pct_change()
    right_ret = merged["right_value"].pct_change()
    corr = left_ret.corr(right_ret)
    return float(corr) if pd.notna(corr) else None


def build_usdcnh_proxy_frame(fx_df: pd.DataFrame) -> pd.DataFrame:
    if fx_df.empty:
        return pd.DataFrame()
    out = fx_df.copy()
    if "bid_close" in out.columns:
        out["close"] = pd.to_numeric(out["bid_close"], errors="coerce")
    elif "ask_close" in out.columns:
        out["close"] = pd.to_numeric(out["ask_close"], errors="coerce")
    elif "close" in out.columns:
        out["close"] = pd.to_numeric(out["close"], errors="coerce")
    else:
        return pd.DataFrame()
    if "trade_date" not in out.columns:
        return pd.DataFrame()
    out = out[["trade_date", "close"]].dropna(subset=["trade_date", "close"]).copy()
    if out.empty:
        return pd.DataFrame()
    out["label"] = "美元指数代理"
    out["proxy_source"] = "USDCNH"
    return sort_and_dedup_by_column(out, "trade_date")


def resolve_dollar_proxy_frame(dollar_index_df: pd.DataFrame, fx_df: pd.DataFrame, cache_path: Path) -> pd.DataFrame:
    primary = normalize_market_frame(dollar_index_df)
    if not primary.empty:
        primary = primary.copy()
        primary["proxy_source"] = "FRED"
        save_csv_frame(cache_path, primary)
        return primary

    fx_proxy = build_usdcnh_proxy_frame(fx_df)
    if not fx_proxy.empty:
        save_csv_frame(cache_path, fx_proxy)
        return fx_proxy

    cached = normalize_market_frame(load_csv_frame(cache_path))
    if cached.empty:
        return pd.DataFrame()
    cached = cached.copy()
    if "proxy_source" not in cached.columns:
        cached["proxy_source"] = "CACHE"
    return cached


def build_svg_radar_chart(
    title: str,
    categories: list[str],
    series: list[dict[str, Any]],
    width: int = 520,
    height: int = 420,
) -> str:
    valid_series = [item for item in series if item.get("values")]
    if len(categories) < 3 or not valid_series:
        return f'<div class="chart-card"><div class="chart-title">{html_escape(title)}</div><div class="empty">暂无图表数据</div></div>'

    center_x = width / 2
    center_y = height / 2 + 18
    radius = min(width, height) / 2 - 72
    angles = [2 * math.pi * idx / len(categories) - math.pi / 2 for idx in range(len(categories))]

    def point(angle: float, value: float) -> tuple[float, float]:
        ratio = max(0.0, min(100.0, value)) / 100
        return center_x + math.cos(angle) * radius * ratio, center_y + math.sin(angle) * radius * ratio

    grids = []
    for level in range(1, 6):
        level_ratio = level / 5
        polygon_points = []
        for angle in angles:
            x = center_x + math.cos(angle) * radius * level_ratio
            y = center_y + math.sin(angle) * radius * level_ratio
            polygon_points.append(f"{x:.1f},{y:.1f}")
        grids.append(f'<polygon points="{" ".join(polygon_points)}" fill="none" stroke="#dbeafe" stroke-width="1" />')
    axes = []
    labels = []
    for idx, angle in enumerate(angles):
        axis_x = center_x + math.cos(angle) * radius
        axis_y = center_y + math.sin(angle) * radius
        label_x = center_x + math.cos(angle) * (radius + 22)
        label_y = center_y + math.sin(angle) * (radius + 18)
        anchor = "middle"
        if math.cos(angle) > 0.35:
            anchor = "start"
        elif math.cos(angle) < -0.35:
            anchor = "end"
        axes.append(f'<line x1="{center_x:.1f}" y1="{center_y:.1f}" x2="{axis_x:.1f}" y2="{axis_y:.1f}" class="grid-line" />')
        labels.append(f'<text x="{label_x:.1f}" y="{label_y:.1f}" text-anchor="{anchor}" class="axis-label">{html_escape(categories[idx])}</text>')

    polygons = []
    legend = []
    for item in valid_series:
        color = str(item.get("color", "#2563eb"))
        values = [as_float(value) or 0.0 for value in item.get("values", [])[: len(categories)]]
        if len(values) < len(categories):
            values += [0.0] * (len(categories) - len(values))
        pts = [point(angle, value) for angle, value in zip(angles, values)]
        point_str = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        polygons.append(
            f'<polygon points="{point_str}" fill="{color}" fill-opacity="0.14" stroke="{color}" stroke-width="2" />'
            + "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="{color}" />' for x, y in pts)
        )
        legend.append(
            f'<span class="legend-item"><span class="legend-dot" style="background:{html_escape(color)}"></span>{html_escape(str(item.get("label", "")))}</span>'
        )

    svg = (
        f'<svg viewBox="0 0 {width} {height}" class="chart-svg">'
        f'{"".join(grids)}{"".join(axes)}{"".join(polygons)}{"".join(labels)}'
        "</svg>"
    )
    return f'<div class="chart-card"><div class="chart-title">{html_escape(title)}</div><div class="legend">{"".join(legend)}</div>{svg}</div>'


def build_svg_heatmap(
    title: str,
    row_labels: list[str],
    col_labels: list[str],
    values: list[list[float | None]],
    width: int = 720,
    height: int = 360,
) -> str:
    if not row_labels or not col_labels or not values:
        return f'<div class="chart-card"><div class="chart-title">{html_escape(title)}</div><div class="empty">暂无图表数据</div></div>'

    left = 132
    top = 48
    right = 16
    bottom = 24
    inner_w = width - left - right
    inner_h = height - top - bottom
    cell_w = inner_w / max(len(col_labels), 1)
    cell_h = inner_h / max(len(row_labels), 1)

    def heat_color(value: float | None) -> str:
        if value is None:
            return "#e5e7eb"
        ratio = max(0.0, min(100.0, value)) / 100
        if ratio < 0.2:
            return "#eff6ff"
        if ratio < 0.4:
            return "#bfdbfe"
        if ratio < 0.6:
            return "#60a5fa"
        if ratio < 0.8:
            return "#2563eb"
        return "#1e3a8a"

    nodes = []
    for col_idx, label in enumerate(col_labels):
        x = left + col_idx * cell_w + cell_w / 2
        nodes.append(f'<text x="{x:.1f}" y="22" text-anchor="middle" class="axis-label">{html_escape(label)}</text>')
    for row_idx, row_label in enumerate(row_labels):
        y = top + row_idx * cell_h + cell_h / 2
        nodes.append(f'<text x="{left-10:.1f}" y="{y+4:.1f}" text-anchor="end" class="axis-label">{html_escape(row_label)}</text>')
        for col_idx, value in enumerate(values[row_idx][: len(col_labels)]):
            x = left + col_idx * cell_w
            fill = heat_color(value)
            text_fill = "#ffffff" if value is not None and value >= 55 else "#0f172a"
            display = "N/A" if value is None else fmt_num(value, 0)
            nodes.append(
                f'<rect x="{x+1:.1f}" y="{top + row_idx * cell_h + 1:.1f}" width="{cell_w-2:.1f}" height="{cell_h-2:.1f}" rx="10" fill="{fill}" />'
                f'<text x="{x + cell_w/2:.1f}" y="{top + row_idx * cell_h + cell_h/2 + 4:.1f}" text-anchor="middle" fill="{text_fill}" font-size="12">{html_escape(display)}</text>'
            )
    svg = f'<svg viewBox="0 0 {width} {height}" class="chart-svg">{"".join(nodes)}</svg>'
    return f'<div class="chart-card"><div class="chart-title">{html_escape(title)}</div>{svg}</div>'


def policy_focus_commodity(item: dict[str, Any]) -> str:
    joined = " ".join(
        [str(item.get("institution", "")), str(item.get("action", "")), str(item.get("title", ""))]
    )
    if any(keyword in joined for keyword in ("美联储", "Fed", "加息", "降息")):
        return "黄金 / 铜"
    if any(keyword in joined for keyword in ("日本央行", "英国央行")):
        return "黄金"
    return "黄金 / 铜 / 锂"


def build_international_peer_analysis(policy_entries: list[dict[str, Any]]) -> dict[str, Any]:
    base_dir = ROOT / "data" / "international_mining"
    summary = load_json_object(base_dir / "international_mining_analysis_summary.json")
    company_df = load_csv_frame(base_dir / "standardized_company_dimensions.csv")
    if company_df.empty:
        return {
            "cards_html": '<div class="empty">国际矿企标准化数据库暂不可用。</div>',
            "overview_rows": [],
            "linkage_rows": [],
            "stage_rows": [],
            "policy_rows": [],
            "insight_items": ["国际矿企数据库未生成，当前版本仅保留紫金自身与商品价格链路。"],
            "note": "如需启用国际矿企多维对标，请先生成 data/international_mining 标准化产出。",
        }

    company_df = company_df.fillna("").copy()
    if "scale_reference_value" in company_df.columns:
        company_df["scale_reference_value"] = pd.to_numeric(company_df["scale_reference_value"], errors="coerce")
    if "source_date" in company_df.columns:
        company_df["source_date"] = company_df["source_date"].astype(str)

    selected_metrics: dict[str, tuple[str, dict[str, Any]]] = {}
    for commodity_label in ("黄金", "铜", "锂"):
        candidates = [
            (key, value)
            for key, value in summary.get("competition_metrics", {}).items()
            if str(key).startswith(f"{commodity_label}-")
        ]
        if candidates:
            selected_metrics[commodity_label] = max(
                candidates,
                key=lambda item: int(item[1].get("company_count", 0)),
            )

    ramp_up_count = int((company_df.get("operating_stage", pd.Series(dtype=str)) == "投产爬坡").sum())
    build_count = int((company_df.get("operating_stage", pd.Series(dtype=str)) == "开发建设").sum())
    status_counts = summary.get("status_distribution", {})
    dominant_competition = max(
        ((key, value.get("hhi", 0)) for key, value in summary.get("competition_metrics", {}).items()),
        key=lambda item: item[1],
        default=("N/A", 0),
    )
    cards_html = (
        '<div class="cards compact">'
        + stat_card("国际矿企覆盖", str(summary.get("unique_company_count", 0)))
        + stat_card("三年量化", str(status_counts.get("三年量化", 0)), tone="positive" if status_counts.get("三年量化", 0) else "neutral")
        + stat_card("投产爬坡", str(ramp_up_count), tone="positive" if ramp_up_count else "neutral")
        + stat_card("开发建设", str(build_count))
        + stat_card("集中度最高", str(dominant_competition[0]).split("-")[0])
        + stat_card("覆盖国家", str(summary.get("countries_covered", 0)))
        + "</div>"
    )

    stage_scores = {"投产爬坡": 92.0, "开发建设": 82.0, "成熟运营": 60.0, "待识别": 45.0, "维护收缩": 20.0}

    def score_row(row: pd.Series, group_max: float) -> dict[str, float]:
        scale_value = as_float(row.get("scale_reference_value"))
        scale_score = ((scale_value or 0.0) / group_max * 100) if group_max not in (None, 0) else 0.0
        completeness = min(max(as_float(row.get("comparable_years")) or 0.0, as_float(row.get("disclosed_years")) or 0.0), 3.0) / 3.0 * 100
        stage_score = stage_scores.get(str(row.get("operating_stage", "")), 35.0)
        growth_score = 35.0
        if str(row.get("capacity_addition", "")).strip():
            growth_score += 35.0
        if str(row.get("commissioning", "")).strip():
            growth_score += 30.0
        region_score = min(len(parse_list_text(row.get("region_list"))) * 35.0, 100.0)
        return {
            "规模": round(min(scale_score, 100.0), 1),
            "量化完整度": round(min(completeness, 100.0), 1),
            "扩产弹性": round(min(growth_score, 100.0), 1),
            "项目阶段": round(stage_score, 1),
            "区域分散": round(region_score, 1),
        }

    radar_categories = ["规模", "量化完整度", "扩产弹性", "项目阶段", "区域分散"]
    radar_series: list[dict[str, Any]] = []
    heatmap_labels: list[str] = []
    heatmap_values: list[list[float | None]] = []
    advantage_rows: list[list[str]] = []
    focus_records: list[tuple[str, pd.Series, dict[str, float]]] = []
    color_map = {
        "Zijin Mining": "#2563eb",
        "gold-leader": "#f59e0b",
        "copper-leader": "#b45309",
        "lithium-leader": "#8b5cf6",
    }

    zijin_rows = company_df[company_df["company"] == "Zijin Mining"].copy()
    if not zijin_rows.empty:
        score_list = []
        for _, row in zijin_rows.iterrows():
            commodity_group = company_df[company_df["commodity_label"] == row.get("commodity_label", "")]
            group_max = as_float(commodity_group["scale_reference_value"].max()) or 0.0
            score_list.append(score_row(row, group_max))
        avg_scores = {
            key: round(sum(item[key] for item in score_list) / len(score_list), 1)
            for key in radar_categories
        }
        radar_series.append({"label": "紫金 Mining", "color": color_map["Zijin Mining"], "values": [avg_scores[key] for key in radar_categories]})

    leader_keys = {"黄金": "gold-leader", "铜": "copper-leader", "锂": "lithium-leader"}
    for commodity_label in ("黄金", "铜", "锂"):
        group = company_df[company_df.get("commodity_label", "") == commodity_label].copy()
        if group.empty:
            continue
        group = group.sort_values(["scale_reference_value", "company"], ascending=[False, True], na_position="last")
        group_max = as_float(group["scale_reference_value"].max()) or 0.0
        zijin_row = group[group["company"] == "Zijin Mining"].head(1)
        if not zijin_row.empty:
            zijin_item = zijin_row.iloc[0]
            zijin_scores = score_row(zijin_item, group_max)
            focus_records.append((f"紫金-{commodity_label}", zijin_item, zijin_scores))
        leader_row = group[group["company"] != "Zijin Mining"].head(1)
        if not leader_row.empty:
            peer_item = leader_row.iloc[0]
            peer_scores = score_row(peer_item, group_max)
            focus_records.append((f"{peer_item['company']}({commodity_label})", peer_item, peer_scores))
            radar_series.append(
                {
                    "label": f"{peer_item['company']}({commodity_label})",
                    "color": color_map[leader_keys[commodity_label]],
                    "values": [peer_scores[key] for key in radar_categories],
                }
            )

    radar_html = build_svg_radar_chart("代表矿企竞争力雷达图", radar_categories, radar_series[:4])
    for label, row, scores in focus_records[:6]:
        heatmap_labels.append(label)
        heatmap_values.append([scores[key] for key in radar_categories])
        advantage_rows.append(
            [
                label,
                str(row.get("status_label", "N/A")),
                str(row.get("operating_stage", "N/A")),
                clip_text(row.get("capacity_addition") or row.get("commissioning"), 32),
                clip_text(row.get("assumptions") or row.get("current_capacity"), 34),
            ]
        )
    heatmap_html = build_svg_heatmap("重点矿企供给压力热力图", heatmap_labels, radar_categories, heatmap_values)

    stage_focus_df = company_df[company_df.get("operating_stage", "").isin(["投产爬坡", "开发建设"])].copy()
    stage_focus_df = stage_focus_df.sort_values(
        ["source_date", "scale_reference_value"],
        ascending=[False, False],
        na_position="last",
    ).head(5)
    project_items = [
        f"{item.company}（{item.commodity_label}）处于{item.operating_stage}阶段，当前主线是 {clip_text(item.commissioning or item.capacity_addition, 44)}。"
        for item in stage_focus_df.itertuples(index=False)
    ]

    policy_items: list[str] = []
    for item in policy_entries[:4]:
        focus_commodity = policy_focus_commodity(item)
        policy_items.append(
            f"{item.get('date', '')} {item.get('institution', '')}{item.get('action', '')}，优先影响 {focus_commodity}，需复核国际资本开支与紫金扩产预期。"
        )
    if not policy_items:
        policy_items.append("当前未出现新的高权重政策扰动，国际矿企对标重点仍在扩产兑现与商品价格联动。")

    insight_items = [
        f"国际矿企样本覆盖 {summary.get('unique_company_count', 0)} 家、{summary.get('countries_covered', 0)} 个国家，已经能够支撑竞争格局的日常对标。",
        f"头部集中度最高的矿种是 {str(dominant_competition[0]).split('-')[0]}，说明该赛道更容易出现头部矿企对价格预期的主导效应。",
        f"当前海外供给扰动主要来自投产爬坡 {ramp_up_count} 条与开发建设 {build_count} 条项目，而不是成熟矿山的稳态生产偏移。",
        "正式报表中只保留竞争力评分、供给压力热力图与关键项目结论，移除大段原始索引表。",
    ]
    return {
        "cards_html": cards_html,
        "radar_html": radar_html,
        "heatmap_html": heatmap_html,
        "advantage_rows": advantage_rows,
        "project_items": project_items,
        "policy_items": policy_items,
        "insight_items": insight_items,
        "note": "将国际矿企多维对标从原始列表改为竞争力雷达图、供给压力热力图和关键结论卡，突出不同矿企的优势与差距。",
    }


def build_commodity_theme_analysis(
    commodity_price_analysis: dict[str, Any],
    official_commodity_frames: dict[str, pd.DataFrame],
) -> dict[str, Any]:
    label_map = {"gold": "黄金", "copper": "铜", "lithium": "锂"}
    metric_rows: list[dict[str, Any]] = []
    for key, label in label_map.items():
        frame = official_commodity_frames.get(key, pd.DataFrame())
        latest = latest_row(frame)
        metric_rows.append(
            {
                "label": label,
                "latest": as_float(latest.get("close")) if latest is not None else None,
                "date": str(latest.get("trade_date", "N/A")) if latest is not None else "N/A",
                "ret_5d": compute_return(frame["close"], 5) if not frame.empty and "close" in frame.columns else None,
                "ret_20d": compute_return(frame["close"], 20) if not frame.empty and "close" in frame.columns else None,
                "ret_60d": compute_return(frame["close"], 60) if not frame.empty and "close" in frame.columns else None,
                "drawdown_20d": compute_drawdown(frame["close"], 20) if not frame.empty and "close" in frame.columns else None,
                "vol_60d": annualized_volatility(frame),
            }
        )

    valid_ret20 = [item for item in metric_rows if item["ret_20d"] is not None]
    strongest = max(valid_ret20, key=lambda item: item["ret_20d"], default={"label": "N/A", "ret_20d": None})
    weakest = min(valid_ret20, key=lambda item: item["ret_20d"], default={"label": "N/A", "ret_20d": None})
    highest_vol = max(metric_rows, key=lambda item: item["vol_60d"] if item["vol_60d"] is not None else -10**9, default={"label": "N/A", "vol_60d": None})

    cards_html = (
        '<div class="cards compact">'
        + stat_card("最强品种", str(strongest.get("label", "N/A")), subtitle=f"20日 {fmt_signed_pct(strongest.get('ret_20d'))}", tone="positive")
        + stat_card("最弱品种", str(weakest.get("label", "N/A")), subtitle=f"20日 {fmt_signed_pct(weakest.get('ret_20d'))}", tone="negative")
        + stat_card("最高波动", str(highest_vol.get("label", "N/A")), subtitle=f"60日波动 {fmt_pct(highest_vol.get('vol_60d'))}")
        + stat_card("供给覆盖", commodity_price_analysis.get("supply_company_coverage", "0/50"))
        + stat_card("三年量化", str(commodity_price_analysis.get("supply_quantified_company_count", 0)))
        + "</div>"
    )

    strength_chart = build_svg_bar_chart(
        "核心矿产强弱对比",
        [item["label"] for item in metric_rows],
        [
            {"label": "5日", "key": "5日", "color": "#93c5fd", "values": [item["ret_5d"] for item in metric_rows]},
            {"label": "20日", "key": "20日", "color": "#2563eb", "values": [item["ret_20d"] for item in metric_rows]},
            {"label": "60日", "key": "60日", "color": "#1d4ed8", "values": [item["ret_60d"] for item in metric_rows]},
        ],
        chart_id="commodity-strength",
    )
    heatmap_html = build_svg_heatmap(
        "核心矿产波动与回撤热力图",
        [item["label"] for item in metric_rows],
        ["5日", "20日", "60日", "20日回撤", "60日波动"],
        [
            [
                abs(item["ret_5d"]) if item["ret_5d"] is not None else None,
                abs(item["ret_20d"]) if item["ret_20d"] is not None else None,
                abs(item["ret_60d"]) if item["ret_60d"] is not None else None,
                abs(item["drawdown_20d"]) if item["drawdown_20d"] is not None else None,
                item["vol_60d"],
            ]
            for item in metric_rows
        ],
    )

    spread_pairs = []
    spread_map = {item["label"]: item["ret_20d"] for item in metric_rows}
    for left, right in (("铜", "黄金"), ("锂", "铜"), ("锂", "黄金")):
        left_value = spread_map.get(left)
        right_value = spread_map.get(right)
        if left_value is None or right_value is None:
            continue
        spread_pairs.append(f"{left}相对{right}近20日强弱差 {fmt_signed_pct(left_value - right_value)}。")
    theme_rows = [
        [
            "趋势主线",
            f"{strongest.get('label', 'N/A')} 近20日最强，{weakest.get('label', 'N/A')} 相对偏弱。",
            "优先围绕最强品种判断紫金对应业务弹性，弱势品种只保留对冲解释。",
        ],
        [
            "强弱价差",
            spread_pairs[0] if spread_pairs else "当前强弱价差数据不足。",
            "强弱价差比绝对价格更适合跨品种比较。",
        ],
        [
            "历史波动",
            f"{highest_vol.get('label', 'N/A')} 的60日年化波动最高，为 {fmt_pct(highest_vol.get('vol_60d'))}。",
            "高波动品种需要结合国际矿企扩产节奏和紫金项目兑现节奏一起看。",
        ],
    ]
    supply_focus_rows = commodity_price_analysis.get("supply_summary_rows", [])
    event_focus_rows = commodity_price_analysis.get("event_rows", [])[:5]
    return {
        "cards_html": cards_html,
        "strength_chart": strength_chart,
        "heatmap_html": heatmap_html,
        "theme_rows": theme_rows,
        "supply_focus_rows": supply_focus_rows,
        "event_focus_rows": event_focus_rows,
        "insight_items": [
            f"当前价格主线由 {strongest.get('label', 'N/A')} 领跑，说明市场更偏向对应金属的供需或风险偏好逻辑。",
            spread_pairs[0] if spread_pairs else "跨品种强弱价差暂未形成明显偏向。",
            f"最高波动来自 {highest_vol.get('label', 'N/A')}，需要防止高波动品种在日报里用大量明细表稀释结论。",
        ],
        "note": "将价格验证板块压缩为趋势、强弱价差与历史波动三条主题线，仅保留支撑核心结论的关键数据。",
    }


def build_dollar_bond_analysis(
    dollar_index_df: pd.DataFrame,
    treasury_2y_df: pd.DataFrame,
    treasury_10y_df: pd.DataFrame,
    yield_curve_rows: list[list[str]],
    official_commodity_frames: dict[str, pd.DataFrame],
) -> dict[str, Any]:
    has_dollar = not dollar_index_df.empty
    has_treasury = not treasury_10y_df.empty or not treasury_2y_df.empty
    if not has_dollar and not has_treasury:
        return {"enabled": False}

    dollar_latest = latest_row(dollar_index_df)
    latest_10y = latest_row(treasury_10y_df)
    proxy_source = str(dollar_latest.get("proxy_source", "FRED")) if dollar_latest is not None else "FRED"
    proxy_source_map = {
        "FRED": "FRED 广义美元指数",
        "USDCNH": "USDCNH 替代口径",
        "CACHE": "本地缓存口径",
    }
    proxy_subtitle = proxy_source_map.get(proxy_source, proxy_source)
    dollar_label = "美元指数代理" if proxy_source == "FRED" else "美元强弱代理"
    spread_value = yield_curve_rows[2][2] if len(yield_curve_rows) >= 3 else "N/A"
    dollar_labels, dollar_norm = normalized_series(dollar_index_df)
    _, treasury_2y_norm = normalized_series(treasury_2y_df)
    treasury_labels, treasury_10y_norm = normalized_series(treasury_10y_df)
    chart_labels = dollar_labels or treasury_labels
    chart_series = []
    if dollar_norm:
        chart_series.append({"label": dollar_label, "key": dollar_label, "color": "#dc2626", "values": dollar_norm})
    if treasury_2y_norm:
        chart_series.append({"label": "美国2Y", "key": "美国2Y", "color": "#7c3aed", "values": treasury_2y_norm})
    if treasury_10y_norm:
        chart_series.append({"label": "美国10Y", "key": "美国10Y", "color": "#2563eb", "values": treasury_10y_norm})

    corr_gold = compute_correlation(dollar_index_df, official_commodity_frames.get("gold", pd.DataFrame()))
    corr_copper = compute_correlation(dollar_index_df, official_commodity_frames.get("copper", pd.DataFrame()))
    corr_ten_gold = compute_correlation(treasury_10y_df, official_commodity_frames.get("gold", pd.DataFrame()))
    cards_html = (
        '<div class="cards compact">'
        + stat_card("美元指数代理", fmt_num(dollar_latest.get("close") if dollar_latest is not None else None), subtitle=proxy_subtitle)
        + stat_card("美国10Y", fmt_pct(latest_10y.get("close") if latest_10y is not None else None, 2))
        + stat_card("10Y-2Y", spread_value, tone="negative" if str(spread_value).startswith("-") else "neutral")
        + stat_card("美元-黄金相关", fmt_num(corr_gold, 2))
        + "</div>"
    )
    relationship_rows = [
        ["美元 vs 黄金", fmt_num(corr_gold, 2), "负相关越强，越利于黄金走强逻辑成立。"],
        ["美元 vs 铜", fmt_num(corr_copper, 2), "若美元转弱且铜同步走强，通常对应风险偏好与需求修复。"],
        ["10Y vs 黄金", fmt_num(corr_ten_gold, 2), "长端利率上行通常压制黄金估值弹性。"],
        ["期限利差", str(spread_value), "利差倒挂或收窄会影响衰退定价与商品风险偏好。"],
    ]
    insight_items = [
        f"{proxy_subtitle}近20日 {fmt_signed_pct(compute_return(dollar_index_df['close'], 20) if has_dollar and 'close' in dollar_index_df.columns else None)}，需与黄金和铜价共同判断风险偏好切换。",
        f"美国10Y近20日 {fmt_signed_pct(compute_return(treasury_10y_df['close'], 20) if not treasury_10y_df.empty and 'close' in treasury_10y_df.columns else None)}，对黄金估值的压制/释放更直接。",
        "如果该模块无数据则在正式报表中自动隐藏，避免出现空板块。",
    ]
    return {
        "enabled": True,
        "cards_html": cards_html,
        "chart_html": build_svg_line_chart("美元与美债联动趋势", chart_labels, chart_series, chart_id="dollar-bond"),
        "relationship_rows": relationship_rows,
        "insight_items": insight_items,
        "note": f"保留美元强弱代理、美国10Y与期限利差，并补充其与黄金/铜的相关性；当前美元口径为 {proxy_subtitle}。",
    }


def render_html_report(config: dict[str, Any], fetcher: TushareFetcher, data: ReportData) -> str:
    _ = fetcher
    portfolio = config["portfolio"]
    focus_monitor = config.get("focus_monitor", {})
    row = latest_row(data.zijin_df)
    db_row = latest_row(data.daily_basic)
    shares = portfolio["shares"]
    cost_price = portfolio["cost_price"]
    total_cost = shares * cost_price

    close = as_float(row.get("close")) if row is not None else None
    realtime_quote = data.realtime_quote or {}
    current_price = as_float(realtime_quote.get("price"))
    current_pre_close = as_float(realtime_quote.get("pre_close"))
    current_basis_price = current_price if current_price is not None else close
    market_value = shares * current_basis_price if current_basis_price is not None else None
    pnl = market_value - total_cost if market_value is not None else None
    pnl_pct = (current_basis_price / cost_price - 1.0) * 100 if current_basis_price not in (None, 0) else None
    ma60 = as_float(row.get("ma60")) if row is not None else None
    drawdown_20d = as_float(row.get("drawdown_20d")) if row is not None else None
    pe_ttm = db_row.get("pe_ttm") if db_row is not None else None
    pb = db_row.get("pb") if db_row is not None else None
    current_change_pct = (
        (current_price / current_pre_close - 1.0) * 100
        if current_price is not None and current_pre_close not in (None, 0)
        else None
    )
    quote_time_text = " ".join(
        part for part in [str(realtime_quote.get("date") or "").strip(), str(realtime_quote.get("time") or "").strip()] if part
    ).strip()
    if current_price is not None:
        current_price_subtitle = quote_time_text or "实时行情"
        if current_pre_close is not None:
            current_price_subtitle = f"{current_price_subtitle} / 昨收 {fmt_money(current_pre_close)}"
    else:
        current_price_subtitle = "实时行情暂不可用，已降级为收盘口径"
    valuation_basis_text = f"{shares:,} 股 · {'当前价口径' if current_price is not None else '收盘价口径'}"

    summary_cards = (
        '<div class="cards">'
        + stat_card("最新收盘", fmt_money(close), subtitle=f"交易日 {row.get('trade_date', 'N/A') if row is not None else 'N/A'}")
        + stat_card("当前价", fmt_money(current_price), subtitle=current_price_subtitle, tone=css_change_class(current_change_pct))
        + stat_card("当前市值", fmt_money(market_value), subtitle=valuation_basis_text)
        + stat_card("浮动盈亏", fmt_money(pnl), subtitle=fmt_signed_pct(pnl_pct), tone=css_change_class(pnl_pct))
        + stat_card("60日均线", fmt_money(ma60), subtitle="右侧趋势观察")
        + stat_card("近20日回撤", fmt_signed_pct(drawdown_20d), subtitle="高点回撤", tone=css_change_class(drawdown_20d))
        + stat_card("PE / PB", f"{fmt_num(pe_ttm)} / {fmt_num(pb)}", subtitle="估值快照")
        + "</div>"
    )

    commodity_price_analysis = data.commodity_price_analysis or {}
    revenue_structure_analysis = data.revenue_structure_analysis or {}
    revenue_forecast_analysis = data.revenue_forecast_analysis or {}
    central_bank_gold_analysis = data.central_bank_gold_analysis or {}
    international_peer_analysis = build_international_peer_analysis(data.policy_entries)

    price_labels, price_series = price_chart_series(data.zijin_df)
    _, zijin_norm = normalized_series(data.zijin_df)
    _, gold_norm = normalized_series(data.gold_proxy_df)
    copper_df = data.future_frames.get("铜主力", pd.DataFrame())
    _, copper_norm = normalized_series(copper_df)
    compare_series = []
    if zijin_norm:
        compare_series.append({"label": "紫金矿业", "color": "#2563eb", "values": zijin_norm})
    if gold_norm:
        compare_series.append({"label": "黄金ETF代理", "color": "#f59e0b", "values": gold_norm})
    if copper_norm:
        compare_series.append({"label": "铜主力", "color": "#10b981", "values": copper_norm})

    fx_trend = pd.DataFrame()
    if not data.fx_df.empty:
        fx_trend = data.fx_df.copy()
        if "bid_close" in fx_trend.columns:
            fx_trend["close"] = pd.to_numeric(fx_trend["bid_close"], errors="coerce")
        elif "ask_close" in fx_trend.columns:
            fx_trend["close"] = pd.to_numeric(fx_trend["ask_close"], errors="coerce")
        fx_trend = sort_by_column(fx_trend, "trade_date")
    _, fx_norm = normalized_series(fx_trend)
    nasdaq_df = data.global_index_frames.get("纳斯达克", pd.DataFrame())
    a50_df = data.global_index_frames.get("富时A50", pd.DataFrame())
    _, nasdaq_norm = normalized_series(nasdaq_df)
    _, a50_norm = normalized_series(a50_df)
    macro_series = []
    if gold_norm:
        macro_series.append({"label": "黄金ETF代理", "color": "#f59e0b", "values": gold_norm})
    if fx_norm:
        macro_series.append({"label": "USDCNH", "color": "#dc2626", "values": fx_norm})
    if nasdaq_norm:
        macro_series.append({"label": "纳斯达克", "color": "#2563eb", "values": nasdaq_norm})
    if a50_norm:
        macro_series.append({"label": "富时A50", "color": "#10b981", "values": a50_norm})

    shibor_trend = pd.DataFrame()
    if not data.shibor_df.empty and "date" in data.shibor_df.columns:
        shibor_trend = data.shibor_df.copy()
        shibor_trend["trade_date"] = shibor_trend["date"]
        if "3m" in shibor_trend.columns:
            shibor_trend["close"] = pd.to_numeric(shibor_trend["3m"], errors="coerce")
        shibor_trend = sort_by_column(shibor_trend, "trade_date")
    _, shibor_norm = normalized_series(shibor_trend)
    yc_trend = pd.DataFrame()
    if not data.yc_df.empty and "yield" in data.yc_df.columns:
        yc_trend = data.yc_df.copy()
        yc_trend["close"] = pd.to_numeric(yc_trend["yield"], errors="coerce")
        yc_trend = sort_by_column(yc_trend, "trade_date")
    _, yc_norm = normalized_series(yc_trend)
    rate_series = []
    if shibor_norm:
        rate_series.append({"label": "SHIBOR 3M", "color": "#7c3aed", "values": shibor_norm})
    if yc_norm:
        rate_series.append({"label": "中债10Y", "color": "#0f766e", "values": yc_norm})
    if gold_norm:
        rate_series.append({"label": "黄金ETF代理", "color": "#f59e0b", "values": gold_norm})

    precious_panels = []
    precious_overview_rows: list[list[str]] = []
    precious_colors = {"黄金主力": "#f59e0b", "铜主力": "#b45309", "锂指数代理": "#8b5cf6"}
    for label, frame in data.precious_frames.items():
        snapshot = price_snapshot(label, frame)
        if snapshot:
            precious_overview_rows.append(snapshot)
        timeframe_map = build_timeframe_map(frame)
        precious_panels.append(
            render_timeframe_chart_panel(
                f"{label}多周期走势",
                f"precious-{label}",
                timeframe_map,
                label,
                precious_colors.get(label, "#2563eb"),
                guides=compute_support_resistance(frame),
            )
        )

    sector_compare_items = []
    metals_compare_map = {
        "黄金主力": build_timeframe_map(data.precious_frames.get("黄金主力", pd.DataFrame())),
        "铜主力": build_timeframe_map(data.precious_frames.get("铜主力", pd.DataFrame())),
    }
    sector_colors = {"AI": "#2563eb", "芯片": "#10b981", "通信": "#ec4899", "电力": "#f97316"}
    sector_snapshot_rows: list[list[str]] = []
    for label, frame in data.theme_frames.items():
        snapshot = price_snapshot(label, frame)
        if snapshot:
            sector_snapshot_rows.append(snapshot)
        sector_compare_items.append(
            render_timeframe_chart_panel(
                f"{label} 与贵金属对比",
                f"theme-{label}",
                build_timeframe_map(frame),
                label,
                sector_colors.get(label, "#2563eb"),
                extra_series=[
                    ("黄金主力", metals_compare_map["黄金主力"], "#f59e0b"),
                    ("铜主力", metals_compare_map["铜主力"], "#b45309"),
                ],
            )
        )

    dollar_labels, dollar_norm = normalized_series(data.dollar_index_df)
    treasury_curve_norm = []
    treasury_10y_norm = []
    treasury_2y_df = pd.DataFrame()
    treasury_10y_df = pd.DataFrame()
    yield_curve_rows: list[list[str]] = []
    yield_curve_labels: list[str] = []
    yield_curve_values: list[float] = []
    if not data.treasury_curve_df.empty:
        if "y2" in data.treasury_curve_df.columns:
            treasury_2y_df = data.treasury_curve_df[["trade_date", "y2"]].rename(columns={"y2": "close"}).dropna()
        if "y10" in data.treasury_curve_df.columns:
            treasury_10y_df = data.treasury_curve_df[["trade_date", "y10"]].rename(columns={"y10": "close"}).dropna()
        normalized_series(treasury_2y_df)
        _, treasury_10y_norm = normalized_series(treasury_10y_df)
        treasury_curve_norm = treasury_10y_norm
        latest_curve = latest_row(data.treasury_curve_df)
        if latest_curve is not None:
            spread = None
            if as_float(latest_curve.get("y10")) is not None and as_float(latest_curve.get("y2")) is not None:
                spread = as_float(latest_curve.get("y10")) - as_float(latest_curve.get("y2"))
            yield_curve_rows = [
                ["美国2Y", str(latest_curve.get("trade_date", "N/A")), fmt_pct(latest_curve.get("y2"), 2), "短端基准"],
                ["美国10Y", str(latest_curve.get("trade_date", "N/A")), fmt_pct(latest_curve.get("y10"), 2), "长端基准"],
                ["10Y-2Y利差", str(latest_curve.get("trade_date", "N/A")), fmt_pct(spread, 2), "期限利差"],
            ]
            for label, key in (("3M", "m3"), ("1Y", "y1"), ("2Y", "y2"), ("10Y", "y10"), ("30Y", "y30")):
                value = as_float(latest_curve.get(key))
                if value is None:
                    continue
                yield_curve_labels.append(label)
                yield_curve_values.append(value)

    boe_labels, boe_norm = normalized_series(data.boe_rate_df)
    policy_rate_compare = []
    if dollar_norm:
        policy_rate_compare.append({"label": "美元指数代理", "key": "美元指数代理", "color": "#dc2626", "values": dollar_norm})
    if treasury_curve_norm:
        policy_rate_compare.append({"label": "美国10Y", "key": "美国10Y", "color": "#2563eb", "values": treasury_curve_norm})
    if boe_norm:
        policy_rate_compare.append({"label": "英国央行利率", "key": "英国央行利率", "color": "#10b981", "values": boe_norm})
    policy_compare_labels = dollar_labels or treasury_10y_df.get("trade_date", pd.Series(dtype=str)).tolist() or boe_labels

    policy_timeline_rows = [
        [
            str(item.get("date", "")),
            str(item.get("institution", "")),
            str(item.get("action", "")),
            str(item.get("rate", "")),
            str(item.get("title", ""))[:72],
        ]
        for item in data.policy_entries[:12]
    ]

    research_org_counter: dict[str, int] = {}
    research_tag_counter: dict[str, int] = {}
    for item in data.research_entries:
        org = str(item.get("institution") or item.get("org_name") or "未知来源")
        research_org_counter[org] = research_org_counter.get(org, 0) + 1
        for tag in item.get("tags", []):
            research_tag_counter[str(tag)] = research_tag_counter.get(str(tag), 0) + 1
    research_org_rows = [
        [org, str(count)]
        for org, count in sorted(research_org_counter.items(), key=lambda pair: pair[1], reverse=True)[:8]
    ]
    research_tag_rows = [
        [tag, str(count)]
        for tag, count in sorted(research_tag_counter.items(), key=lambda pair: pair[1], reverse=True)[:10]
    ]
    research_recent_count = sum(1 for item in data.research_entries if str(item.get("date", "")) >= days_ago_str(30))
    research_alert_rows = [
        [
            str(item.get("date", "")),
            str(item.get("core_theme", "")),
            str(item.get("institution", "")),
            str(item.get("credibility", "")),
            str(item.get("title", ""))[:72],
        ]
        for item in data.research_alerts[:10]
    ]
    research_summary_cards = (
        '<div class="cards compact">'
        + stat_card("研报/资讯条目", str(len(data.research_entries)))
        + stat_card("覆盖机构", str(len(research_org_counter)))
        + stat_card("近30天新增", str(research_recent_count), tone="positive" if research_recent_count else "neutral")
        + stat_card("本次新增提醒", str(len(data.research_alerts)), tone="positive" if data.research_alerts else "neutral")
        + stat_card("热门主题", next(iter(research_tag_counter.keys()), "N/A"))
        + "</div>"
    )

    policy_action_counter: dict[str, int] = {}
    for item in data.policy_entries:
        action = str(item.get("action", "观察"))
        policy_action_counter[action] = policy_action_counter.get(action, 0) + 1
    latest_policy_item = data.policy_entries[0] if data.policy_entries else {}
    policy_alert_items = []
    if latest_policy_item:
        policy_alert_items.append(
            f"最近政策事件：{latest_policy_item.get('date', 'N/A')} {latest_policy_item.get('institution', '')}{latest_policy_item.get('action', '')}，利率 {latest_policy_item.get('rate', 'N/A')}。"
        )
    if yield_curve_rows:
        policy_alert_items.append(f"当前美债期限利差：{yield_curve_rows[-1][2]}，用于跟踪衰退预期与风险偏好切换。")
    if dollar_norm:
        policy_alert_items.append(
            f"美元指数代理近20日表现 {fmt_signed_pct(compute_return(data.dollar_index_df['close'], 20) if not data.dollar_index_df.empty else None)}，需与黄金和铜价联动复核。"
        )
    policy_summary_cards = (
        '<div class="cards compact">'
        + stat_card("政策事件库", str(len(data.policy_entries)))
        + stat_card("加息事件", str(policy_action_counter.get("加息", 0)), tone="negative" if policy_action_counter.get("加息", 0) else "neutral")
        + stat_card("降息事件", str(policy_action_counter.get("降息", 0)), tone="positive" if policy_action_counter.get("降息", 0) else "neutral")
        + stat_card("维持事件", str(policy_action_counter.get("维持", 0)))
        + "</div>"
    )

    linked_gold_news = [
        item
        for item in data.research_entries
        if any(tag in item.get("tags", []) for tag in ("黄金", "央行政策", "央行购金"))
    ][:8]
    central_bank_tracking_cards = (
        '<div class="cards compact">'
        + stat_card("最新已披露月份", str(central_bank_gold_analysis.get("latest_month_label", "N/A")))
        + stat_card("全球净购金", fmt_num(central_bank_gold_analysis.get("latest_global_tonnes"), 1, "t"), tone="positive" if as_float(central_bank_gold_analysis.get("latest_global_tonnes")) not in (None, 0) and as_float(central_bank_gold_analysis.get("latest_global_tonnes")) > 0 else "neutral")
        + stat_card("中国当月增持", fmt_num(central_bank_gold_analysis.get("latest_china_tonnes"), 1, "t"), tone="positive" if as_float(central_bank_gold_analysis.get("latest_china_tonnes")) not in (None, 0) and as_float(central_bank_gold_analysis.get("latest_china_tonnes")) > 0 else "neutral")
        + stat_card("中国年内累计", fmt_num(central_bank_gold_analysis.get("china_ytd_tonnes"), 1, "t"))
        + stat_card("中国连续购金", f"{central_bank_gold_analysis.get('china_consecutive_months') if central_bank_gold_analysis.get('china_consecutive_months') is not None else 'N/A'}个月")
        + "</div>"
    )

    position_rows = []
    if row is not None:
        position_rows = [
            ["持仓股数", f"{shares:,} 股"],
            ["持仓成本", fmt_money(cost_price)],
            ["总成本", fmt_money(total_cost)],
            ["最新收盘", fmt_money(close)],
            ["当前价", fmt_money(current_price)],
            ["最新市值", fmt_money(market_value)],
            ["浮动盈亏", fmt_money(pnl)],
            ["盈亏比例", fmt_signed_pct(pnl_pct)],
            ["估值口径", "当前价" if current_price is not None else "收盘价降级"],
            ["5日涨跌幅", fmt_signed_pct(row.get("ret_5d"))],
            ["20日涨跌幅", fmt_signed_pct(row.get("ret_20d"))],
            ["5日均线", fmt_money(row.get("ma5"))],
            ["20日均线", fmt_money(row.get("ma20"))],
            ["60日均线", fmt_money(ma60)],
        ]

    signal_items = []
    if row is not None:
        prev = prev_row(data.zijin_df)
        prev_ma60 = as_float(prev.get("ma60")) if prev is not None else None
        trigger_ma60 = ma60 is not None and prev_ma60 is not None and close is not None and close < ma60 and ma60 < prev_ma60
        trigger_drawdown = drawdown_20d is not None and drawdown_20d <= -10
        signal_items.append("已触发60日均线右侧减仓观察。" if trigger_ma60 else "60日均线右侧减仓信号暂未触发。")
        signal_items.append("近20日回撤已超过10%，重点看反弹力度。" if trigger_drawdown else "近20日回撤未达到10%警戒。")
        signal_items.append("当前仍在盈利区间，优先坚持右侧止盈。" if close is not None and close > cost_price else "当前不在明显盈利区，优先做逻辑复盘。")

    moneyflow_rows = []
    mf_row = latest_row(data.moneyflow)
    if mf_row is not None:
        moneyflow_rows = [
            ["小单净流入(万元)", fmt_num(mf_row.get("buy_sm_amount"), 2)],
            ["中单净流入(万元)", fmt_num(mf_row.get("buy_md_amount"), 2)],
            ["大单净流入(万元)", fmt_num(mf_row.get("buy_lg_amount"), 2)],
            ["特大单净流入(万元)", fmt_num(mf_row.get("buy_elg_amount"), 2)],
            ["卖出小单(万元)", fmt_num(mf_row.get("sell_sm_amount"), 2)],
            ["卖出大单(万元)", fmt_num(mf_row.get("sell_lg_amount"), 2)],
        ]

    gold_rows: list[list[str]] = []
    gold_snapshot = price_snapshot("黄金ETF代理", data.gold_proxy_df)
    if gold_snapshot:
        gold_rows.append(gold_snapshot)
    for label, df in data.future_frames.items():
        snapshot = price_snapshot(label, df)
        if snapshot:
            gold_rows.append(snapshot)

    ann_rows = frame_rows(
        data.anns,
        5,
        lambda item: [str(item.get("ann_date", "")), str(item.get("title", ""))[:80]],
    )
    holder_rows = frame_rows(
        data.holder_trade,
        5,
        lambda item: [
            str(item.get("ann_date", "")),
            str(item.get("holder_name", ""))[:24],
            str(item.get("in_de", "")),
            fmt_num(item.get("change_ratio")),
        ],
    )
    forecast_rows = frame_rows(
        data.forecast,
        3,
        lambda item: [
            str(item.get("ann_date", "")),
            str(item.get("type", "")),
            str(item.get("summary", ""))[:60],
        ],
    )
    express_rows = frame_rows(
        data.express,
        3,
        lambda item: [
            str(item.get("ann_date", "")),
            fmt_num(item.get("revenue"), 0),
            fmt_num(item.get("n_income"), 0),
            fmt_signed_pct(item.get("dt_netprofit_yoy")),
        ],
    )
    disclosure_rows = frame_rows(
        data.disclosure,
        3,
        lambda item: [
            str(item.get("end_date", "")),
            str(item.get("ann_date", "")),
            str(item.get("pre_date", "")),
            str(item.get("actual_date", "")),
        ],
    )

    fi_row = latest_row(data.fina_indicator)
    inc_row = latest_row(data.income)
    cfo_row = latest_row(data.cashflow)
    div_row = latest_row(data.dividend)

    quarter_rows = []
    latest_fin_row = fi_row if fi_row is not None else inc_row if inc_row is not None else cfo_row
    if latest_fin_row is not None:
        quarter_rows = [
            ["最新报告期", str(latest_fin_row.get("end_date", "N/A"))],
            ["ROE", fmt_pct(fi_row.get("roe")) if fi_row is not None else "N/A"],
            ["毛利率", fmt_pct(fi_row.get("grossprofit_margin")) if fi_row is not None else "N/A"],
            ["资产负债率", fmt_pct(fi_row.get("debt_to_assets")) if fi_row is not None else "N/A"],
            ["营业收入", fmt_num(inc_row.get("revenue"), 0) if inc_row is not None else "N/A"],
            ["归母净利润", fmt_num(inc_row.get("n_income_attr_p"), 0) if inc_row is not None else "N/A"],
            ["经营现金流净额", fmt_num(cfo_row.get("n_cashflow_act"), 0) if cfo_row is not None else "N/A"],
            ["每股分红", fmt_num(div_row.get("cash_div"), 4) if div_row is not None else "N/A"],
        ]

    financial_series_items = []
    revenue_series = extract_financial_trend(data.income, "营业收入(亿元)", "revenue", scale=1e8)
    profit_series = extract_financial_trend(data.income, "归母净利润(亿元)", "n_income_attr_p", scale=1e8)
    cashflow_series = extract_financial_trend(data.cashflow, "经营现金流(亿元)", "n_cashflow_act", scale=1e8)
    for item, color in (
        (revenue_series, "#2563eb"),
        (profit_series, "#10b981"),
        (cashflow_series, "#f59e0b"),
    ):
        if item:
            financial_series_items.append(
                {"label": item["label"], "color": color, "values": item["values"], "labels": item["labels"]}
            )
    financial_labels = join_chart_labels(financial_series_items)
    financial_chart_series = [
        {"label": item["label"], "color": item["color"], "values": item["values"]}
        for item in financial_series_items
    ]

    weekly_rows = [
        [
            "紫金矿业",
            fmt_signed_pct(compute_return(data.zijin_df["close"], 5) if not data.zijin_df.empty else None),
            fmt_signed_pct(compute_return(data.zijin_df["close"], 20) if not data.zijin_df.empty else None),
            fmt_signed_pct(compute_drawdown(data.zijin_df["close"], 20) if not data.zijin_df.empty else None),
            "核心仓趋势跟踪",
        ],
        [
            "黄金ETF代理",
            fmt_signed_pct(compute_return(data.gold_proxy_df["close"], 5) if not data.gold_proxy_df.empty else None),
            fmt_signed_pct(compute_return(data.gold_proxy_df["close"], 20) if not data.gold_proxy_df.empty else None),
            fmt_signed_pct(compute_drawdown(data.gold_proxy_df["close"], 20) if not data.gold_proxy_df.empty else None),
            "黄金主逻辑热度",
        ],
    ]
    for label, df in data.future_frames.items():
        weekly_rows.append(
            [
                label,
                fmt_signed_pct(compute_return(df["close"], 5) if not df.empty else None),
                fmt_signed_pct(compute_return(df["close"], 20) if not df.empty else None),
                fmt_signed_pct(compute_drawdown(df["close"], 20) if not df.empty else None),
                "资源品趋势代理",
            ]
        )

    strategy_items = []
    if close is None:
        strategy_items.append("未获取到最新收盘价，先检查行情抓取状态。")
    elif close > 30:
        strategy_items.append("股价位于30元以上超额利润区，重点观察右侧减仓信号。")
    elif cost_price <= close <= 30:
        strategy_items.append("股价位于安全边际区间，按兵不动，等待趋势进一步明朗。")
    elif 24 <= close < cost_price:
        strategy_items.append("股价位于浮亏观察区，不恐慌、不补仓。")
    else:
        strategy_items.append("跌破23.99元以下时，不自动卖出，优先复核四大逻辑。")
    strategy_items.extend(
        [
            f"默认每次机动操作 {portfolio['trim_unit']:,} 股，底仓下限 {portfolio['core_position_floor']:.0%}。",
            "若跌破60日线且均线拐头向下，或金铜趋势同步走弱，进入右侧减仓观察。",
            "不设置自动价格止损，以逻辑止损替代机械止损。",
        ]
    )

    logic_items = config["logic_monitor"]["rules"] + [
        f"当以上反向信号中至少 {config['logic_monitor']['exit_threshold']} 项被确认时，重新评估持仓逻辑。"
    ]

    macro_logic_cards = ""
    for item in focus_monitor.get("macro_logic", []):
        macro_logic_cards += list_card(item["title"], item["summary"], item.get("watch_points", []))

    micro_logic_cfg = focus_monitor.get("micro_logic", {})
    micro_logic_cards = ""
    for item in micro_logic_cfg.get("support_points", []):
        micro_logic_cards += list_card(item["title"], item["summary"], item.get("watch_points", []))

    production_rows = [
        [
            item["product"],
            item["actual_2025"],
            item["target_2026"],
            item["target_2028"],
            item["growth_range"],
        ]
        for item in micro_logic_cfg.get("production_targets", [])
    ]

    commodity_theme_analysis = build_commodity_theme_analysis(commodity_price_analysis, data.official_commodity_frames)

    revenue_cards = (
        '<div class="cards compact">'
        + stat_card("当前拆分板块", str(len(revenue_structure_analysis.get("current_rows", []))))
        + stat_card("5年趋势", str(len(revenue_structure_analysis.get("trend_labels", []))))
        + stat_card("8期对比", str(len(revenue_structure_analysis.get("period_labels", []))))
        + stat_card("披露口径", "审计+估算")
        + "</div>"
    )

    forecast_cards = (
        '<div class="cards compact">'
        + stat_card("预测季度", str(len(revenue_forecast_analysis.get("labels", []))))
        + stat_card("核心假设", str(len(revenue_forecast_analysis.get("assumption_rows", []))))
        + stat_card("区间测算", str(len(revenue_forecast_analysis.get("range_rows", []))))
        + stat_card("模型口径", "价格×产量")
        + "</div>"
    )

    dollar_bond_analysis = build_dollar_bond_analysis(
        data.dollar_index_df,
        treasury_2y_df,
        treasury_10y_df,
        yield_curve_rows,
        data.official_commodity_frames,
    )
    global_overview_rows = [
        [
            "紫金当日定位",
            f"当前价 {fmt_money(current_price)}，浮盈 {fmt_money(pnl)}，20日回撤 {fmt_signed_pct(drawdown_20d)}。",
            "先判断价格是否仍处于成本线以上，再决定是否需要进入右侧减仓观察。",
            "盘中刷新后优先确认当前价口径是否有效。",
        ],
        [
            "国际竞争格局",
            international_peer_analysis.get("insight_items", ["国际矿企数据库已接入日报。"])[1],
            "高集中度赛道更容易被头部矿企扩产或项目延期重定价。",
            "重点盯住雷达图与供给热力图中的高分矿企。",
        ],
        [
            "核心矿产环境",
            commodity_theme_analysis.get("insight_items", ["核心矿产主题分析已生成。"])[0],
            "价格主线决定紫金金/铜/锂三条业务链的利润弹性排序。",
            "只跟踪最强品种、最大波动品种与供给覆盖变化。",
        ],
        [
            "美元与利率",
            dollar_bond_analysis.get("insight_items", ["美元与美债模块暂无新增结论。"])[0] if dollar_bond_analysis.get("enabled") else "美元与美债数据不足，正式版已自动隐藏空板块。",
            "美元与长端利率主要影响黄金估值，其次影响铜的风险偏好定价。",
            "若美元走弱且10Y回落，更有利于黄金业务情绪修复。",
        ],
    ]
    impact_rows = [
        ["国际矿企扩产", "头部矿企投产爬坡决定未来供给兑现节奏", "影响紫金同类项目估值锚与市场预期", "对照国际矿企热力图看紫金扩产位置"],
        ["核心矿产价格", "价格强弱与波动决定利润弹性排序", "金/铜/锂业务对盈利与估值的贡献权重变化", "只保留趋势最强、波动最高与供给覆盖三个结论"],
        ["美元与长端利率", "影响黄金估值与资源股风险偏好", "黄金链条受影响最直接，铜受风险偏好传导更明显", "联动看美元-黄金、10Y-黄金相关性"],
        ["公司经营与预测", "产量目标和收入预测连接市场价格与项目兑现", "决定日报的业务参考价值是否可落地", "用营收结构和两季度预测验证核心结论"],
    ]
    outlook_items = [
        "先看紫金当日价格与成本线、60日线的位置关系，再决定是否进入右侧减仓观察。",
        "国际矿企部分只保留高集中度赛道、代表矿企评分和关键项目动向，不再展示大段索引表。",
        "核心矿产只保留趋势、强弱价差与波动三条主线，删除月均表和分散列表。",
        "美元与美债模块仅在有数据时显示，并用其解释黄金与铜的定价环境；无数据时自动隐藏。",
    ]

    styles = """
body{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;background:#f3f6fb;color:#1f2937}
.container{max-width:1360px;margin:0 auto;padding:24px}
.hero{background:linear-gradient(135deg,#0f172a,#1d4ed8);color:#fff;padding:28px 32px;border-radius:20px;box-shadow:0 20px 60px rgba(15,23,42,.25)}
.hero h1{margin:0 0 8px;font-size:30px}
.hero-meta{display:flex;gap:18px;flex-wrap:wrap;font-size:14px;opacity:.92}
.hero-brief{margin-top:14px;font-size:14px;line-height:1.7;max-width:920px;color:rgba(255,255,255,.92)}
.hero-actions{display:flex;gap:12px;flex-wrap:wrap;align-items:center;margin-top:18px}
.action-btn{border:1px solid rgba(255,255,255,.28);background:rgba(255,255,255,.14);color:#fff;border-radius:12px;padding:10px 16px;font-size:13px;font-weight:700;cursor:pointer;transition:all .2s ease}
.action-btn:hover{background:rgba(255,255,255,.22)}
.action-btn:disabled{opacity:.72;cursor:wait}
.refresh-status{font-size:13px;opacity:.92}
.refresh-status.error{color:#fecaca}
.refresh-status.success{color:#bbf7d0}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:16px;margin:22px 0}
.cards.compact{grid-template-columns:repeat(auto-fit,minmax(150px,1fr))}
.card{background:#fff;border-radius:18px;padding:18px 18px 16px;box-shadow:0 10px 30px rgba(15,23,42,.08);border:1px solid #e5e7eb}
.card.positive{border-color:#bbf7d0;background:linear-gradient(180deg,#fff,#f0fdf4)}
.card.negative{border-color:#fecaca;background:linear-gradient(180deg,#fff,#fef2f2)}
.card-title{font-size:13px;color:#6b7280;margin-bottom:8px}
.card-value{font-size:28px;font-weight:700;line-height:1.15}
.card-subtitle{margin-top:8px;font-size:12px;color:#6b7280}
.section{margin-top:24px;background:#fff;border-radius:20px;padding:22px;box-shadow:0 10px 30px rgba(15,23,42,.08);border:1px solid #e5e7eb}
.section h2{margin:0 0 16px;font-size:22px}
.section h3{margin:20px 0 12px;font-size:16px}
.grid-2{display:grid;grid-template-columns:1.1fr .9fr;gap:18px}
.grid-3{display:grid;grid-template-columns:repeat(3,1fr);gap:18px}
.chart-card{background:#f8fafc;border:1px solid #e5e7eb;border-radius:18px;padding:14px}
.chart-title{font-size:14px;font-weight:700;margin-bottom:8px}
.chart-svg{width:100%;height:auto;display:block}
.grid-line{stroke:#dbeafe;stroke-width:1}
.axis-label{font-size:11px;fill:#64748b}
.event-line{stroke:#cbd5e1;stroke-width:1.2;stroke-dasharray:4 4}
.event-label{font-size:10px;fill:#475569}
.point-marker{fill:#fff;stroke:#1d4ed8;stroke-width:1.5}
.point-label{font-size:10px;fill:#334155}
.donut-layout{display:grid;grid-template-columns:360px 1fr;gap:18px;align-items:center}
.donut-legend{display:flex;flex-direction:column;gap:10px}
.donut-legend-row{display:grid;grid-template-columns:14px 1fr auto;gap:10px;align-items:center;font-size:13px;color:#334155}
.donut-total{font-size:22px;font-weight:700;fill:#0f172a}
.legend{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:8px}
.legend-item{display:inline-flex;align-items:center;gap:6px;font-size:12px;color:#475569;background:transparent;border:none;padding:0;cursor:pointer}
.legend-item.off{opacity:.45}
.legend-dot{width:10px;height:10px;border-radius:999px;display:inline-block}
.logic-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px}
.logic-card{background:#f8fafc;border:1px solid #e5e7eb;border-radius:18px;padding:16px}
.logic-title{font-size:15px;font-weight:700;margin-bottom:8px;color:#0f172a}
.logic-summary{font-size:13px;color:#475569;margin-bottom:10px;line-height:1.6}
.chart-switcher{background:#f8fafc;border:1px solid #e5e7eb;border-radius:18px;padding:14px}
.switcher-head{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;margin-bottom:10px}
.time-tabs{display:flex;gap:8px;flex-wrap:wrap}
.time-btn{border:1px solid #cbd5e1;background:#fff;color:#334155;border-radius:999px;padding:6px 12px;font-size:12px;cursor:pointer}
.time-btn.active{background:#1d4ed8;color:#fff;border-color:#1d4ed8}
.time-panel{display:none}
.time-panel.active{display:block}
.filter-bar{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:14px}
.filter-input{flex:1 1 280px;border:1px solid #cbd5e1;border-radius:12px;padding:10px 12px;font-size:13px;background:#fff}
.filter-clear{border:1px solid #cbd5e1;background:#fff;border-radius:12px;padding:10px 14px;font-size:13px;cursor:pointer}
.info-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px}
.info-card{background:#f8fafc;border:1px solid #e5e7eb;border-radius:16px;padding:14px}
.info-head{display:flex;justify-content:space-between;gap:10px;align-items:center;margin-bottom:8px;font-size:12px}
.info-source{display:inline-flex;align-items:center;gap:6px;padding:4px 8px;background:#dbeafe;color:#1d4ed8;border-radius:999px;font-weight:600}
.info-title{font-size:14px;font-weight:700;line-height:1.5;margin-bottom:8px}
.info-summary{font-size:13px;color:#475569;line-height:1.6;min-height:42px}
.dual-text .text-secondary{display:none;color:#64748b}
.dual-text.show-original .text-primary{display:none}
.dual-text.show-original .text-secondary{display:block}
.translation-toggle{margin-left:auto}
.tag-row{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0}
.tag{display:inline-flex;align-items:center;padding:4px 8px;border-radius:999px;background:#e2e8f0;color:#334155;font-size:12px}
.tag.action{background:#fee2e2;color:#b91c1c}
.info-link{display:inline-block;margin-top:10px;font-size:12px;color:#1d4ed8;text-decoration:none}
.section-note{font-size:13px;color:#64748b;margin:-4px 0 14px}
.executive-list{margin:0;padding-left:18px}
.executive-list li{margin:10px 0;line-height:1.7}
.status-board{display:flex;flex-direction:column;gap:16px}
.status-detail{background:#f8fafc;border:1px solid #e5e7eb;border-radius:16px;padding:12px 14px}
.status-detail summary{cursor:pointer;font-weight:700;color:#334155}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{padding:10px 12px;border-bottom:1px solid #e5e7eb;text-align:left;vertical-align:top}
th{background:#f8fafc;color:#475569;font-weight:700}
tr:hover td{background:#fafcff}
ul{margin:0;padding-left:20px}
li{margin:8px 0}
.empty{padding:18px;color:#6b7280;background:#f8fafc;border:1px dashed #cbd5e1;border-radius:12px}
.muted{color:#6b7280}
.footer{margin:26px 0 8px;text-align:center;color:#64748b;font-size:12px}
@media (max-width:960px){.grid-2,.grid-3,.donut-layout{grid-template-columns:1fr}.container{padding:16px}.hero{padding:22px}.switcher-head{align-items:flex-start}}
"""

    scripts = """
document.addEventListener("click", function(event) {
  const timeBtn = event.target.closest(".time-btn");
  if (timeBtn) {
    const panelId = timeBtn.dataset.timePanel;
    const timeframe = timeBtn.dataset.timeframe;
    document.querySelectorAll('.time-btn[data-time-panel="' + panelId + '"]').forEach(function(node) {
      node.classList.toggle("active", node === timeBtn);
    });
    document.querySelectorAll('.time-panel[data-panel-id="' + panelId + '"]').forEach(function(node) {
      node.classList.toggle("active", node.dataset.timeframe === timeframe);
    });
    return;
  }

  const legendBtn = event.target.closest(".legend-toggle");
  if (legendBtn) {
    const chartId = legendBtn.dataset.targetChart;
    const seriesKey = legendBtn.dataset.targetSeries;
    const disable = !legendBtn.classList.contains("off");
    legendBtn.classList.toggle("off", disable);
    document.querySelectorAll("polyline[data-chart-id]").forEach(function(line) {
      if (line.dataset.chartId === chartId && line.dataset.seriesKey === seriesKey) {
        line.style.opacity = disable ? "0.15" : "1";
      }
    });
    document.querySelectorAll("rect[data-chart-id]").forEach(function(bar) {
      if (bar.dataset.chartId === chartId && bar.dataset.seriesKey === seriesKey) {
        bar.style.opacity = disable ? "0.15" : "1";
      }
    });
    return;
  }

  const resetBtn = event.target.closest("[data-filter-reset]");
  if (resetBtn) {
    const sectionId = resetBtn.dataset.filterReset;
    const input = document.getElementById(sectionId + "-search");
    if (input) {
      input.value = "";
      applyFilter(input);
    }
    return;
  }

  const translationBtn = event.target.closest(".translation-toggle");
  if (translationBtn) {
    const toggleId = translationBtn.dataset.toggleId;
    document.querySelectorAll('.dual-text[data-toggle-id="' + toggleId + '"]').forEach(function(node) {
      node.classList.toggle("show-original");
    });
  }
});

document.addEventListener("input", function(event) {
  if (event.target.classList.contains("filter-input")) {
    applyFilter(event.target);
  }
});

function applyFilter(input) {
  const sectionId = input.id.replace(/-search$/, "");
  const query = input.value.trim().toLowerCase();
  const grid = document.getElementById(sectionId);
  if (!grid) {
    return;
  }
  grid.querySelectorAll(".info-card").forEach(function(card) {
    const haystack = [
      card.dataset.filterSource || "",
      card.dataset.filterDate || "",
      card.dataset.filterTags || "",
      card.textContent || ""
    ].join(" ").toLowerCase();
    card.style.display = !query || haystack.indexOf(query) >= 0 ? "" : "none";
  });
}

async function refreshReport(button) {
  const statusNode = document.getElementById("refresh-status");
  if (window.location.protocol === "file:") {
    if (statusNode) {
      statusNode.textContent = "当前是本地文件模式，请通过本地服务打开日报后再使用刷新按钮。";
      statusNode.className = "refresh-status error";
    }
    return;
  }

  button.disabled = true;
  if (statusNode) {
    statusNode.textContent = "正在刷新数据并重新生成日报，请稍候...";
    statusNode.className = "refresh-status";
  }

  try {
    const response = await fetch("/api/refresh-report", {
      method: "POST",
      headers: {"Content-Type": "application/json"}
    });
    const payload = await response.json().catch(function() { return {}; });
    if (!response.ok || !payload.ok) {
      throw new Error(payload.error || "刷新失败");
    }
    if (statusNode) {
      statusNode.textContent = "刷新完成，正在载入最新日报...";
      statusNode.className = "refresh-status success";
    }
    window.location.href = "/";
  } catch (error) {
    if (statusNode) {
      statusNode.textContent = "刷新失败：" + (error && error.message ? error.message : "未知错误");
      statusNode.className = "refresh-status error";
    }
  } finally {
    button.disabled = false;
  }
}
"""

    html_parts = [
        "<!DOCTYPE html>",
        '<html lang="zh-CN">',
        "<head>",
        '<meta charset="utf-8" />',
        '<meta name="viewport" content="width=device-width, initial-scale=1" />',
        f"<title>紫金矿业跟踪日报 {today_str()}</title>",
        f"<style>{styles}</style>",
        "</head>",
        "<body>",
        '<div class="container">',
        '<section class="hero">',
        f"<h1>紫金矿业跟踪日报</h1>",
        '<div class="hero-meta">',
        f"<span>日期：{html_escape(today_str())}</span>",
        f"<span>生成时间：{html_escape(now_text())}</span>",
        f"<span>标的：{html_escape(portfolio['name'])} {html_escape(portfolio['ts_code'])}</span>",
        "</div>",
        '<div class="hero-brief">围绕紫金矿业当日行情、核心矿产品、国际矿企对标和核心业务进展，优先输出可直接决策的结论；将数据库式罗列与说明性总览后移，减少开篇噪音。</div>',
        '<div class="hero-actions">',
        '<button type="button" class="action-btn" data-refresh-report onclick="refreshReport(this)">刷新数据</button>',
        '<span id="refresh-status" class="refresh-status">按钮会重新抓取数据并生成最新 HTML 日报。</span>',
        "</div>",
        "</section>",
        '<section class="section"><h2>全局总览</h2>',
        '<div class="section-note">按照“全局总览-核心维度拆解-关联影响分析-结论与展望”的逻辑重排，首页只保留最关键的业务结论。</div>',
        summary_cards,
        '<div class="grid-2">',
        "<div><h3>核心发现</h3>"
        + html_table(["维度", "当前判断", "业务含义", "今日动作"], global_overview_rows)
        + "</div>",
        "<div><h3>今日结论</h3>" + html_list(outlook_items) + "</div>",
        "</div></section>",
        '<section class="section"><h2>核心维度拆解：国际矿企多维对标</h2>',
        f"<div class=\"section-note\">{html_escape(international_peer_analysis.get('note', ''))}</div>",
        str(international_peer_analysis.get("cards_html", "")),
        '<div class="grid-2">',
        str(international_peer_analysis.get("radar_html", "")),
        str(international_peer_analysis.get("heatmap_html", "")),
        "</div>",
        '<div class="grid-2">',
        "<div><h3>代表矿企差异</h3>"
        + html_table(
            ["矿企", "披露状态", "项目阶段", "增量主线", "关键假设"],
            international_peer_analysis.get("advantage_rows", []),
        )
        + "</div>",
        "<div><h3>关键项目与政策结论</h3>"
        + html_list(international_peer_analysis.get("project_items", []))
        + "<h3>政策映射</h3>"
        + html_list(international_peer_analysis.get("policy_items", []))
        + "</div>",
        "</div></section>",
        '<section class="section"><h2>核心维度拆解：核心矿产价格验证</h2>',
        f"<div class=\"section-note\">{html_escape(commodity_theme_analysis.get('note', ''))}</div>",
        str(commodity_theme_analysis.get("cards_html", "")),
        build_svg_line_chart(
            "金铜锂过去12个月价格趋势（基期=100）",
            commodity_price_analysis.get("labels", []),
            commodity_price_analysis.get("normalized_series", []),
            event_markers=commodity_price_analysis.get("event_markers", []),
            point_markers=commodity_price_analysis.get("point_markers", []),
            chart_id="commodity-price-12m",
        ),
        '<div class="grid-2">',
        str(commodity_theme_analysis.get("strength_chart", "")),
        str(commodity_theme_analysis.get("heatmap_html", "")),
        "</div>",
        '<div class="grid-2">',
        "<div><h3>主题结论</h3>"
        + html_table(["主题", "核心结论", "解读"], commodity_theme_analysis.get("theme_rows", []))
        + "</div>",
        "<div><h3>供给验证重点</h3>"
        + html_table(["矿种", "覆盖企业数", "三年量化", "部分/未完整披露", "来源类型"], commodity_theme_analysis.get("supply_focus_rows", []))
        + "<h3>关键事件</h3>"
        + html_table(["月份", "事件", "影响说明"], commodity_theme_analysis.get("event_focus_rows", []))
        + "</div>",
        "</div></section>",
        (
            '<section class="section"><h2>核心维度拆解：美元与美债联动</h2>'
            + f"<div class=\"section-note\">{html_escape(dollar_bond_analysis.get('note', ''))}</div>"
            + str(dollar_bond_analysis.get("cards_html", ""))
            + '<div class="grid-2">'
            + str(dollar_bond_analysis.get("chart_html", ""))
            + "<div><h3>相关性解读</h3>"
            + html_table(["关系", "近60日相关性", "含义"], dollar_bond_analysis.get("relationship_rows", []))
            + "<h3>观察要点</h3>"
            + html_list(dollar_bond_analysis.get("insight_items", []))
            + "</div></div></section>"
        )
        if dollar_bond_analysis.get("enabled")
        else "",
        '<section class="section"><h2>关联影响分析</h2>',
        '<div class="section-note">把国际矿企、核心矿产、利率环境和公司经营变量统一映射到紫金业务与估值。</div>',
        '<div class="grid-2">',
        "<div><h3>传导链条</h3>" + html_table(["维度", "传导链", "对紫金影响", "跟踪动作"], impact_rows) + "</div>",
        "<div><h3>每日持仓与交易结构</h3>"
        + html_table(["项目", "数值"], position_rows)
        + "<h3>资金流摘要</h3>"
        + html_table(["项目", "数值"], moneyflow_rows[:4] if moneyflow_rows else [])
        + "<h3>信号解读</h3>"
        + html_list(signal_items)
        + "<h3>操作提示</h3>"
        + html_list(strategy_items)
        + "</div>",
        "</div>",
        '<div class="grid-2" style="margin-top:18px">',
        build_svg_line_chart("紫金矿业收盘价与均线", price_labels, price_series),
        build_svg_line_chart("财务动能历史趋势", financial_labels, financial_chart_series),
        "</div>",
        "<h3>产量目标路径</h3>",
        html_table(["产品", "2025实际", "2026目标", "2028目标", "增长幅度"], production_rows),
        "</section>",
        '<section class="section"><h2>主营营收结构</h2>',
        '<div class="section-note">以最新审计年报为主口径拆分黄金、铜、碳酸锂板块；黄金、铜仅保留与扩产项目直接对应的矿山产品收入，冶炼收入归入其他业务；对于未单列披露的锂收入，保留估算说明，不把粗口径误写成精确口径。</div>',
        revenue_cards,
        f"<div class=\"section-note\">{html_escape(revenue_structure_analysis.get('note', ''))}</div>",
        '<div class="grid-2">',
        build_svg_donut_chart("2025年矿山业务映射营收结构占比", revenue_structure_analysis.get("current_slices", [])),
        build_svg_line_chart(
            "过去5年板块营收占比趋势",
            revenue_structure_analysis.get("trend_labels", []),
            revenue_structure_analysis.get("trend_series", []),
            chart_id="revenue-share-trend",
        ),
        "</div>",
        "<h3>当前板块占比与增速</h3>",
        html_table(["板块", "营收(亿元)", "占比", "同比(对2024A)", "环比/可比性", "口径"], revenue_structure_analysis.get("current_rows", [])),
        build_svg_bar_chart(
            "连续8个报告期分板块收入对比",
            revenue_structure_analysis.get("period_labels", []),
            revenue_structure_analysis.get("period_series", []),
            chart_id="revenue-periods",
        ),
        build_svg_line_chart(
            "金铜锂24个月营收曲线（过去12个月 + 未来12个月）",
            revenue_forecast_analysis.get("timeline_labels", []),
            revenue_forecast_analysis.get("timeline_series", []),
            event_markers=revenue_forecast_analysis.get("timeline_event_markers", []),
            chart_id="revenue-24m-timeline",
        ),
        "<h3>板块增速摘要</h3>",
        html_table(["板块", "当前营收(亿元)", "同比(对2024A)", "环比/说明"], revenue_structure_analysis.get("growth_rows", [])),
        "</section>",
        '<section class="section"><h2>未来两季度营收预测</h2>',
        '<div class="section-note">模型同时考虑当前市场价格、2026产量指引、扩产项目投产节奏与2025矿山业务口径基数，输出金、铜、锂分板块预测，并将其他业务按审计收入季度均值平推后合并为总营收区间。</div>',
        forecast_cards,
        f"<div class=\"section-note\">{html_escape(revenue_forecast_analysis.get('note', ''))}</div>",
        build_svg_bar_chart(
            "未来两个季度分板块与总营收预测",
            revenue_forecast_analysis.get("labels", []),
            revenue_forecast_analysis.get("series", []),
            chart_id="revenue-forecast",
        ),
        "<h3>核心假设</h3>",
        html_table(["板块", "当前价/12月均价", "Q3产量系数", "Q4产量系数", "波动区间"], revenue_forecast_analysis.get("assumption_rows", [])),
        "<h3>总营收预测区间</h3>",
        html_table(["季度", "下沿(亿元)", "基准(亿元)", "上沿(亿元)"], revenue_forecast_analysis.get("range_rows", [])),
        "</section>",
        '<section class="section"><h2>全球央行货币政策追踪</h2>',
        '<div class="section-note">跟踪美联储、日本央行、英国央行等核心央行的政策事件、动作与利率口径，并保留政策文本链接用于回溯。</div>',
        policy_summary_cards,
        '<div class="grid-2">',
        build_svg_line_chart("政策变化趋势对比", policy_compare_labels, policy_rate_compare, chart_id="policy-rate-compare"),
        "<div><h3>政策预警与观察</h3>" + html_list(policy_alert_items) + "<h3>事件时间线</h3>" + html_table(["日期", "机构", "动作", "利率", "标题"], policy_timeline_rows) + "</div>",
        "</div>",
        "<h3>政策事件卡片</h3>",
        render_policy_cards(data.policy_entries, "policy-cards"),
        "</section>",
        '<section class="section"><h2>全球央行购金趋势跟踪</h2>',
        '<div class="section-note">数据源为 WGC 月报、IMF/IFS 与各国央行公开储备变动。近30/90/180天采用近1/3/6个已披露月度滚动汇总；未在官方月报高亮中列示的国家不强行补零。</div>',
        central_bank_tracking_cards,
        '<div class="section-note">' + html.escape(str(central_bank_gold_analysis.get("summary_text", "暂无最新官方月度购金解读。"))) + "</div>",
        '<div class="grid-2">',
        build_svg_line_chart(
            "全球央行月度净购金趋势（WGC/IMF口径）",
            central_bank_gold_analysis.get("global_labels", []),
            [{"label": "全球净购金", "key": "全球净购金", "color": "#f59e0b", "values": central_bank_gold_analysis.get("global_values", [])}],
            chart_id="central-bank-gold-global",
        ),
        build_svg_bar_chart(
            "主要央行年度累计变动（按已披露口径）",
            central_bank_gold_analysis.get("top_country_labels", []),
            [{"label": "年度累计", "key": "年度累计", "color": "#2563eb", "values": central_bank_gold_analysis.get("top_country_values", [])}],
            chart_id="central-bank-gold-ytd",
        ),
        "</div>",
        '<div class="grid-2">',
        "<div><h3>全球窗口统计</h3>"
        + html_table(["窗口", "净变动", "说明"], central_bank_gold_analysis.get("global_period_rows", []))
        + "<h3>主要央行披露汇总</h3>"
        + html_table(["央行/国家", "类型", "近30天", "近90天", "近180天", "年度累计", "备注"], central_bank_gold_analysis.get("tracked_country_rows", []))
        + "</div>",
        "<div><h3>中国连续购金时间线</h3>"
        + build_svg_line_chart(
            "中国央行已披露月度购金轨迹",
            central_bank_gold_analysis.get("china_timeline_labels", []),
            [{"label": "中国月度增持", "key": "中国月度增持", "color": "#dc2626", "values": central_bank_gold_analysis.get("china_timeline_values", [])}],
            chart_id="central-bank-gold-china",
        )
        + "<h3>中国购金轨迹表</h3>"
        + html_table(["月份", "增持量", "口径"], central_bank_gold_analysis.get("china_timeline_rows", []))
        + "</div>",
        "</div>",
        '<div class="grid-2">',
        "<div><h3>核心驱动因素</h3>"
        + html_list(central_bank_gold_analysis.get("driver_items", []))
        + "<h3>区域策略差异</h3>"
        + html_table(["区域/央行", "策略特征", "当前判断"], central_bank_gold_analysis.get("regional_rows", []))
        + "</div>",
        "<div><h3>对黄金与紫金业务的传导</h3>"
        + html_table(["维度", "传导逻辑", "对紫金影响", "业务建议"], central_bank_gold_analysis.get("impact_rows", []))
        + "<h3>数据校验与更新说明</h3>"
        + html_table(["维度", "数据源", "当前覆盖", "校验说明"], central_bank_gold_analysis.get("source_rows", []))
        + "</div>",
        "</div>",
        "<h3>关联资讯</h3>",
        render_research_cards(linked_gold_news, "gold-linked-news"),
        "</section>",
        '<section class="section"><h2>机构研报与资讯追踪</h2>',
        '<div class="section-note">自动整合机构研报、相关产业资讯与智能标签，支持按关键词、机构与时间维度检索。</div>',
        research_summary_cards,
        '<div class="grid-2">',
        "<div><h3>机构覆盖</h3>" + html_table(["机构/来源", "条目数"], research_org_rows) + "</div>",
        "<div><h3>标签分布</h3>" + html_table(["标签", "条目数"], research_tag_rows) + "</div>",
        "</div>",
        "<h3>新增研报提醒</h3>",
        html_table(["日期", "方向", "机构", "可信度", "标题"], research_alert_rows),
        "<h3>标准化摘要卡片</h3>",
        render_research_cards(data.research_entries, "research-cards"),
        "</section>",
        '<section class="section"><h2>结论与展望</h2>',
        '<div class="section-note">正文末尾只保留下一阶段最重要的跟踪要点与策略观察，避免附录型信息打断阅读。</div>',
        html_list(outlook_items + international_peer_analysis.get("insight_items", [])[:2] + commodity_theme_analysis.get("insight_items", [])[:1]),
        "</section>",
        '<section class="section"><h2>公司事件与舆情</h2><div class="grid-2">',
        "<div>"
        "<h3>最新公告</h3>" + html_table(["日期", "标题"], ann_rows)
        + "<h3>股东增减持</h3>" + html_table(["日期", "股东", "方向", "占流通比"], holder_rows)
        + "<h3>关键词快讯</h3>" + html_table(["时间", "来源", "标题"], data.news_rows)
        + "</div>",
        "<div>"
        "<h3>业绩预告</h3>" + html_table(["日期", "类型", "摘要"], forecast_rows)
        + "<h3>业绩快报</h3>" + html_table(["日期", "营收", "归母净利", "扣非同比"], express_rows)
        + "<h3>财报披露计划</h3>" + html_table(["报告期", "公告日", "预约披露", "实际披露"], disclosure_rows)
        + "</div>",
        "</div></section>",
        '<section class="section"><h2>每周与每季度复盘</h2><div class="grid-2">',
        "<div><h3>每周关注事项</h3>" + html_table(["资产", "5日", "20日", "20日回撤", "含义"], weekly_rows) + "</div>",
        "<div><h3>季度财务快照</h3>" + html_table(["指标", "数值"], quarter_rows) + "</div>",
        "</div><h3>逻辑止损监控</h3>" + html_list(logic_items, checkable=True) + "</section>",
        '<div class="footer">接口无权限的模块会自动降级显示，不影响 HTML 日报生成。</div>',
        f"<script>{scripts}</script>",
        "</div>",
        "</body>",
        "</html>",
    ]
    return "".join(html_parts)


def collect_report_data(config: dict[str, Any], fetcher: TushareFetcher) -> ReportData:
    report_cfg = config["report"]
    portfolio = config["portfolio"]
    lookback_days = int(report_cfg.get("lookback_days", 180))
    now = datetime.now(SH_TZ)
    end_date = now.strftime("%Y%m%d")
    start_date = days_ago_str(lookback_days, now)
    commodity_start_date = days_ago_str(max(lookback_days, 550), now)
    stock_code = portfolio["ts_code"]

    zijin_df = enrich_price_frame(fetcher.bar("紫金矿业日线", stock_code, "E", start_date, end_date))
    realtime_quote = fetcher.safe_any("紫金矿业实时行情", fetch_realtime_quote, {}, stock_code)
    daily_basic = normalize_trade_date(
        fetcher.query(
            "紫金矿业每日指标",
            "daily_basic",
            ts_code=stock_code,
            start_date=start_date,
            end_date=end_date,
            fields="ts_code,trade_date,turnover_rate,pe_ttm,pb,total_mv,circ_mv",
        )
    )
    moneyflow = normalize_trade_date(
        fetcher.query(
            "紫金矿业资金流",
            "moneyflow",
            ts_code=stock_code,
            start_date=days_ago_str(15, now),
            end_date=end_date,
        )
    )

    gold_proxy_df = enrich_price_frame(
        fetcher.bar("黄金ETF代理", config["watchlist"]["etf_proxies"][0]["ts_code"], "FD", start_date, end_date)
    )

    future_frames: dict[str, pd.DataFrame] = {}
    for item in config["watchlist"]["futures_main"]:
        future_frames[item["label"]] = enrich_price_frame(
            fetcher.bar(f"{item['label']}日线", item["ts_code"], "FT", start_date, end_date)
        )

    official_commodity_frames = {
        "gold": normalize_market_frame(fetcher.bar("黄金官方行情", "AU.SHF", "FT", commodity_start_date, end_date)),
        "copper": normalize_market_frame(fetcher.bar("铜官方行情", "CU.SHF", "FT", commodity_start_date, end_date)),
        "lithium": fetch_mapped_future_frame(fetcher, "碳酸锂官方行情", "LC.GFE", commodity_start_date, end_date),
    }

    cn_index_rows: list[list[str]] = []
    for item in config["watchlist"]["indices_cn"]:
        df = enrich_price_frame(fetcher.bar(f"{item['label']}指数", item["ts_code"], "I", start_date, end_date))
        snapshot = price_snapshot(item["label"], df)
        if snapshot:
            cn_index_rows.append(snapshot)

    global_index_rows: list[list[str]] = []
    global_index_frames: dict[str, pd.DataFrame] = {}
    for item in config["watchlist"]["indices_global"]:
        df = normalize_trade_date(
            fetcher.query(
                f"{item['label']}国际指数",
                "index_global",
                ts_code=item["ts_code"],
                start_date=start_date,
                end_date=end_date,
            )
        )
        df = enrich_price_frame(df)
        global_index_frames[item["label"]] = df
        snapshot = price_snapshot(item["label"], df)
        if snapshot:
            global_index_rows.append(snapshot)

    fx_df = normalize_trade_date(
        fetcher.query(
            "美元兑离岸人民币",
            "fx_daily",
            ts_code=config["watchlist"]["fx_pairs"][0]["ts_code"],
            start_date=days_ago_str(45, now),
            end_date=end_date,
        )
    )
    shibor_df = fetcher.query(
        "SHIBOR利率",
        "shibor",
        start_date=days_ago_str(45, now),
        end_date=end_date,
    )
    yc_df = fetcher.query(
        "中债收益率曲线",
        "yc_cb",
        ts_code="1001.CB",
        curve_type="0",
        curve_term=10.0,
        start_date=days_ago_str(15, now),
        end_date=end_date,
    )
    yc_df = normalize_trade_date(yc_df)

    anns = fetcher.query(
        "紫金矿业公告",
        "anns_d",
        ts_code=stock_code,
        start_date=days_ago_str(90, now),
        end_date=end_date,
    )
    holder_trade = fetcher.query(
        "紫金矿业股东增减持",
        "stk_holdertrade",
        ts_code=stock_code,
        start_date=days_ago_str(90, now),
        end_date=end_date,
    )
    forecast = fetcher.query("紫金矿业业绩预告", "forecast", ts_code=stock_code)
    express = fetcher.query("紫金矿业业绩快报", "express", ts_code=stock_code)
    disclosure = fetcher.query("紫金矿业披露计划", "disclosure_date", ts_code=stock_code)
    fina_indicator = sort_and_dedup_by_column(
        fetcher.query("紫金矿业财务指标", "fina_indicator", ts_code=stock_code),
        "end_date",
    )
    income = sort_and_dedup_by_column(fetcher.query("紫金矿业利润表", "income", ts_code=stock_code), "end_date")
    cashflow = sort_and_dedup_by_column(fetcher.query("紫金矿业现金流", "cashflow", ts_code=stock_code), "end_date")
    dividend = sort_and_dedup_by_column(fetcher.query("紫金矿业分红", "dividend", ts_code=stock_code), "end_date")
    mainbiz = fetcher.query(
        "紫金矿业主营构成",
        "fina_mainbz",
        ts_code=stock_code,
        type="P",
        start_date="20200101",
        end_date=end_date,
    )

    news_df = fetcher.query(
        "东财快讯",
        "news",
        src="eastmoney",
        start_date=hours_ago_text(24, now),
        end_date=now.strftime("%Y-%m-%d %H:%M:%S"),
    )
    if not news_df.empty:
        news_df = news_df.copy()
        news_df["src"] = "eastmoney"
    news_rows = filter_news(news_df)

    precious_frames: dict[str, pd.DataFrame] = {}
    for item in config["watchlist"].get("precious_assets", []):
        if item.get("source") == "future":
            df = fetcher.bar(f"{item['label']}扩展行情", item["ts_code"], item.get("asset", "FT"), start_date, end_date)
            precious_frames[item["label"]] = normalize_market_frame(df)
        elif item.get("source") == "ths":
            df = fetcher.query(
                f"{item['label']}主题指数",
                "ths_daily",
                ts_code=item["ts_code"],
                start_date=start_date,
                end_date=end_date,
            )
            precious_frames[item["label"]] = normalize_market_frame(df)

    theme_frames: dict[str, pd.DataFrame] = {}
    for item in config["watchlist"].get("theme_indices", []):
        if item.get("source") == "ths":
            df = fetcher.query(
                f"{item['label']}赛道指数",
                "ths_daily",
                ts_code=item["ts_code"],
                start_date=start_date,
                end_date=end_date,
            )
            theme_frames[item["label"]] = normalize_market_frame(df)
        else:
            theme_frames[item["label"]] = pd.DataFrame()

    macro_proxy_cfg = config.get("external_sources", {}).get("macro_proxies", {}).get("dollar_index_fred", {})
    raw_dollar_index_df = fetcher.safe_any(
        "美元指数代理(FRED)",
        fetch_fred_series,
        pd.DataFrame(),
        macro_proxy_cfg.get("series_id", "DTWEXBGS"),
        macro_proxy_cfg.get("label", "美元指数代理"),
    )
    macro_cache_cfg = config.get("external_sources", {}).get("macro_proxies", {})
    dollar_cache_path = ROOT / macro_cache_cfg.get("dollar_index_cache_file", "data/cache/dollar_index_proxy.csv")
    dollar_index_df = resolve_dollar_proxy_frame(raw_dollar_index_df, fx_df, dollar_cache_path)
    treasury_curve_df = fetcher.safe_any("美国国债收益率曲线", fetch_treasury_curve, pd.DataFrame())
    if not treasury_curve_df.empty:
        treasury_curve_df = treasury_curve_df.copy()
        treasury_curve_df["trade_date"] = treasury_curve_df["trade_date"].astype(str)
        treasury_curve_df = treasury_curve_df.sort_values("trade_date").reset_index(drop=True)

    report_rc = fetcher.query(
        "紫金矿业机构研报",
        "report_rc",
        ts_code=stock_code,
        start_date=days_ago_str(120, now),
        end_date=end_date,
    )
    research_entries: list[dict[str, Any]] = []
    if not report_rc.empty:
        for _, item in report_rc.head(20).iterrows():
            title = str(item.get("report_title", ""))
            org_name = str(item.get("org_name", ""))
            summary = "；".join(
                filter(
                    None,
                    [
                        f"评级 {item.get('rating')}" if str(item.get("rating", "")) else "",
                        f"EPS {fmt_num(item.get('eps'))}" if as_float(item.get("eps")) is not None else "",
                        f"净利润预测 {fmt_num(item.get('np'), 0)}" if as_float(item.get("np")) is not None else "",
                    ],
                )
            )
            tags = classify_tags(" ".join([title, org_name, summary]))
            research_entries.append(
                {
                    "source": "Tushare研报",
                    "org_name": org_name,
                    "institution": org_name,
                    "title": title,
                    "summary": summary or str(item.get("classify", "")),
                    "date": str(item.get("report_date", "")),
                    "tags": sorted(set(tags + ["研报"])),
                    "rating": str(item.get("rating", "")),
                    "author": str(item.get("author_name", "")),
                    "link": "",
                }
            )

    keyword_set = tuple(config.get("external_sources", {}).get("research", {}).get("keywords", []))
    if not news_df.empty:
        for _, item in news_df.iterrows():
            title = str(item.get("title") or item.get("content") or "")
            if keyword_set and not any(keyword in title for keyword in keyword_set):
                continue
            tags = classify_tags(title)
            research_entries.append(
                {
                    "source": str(item.get("src", "news")),
                    "org_name": str(item.get("src", "news")),
                    "institution": str(item.get("src", "news")),
                    "title": title[:120],
                    "summary": str(item.get("content", ""))[:180],
                    "date": re.sub(r"[^0-9]", "", str(item.get("datetime", "")))[:8],
                    "tags": sorted(set(tags + ["资讯"])),
                    "link": "",
                }
            )

    research_cache = ROOT / config.get("external_sources", {}).get("research", {}).get("cache_file", "data/cache/research_entries.json")
    research_entries = cache_json_records(research_cache, research_entries, ["source", "title", "date"])

    policy_entries = []
    policy_entries.extend(fetcher.safe_any("美联储政策事件", fetch_fed_policy_events, []))
    policy_entries.extend(fetcher.safe_any("日本央行政策事件", fetch_boj_policy_events, []))
    policy_entries.extend(fetcher.safe_any("英国央行政策事件", fetch_boe_policy_events, []))
    policy_cache = ROOT / config.get("external_sources", {}).get("policy", {}).get("cache_file", "data/cache/policy_events.json")
    policy_entries = cache_json_records(policy_cache, policy_entries, ["institution", "title", "date"])

    central_bank_gold_entries = fetcher.safe_any(
        "全球央行购金月报",
        fetch_goldhub_gold_purchase_entries,
        [],
        now,
        int(config.get("external_sources", {}).get("gold_purchase", {}).get("lookback_months", 8)),
    )
    gold_cache = ROOT / config.get("external_sources", {}).get("gold_purchase", {}).get("cache_file", "data/cache/central_bank_gold.json")
    central_bank_gold_entries = cache_json_records(gold_cache, central_bank_gold_entries, ["title"])

    translation_config = load_translation_config(config)
    translation_cache_root = ROOT / config.get("external_sources", {}).get("translation", {}).get("cache_dir", "data/cache/translations")
    translation_alert_root = ROOT / config.get("external_sources", {}).get("translation", {}).get("alert_dir", "data/alerts/translations")

    research_entries = translate_entries(
        research_entries,
        translation_config,
        translation_cache_root / "research_entries.json",
        translation_alert_root / f"research_translation_failures_{today_str()}.json",
    )
    policy_entries = translate_entries(
        policy_entries,
        translation_config,
        translation_cache_root / "policy_entries.json",
        translation_alert_root / f"policy_translation_failures_{today_str()}.json",
    )
    central_bank_gold_entries = translate_entries(
        central_bank_gold_entries,
        translation_config,
        translation_cache_root / "gold_entries.json",
        translation_alert_root / f"gold_translation_failures_{today_str()}.json",
    )

    research_entries = filter_target_research(research_entries)
    alert_cfg = config.get("external_sources", {}).get("research_tracking", {})
    research_alerts = track_research_updates(
        research_entries,
        ROOT / alert_cfg.get("state_file", "data/cache/research_tracking_state.json"),
        ROOT / alert_cfg.get("alert_file", f"data/alerts/research_updates_{today_str()}.json"),
    )

    boe_rate_df = fetcher.safe_any("英国央行利率历史", fetch_boe_rate_history, pd.DataFrame())
    boe_rate_df = normalize_market_frame(boe_rate_df)

    price_events = config.get("commodity_analysis", {}).get("price_events", [])
    production_targets = config.get("focus_monitor", {}).get("micro_logic", {}).get("production_targets", [])
    commodity_price_analysis = build_price_analysis(official_commodity_frames, price_events)
    supply_plan_cache = ROOT / config.get("external_sources", {}).get("commodity_supply_plans", {}).get(
        "cache_file",
        "data/cache/commodity_supply_plans.json",
    )
    supply_plan_analysis = build_supply_plan_analysis(load_json_records(supply_plan_cache))
    commodity_price_analysis.update(supply_plan_analysis)
    revenue_structure_analysis = build_revenue_analysis(mainbiz, income, official_commodity_frames["lithium"], production_targets)
    revenue_forecast_analysis = build_forecast_analysis(
        revenue_structure_analysis,
        official_commodity_frames,
        production_targets,
        income,
    )
    central_bank_gold_analysis = build_central_bank_gold_analysis(
        central_bank_gold_entries,
        official_commodity_frames.get("gold", pd.DataFrame()),
    )

    return ReportData(
        zijin_df=zijin_df,
        realtime_quote=realtime_quote,
        daily_basic=daily_basic,
        moneyflow=moneyflow,
        gold_proxy_df=gold_proxy_df,
        future_frames=future_frames,
        cn_index_rows=cn_index_rows,
        global_index_rows=global_index_rows,
        global_index_frames=global_index_frames,
        fx_df=fx_df,
        shibor_df=shibor_df,
        yc_df=yc_df,
        anns=anns,
        holder_trade=holder_trade,
        forecast=forecast,
        express=express,
        disclosure=disclosure,
        fina_indicator=fina_indicator,
        income=income,
        cashflow=cashflow,
        dividend=dividend,
        news_rows=news_rows,
        precious_frames=precious_frames,
        theme_frames=theme_frames,
        dollar_index_df=dollar_index_df,
        treasury_curve_df=treasury_curve_df,
        research_entries=research_entries,
        research_alerts=research_alerts,
        policy_entries=policy_entries,
        central_bank_gold_entries=central_bank_gold_entries,
        boe_rate_df=boe_rate_df,
        mainbiz=mainbiz,
        official_commodity_frames=official_commodity_frames,
        commodity_price_analysis=commodity_price_analysis,
        revenue_structure_analysis=revenue_structure_analysis,
        revenue_forecast_analysis=revenue_forecast_analysis,
        central_bank_gold_analysis=central_bank_gold_analysis,
    )


def build_report(config: dict[str, Any], fetcher: TushareFetcher) -> tuple[str, ReportData]:
    data = collect_report_data(config, fetcher)
    return render_html_report(config=config, fetcher=fetcher, data=data), data


def save_report(config: dict[str, Any], content: str) -> Path:
    out_root = ROOT / config["report"].get("output_dir", "reports")
    folder = out_root / today_str()[:4] / today_str()[4:6]
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"zijin_daily_{today_str()}.html"
    path.write_text(content, encoding="utf-8")
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成紫金矿业每日跟踪日报")
    parser.add_argument(
        "--config",
        default=str(ROOT / "config" / "portfolio.json"),
        help="配置文件路径，默认使用 config/portfolio.json",
    )
    parser.add_argument("--stdout", action="store_true", help="同时输出到标准输出")
    parser.add_argument("--mode", choices=["manual", "scheduled"], default="manual", help="manual 为手动生成，scheduled 为按交易时段调度")
    parser.add_argument("--force", action="store_true", help="忽略交易时段判断，强制执行")
    parser.add_argument("--archive-now", action="store_true", help="忽略收盘时间，立即生成归档快照")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    token = os.getenv("TUSHARE_TOKEN", "").strip()
    if not token:
        print("缺少环境变量 TUSHARE_TOKEN，请先在 .env 或系统环境变量中设置。", file=sys.stderr)
        return 2

    config = load_config(Path(args.config))
    fetcher = TushareFetcher(token)
    now = datetime.now(SH_TZ)
    do_archive = args.archive_now
    if args.mode == "scheduled" and not args.force:
        calendar_df = fetcher.query(
            "A股交易日历",
            "trade_cal",
            exchange="SSE",
            start_date=now.strftime("%Y%m%d"),
            end_date=now.strftime("%Y%m%d"),
        )
        trading_day = is_trading_day(calendar_df, now)
        should_update = should_run_hourly_update(now, trading_day)
        should_archive = should_archive_after_close(now, trading_day)
        do_archive = should_archive
        if not should_update and not should_archive:
            print(f"当前非交易时段，无需执行。时间：{now.strftime('%Y-%m-%d %H:%M:%S')}")
            return 0
    elif args.force:
        do_archive = args.archive_now or should_archive_after_close(now, True)

    content, data = build_report(config, fetcher)
    report_path = save_report(config, content)

    if do_archive:
        archive_root = ROOT / config.get("archive", {}).get("output_dir", "data/archive")
        trade_date = current_trade_date(now)
        if not archive_exists(archive_root, trade_date):
            archive_path, manifest_path = archive_trading_snapshot(
                archive_root,
                trade_date,
                data,
                [{"name": item.name, "ok": item.ok, "detail": item.detail} for item in fetcher.status],
            )
            print(f"交易日归档已生成：{archive_path}")
            print(f"归档校验清单：{manifest_path}")

    print(f"日报已生成：{report_path}")
    if args.stdout:
        print()
        print(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
