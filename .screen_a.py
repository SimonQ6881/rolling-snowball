import math
from pathlib import Path

import numpy as np
import pandas as pd
import tushare as ts


ROOT = Path("/Users/user/Documents/personal/zijinDaily")
TRADE_DATE = "20260710"
MARKET_COUNT = 5306
STRICT_CURRENT_COUNT = 0
CANDIDATES = [
    {"代码": "000932", "名称": "华菱钢铁", "ts_code": "000932.SZ", "股息率": 4.5714, "PE": 10.6772, "PB": 0.4295},
    {"代码": "601860", "名称": "紫金银行", "ts_code": "601860.SH", "股息率": 4.0160, "PE": 7.2853, "PB": 0.4459},
    {"代码": "000726", "名称": "鲁泰A", "ts_code": "000726.SZ", "股息率": 4.4957, "PE": 8.4348, "PB": 0.4639},
    {"代码": "600585", "名称": "海螺水泥", "ts_code": "600585.SH", "股息率": 4.9461, "PE": 11.6706, "PB": 0.4678},
    {"代码": "600269", "名称": "赣粤高速", "ts_code": "600269.SH", "股息率": 4.1872, "PE": 8.4171, "PB": 0.4801},
]


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
        return 0, None
    div = div.copy()
    div["year"] = div["end_date"].astype(str).str[:4]
    impl = div[(div["cash_div_tax"].fillna(0) > 0) & (div["div_proc"] == "实施")]
    years = sorted({int(y) for y in impl["year"].dropna().tolist()})
    if not years:
        return 0, None
    consec = 1
    for i in range(len(years) - 1, 0, -1):
        if years[i] - years[i - 1] == 1:
            consec += 1
        else:
            break
    return consec, years[-1]


def calc_financials(pro, ts_code):
    inc_map = {}
    for period in ("20201231", "20211231", "20221231", "20231231"):
        inc = pro.income(
            ts_code=ts_code,
            period=period,
            fields="ts_code,end_date,n_income_attr_p",
        )
        if inc is not None and not inc.empty:
            inc = inc.dropna(subset=["end_date"]).drop_duplicates(subset=["end_date"], keep="last")
            if not inc.empty:
                inc_map[period] = inc.iloc[0]["n_income_attr_p"]

    fi_rows = []
    for period in ("20211231", "20221231", "20231231"):
        fi = pro.fina_indicator(
            ts_code=ts_code,
            period=period,
            fields="ts_code,end_date,grossprofit_margin,netprofit_margin",
        )
        if fi is not None and not fi.empty:
            fi = fi.dropna(subset=["end_date"]).drop_duplicates(subset=["end_date"], keep="last")
            if not fi.empty:
                fi_rows.append(fi.iloc[0][["end_date", "grossprofit_margin", "netprofit_margin"]].to_dict())
    fi = pd.DataFrame(fi_rows)

    return {
        "yoy21": yoy(inc_map.get("20211231"), inc_map.get("20201231")),
        "yoy22": yoy(inc_map.get("20221231"), inc_map.get("20211231")),
        "yoy23": yoy(inc_map.get("20231231"), inc_map.get("20221231")),
        "avg_gm": fi["grossprofit_margin"].mean(),
        "avg_nm": fi["netprofit_margin"].mean(),
    }


def fail_reasons(row):
    reasons = []
    if not (row["股息率"] >= 3):
        reasons.append("股息率<3%")
    if not (8 <= row["PE"] <= 12):
        reasons.append("PE不在8-12")
    if not (0.15 <= row["PB"] <= 0.25):
        reasons.append("PB不在0.15-0.25")
    if not (row["3年平均毛利率"] >= 30):
        reasons.append("3年平均毛利率<30%")
    if not (row["3年平均净利率"] >= 15):
        reasons.append("3年平均净利率<15%")
    if not (
        pd.notna(row["2021净利增速"])
        and row["2021净利增速"] >= 5
        and pd.notna(row["2022净利增速"])
        and row["2022净利增速"] >= 5
        and pd.notna(row["2023净利增速"])
        and row["2023净利增速"] >= 5
    ):
        reasons.append("2021-2023归母净利润增速未连续>=5%")
    if not (row["连续分红年限"] >= 5):
        reasons.append("连续分红年限<5")
    return "；".join(reasons) if reasons else "无"


def distance_score(row):
    score = 0.0
    score += max(0.0, 3 - row["股息率"])
    if row["PE"] < 8:
        score += 8 - row["PE"]
    elif row["PE"] > 12:
        score += row["PE"] - 12
    if row["PB"] < 0.15:
        score += 0.15 - row["PB"]
    elif row["PB"] > 0.25:
        score += row["PB"] - 0.25
    score += max(0.0, 30 - row["3年平均毛利率"]) / 10
    score += max(0.0, 15 - row["3年平均净利率"]) / 5
    for key in ("2021净利增速", "2022净利增速", "2023净利增速"):
        score += max(0.0, 5 - row[key]) / 5 if pd.notna(row[key]) else 1
    score += max(0.0, 5 - row["连续分红年限"]) / 2
    return round(score, 4)


def main():
    pro = ts.pro_api()
    rows = []
    for r in CANDIDATES:
        fin = calc_financials(pro, r["ts_code"])
        div_years, latest_div_year = calc_dividend_years(pro, r["ts_code"])
        rows.append(
            {
                "代码": r["代码"],
                "名称": r["名称"],
                "ts_code": r["ts_code"],
                "股息率": round(float(r["股息率"]), 4),
                "PE": round(float(r["PE"]), 4),
                "PB": round(float(r["PB"]), 4),
                "2021净利增速": None if pd.isna(fin["yoy21"]) else round(float(fin["yoy21"]), 2),
                "2022净利增速": None if pd.isna(fin["yoy22"]) else round(float(fin["yoy22"]), 2),
                "2023净利增速": None if pd.isna(fin["yoy23"]) else round(float(fin["yoy23"]), 2),
                "3年平均毛利率": None if pd.isna(fin["avg_gm"]) else round(float(fin["avg_gm"]), 2),
                "3年平均净利率": None if pd.isna(fin["avg_nm"]) else round(float(fin["avg_nm"]), 2),
                "连续分红年限": int(div_years),
                "最近实施分红对应年": latest_div_year,
            }
        )

    near = pd.DataFrame(rows)
    near["未达标指标"] = near.apply(fail_reasons, axis=1)
    near["距离分数"] = near.apply(distance_score, axis=1)
    near = near.sort_values(["距离分数", "PB", "PE"])

    final = near[
        (near["股息率"] >= 3)
        & (near["PE"].between(8, 12, inclusive="both"))
        & (near["PB"].between(0.15, 0.25, inclusive="both"))
        & (near["3年平均毛利率"] >= 30)
        & (near["3年平均净利率"] >= 15)
        & (near["2021净利增速"] >= 5)
        & (near["2022净利增速"] >= 5)
        & (near["2023净利增速"] >= 5)
        & (near["连续分红年限"] >= 5)
    ].copy()

    ROOT.joinpath(".screen_summary.txt").write_text(
        "\n".join(
            [
                f"trade_date={TRADE_DATE}",
                f"market_count={MARKET_COUNT}",
                f"strict_current_count={STRICT_CURRENT_COUNT}",
                f"shortlist_count={len(CANDIDATES)}",
                f"final_count={len(final)}",
            ]
        ),
        encoding="utf-8",
    )
    near.to_csv(ROOT / ".screen_near.csv", index=False)
    final.to_csv(ROOT / ".screen_final.csv", index=False)


if __name__ == "__main__":
    main()
