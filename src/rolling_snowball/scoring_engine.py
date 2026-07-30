from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .rules import load_rule_snapshot


STOCK_NAME_ST_PATTERN = re.compile(r"^\*?ST", re.IGNORECASE)


@dataclass(frozen=True)
class StockCandidateInput:
    ts_code: str
    stock_name: str
    market: str
    sw_level1_industry: str
    list_status: str
    latest_report_period: str | None = None
    audit_opinion: str | None = None
    nonrec_np_3y: tuple[float | None, ...] = ()
    nonrec_np_yoy_3y: tuple[float | None, ...] = ()
    operating_cashflow_3y: tuple[float | None, ...] = ()
    gross_margin_avg_3y: float | None = None
    roe_avg_3y: float | None = None
    net_margin_avg_3y: float | None = None
    latest_revenue: float | None = None
    latest_nonrec_np: float | None = None
    revenue_cagr_3y: float | None = None
    nonrec_np_cagr_3y: float | None = None
    shareholder_return_ratio_3y: float | None = None
    dividend_sum_3y: float | None = None
    buyback_sum_3y: float | None = None
    parent_np_sum_3y: float | None = None
    cash_conversion_ratio_3y: float | None = None
    asset_liability_ratio_latest: float | None = None
    cash_to_short_debt_ratio: float | None = None
    total_market_cap: float | None = None
    avg_turnover_20d: float | None = None
    pe_ttm: float | None = None
    pb_latest: float | None = None
    dividend_yield_avg_3y: float | None = None
    roe_std_3y: float | None = None


@dataclass(frozen=True)
class StockScoreResult:
    ts_code: str
    run_id: str
    stock_name: str
    market: str
    sw_level1_industry: str
    latest_report_period: str | None
    audit_opinion: str | None
    current_pool: str | None
    total_score: float | None
    industry_rank: int | None
    industry_total: int | None
    global_rank: int | None
    gross_margin_avg_3y: float | None
    roe_avg_3y: float | None
    net_margin_avg_3y: float | None
    revenue_cagr_3y: float | None
    nonrec_np_cagr_3y: float | None
    shareholder_return_ratio_3y: float | None
    dividend_sum_3y: float | None
    buyback_sum_3y: float | None
    parent_np_sum_3y: float | None
    cash_conversion_ratio_3y: float | None
    asset_liability_ratio_latest: float | None
    pe_ttm: float | None
    pb_latest: float | None
    dividend_yield_avg_3y: float | None
    roe_std_3y: float | None
    manual_review_required: bool
    is_filtered: bool
    filter_reasons: tuple[str, ...]
    cashflow_warning: bool
    short_debt_warning: bool
    pe_invalid: bool
    pb_invalid: bool
    data_missing: bool
    warning_tags: tuple[str, ...]
    rule_version: str
    data_version: str
    scored_at: datetime


def _has_st_flag(stock_name: str) -> bool:
    return bool(STOCK_NAME_ST_PATTERN.match(stock_name.strip()))


def _count_true(values: list[bool]) -> int:
    return sum(1 for item in values if item)


def _has_enough_series(series: tuple[float | None, ...], expected: int = 3) -> bool:
    return len(series) >= expected and all(value is not None for value in series[:expected])


