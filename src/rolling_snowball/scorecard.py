from __future__ import annotations

from collections import defaultdict
from statistics import median
from typing import Any

from .rules import load_rule_snapshot


def _round_score(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value, 2)


def _values(rows: list[dict[str, Any]], key: str, *, positive_only: bool = False) -> list[float]:
    values: list[float] = []
    for row in rows:
        value = row.get(key)
        if value is None:
            continue
        if positive_only and value <= 0:
            continue
        values.append(float(value))
    return values


def _percentile_score(
    rows: list[dict[str, Any]],
    key: str,
    value: float | None,
    *,
    higher_is_better: bool = True,
    positive_only: bool = False,
) -> float:
    if value is None:
        return 0.0
    values = _values(rows, key, positive_only=positive_only)
    if not values:
        return 0.0
    if higher_is_better:
        return round(sum(1 for item in values if item <= value) / len(values) * 100.0, 2)
    return round(sum(1 for item in values if item >= value) / len(values) * 100.0, 2)


def _weighted_sum(items: list[tuple[float, float]]) -> float:
    return round(sum(score * weight for score, weight in items), 2)


def _stabilize_percentile_score(
    score: float,
    *,
    sample_size: int,
    min_full_sample: int,
    neutral_score: float,
) -> float:
    if sample_size <= 0:
        return neutral_score
    if sample_size >= min_full_sample:
        return score
    # Very small industries create brittle percentiles; pull them toward neutral.
    weight = max(sample_size - 1, 0) / max(min_full_sample - 1, 1)
    return round(neutral_score + (score - neutral_score) * weight, 2)


def _add_tag(row: dict[str, Any], tag: str) -> None:
    tags = list(row.get("warning_tags", []))
    if tag not in tags:
        tags.append(tag)
    row["warning_tags"] = tags


def _mark_missing_metric(row: dict[str, Any]) -> None:
    row["data_missing"] = True
    _add_tag(row, "data_missing")


def _mark_invalid_metric(row: dict[str, Any], tag: str | None = None) -> None:
    _add_tag(row, "metric_invalid")
    if tag:
        _add_tag(row, tag)


