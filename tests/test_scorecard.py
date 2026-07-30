from __future__ import annotations

from src.rolling_snowball.scorecard import apply_scores


def _base_row(ts_code: str, **overrides: float | int | str | bool | list[str] | None) -> dict[str, object]:
    row: dict[str, object] = {
        "ts_code": ts_code,
        "sw_level1_industry": "食品饮料",
        "_latest_revenue": None,
        "_latest_nonrec_np": None,
        "_total_market_cap_internal": None,
        "gross_margin_avg_3y": None,
        "roe_avg_3y": None,
        "net_margin_avg_3y": None,
        "revenue_cagr_3y": None,
        "nonrec_np_cagr_3y": None,
        "shareholder_return_ratio_3y": None,
        "cash_conversion_ratio_3y": None,
        "asset_liability_ratio_latest": None,
        "pe_ttm": None,
        "pb_latest": None,
        "dividend_yield_avg_3y": None,
        "roe_std_3y": None,
        "pe_invalid": False,
        "pb_invalid": False,
        "warning_tags": [],
        "data_missing": False,
        "is_filtered": False,
    }
    row.update(overrides)
    return row


def test_apply_scores_calculates_total_score_pool_and_rank() -> None:
    rows = [
        _base_row(
            "000001.SZ",
            _latest_revenue=300.0,
            _latest_nonrec_np=50.0,
            _total_market_cap_internal=8_000_000_000.0,
            gross_margin_avg_3y=0.40,
            roe_avg_3y=0.20,
            net_margin_avg_3y=0.15,
            revenue_cagr_3y=0.25,
            nonrec_np_cagr_3y=0.30,
            shareholder_return_ratio_3y=0.10,
            cash_conversion_ratio_3y=1.20,
            asset_liability_ratio_latest=0.30,
            pe_ttm=15.0,
            pb_latest=2.0,
            dividend_yield_avg_3y=0.03,
            roe_std_3y=0.02,
        ),
        _base_row(
            "000002.SZ",
            _latest_revenue=100.0,
            _latest_nonrec_np=10.0,
            _total_market_cap_internal=3_500_000_000.0,
            gross_margin_avg_3y=0.20,
            roe_avg_3y=0.08,
            net_margin_avg_3y=0.06,
            revenue_cagr_3y=0.08,
            nonrec_np_cagr_3y=0.05,
            shareholder_return_ratio_3y=0.02,
            cash_conversion_ratio_3y=0.70,
            asset_liability_ratio_latest=0.55,
            pe_ttm=30.0,
            pb_latest=4.0,
            dividend_yield_avg_3y=0.01,
            roe_std_3y=0.08,
        ),
        _base_row(
            "000003.SZ",
            _latest_revenue=200.0,
            _latest_nonrec_np=20.0,
            _total_market_cap_internal=4_000_000_000.0,
            gross_margin_avg_3y=0.30,
            roe_avg_3y=0.10,
            net_margin_avg_3y=0.08,
            revenue_cagr_3y=0.10,
            nonrec_np_cagr_3y=0.10,
            shareholder_return_ratio_3y=0.03,
            cash_conversion_ratio_3y=0.80,
            asset_liability_ratio_latest=0.50,
            pe_ttm=20.0,
            pb_latest=3.0,
            dividend_yield_avg_3y=0.015,
            roe_std_3y=0.05,
            is_filtered=True,
        ),
        _base_row(
            "000004.SZ",
            _latest_revenue=90.0,
            _latest_nonrec_np=8.0,
            _total_market_cap_internal=3_200_000_000.0,
            gross_margin_avg_3y=0.18,
            roe_avg_3y=0.06,
            net_margin_avg_3y=0.05,
            revenue_cagr_3y=0.06,
            nonrec_np_cagr_3y=0.04,
            shareholder_return_ratio_3y=0.01,
            cash_conversion_ratio_3y=0.65,
            asset_liability_ratio_latest=0.58,
            pe_ttm=35.0,
            pb_latest=4.5,
            dividend_yield_avg_3y=0.008,
            roe_std_3y=0.09,
        ),
        _base_row(
            "000005.SZ",
            _latest_revenue=80.0,
            _latest_nonrec_np=6.0,
            _total_market_cap_internal=3_100_000_000.0,
            gross_margin_avg_3y=0.16,
            roe_avg_3y=0.05,
            net_margin_avg_3y=0.04,
            revenue_cagr_3y=0.03,
            nonrec_np_cagr_3y=0.02,
            shareholder_return_ratio_3y=0.005,
            cash_conversion_ratio_3y=0.60,
            asset_liability_ratio_latest=0.60,
            pe_ttm=40.0,
            pb_latest=5.0,
            dividend_yield_avg_3y=0.005,
            roe_std_3y=0.10,
        ),
    ]

    scored = apply_scores(rows)
    first = next(item for item in scored if item["ts_code"] == "000001.SZ")
    second = next(item for item in scored if item["ts_code"] == "000002.SZ")
    third = next(item for item in scored if item["ts_code"] == "000003.SZ")

    assert first["total_score"] is not None
    assert second["total_score"] is not None
    assert float(first["total_score"]) > float(second["total_score"])
    assert first["current_pool"] == "重点观察池"
    assert second["current_pool"] == "重点观察池"
    assert first["global_rank"] == 1
    assert second["global_rank"] == 2
    assert first["industry_rank"] == 1
    assert second["industry_rank"] == 2
    assert first["industry_total"] == 5
    assert third["industry_total"] == 5
    assert third["total_score"] is None
    assert third["industry_rank"] is None


