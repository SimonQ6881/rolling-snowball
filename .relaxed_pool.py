from pathlib import Path

import numpy as np
import pandas as pd
import tushare as ts


ROOT = Path("/Users/user/Documents/personal/zijinDaily")
TRADE_DATE = "20260710"


def load_market(pro):
    basic = pro.stock_basic(
        exchange="",
        list_status="L",
        fields="ts_code,symbol,name,industry,market,list_date",
    )
    parts = []
    for offset in (0, 2000, 4000, 6000):
        df = pro.daily_basic(
            trade_date=TRADE_DATE,
            fields="ts_code,close,pe_ttm,pb,dv_ttm",
            limit=2000,
            offset=offset,
        )
        if df is None or df.empty:
            break
        parts.append(df)
        if len(df) < 2000:
            break
    market = pd.concat(parts, ignore_index=True)
    df = basic.merge(market, on="ts_code", how="inner")
    df = df[~df["name"].fillna("").str.contains("ST|退")].copy()
    return df


def sector_masks(df):
    return {
        "银行": df["industry"].eq("银行"),
        "运营商": df["name"].isin(["中国移动", "中国电信", "中国联通"]),
        "资源类": df["industry"].fillna("").str.contains(
            "煤|石油|铜|铝|铅锌|黄金|普钢|特钢|小金属|焦炭|钾肥|磷化工|油气"
        ),
        "公用事业": df["industry"].fillna("").str.contains(
            "火力发电|水力发电|电力|供气供热|燃气|水务"
        ),
        "消费类": df["industry"].fillna("").str.contains(
            "纺织|服饰|食品|饮料|乳制品|家居|家用轻工|白酒|啤酒|调味发酵品"
        ),
    }


def yoy(curr, prev):
    if pd.isna(curr) or pd.isna(prev) or prev == 0:
        return np.nan
    return (curr - prev) / abs(prev) * 100


def calc_dividend_years(pro, ts_code):
    div = pro.dividend(
        ts_code=ts_code,
        fields="ts_code,end_date,ann_date,cash_div_tax,div_proc",
    )
    if div is None or div.empty:
        return 0
    div = div.copy()
    div["year"] = div["end_date"].astype(str).str[:4]
    years = sorted(
        {
            int(y)
            for y in div[
                (div["cash_div_tax"].fillna(0) > 0) & (div["div_proc"] == "实施")
            ]["year"].dropna().tolist()
        }
    )
    if not years:
        return 0
    consec = 1
    for i in range(len(years) - 1, 0, -1):
        if years[i] - years[i - 1] == 1:
            consec += 1
        else:
            break
    return consec


def calc_financials(pro, ts_code):
    income_map = {}
    for period in ("20221231", "20231231", "20241231", "20251231"):
        df = pro.income(
            ts_code=ts_code,
            period=period,
            fields="ts_code,end_date,n_income_attr_p,total_revenue,revenue",
        )
        if df is None or df.empty:
            continue
        df = df.dropna(subset=["end_date"]).drop_duplicates(subset=["end_date"], keep="last")
        if df.empty:
            continue
        row = df.iloc[0]
        income_map[period] = {
            "profit": row.get("n_income_attr_p"),
            "revenue": row.get("revenue") if pd.notna(row.get("revenue")) else row.get("total_revenue"),
        }

    fi_rows = []
    for period in ("20231231", "20241231", "20251231"):
        df = pro.fina_indicator(
            ts_code=ts_code,
            period=period,
            fields="ts_code,end_date,grossprofit_margin,netprofit_margin,roe_dt,roe",
        )
        if df is None or df.empty:
            continue
        df = df.dropna(subset=["end_date"]).drop_duplicates(subset=["end_date"], keep="last")
        if df.empty:
            continue
        fi_rows.append(df.iloc[0][["end_date", "grossprofit_margin", "netprofit_margin", "roe_dt", "roe"]].to_dict())
    fi = pd.DataFrame(fi_rows)

    p22 = income_map.get("20221231", {}).get("profit")
    p23 = income_map.get("20231231", {}).get("profit")
    p24 = income_map.get("20241231", {}).get("profit")
    p25 = income_map.get("20251231", {}).get("profit")
    return {
        "profit_2023": p23,
        "profit_2024": p24,
        "profit_2025": p25,
        "yoy_2023": yoy(p23, p22),
        "yoy_2024": yoy(p24, p23),
        "yoy_2025": yoy(p25, p24),
        "avg_gm": fi["grossprofit_margin"].dropna().mean() if not fi.empty else np.nan,
        "avg_nm": fi["netprofit_margin"].dropna().mean() if not fi.empty else np.nan,
        "avg_roe_dt": fi["roe_dt"].dropna().mean() if not fi.empty else np.nan,
        "avg_roe": fi["roe"].dropna().mean() if not fi.empty else np.nan,
    }