def apply_scores(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return apply_scores_with_snapshot(rows)


def apply_scores_with_snapshot(
    rows: list[dict[str, Any]],
    snapshot: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    if not rows:
        return rows

    snapshot = snapshot or load_rule_snapshot()
    dimension_weights = snapshot["score_dimensions"]
    top_level_weights = snapshot["top_level_weights"]
    key_watch_top_n = int(snapshot["pool_thresholds"].get("key_watch_top_n", 20))
    guardrails = snapshot.get("scoring_guardrails", {})
    min_industry_sample = int(guardrails.get("min_industry_sample_for_full_percentile", 5))
    neutral_percentile_score = float(guardrails.get("neutral_percentile_score", 50.0))

    industry_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        industry_groups[row["sw_level1_industry"]].append(row)

    for industry_rows in industry_groups.values():
        industry_std_values = _values(industry_rows, "roe_std_3y")
        industry_std_median = median(industry_std_values) if industry_std_values else None
        stability_rows: list[dict[str, Any]] = []
        for row in industry_rows:
            row["industry_total"] = len(industry_rows)
            row["industry_roe_std_median_3y"] = industry_std_median
            if len(industry_rows) < min_industry_sample:
                _add_tag(row, "small_industry_sample")
            if industry_std_median is not None and row.get("roe_std_3y") is not None:
                row["roe_stability_gap"] = round(industry_std_median - float(row["roe_std_3y"]), 4)
            else:
                row["roe_stability_gap"] = None
            stability_rows.append(row)

        for row in industry_rows:
            row["revenue_pct_in_industry"] = _stabilize_percentile_score(
                _percentile_score(
                    industry_rows,
                    "_latest_revenue",
                    row.get("_latest_revenue"),
                    higher_is_better=True,
                ),
                sample_size=len(industry_rows),
                min_full_sample=min_industry_sample,
                neutral_score=neutral_percentile_score,
            )
            row["nonrec_np_pct_in_industry"] = _stabilize_percentile_score(
                _percentile_score(
                    industry_rows,
                    "_latest_nonrec_np",
                    row.get("_latest_nonrec_np"),
                    higher_is_better=True,
                ),
                sample_size=len(industry_rows),
                min_full_sample=min_industry_sample,
                neutral_score=neutral_percentile_score,
            )
            row["market_cap_pct_in_industry"] = _stabilize_percentile_score(
                _percentile_score(
                    industry_rows,
                    "_total_market_cap_internal",
                    row.get("_total_market_cap_internal"),
                    higher_is_better=True,
                ),
                sample_size=len(industry_rows),
                min_full_sample=min_industry_sample,
                neutral_score=neutral_percentile_score,
            )
            row["industry_position_score_raw"] = _weighted_sum(
                [
                    (row["revenue_pct_in_industry"], 0.4),
                    (row["nonrec_np_pct_in_industry"], 0.4),
                    (row["market_cap_pct_in_industry"], 0.2),
                ]
            )

            roe_pct = _stabilize_percentile_score(
                _percentile_score(industry_rows, "roe_avg_3y", row.get("roe_avg_3y"), higher_is_better=True),
                sample_size=len(industry_rows),
                min_full_sample=min_industry_sample,
                neutral_score=neutral_percentile_score,
            )
            stability_pct = _stabilize_percentile_score(
                _percentile_score(
                    stability_rows,
                    "roe_stability_gap",
                    row.get("roe_stability_gap"),
                    higher_is_better=True,
                ),
                sample_size=len(industry_rows),
                min_full_sample=min_industry_sample,
                neutral_score=neutral_percentile_score,
            )
            row["capital_return_stability_score_raw"] = _weighted_sum(
                [(roe_pct, 0.6), (stability_pct, 0.4)]
            )

    for row in rows:
        industry_rows = industry_groups[row["sw_level1_industry"]]

        def indicator_score(
            key: str,
            *,
            higher_is_better: bool = True,
            positive_only: bool = False,
            invalid_flag: str | None = None,
        ) -> float:
            value = row.get(key)
            if invalid_flag and row.get(invalid_flag):
                _mark_invalid_metric(row, invalid_flag)
                return 0.0
            if positive_only and value is not None and float(value) <= 0:
                _mark_invalid_metric(row)
                return 0.0
            score = _stabilize_percentile_score(
                _percentile_score(
                    industry_rows,
                    key,
                    value,
                    higher_is_better=higher_is_better,
                    positive_only=positive_only,
                ),
                sample_size=len(industry_rows),
                min_full_sample=min_industry_sample,
                neutral_score=neutral_percentile_score,
            )
            if value is None:
                _mark_missing_metric(row)
            return score

        row["gross_margin_score"] = indicator_score("gross_margin_avg_3y", higher_is_better=True)
        row["roe_score"] = indicator_score("roe_avg_3y", higher_is_better=True)
        row["net_margin_score"] = indicator_score("net_margin_avg_3y", higher_is_better=True)
        row["industry_position_score"] = row["industry_position_score_raw"] or 0.0
        if row.get("_latest_revenue") is None or row.get("_latest_nonrec_np") is None or row.get("_total_market_cap_internal") is None:
            _mark_missing_metric(row)

        row["revenue_cagr_score"] = indicator_score("revenue_cagr_3y", higher_is_better=True)
        row["nonrec_np_cagr_score"] = indicator_score("nonrec_np_cagr_3y", higher_is_better=True)
        row["shareholder_return_score"] = indicator_score("shareholder_return_ratio_3y", higher_is_better=True)

        row["cash_conversion_score"] = indicator_score("cash_conversion_ratio_3y", higher_is_better=True)
        row["asset_liability_score"] = indicator_score(
            "asset_liability_ratio_latest",
            higher_is_better=False,
        )
        row["capital_return_stability_score"] = row["capital_return_stability_score_raw"] or 0.0
        if row.get("capital_return_stability_score_raw") is None:
            _mark_missing_metric(row)

        row["pe_score"] = indicator_score(
            "pe_ttm",
            higher_is_better=False,
            positive_only=True,
            invalid_flag="pe_invalid",
        )
        row["pb_score"] = indicator_score(
            "pb_latest",
            higher_is_better=False,
            positive_only=True,
            invalid_flag="pb_invalid",
        )
        row["dividend_yield_score"] = indicator_score("dividend_yield_avg_3y", higher_is_better=True)

        row["gross_margin_weighted_score"] = _weighted_sum(
            [(row["gross_margin_score"], dimension_weights["biz_quality"]["gross_margin"])]
        )
        row["roe_weighted_score"] = _weighted_sum(
            [(row["roe_score"], dimension_weights["biz_quality"]["roe_avg_3y"])]
        )
        row["net_margin_weighted_score"] = _weighted_sum(
            [(row["net_margin_score"], dimension_weights["biz_quality"]["net_margin_avg_3y"])]
        )
        row["industry_position_weighted_score"] = _weighted_sum(
            [(row["industry_position_score"], dimension_weights["biz_quality"]["industry_position"])]
        )
        row["biz_quality_score"] = _weighted_sum(
            [
                (row["gross_margin_score"], dimension_weights["biz_quality"]["gross_margin"]),
                (row["roe_score"], dimension_weights["biz_quality"]["roe_avg_3y"]),
                (row["net_margin_score"], dimension_weights["biz_quality"]["net_margin_avg_3y"]),
                (row["industry_position_score"], dimension_weights["biz_quality"]["industry_position"]),
            ]
        )

        row["revenue_cagr_weighted_score"] = _weighted_sum(
            [(row["revenue_cagr_score"], dimension_weights["growth_delivery"]["revenue_cagr_3y"])]
        )
        row["nonrec_np_cagr_weighted_score"] = _weighted_sum(
            [(row["nonrec_np_cagr_score"], dimension_weights["growth_delivery"]["nonrec_np_cagr_3y"])]
        )
        row["shareholder_return_weighted_score"] = _weighted_sum(
            [(row["shareholder_return_score"], dimension_weights["growth_delivery"]["shareholder_return_ratio_3y"])]
        )
        row["growth_delivery_score"] = _weighted_sum(
            [
                (row["revenue_cagr_score"], dimension_weights["growth_delivery"]["revenue_cagr_3y"]),
                (row["nonrec_np_cagr_score"], dimension_weights["growth_delivery"]["nonrec_np_cagr_3y"]),
                (row["shareholder_return_score"], dimension_weights["growth_delivery"]["shareholder_return_ratio_3y"]),
            ]
        )

        row["cash_conversion_weighted_score"] = _weighted_sum(
            [(row["cash_conversion_score"], dimension_weights["financial_quality"]["cash_conversion_ratio_3y"])]
        )
        row["asset_liability_weighted_score"] = _weighted_sum(
            [(row["asset_liability_score"], dimension_weights["financial_quality"]["asset_liability_ratio_latest"])]
        )
        row["capital_return_stability_weighted_score"] = _weighted_sum(
            [(row["capital_return_stability_score"], dimension_weights["financial_quality"]["capital_return_stability"])]
        )
        row["financial_quality_score"] = _weighted_sum(
            [
                (row["cash_conversion_score"], dimension_weights["financial_quality"]["cash_conversion_ratio_3y"]),
                (row["asset_liability_score"], dimension_weights["financial_quality"]["asset_liability_ratio_latest"]),
                (row["capital_return_stability_score"], dimension_weights["financial_quality"]["capital_return_stability"]),
            ]
        )

        row["pe_weighted_score"] = _weighted_sum(
            [(row["pe_score"], dimension_weights["valuation_fit"]["pe_ttm"])]
        )
        row["pb_weighted_score"] = _weighted_sum(
            [(row["pb_score"], dimension_weights["valuation_fit"]["pb_latest"])]
        )
        row["dividend_yield_weighted_score"] = _weighted_sum(
            [(row["dividend_yield_score"], dimension_weights["valuation_fit"]["dividend_yield_avg_3y"])]
        )
        row["valuation_fit_score"] = _weighted_sum(
            [
                (row["pe_score"], dimension_weights["valuation_fit"]["pe_ttm"]),
                (row["pb_score"], dimension_weights["valuation_fit"]["pb_latest"]),
                (row["dividend_yield_score"], dimension_weights["valuation_fit"]["dividend_yield_avg_3y"]),
            ]
        )

        if row.get("is_filtered"):
            row["current_pool"] = None
            row["total_score"] = None
            row["global_rank"] = None
            row["industry_rank"] = None
            row["biz_quality_weighted_score"] = None
            row["growth_delivery_weighted_score"] = None
            row["financial_quality_weighted_score"] = None
            row["valuation_fit_weighted_score"] = None
            continue

        row["biz_quality_weighted_score"] = _weighted_sum(
            [(row["biz_quality_score"], top_level_weights["biz_quality"])]
        )
        row["growth_delivery_weighted_score"] = _weighted_sum(
            [(row["growth_delivery_score"], top_level_weights["growth_delivery"])]
        )
        row["financial_quality_weighted_score"] = _weighted_sum(
            [(row["financial_quality_score"], top_level_weights["financial_quality"])]
        )
        row["valuation_fit_weighted_score"] = _weighted_sum(
            [(row["valuation_fit_score"], top_level_weights["valuation_fit"])]
        )
        row["total_score"] = _round_score(
            (row["biz_quality_weighted_score"] or 0.0)
            + (row["growth_delivery_weighted_score"] or 0.0)
            + (row["financial_quality_weighted_score"] or 0.0)
            + (row["valuation_fit_weighted_score"] or 0.0)
        )
        row["current_pool"] = None

    scored_rows = [row for row in rows if row.get("total_score") is not None]
    scored_rows.sort(key=lambda item: (-float(item["total_score"]), item["ts_code"]))
    for index, row in enumerate(scored_rows, start=1):
        row["global_rank"] = index
        row["current_pool"] = "重点观察池" if index <= key_watch_top_n else "观察池"

    for industry_rows in industry_groups.values():
        ranked_rows = [row for row in industry_rows if row.get("total_score") is not None]
        ranked_rows.sort(key=lambda item: (-float(item["total_score"]), item["ts_code"]))
        for index, row in enumerate(ranked_rows, start=1):
            row["industry_rank"] = index

    return rows
