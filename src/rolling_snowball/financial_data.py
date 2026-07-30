from __future__ import annotations

import json
from dataclasses import replace
from functools import lru_cache
from typing import Any

import pandas as pd
import tushare as ts

from .master_sync import load_tushare_token
from .scoring_engine import StockCandidateInput


def as_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if pd.isna(value):
            return None
        return float(value)
    text = str(value).strip().replace(",", "")
    if not text or text.lower() == "nan":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def pick_value(row: pd.Series | None, *names: str) -> Any:
    if row is None:
        return None
    for name in names:
        if name in row.index:
            value = row.get(name)
            if value is not None and str(value).strip() not in {"", "nan", "None"}:
                return value
    return None


def latest_row(df: pd.DataFrame, sort_column: str) -> pd.Series | None:
    if df.empty or sort_column not in df.columns:
        return None
    working = df.copy()
    working[sort_column] = working[sort_column].astype(str)
    working = working.sort_values(sort_column)
    return working.iloc[-1]


def annual_rows(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "end_date" not in df.columns:
        return pd.DataFrame()
    working = df.copy()
    working["end_date"] = working["end_date"].astype(str)
    working = working[working["end_date"].str.endswith("1231")].copy()
    if working.empty:
        return working
    working = working.sort_values("end_date").drop_duplicates("end_date", keep="last")
    return working


def _normalize_ratio(value: float | None) -> float | None:
    if value is None:
        return None
    if abs(value) > 1.5:
        return value / 100.0
    return value


def _extract_series(df: pd.DataFrame, field_names: tuple[str, ...], count: int) -> list[float | None]:
    annual = annual_rows(df)
    if annual.empty:
        return []
    sample = annual.tail(count).copy()
    values: list[float | None] = []
    for _, row in sample.iterrows():
        values.append(as_float(pick_value(row, *field_names)))
    return values


def _yoy_series(values: list[float | None]) -> list[float | None]:
    out: list[float | None] = []
    for prev, curr in zip(values[:-1], values[1:]):
        if prev in (None, 0) or curr is None:
            out.append(None)
            continue
        out.append((curr - prev) / abs(prev))
    return out


def _mean_ratio(values: list[float | None]) -> float | None:
    valid = [_normalize_ratio(value) for value in values if value is not None]
    if not valid:
        return None
    return float(sum(valid) / len(valid))


def _std_ratio(values: list[float | None]) -> float | None:
    valid = [_normalize_ratio(value) for value in values if value is not None]
    if len(valid) < 2:
        return None
    return float(pd.Series(valid, dtype="float64").std(ddof=0))


def _cagr(values: list[float | None]) -> float | None:
    if len(values) < 4:
        return None
    start = values[0]
    end = values[-1]
    if start is None or end is None or start <= 0 or end < 0:
        return None
    return float((end / start) ** (1 / 3) - 1)


def _latest_report_period(*frames: pd.DataFrame) -> str | None:
    end_dates: list[str] = []
    for frame in frames:
        if frame.empty or "end_date" not in frame.columns:
            continue
        values = frame["end_date"].dropna().astype(str).tolist()
        if values:
            end_dates.append(max(values))
    return max(end_dates) if end_dates else None


def _normalize_audit_opinion(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if "无法表示意见" in text:
        return "无法表示意见"
    if "否定意见" in text:
        return "否定意见"
    if "无保留意见" in text:
        return "无保留意见"
    if "保留意见" in text:
        return "保留意见"
    return text


def _latest_audit_opinion(audit_df: pd.DataFrame) -> str | None:
    if audit_df.empty:
        return None
    sort_columns = [column for column in ("end_date", "ann_date") if column in audit_df.columns]
    if not sort_columns:
        return None
    working = audit_df.copy()
    for column in sort_columns:
        working[column] = working[column].fillna("").astype(str)
    working = working.sort_values(sort_columns)
    latest = working.iloc[-1]
    return _normalize_audit_opinion(pick_value(latest, "audit_result"))


def _sum_values(values: list[float | None]) -> float | None:
    valid = [value for value in values if value is not None]
    if not valid:
        return None
    return float(sum(valid))


def _mean_values(values: list[float | None]) -> float | None:
    valid = [value for value in values if value is not None]
    if not valid:
        return None
    return float(sum(valid) / len(valid))


def _year_end_close_map(daily_df: pd.DataFrame, years: list[str]) -> dict[str, float | None]:
    result: dict[str, float | None] = {year: None for year in years}
    if daily_df.empty or "trade_date" not in daily_df.columns or "close" not in daily_df.columns:
        return result
    working = daily_df.copy()
    working["trade_date"] = working["trade_date"].astype(str)
    working["close"] = pd.to_numeric(working["close"], errors="coerce")
    working = working.dropna(subset=["close"]).sort_values("trade_date")
    for year in years:
        year_rows = working[working["trade_date"].str.startswith(year)]
        if year_rows.empty:
            continue
        result[year] = as_float(year_rows.iloc[-1]["close"])
    return result


def _aggregate_dividend_metrics(dividend_df: pd.DataFrame, daily_df: pd.DataFrame) -> tuple[float | None, float | None]:
    if dividend_df.empty or "end_date" not in dividend_df.columns:
        return None, None

    working = dividend_df.copy()
    working["end_date"] = working["end_date"].astype(str)
    if "div_proc" in working.columns:
        working = working[working["div_proc"].astype(str) == "实施"].copy()
    if working.empty:
        return 0.0, 0.0

    cash_column = "cash_div_tax" if "cash_div_tax" in working.columns else "cash_div"
    if cash_column not in working.columns:
        return None, None

    working[cash_column] = pd.to_numeric(working[cash_column], errors="coerce")
    if "base_share" in working.columns:
        working["base_share"] = pd.to_numeric(working["base_share"], errors="coerce")
    else:
        working["base_share"] = pd.NA
    working = working.dropna(subset=[cash_column])
    if working.empty:
        return 0.0, 0.0

    working["year"] = working["end_date"].str[:4]
    years = sorted(working["year"].dropna().astype(str).unique().tolist())[-3:]
    if not years:
        return 0.0, 0.0
    working = working[working["year"].isin(years)].copy()

    annual_per_share = working.groupby("year")[cash_column].sum().to_dict()

    total_dividend_amount = 0.0
    amount_available = False
    for _, row in working.iterrows():
        per_share = as_float(row.get(cash_column))
        base_share = as_float(row.get("base_share"))
        if per_share is None or base_share is None:
            continue
        total_dividend_amount += per_share * base_share * 10_000
        amount_available = True

    close_map = _year_end_close_map(daily_df, years)
    annual_yields: list[float | None] = []
    for year in years:
        annual_per_share_value = as_float(annual_per_share.get(year))
        year_close = close_map.get(year)
        if annual_per_share_value is None or year_close in (None, 0):
            annual_yields.append(None)
            continue
        annual_yields.append(annual_per_share_value / year_close)

    return (total_dividend_amount if amount_available else None), _mean_values(annual_yields)


def _aggregate_repurchase_amount(repurchase_df: pd.DataFrame) -> float | None:
    if repurchase_df.empty:
        return 0.0

    working = repurchase_df.copy()
    sort_column = "ann_date" if "ann_date" in working.columns else "end_date"
    if sort_column not in working.columns or "proc" not in working.columns or "amount" not in working.columns:
        return None
    working[sort_column] = working[sort_column].fillna("").astype(str)
    working["end_date"] = working.get("end_date", pd.Series(dtype="object")).fillna("").astype(str)
    working["proc"] = working["proc"].fillna("").astype(str)
    working["amount"] = pd.to_numeric(working["amount"], errors="coerce")
    working = working.sort_values(sort_column)

    plan_amounts: dict[int, float] = {}
    plan_years: dict[int, str] = {}
    current_plan_id: int | None = None
    plan_counter = 0

    for _, row in working.iterrows():
        proc = str(row.get("proc") or "")
        amount = as_float(row.get("amount"))
        end_date = str(row.get("end_date") or "")
        ann_date = str(row.get("ann_date") or "")
        plan_year = (end_date[:4] if end_date else ann_date[:4]) or ""

        if proc == "预案":
            plan_counter += 1
            current_plan_id = plan_counter
            plan_years[current_plan_id] = plan_year
            continue

        if proc not in {"实施", "完成"} or amount is None:
            continue

        if current_plan_id is None:
            plan_counter += 1
            current_plan_id = plan_counter
            plan_years[current_plan_id] = plan_year

        plan_amounts[current_plan_id] = max(amount, plan_amounts.get(current_plan_id, 0.0))
        if plan_year:
            plan_years[current_plan_id] = plan_year

    if not plan_amounts:
        return 0.0

    target_years = sorted({year for year in plan_years.values() if year})[-3:]
    return float(
        sum(
            amount
            for plan_id, amount in plan_amounts.items()
            if plan_years.get(plan_id) in target_years
        )
    )


def build_candidate_from_frames(
    candidate: StockCandidateInput,
    *,
    fina_indicator_df: pd.DataFrame,
    income_df: pd.DataFrame,
    cashflow_df: pd.DataFrame,
    daily_basic_df: pd.DataFrame,
    daily_df: pd.DataFrame,
    balancesheet_df: pd.DataFrame,
    audit_df: pd.DataFrame,
    dividend_df: pd.DataFrame,
    repurchase_df: pd.DataFrame,
) -> StockCandidateInput:
    annual_fina = annual_rows(fina_indicator_df)
    annual_income = annual_rows(income_df)
    annual_cashflow = annual_rows(cashflow_df)

    nonrec_np_4y = _extract_series(annual_fina, ("profit_dedt",), 4)
    nonrec_np_3y = nonrec_np_4y[-3:] if len(nonrec_np_4y) >= 3 else nonrec_np_4y
    nonrec_np_yoy_3y = _yoy_series(nonrec_np_4y)[-3:] if len(nonrec_np_4y) >= 4 else []

    operating_cashflow_3y = _extract_series(annual_cashflow, ("n_cashflow_act", "n_cash_flows_fnc_act"), 3)
    revenue_4y = _extract_series(annual_income, ("revenue", "total_revenue", "total_revenue_ps"), 4)
    parent_np_3y = _extract_series(annual_income, ("n_income_attr_p", "n_income"), 3)

    gross_margin_3y = _extract_series(annual_fina, ("grossprofit_margin", "gross_margin"), 3)
    roe_3y = _extract_series(annual_fina, ("roe", "roe_dt"), 3)
    net_margin_3y = _extract_series(annual_fina, ("netprofit_margin", "net_margin"), 3)

    latest_fina_row = latest_row(fina_indicator_df, "end_date")
    latest_income_row = latest_row(income_df, "end_date")
    latest_daily_basic_row = latest_row(daily_basic_df, "trade_date")
    latest_balance_row = latest_row(balancesheet_df, "end_date")

    total_market_cap = None
    raw_total_mv = as_float(pick_value(latest_daily_basic_row, "total_mv"))
    if raw_total_mv is not None:
        total_market_cap = raw_total_mv * 10_000

    avg_turnover_20d = None
    if not daily_df.empty and "amount" in daily_df.columns:
        working_daily = daily_df.copy()
        working_daily["trade_date"] = working_daily["trade_date"].astype(str)
        working_daily["amount"] = pd.to_numeric(working_daily["amount"], errors="coerce")
        sample = working_daily.sort_values("trade_date").tail(20)
        if not sample.empty:
            avg_amount = as_float(sample["amount"].mean())
            if avg_amount is not None:
                avg_turnover_20d = avg_amount * 1_000

    cash_to_short_debt_ratio = None
    money_cap = as_float(pick_value(latest_balance_row, "money_cap"))
    short_debt = sum(
        value or 0.0
        for value in (
            as_float(pick_value(latest_balance_row, "st_borr")),
            as_float(pick_value(latest_balance_row, "non_cur_liab_due_1y")),
        )
    )
    if money_cap is not None and short_debt > 0:
        cash_to_short_debt_ratio = money_cap / short_debt

    cash_conversion_ratio_3y = None
    if len(nonrec_np_3y) == 3 and len(operating_cashflow_3y) == 3:
        nonrec_sum = sum(value for value in nonrec_np_3y if value is not None)
        ocf_sum = sum(value for value in operating_cashflow_3y if value is not None)
        if nonrec_sum > 0:
            cash_conversion_ratio_3y = ocf_sum / nonrec_sum

    dividend_sum_3y, dividend_yield_avg_3y = _aggregate_dividend_metrics(dividend_df, daily_df)
    buyback_sum_3y = _aggregate_repurchase_amount(repurchase_df)
    shareholder_return_ratio_3y = None
    parent_np_sum_3y = _sum_values(parent_np_3y)
    if parent_np_sum_3y is not None and parent_np_sum_3y > 0:
        shareholder_return_ratio_3y = ((dividend_sum_3y or 0.0) + (buyback_sum_3y or 0.0)) / parent_np_sum_3y

    return replace(
        candidate,
        latest_report_period=_latest_report_period(
            fina_indicator_df,
            income_df,
            cashflow_df,
            balancesheet_df,
        )
        or candidate.latest_report_period,
        audit_opinion=_latest_audit_opinion(audit_df) or candidate.audit_opinion,
        nonrec_np_3y=tuple(nonrec_np_3y),
        nonrec_np_yoy_3y=tuple(nonrec_np_yoy_3y),
        operating_cashflow_3y=tuple(operating_cashflow_3y),
        gross_margin_avg_3y=_mean_ratio(gross_margin_3y),
        roe_avg_3y=_mean_ratio(roe_3y),
        net_margin_avg_3y=_mean_ratio(net_margin_3y),
        latest_revenue=as_float(pick_value(latest_income_row, "revenue", "total_revenue", "total_revenue_ps")),
        latest_nonrec_np=as_float(pick_value(latest_fina_row, "profit_dedt")),
        revenue_cagr_3y=_cagr(revenue_4y),
        nonrec_np_cagr_3y=_cagr(nonrec_np_4y),
        shareholder_return_ratio_3y=shareholder_return_ratio_3y,
        dividend_sum_3y=dividend_sum_3y,
        buyback_sum_3y=buyback_sum_3y,
        parent_np_sum_3y=parent_np_sum_3y,
        cash_conversion_ratio_3y=cash_conversion_ratio_3y,
        asset_liability_ratio_latest=_normalize_ratio(as_float(pick_value(latest_fina_row, "debt_to_assets"))),
        cash_to_short_debt_ratio=cash_to_short_debt_ratio,
        total_market_cap=total_market_cap,
        avg_turnover_20d=avg_turnover_20d,
        pe_ttm=as_float(pick_value(latest_daily_basic_row, "pe_ttm", "pe")),
        pb_latest=as_float(pick_value(latest_daily_basic_row, "pb")),
        dividend_yield_avg_3y=dividend_yield_avg_3y,
        roe_std_3y=_std_ratio(roe_3y),
    )


class TushareScoringDataSource:
    def __init__(self) -> None:
        self.pro = ts.pro_api(load_tushare_token())

    @lru_cache(maxsize=2048)
    def _query_json(self, api_name: str, kwargs_json: str) -> str:
        kwargs = json.loads(kwargs_json)
        method = getattr(self.pro, api_name, None)
        try:
            if callable(method):
                df = method(**kwargs)
            else:
                df = self.pro.query(api_name, **kwargs)
        except Exception:  # noqa: BLE001
            return "[]"
        if not isinstance(df, pd.DataFrame) or df.empty:
            return "[]"
        return df.to_json(orient="records", force_ascii=False)

    def query(self, api_name: str, **kwargs: Any) -> pd.DataFrame:
        payload = self._query_json(api_name, json.dumps(kwargs, sort_keys=True, ensure_ascii=False))
        data = json.loads(payload)
        return pd.DataFrame(data)

    def enrich_candidate(self, candidate: StockCandidateInput) -> StockCandidateInput:
        ts_code = candidate.ts_code
        fina_indicator_df = self.query(
            "fina_indicator",
            ts_code=ts_code,
            fields="ts_code,end_date,roe,roe_dt,grossprofit_margin,netprofit_margin,debt_to_assets,profit_dedt",
        )
        income_df = self.query(
            "income",
            ts_code=ts_code,
            fields="ts_code,end_date,revenue,total_revenue,n_income_attr_p",
        )
        cashflow_df = self.query(
            "cashflow",
            ts_code=ts_code,
            fields="ts_code,end_date,n_cashflow_act,n_cash_flows_fnc_act",
        )
        daily_basic_df = self.query(
            "daily_basic",
            ts_code=ts_code,
            fields="ts_code,trade_date,pe_ttm,pb,total_mv",
        )
        daily_df = self.query(
            "daily",
            ts_code=ts_code,
            fields="ts_code,trade_date,close,amount",
        )
        balancesheet_df = self.query(
            "balancesheet",
            ts_code=ts_code,
            fields="ts_code,end_date,money_cap,st_borr,non_cur_liab_due_1y",
        )
        audit_df = self.query(
            "fina_audit",
            ts_code=ts_code,
            fields="ts_code,ann_date,end_date,audit_result",
        )
        dividend_df = self.query(
            "dividend",
            ts_code=ts_code,
            fields="ts_code,end_date,ann_date,div_proc,cash_div,cash_div_tax,record_date,ex_date,base_share",
        )
        repurchase_df = self.query(
            "repurchase",
            ts_code=ts_code,
            fields="ts_code,ann_date,end_date,proc,exp_date,amount",
        )
        return build_candidate_from_frames(
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