def evaluate_candidate(
    candidate: StockCandidateInput,
    *,
    run_id: str,
    rule_version: str,
    data_version: str,
    scored_at: datetime | None = None,
    rule_snapshot: dict[str, Any] | None = None,
) -> StockScoreResult:
    snapshot = rule_snapshot or load_rule_snapshot()
    hard_filters = snapshot["hard_filters"]
    compliance = hard_filters["compliance"]
    going_concern = hard_filters["going_concern"]
    cashflow = hard_filters["cashflow"]
    leverage = hard_filters["leverage"]
    liquidity = hard_filters["liquidity"]

    filter_reasons: list[str] = []
    warning_tags: list[str] = []

    manual_review_required = False
    cashflow_warning = False
    short_debt_warning = False
    pe_invalid = candidate.pe_ttm is not None and candidate.pe_ttm <= 0
    pb_invalid = candidate.pb_latest is not None and candidate.pb_latest <= 0

    if compliance.get("exclude_st", True) and _has_st_flag(candidate.stock_name):
        filter_reasons.append("st_flag")

    opinion = (candidate.audit_opinion or "").strip()
    if opinion in set(compliance.get("exclude_audit_opinions", [])):
        filter_reasons.append("audit_opinion_negative")
    elif opinion in set(compliance.get("manual_review_audit_opinions", [])):
        manual_review_required = True

    if _has_enough_series(candidate.nonrec_np_3y):
        if _count_true([value < 0 for value in candidate.nonrec_np_3y[:3]]) >= int(
            going_concern.get("nonrec_negative_years_in_3y", 2)
        ):
            filter_reasons.append("negative_nonrec_np_2of3y")

    if _has_enough_series(candidate.nonrec_np_yoy_3y):
        if _count_true([value < 0 for value in candidate.nonrec_np_yoy_3y[:3]]) >= int(
            going_concern.get("nonrec_decline_years_in_3y", 2)
        ):
            filter_reasons.append("nonrec_np_yoy_decline_2of3y")

    if _has_enough_series(candidate.operating_cashflow_3y) and _has_enough_series(candidate.nonrec_np_3y):
        cashflow_warning = _count_true(
            [
                ocf < nonrec_np
                for ocf, nonrec_np in zip(
                    candidate.operating_cashflow_3y[:3],
                    candidate.nonrec_np_3y[:3],
                )
            ]
        ) >= int(cashflow.get("warn_ocf_lt_nonrec_np_years_in_3y", 2))

        cash_conversion_ratio = candidate.cash_conversion_ratio_3y
        if cash_conversion_ratio is None:
            nonrec_np_sum = sum(candidate.nonrec_np_3y[:3])
            if nonrec_np_sum > 0:
                cash_conversion_ratio = sum(candidate.operating_cashflow_3y[:3]) / nonrec_np_sum
        if cash_conversion_ratio is not None and cash_conversion_ratio < float(
            cashflow.get("exclude_cash_conversion_ratio_3y_lt", 0.6)
        ):
            filter_reasons.append("cash_conversion_ratio_below_0_6")

    if candidate.asset_liability_ratio_latest is not None and candidate.asset_liability_ratio_latest > float(
        leverage.get("exclude_asset_liability_ratio_gt", 0.7)
    ):
        filter_reasons.append("asset_liability_ratio_above_70pct")

    if candidate.cash_to_short_debt_ratio is not None and candidate.cash_to_short_debt_ratio < float(
        leverage.get("warn_cash_to_short_debt_lt", 1.0)
    ):
        short_debt_warning = True

    if candidate.total_market_cap is not None and candidate.total_market_cap < float(
        liquidity.get("exclude_market_cap_lt_cny", 3_000_000_000)
    ):
        filter_reasons.append("market_cap_below_3bn")

    if candidate.avg_turnover_20d is not None and candidate.avg_turnover_20d < float(
        liquidity.get("exclude_avg_turnover_20d_lt_cny", 30_000_000)
    ):
        filter_reasons.append("avg_turnover_20d_below_30m")

    required_fields = (
        candidate.asset_liability_ratio_latest,
        candidate.total_market_cap,
        candidate.avg_turnover_20d,
    )
    data_missing = any(field is None for field in required_fields) or not (
        _has_enough_series(candidate.nonrec_np_3y)
        and _has_enough_series(candidate.nonrec_np_yoy_3y)
        and _has_enough_series(candidate.operating_cashflow_3y)
    )

    if manual_review_required:
        warning_tags.append("manual_review")
    if cashflow_warning:
        warning_tags.append("cashflow_warning")
    if short_debt_warning:
        warning_tags.append("short_debt_warning")
    if pe_invalid:
        warning_tags.append("pe_invalid")
    if pb_invalid:
        warning_tags.append("pb_invalid")
    if data_missing:
        warning_tags.append("data_missing")

    return StockScoreResult(
        ts_code=candidate.ts_code,
        run_id=run_id,
        stock_name=candidate.stock_name,
        market=candidate.market,
        sw_level1_industry=candidate.sw_level1_industry,
        latest_report_period=candidate.latest_report_period,
        audit_opinion=candidate.audit_opinion,
        current_pool=None,
        total_score=None,
        industry_rank=None,
        industry_total=None,
        global_rank=None,
        gross_margin_avg_3y=candidate.gross_margin_avg_3y,
        roe_avg_3y=candidate.roe_avg_3y,
        net_margin_avg_3y=candidate.net_margin_avg_3y,
        revenue_cagr_3y=candidate.revenue_cagr_3y,
        nonrec_np_cagr_3y=candidate.nonrec_np_cagr_3y,
        shareholder_return_ratio_3y=candidate.shareholder_return_ratio_3y,
        dividend_sum_3y=candidate.dividend_sum_3y,
        buyback_sum_3y=candidate.buyback_sum_3y,
        parent_np_sum_3y=candidate.parent_np_sum_3y,
        cash_conversion_ratio_3y=candidate.cash_conversion_ratio_3y,
        asset_liability_ratio_latest=candidate.asset_liability_ratio_latest,
        pe_ttm=candidate.pe_ttm,
        pb_latest=candidate.pb_latest,
        dividend_yield_avg_3y=candidate.dividend_yield_avg_3y,
        roe_std_3y=candidate.roe_std_3y,
        manual_review_required=manual_review_required,
        is_filtered=bool(filter_reasons),
        filter_reasons=tuple(filter_reasons),
        cashflow_warning=cashflow_warning,
        short_debt_warning=short_debt_warning,
        pe_invalid=pe_invalid,
        pb_invalid=pb_invalid,
        data_missing=data_missing,
        warning_tags=tuple(warning_tags),
        rule_version=rule_version,
        data_version=data_version,
        scored_at=scored_at or datetime.now(),
    )