def test_apply_scores_small_industry_sample_reverts_toward_neutral() -> None:
    rows = [
        _base_row(
            "300001.SZ",
            sw_level1_industry="综合类",
            _latest_revenue=120.0,
            _latest_nonrec_np=12.0,
            _total_market_cap_internal=5_000_000_000.0,
            gross_margin_avg_3y=0.35,
            roe_avg_3y=0.16,
            net_margin_avg_3y=0.12,
            revenue_cagr_3y=0.20,
            nonrec_np_cagr_3y=0.22,
            shareholder_return_ratio_3y=0.08,
            cash_conversion_ratio_3y=1.00,
            asset_liability_ratio_latest=0.35,
            pe_ttm=18.0,
            pb_latest=2.2,
            dividend_yield_avg_3y=0.02,
            roe_std_3y=0.03,
        )
    ]

    scored = apply_scores(rows)
    only = scored[0]

    assert only["industry_total"] == 1
    assert only["gross_margin_score"] == 50.0
    assert only["industry_position_score"] == 50.0
    assert only["capital_return_stability_score"] == 50.0
    assert only["total_score"] == 50.0
    assert only["current_pool"] == "重点观察池"
    assert "small_industry_sample" in only["warning_tags"]
    assert "data_missing" not in only["warning_tags"]


def test_apply_scores_assigns_key_watch_pool_to_top_20_only() -> None:
    rows = [
        _base_row(
            f"{index:06d}.SZ",
            _latest_revenue=float(10_000 - index * 10),
            _latest_nonrec_np=float(1_000 - index),
            _total_market_cap_internal=float(20_000_000_000 - index * 100_000_000),
            gross_margin_avg_3y=0.50 - index * 0.005,
            roe_avg_3y=0.30 - index * 0.003,
            net_margin_avg_3y=0.20 - index * 0.002,
            revenue_cagr_3y=0.30 - index * 0.003,
            nonrec_np_cagr_3y=0.28 - index * 0.003,
            shareholder_return_ratio_3y=0.10 - index * 0.002,
            cash_conversion_ratio_3y=1.30 - index * 0.01,
            asset_liability_ratio_latest=0.20 + index * 0.01,
            pe_ttm=10.0 + index,
            pb_latest=1.0 + index * 0.1,
            dividend_yield_avg_3y=0.05 - index * 0.001,
            roe_std_3y=0.01 + index * 0.002,
        )
        for index in range(21)
    ]
    rows.append(
        _base_row(
            "999999.SZ",
            is_filtered=True,
            _latest_revenue=99_999.0,
            _latest_nonrec_np=9_999.0,
            _total_market_cap_internal=99_999_000_000.0,
            gross_margin_avg_3y=0.99,
            roe_avg_3y=0.99,
            net_margin_avg_3y=0.99,
            revenue_cagr_3y=0.99,
            nonrec_np_cagr_3y=0.99,
            shareholder_return_ratio_3y=0.99,
            cash_conversion_ratio_3y=2.0,
            asset_liability_ratio_latest=0.01,
            pe_ttm=1.0,
            pb_latest=0.5,
            dividend_yield_avg_3y=0.10,
            roe_std_3y=0.001,
        )
    )

    scored = apply_scores(rows)
    filtered = next(item for item in scored if item["ts_code"] == "999999.SZ")
    twentieth = next(item for item in scored if item["global_rank"] == 20)
    twenty_first = next(item for item in scored if item["global_rank"] == 21)

    assert filtered["total_score"] is None
    assert filtered["current_pool"] is None
    assert twentieth["current_pool"] == "重点观察池"
    assert twenty_first["current_pool"] == "观察池"


