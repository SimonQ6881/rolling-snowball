from __future__ import annotations

from datetime import datetime

from src.rolling_snowball.scoring_engine import StockCandidateInput, evaluate_candidate


def test_evaluate_candidate_marks_filter_reasons_and_warnings() -> None:
    result = evaluate_candidate(
        StockCandidateInput(
            ts_code="000001.SZ",
            stock_name="*ST样本",
            market="A股",
            sw_level1_industry="银行",
            list_status="L",
            audit_opinion="保留意见",
            nonrec_np_3y=(-1.0, -2.0, 10.0),
            nonrec_np_yoy_3y=(-0.1, -0.2, 0.3),
            operating_cashflow_3y=(-2.0, -1.0, 1.0),
            asset_liability_ratio_latest=0.8,
            cash_to_short_debt_ratio=0.5,
            total_market_cap=2_500_000_000,
            avg_turnover_20d=20_000_000,
            pe_ttm=-5.0,
            pb_latest=-1.0,
        ),
        run_id="run-1",
        rule_version="v1.0",
        data_version="20260729",
        scored_at=datetime(2026, 7, 29, 12, 0, 0),
    )

    assert result.is_filtered is True
    assert result.filter_reasons == (
        "st_flag",
        "negative_nonrec_np_2of3y",
        "nonrec_np_yoy_decline_2of3y",
        "cash_conversion_ratio_below_0_6",
        "asset_liability_ratio_above_70pct",
        "market_cap_below_3bn",
        "avg_turnover_20d_below_30m",
    )
    assert result.manual_review_required is True
    assert result.cashflow_warning is True
    assert result.short_debt_warning is True
    assert result.pe_invalid is True
    assert result.pb_invalid is True
    assert result.data_missing is False
    assert result.warning_tags == (
        "manual_review",
        "cashflow_warning",
        "short_debt_warning",
        "pe_invalid",
        "pb_invalid",
    )


def test_evaluate_candidate_marks_missing_data_when_only_master_fields_exist() -> None:
    result = evaluate_candidate(
        StockCandidateInput(
            ts_code="600000.SH",
            stock_name="浦发银行",
            market="A股",
            sw_level1_industry="银行",
            list_status="L",
        ),
        run_id="run-2",
        rule_version="v1.0",
        data_version="20260729",
        scored_at=datetime(2026, 7, 29, 12, 0, 0),
    )

    assert result.is_filtered is False
    assert result.filter_reasons == ()
    assert result.total_score is None
    assert result.current_pool is None
    assert result.data_missing is True
    assert result.warning_tags == ("data_missing",)