def result_to_db_row(result: StockScoreResult) -> dict[str, Any]:
    return {
        "ts_code": result.ts_code,
        "run_id": result.run_id,
        "stock_name": result.stock_name,
        "market": result.market,
        "sw_level1_industry": result.sw_level1_industry,
        "latest_report_period": result.latest_report_period,
        "audit_opinion": result.audit_opinion,
        "current_pool": result.current_pool,
        "total_score": result.total_score,
        "industry_rank": result.industry_rank,
        "industry_total": result.industry_total,
        "global_rank": result.global_rank,
        "gross_margin_avg_3y": result.gross_margin_avg_3y,
        "roe_avg_3y": result.roe_avg_3y,
        "net_margin_avg_3y": result.net_margin_avg_3y,
        "industry_position_score_raw": None,
        "revenue_pct_in_industry": None,
        "nonrec_np_pct_in_industry": None,
        "market_cap_pct_in_industry": None,
        "revenue_cagr_3y": result.revenue_cagr_3y,
        "nonrec_np_cagr_3y": result.nonrec_np_cagr_3y,
        "shareholder_return_ratio_3y": result.shareholder_return_ratio_3y,
        "dividend_sum_3y": result.dividend_sum_3y,
        "buyback_sum_3y": result.buyback_sum_3y,
        "parent_np_sum_3y": result.parent_np_sum_3y,
        "cash_conversion_ratio_3y": result.cash_conversion_ratio_3y,
        "asset_liability_ratio_latest": result.asset_liability_ratio_latest,
        "capital_return_stability_score_raw": None,
        "pe_ttm": result.pe_ttm,
        "pb_latest": result.pb_latest,
        "dividend_yield_avg_3y": result.dividend_yield_avg_3y,
        "roe_std_3y": result.roe_std_3y,
        "industry_roe_std_median_3y": None,
        "roe_stability_gap": None,
        "biz_quality_score": None,
        "growth_delivery_score": None,
        "financial_quality_score": None,
        "valuation_fit_score": None,
        "gross_margin_score": None,
        "roe_score": None,
        "net_margin_score": None,
        "industry_position_score": None,
        "revenue_cagr_score": None,
        "nonrec_np_cagr_score": None,
        "shareholder_return_score": None,
        "cash_conversion_score": None,
        "asset_liability_score": None,
        "capital_return_stability_score": None,
        "pe_score": None,
        "pb_score": None,
        "dividend_yield_score": None,
        "gross_margin_weighted_score": None,
        "roe_weighted_score": None,
        "net_margin_weighted_score": None,
        "industry_position_weighted_score": None,
        "revenue_cagr_weighted_score": None,
        "nonrec_np_cagr_weighted_score": None,
        "shareholder_return_weighted_score": None,
        "cash_conversion_weighted_score": None,
        "asset_liability_weighted_score": None,
        "capital_return_stability_weighted_score": None,
        "pe_weighted_score": None,
        "pb_weighted_score": None,
        "dividend_yield_weighted_score": None,
        "biz_quality_weighted_score": None,
        "growth_delivery_weighted_score": None,
        "financial_quality_weighted_score": None,
        "valuation_fit_weighted_score": None,
        "manual_review_required": result.manual_review_required,
        "is_filtered": result.is_filtered,
        "filter_reasons": list(result.filter_reasons),
        "cashflow_warning": result.cashflow_warning,
        "short_debt_warning": result.short_debt_warning,
        "pe_invalid": result.pe_invalid,
        "pb_invalid": result.pb_invalid,
        "data_missing": result.data_missing,
        "warning_tags": list(result.warning_tags),
        "rule_version": result.rule_version,
        "data_version": result.data_version,
        "scored_at": result.scored_at,
    }
