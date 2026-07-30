from __future__ import annotations

from math import isclose

import pandas as pd

from src.rolling_snowball.financial_data import build_candidate_from_frames
from src.rolling_snowball.scoring_engine import StockCandidateInput


def test_build_candidate_from_frames_extracts_hard_filter_inputs_and_raw_metrics() -> None:
    candidate = StockCandidateInput(
        ts_code="000001.SZ",
        stock_name="平安银行",
        market="A股",
        sw_level1_industry="银行",
        list_status="L",
    )

    fina_indicator_df = pd.DataFrame(
        [
            {"end_date": "20221231", "roe": 9.0, "grossprofit_margin": 28.0, "netprofit_margin": 18.0, "debt_to_assets": 68.0, "profit_dedt": 100.0},
            {"end_date": "20231231", "roe": 10.0, "grossprofit_margin": 30.0, "netprofit_margin": 20.0, "debt_to_assets": 66.0, "profit_dedt": 110.0},
            {"end_date": "20241231", "roe": 12.0, "grossprofit_margin": 32.0, "netprofit_margin": 22.0, "debt_to_assets": 65.0, "profit_dedt": 121.0},
            {"end_date": "20251231", "roe": 8.0, "grossprofit_margin": 34.0, "netprofit_margin": 24.0, "debt_to_assets": 64.0, "profit_dedt": 90.0},
        ]
    )
    income_df = pd.DataFrame(
        [
            {"end_date": "20221231", "revenue": 1000.0, "n_income_attr_p": 120.0},
            {"end_date": "20231231", "revenue": 1100.0, "n_income_attr_p": 130.0},
            {"end_date": "20241231", "revenue": 1210.0, "n_income_attr_p": 140.0},
            {"end_date": "20251231", "revenue": 1331.0, "n_income_attr_p": 150.0},
        ]
    )
    cashflow_df = pd.DataFrame(
        [
            {"end_date": "20231231", "n_cashflow_act": 80.0},
            {"end_date": "20241231", "n_cashflow_act": 85.0},
            {"end_date": "20251231", "n_cashflow_act": 90.0},
        ]
    )
    daily_basic_df = pd.DataFrame(
        [
            {"trade_date": "20260728", "pe_ttm": 8.5, "pb": 0.95, "total_mv": 350000.0},
        ]
    )
    daily_df = pd.DataFrame(
        [
            {"trade_date": "20231229", "close": 10.0, "amount": 1000.0},
            {"trade_date": "20241231", "close": 12.0, "amount": 1000.0},
            {"trade_date": "20251231", "close": 15.0, "amount": 1000.0},
        ]
        + [{"trade_date": f"202607{i:02d}", "close": 8.0, "amount": 50000.0} for i in range(1, 21)]
    )
    balancesheet_df = pd.DataFrame(
        [
            {"end_date": "20251231", "money_cap": 200.0, "st_borr": 80.0, "non_cur_liab_due_1y": 20.0},
        ]
    )
    audit_df = pd.DataFrame(
        [
            {"ann_date": "20240315", "end_date": "20231231", "audit_result": "标准无保留意见"},
            {"ann_date": "20250315", "end_date": "20241231", "audit_result": "标准无保留意见"},
            {"ann_date": "20260315", "end_date": "20251231", "audit_result": "保留意见"},
        ]
    )
    dividend_df = pd.DataFrame(
        [
            {"end_date": "20231231", "div_proc": "实施", "cash_div_tax": 1.0, "base_share": 0.01},
            {"end_date": "20241231", "div_proc": "实施", "cash_div_tax": 1.2, "base_share": 0.011},
            {"end_date": "20251231", "div_proc": "实施", "cash_div_tax": 1.5, "base_share": 0.012},
        ]
    )
    repurchase_df = pd.DataFrame(
        [
            {"ann_date": "20240101", "end_date": None, "proc": "预案", "amount": 50.0},
            {"ann_date": "20240120", "end_date": "20240119", "proc": "完成", "amount": 30.0},
            {"ann_date": "20240220", "end_date": "20240219", "proc": "完成", "amount": 40.0},
            {"ann_date": "20250105", "end_date": None, "proc": "预案", "amount": 100.0},
            {"ann_date": "20250201", "end_date": "20250131", "proc": "完成", "amount": 60.0},
            {"ann_date": "20250301", "end_date": "20250228", "proc": "完成", "amount": 80.0},
        ]
    )

    enriched = build_candidate_from_frames(
        candidate,
        fina_indicator_df=fina_indicator_df,
        income_df=income_df,
        cashflow_df=cashflow_df,
        daily_basic_df=daily_basic_df,
        daily_df=daily_df,
        balancesheet_df=balancesheet_df,
        audit_df=audit_df,
        dividend_df=dividend_df,
        repurchase_df=repurchase_df,
    )

    assert enriched.nonrec_np_3y == (110.0, 121.0, 90.0)
    assert len(enriched.nonrec_np_yoy_3y) == 3
    assert isclose(enriched.nonrec_np_yoy_3y[-1], (90.0 - 121.0) / 121.0)
    assert enriched.operating_cashflow_3y == (80.0, 85.0, 90.0)
    assert isclose(enriched.gross_margin_avg_3y or 0.0, 0.32)
    assert isclose(enriched.roe_avg_3y or 0.0, 0.10)
    assert isclose(enriched.net_margin_avg_3y or 0.0, 0.22)
    assert isclose(enriched.revenue_cagr_3y or 0.0, 0.10)
    assert isclose(enriched.shareholder_return_ratio_3y or 0.0, (412.0 + 120.0) / (130.0 + 140.0 + 150.0))
    assert enriched.dividend_sum_3y == 412.0
    assert enriched.buyback_sum_3y == 120.0
    assert enriched.parent_np_sum_3y == 420.0
    assert isclose(enriched.cash_conversion_ratio_3y or 0.0, (80.0 + 85.0 + 90.0) / (110.0 + 121.0 + 90.0))
    assert isclose(enriched.asset_liability_ratio_latest or 0.0, 0.64)
    assert isclose(enriched.cash_to_short_debt_ratio or 0.0, 2.0)
    assert enriched.total_market_cap == 3_500_000_000.0
    assert enriched.avg_turnover_20d == 50_000_000.0
    assert enriched.pe_ttm == 8.5
    assert enriched.pb_latest == 0.95
    assert isclose(enriched.dividend_yield_avg_3y or 0.0, 0.1)
    assert enriched.latest_report_period == "20251231"
    assert enriched.audit_opinion == "保留意见"