def test_apply_scores_tags_metric_invalid_without_marking_data_missing() -> None:
    rows = [
        _base_row(
            "600001.SH",
            pe_ttm=-5.0,
            pe_invalid=True,
            pb_latest=1.2,
            _latest_revenue=300.0,
            _latest_nonrec_np=50.0,
            _total_market_cap_internal=8_000_000_000.0,
            gross_margin_avg_3y=0.40,
            roe_avg_3y=0.20,
            net_margin_avg_3y=0.15,
            revenue_cagr_3y=0.25,
            nonrec_np_cagr_3y=0.30,
            shareholder_return_ratio_3y=0.10,
            cash_conversion_ratio_3y=1.20,
            asset_liability_ratio_latest=0.30,
            dividend_yield_avg_3y=0.03,
            roe_std_3y=0.02,
        ),
        _base_row(
            "600002.SH",
            _latest_revenue=250.0,
            _latest_nonrec_np=40.0,
            _total_market_cap_internal=7_000_000_000.0,
            gross_margin_avg_3y=0.38,
            roe_avg_3y=0.18,
            net_margin_avg_3y=0.13,
            revenue_cagr_3y=0.20,
            nonrec_np_cagr_3y=0.24,
            shareholder_return_ratio_3y=0.09,
            cash_conversion_ratio_3y=1.00,
            asset_liability_ratio_latest=0.35,
            pe_ttm=15.0,
            pb_latest=1.4,
            dividend_yield_avg_3y=0.025,
            roe_std_3y=0.03,
        ),
        _base_row(
            "600003.SH",
            _latest_revenue=200.0,
            _latest_nonrec_np=30.0,
            _total_market_cap_internal=6_000_000_000.0,
            gross_margin_avg_3y=0.32,
            roe_avg_3y=0.14,
            net_margin_avg_3y=0.11,
            revenue_cagr_3y=0.15,
            nonrec_np_cagr_3y=0.18,
            shareholder_return_ratio_3y=0.07,
            cash_conversion_ratio_3y=0.95,
            asset_liability_ratio_latest=0.40,
            pe_ttm=20.0,
            pb_latest=1.8,
            dividend_yield_avg_3y=0.02,
            roe_std_3y=0.04,
        ),
        _base_row(
            "600004.SH",
            _latest_revenue=150.0,
            _latest_nonrec_np=20.0,
            _total_market_cap_internal=5_000_000_000.0,
            gross_margin_avg_3y=0.28,
            roe_avg_3y=0.10,
            net_margin_avg_3y=0.08,
            revenue_cagr_3y=0.10,
            nonrec_np_cagr_3y=0.12,
            shareholder_return_ratio_3y=0.05,
            cash_conversion_ratio_3y=0.85,
            asset_liability_ratio_latest=0.45,
            pe_ttm=25.0,
            pb_latest=2.2,
            dividend_yield_avg_3y=0.015,
            roe_std_3y=0.05,
        ),
        _base_row(
            "600005.SH",
            _latest_revenue=100.0,
            _latest_nonrec_np=10.0,
            _total_market_cap_internal=4_000_000_000.0,
            gross_margin_avg_3y=0.22,
            roe_avg_3y=0.08,
            net_margin_avg_3y=0.06,
            revenue_cagr_3y=0.08,
            nonrec_np_cagr_3y=0.06,
            shareholder_return_ratio_3y=0.03,
            cash_conversion_ratio_3y=0.75,
            asset_liability_ratio_latest=0.50,
            pe_ttm=30.0,
            pb_latest=2.6,
            dividend_yield_avg_3y=0.01,
            roe_std_3y=0.06,
        ),
    ]

    scored = apply_scores(rows)
    first = next(item for item in scored if item["ts_code"] == "600001.SH")

    assert first["pe_score"] == 0.0
    assert "metric_invalid" in first["warning_tags"]
    assert "pe_invalid" in first["warning_tags"]
    assert "data_missing" not in first["warning_tags"]