def main():
    pro = ts.pro_api()
    market = load_market(pro)
    masks = sector_masks(market)
    lines = [f"trade_date={TRADE_DATE}", f"market_count={len(market)}"]
    full_rows = []
    for sector, mask in masks.items():
        s = market[mask].copy()
        candidates = s[(s["pb"] <= 0.8) & (s["dv_ttm"].fillna(0) >= 2.5)].copy()
        candidates = candidates.sort_values(["pb", "pe_ttm", "dv_ttm"], ascending=[True, True, False])
        lines.append(f"\n## {sector}")
        lines.append(f"sector_count={len(s)}")
        lines.append(f"pb_le_0_8_and_div_ge_2_5_count={len(candidates)}")
        if candidates.empty:
            lines.append("EMPTY")
            continue
        view = candidates[
            ["ts_code", "symbol", "name", "industry", "dv_ttm", "pe_ttm", "pb"]
        ].head(30)
        lines.append(view.to_csv(index=False))
        for _, row in candidates.iterrows():
            fin = calc_financials(pro, row["ts_code"])
            full_rows.append(
                {
                    "sector": sector,
                    "ts_code": row["ts_code"],
                    "code": row["symbol"],
                    "name": row["name"],
                    "industry": row["industry"],
                    "dividend_yield": row["dv_ttm"],
                    "pe_ttm": row["pe_ttm"],
                    "pb": row["pb"],
                    "yoy_2023": fin["yoy_2023"],
                    "yoy_2024": fin["yoy_2024"],
                    "yoy_2025": fin["yoy_2025"],
                    "avg_gm": fin["avg_gm"],
                    "avg_nm": fin["avg_nm"],
                    "avg_roe_dt": fin["avg_roe_dt"],
                    "avg_roe": fin["avg_roe"],
                    "div_years": calc_dividend_years(pro, row["ts_code"]),
                }
            )
    ROOT.joinpath(".relaxed_sector_scan.txt").write_text("\n".join(lines), encoding="utf-8")
    metrics = pd.DataFrame(full_rows)
    metrics.to_csv(ROOT / ".relaxed_metrics.csv", index=False)

    rules = {
        "银行": {
            "why": "银行净息差业务不适合用毛利率，PE天然低于多数行业，因此改用 ROE_DT + 净利率衡量盈利质量，并把 PE 适配到 4-8。",
            "rule": "PB<=0.8；股息率>=4%；PE 4-8；2023/2024/2025净利增速均为正；3年平均ROE_DT>=9%；3年平均净利率>=35%；连续分红>=5年",
        },
        "运营商": {
            "why": "运营商资本开支重、现金流稳，A股低PB样本极少，因此放宽 PE 到 10-18，并用 ROE_DT + 净利率替代毛利率评价。",
            "rule": "PB<=0.8；股息率>=3.5%；PE 10-18；2023/2024/2025净利增速均为正；3年平均ROE_DT>=4%；3年平均净利率>=5%；连续分红>=5年",
        },
        "资源类": {
            "why": "资源品盈利高度顺周期，不宜硬性要求三年逐年高增长，因此改看低PB、高分红、2025利润修复，以及3年平均毛利率/净利率底线。",
            "rule": "PB<=0.8；股息率>=4%；PE 8-14；2025净利增速为正；3年平均毛利率>=5%；3年平均净利率>=3%；连续分红>=5年",
        },
        "公用事业": {
            "why": "公用事业更看重稳现金流和分红可持续性，不强求高成长，侧重高股息、合理估值、ROE与净利率稳定。",
            "rule": "PB<=0.8；股息率>=5%；PE 8-12；2025净利增速为正；3年平均ROE_DT>=5%；3年平均净利率>=4%；连续分红>=10年",
        },
        "消费类": {
            "why": "当前PB<=0.8的消费股样本很少，因此更强调长期分红、估值不贵以及2024-2025盈利修复，同时保留消费行业对毛利率的要求。",
            "rule": "PB<=0.8；股息率>=4%；PE 7-14；2024/2025净利增速均为正；3年平均毛利率>=20%；3年平均净利率>=7%；连续分红>=10年",
        },
    }

    selected_rows = []
    for _, row in metrics.iterrows():
        sector = row["sector"]
        passed = False
        if sector == "银行":
            passed = (
                row["pb"] <= 0.8
                and row["dividend_yield"] >= 4
                and pd.notna(row["pe_ttm"])
                and 4 <= row["pe_ttm"] <= 8
                and row["yoy_2023"] > 0
                and row["yoy_2024"] > 0
                and row["yoy_2025"] > 0
                and row["avg_roe_dt"] >= 9
                and row["avg_nm"] >= 35
                and row["div_years"] >= 5
            )
        elif sector == "运营商":
            passed = (
                row["pb"] <= 0.8
                and row["dividend_yield"] >= 3.5
                and pd.notna(row["pe_ttm"])
                and 10 <= row["pe_ttm"] <= 18
                and row["yoy_2023"] > 0
                and row["yoy_2024"] > 0
                and row["yoy_2025"] > 0
                and row["avg_roe_dt"] >= 4
                and row["avg_nm"] >= 5
                and row["div_years"] >= 5
            )
        elif sector == "资源类":
            passed = (
                row["pb"] <= 0.8
                and row["dividend_yield"] >= 4
                and pd.notna(row["pe_ttm"])
                and 8 <= row["pe_ttm"] <= 14
                and row["yoy_2025"] > 0
                and row["avg_gm"] >= 5
                and row["avg_nm"] >= 3
                and row["div_years"] >= 5
            )
        elif sector == "公用事业":
            passed = (
                row["pb"] <= 0.8
                and row["dividend_yield"] >= 5
                and pd.notna(row["pe_ttm"])
                and 8 <= row["pe_ttm"] <= 12
                and row["yoy_2025"] > 0
                and row["avg_roe_dt"] >= 5
                and row["avg_nm"] >= 4
                and row["div_years"] >= 10
            )
        elif sector == "消费类":
            passed = (
                row["pb"] <= 0.8
                and row["dividend_yield"] >= 4
                and pd.notna(row["pe_ttm"])
                and 7 <= row["pe_ttm"] <= 14
                and row["yoy_2024"] > 0
                and row["yoy_2025"] > 0
                and row["avg_gm"] >= 20
                and row["avg_nm"] >= 7
                and row["div_years"] >= 10
            )
        if passed:
            selected_rows.append(row.to_dict())

    selected = pd.DataFrame(selected_rows)
    selected.to_csv(ROOT / ".relaxed_selected.csv", index=False)
    ROOT.joinpath(".relaxed_rules.txt").write_text(
        "\n\n".join(
            [
                f"## {sector}\nwhy={cfg['why']}\nrule={cfg['rule']}"
                for sector, cfg in rules.items()
            ]
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
