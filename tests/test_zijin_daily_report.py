from __future__ import annotations

import unittest
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from src.zijin_daily_report import (
    ROOT,
    ReportData,
    build_usdcnh_proxy_frame,
    compute_correlation,
    fetch_realtime_quote,
    load_config,
    render_html_report,
    resolve_dollar_proxy_frame,
)


class _DummyFetcher:
    def __init__(self) -> None:
        self.status = []


def make_report_data(realtime_quote: dict[str, object]) -> ReportData:
    return ReportData(
        zijin_df=pd.DataFrame(
            [
                {
                    "trade_date": "20260703",
                    "close": 27.82,
                    "ma5": 28.11,
                    "ma20": 29.48,
                    "ma60": 31.37,
                    "drawdown_20d": -11.15,
                    "ret_5d": 10.84,
                    "ret_20d": -8.31,
                }
            ]
        ),
        realtime_quote=realtime_quote,
        daily_basic=pd.DataFrame([{"trade_date": "20260703", "pe_ttm": 11.99, "pb": 3.75}]),
        moneyflow=pd.DataFrame(),
        gold_proxy_df=pd.DataFrame(),
        future_frames={},
        cn_index_rows=[],
        global_index_rows=[],
        global_index_frames={},
        fx_df=pd.DataFrame(),
        shibor_df=pd.DataFrame(),
        yc_df=pd.DataFrame(),
        anns=pd.DataFrame(),
        holder_trade=pd.DataFrame(),
        forecast=pd.DataFrame(),
        express=pd.DataFrame(),
        disclosure=pd.DataFrame(),
        fina_indicator=pd.DataFrame(),
        income=pd.DataFrame(),
        cashflow=pd.DataFrame(),
        dividend=pd.DataFrame(),
        news_rows=[],
        precious_frames={},
        theme_frames={},
        dollar_index_df=pd.DataFrame(),
        treasury_curve_df=pd.DataFrame(),
        research_entries=[],
        research_alerts=[],
        policy_entries=[],
        central_bank_gold_entries=[],
        boe_rate_df=pd.DataFrame(),
        mainbiz=pd.DataFrame(),
        official_commodity_frames={},
        commodity_price_analysis={},
        revenue_structure_analysis={},
        revenue_forecast_analysis={},
        central_bank_gold_analysis={},
    )


class ZijinDailyReportTest(unittest.TestCase):
    def test_build_usdcnh_proxy_frame_uses_bid_close(self) -> None:
        fx_df = pd.DataFrame(
            [
                {"trade_date": "20260704", "bid_close": 7.16},
                {"trade_date": "20260705", "bid_close": 7.18},
            ]
        )

        proxy_df = build_usdcnh_proxy_frame(fx_df)

        self.assertEqual(proxy_df["trade_date"].tolist(), ["20260704", "20260705"])
        self.assertEqual(proxy_df["close"].tolist(), [7.16, 7.18])
        self.assertTrue((proxy_df["proxy_source"] == "USDCNH").all())

    def test_resolve_dollar_proxy_frame_falls_back_to_fx_and_cache(self) -> None:
        fx_df = pd.DataFrame([{"trade_date": "20260705", "bid_close": 7.18}])

        with TemporaryDirectory() as tmp_dir:
            cache_path = Path(tmp_dir) / "dollar_proxy.csv"
            proxy_df = resolve_dollar_proxy_frame(pd.DataFrame(), fx_df, cache_path)
            cache_written = cache_path.exists()
            cached_df = resolve_dollar_proxy_frame(pd.DataFrame(), pd.DataFrame(), cache_path)

        self.assertEqual(proxy_df.iloc[-1]["proxy_source"], "USDCNH")
        self.assertTrue(cache_written)
        self.assertFalse(cached_df.empty)
        self.assertEqual(cached_df.iloc[-1]["proxy_source"], "USDCNH")

    def test_compute_correlation_handles_same_column_names(self) -> None:
        left_df = pd.DataFrame(
            [{"trade_date": f"202607{day:02d}", "close": 100 + day} for day in range(1, 15)]
        )
        right_df = pd.DataFrame(
            [{"trade_date": f"202607{day:02d}", "close": 200 + day * 2} for day in range(1, 15)]
        )

        corr = compute_correlation(left_df, right_df)

        self.assertIsNotNone(corr)
        self.assertGreater(float(corr), 0.99)

    def test_fetch_realtime_quote_normalizes_special_values(self) -> None:
        with patch(
            "src.zijin_daily_report.ts.realtime_quote",
            return_value=pd.DataFrame(
                [
                    {
                        "NAME": "紫金矿业",
                        "TS_CODE": "601899.SH",
                        "DATE": "20260706",
                        "TIME": "09:55:14",
                        "PRICE": float("inf"),
                        "PRE_CLOSE": "",
                    }
                ]
            ),
        ):
            quote = fetch_realtime_quote("601899.SH")
        self.assertEqual(quote["ts_code"], "601899.SH")
        self.assertEqual(quote["time"], "09:55:14")
        self.assertIsNone(quote["price"])
        self.assertIsNone(quote["pre_close"])

    def test_render_html_report_shows_current_price_card(self) -> None:
        config = load_config(ROOT / "config" / "portfolio.json")
        data = make_report_data(
            {
                "ts_code": "601899.SH",
                "date": "20260706",
                "time": "09:55:14",
                "price": 28.58,
                "pre_close": 27.82,
            }
        )
        html = render_html_report(config, _DummyFetcher(), data)
        self.assertIn("当前价", html)
        self.assertIn("28.58", html)
        self.assertIn("09:55:14 / 昨收 27.82", html)
        self.assertIn("571,600.00", html)
        self.assertIn("当前价口径", html)
        self.assertIn("全局总览", html)
        self.assertIn("核心维度拆解：国际矿企多维对标", html)
        self.assertIn("核心维度拆解：核心矿产价格验证", html)
        self.assertIn("结论与展望", html)
        self.assertNotIn("接口抓取状态统计面板", html)

    def test_render_html_report_falls_back_when_current_price_missing(self) -> None:
        config = load_config(ROOT / "config" / "portfolio.json")
        data = make_report_data({})
        html = render_html_report(config, _DummyFetcher(), data)
        self.assertIn("当前价", html)
        self.assertIn("实时行情暂不可用，已降级为收盘口径", html)
        self.assertIn("N/A", html)
        self.assertIn("556,400.00", html)
        self.assertIn("收盘价口径", html)
        self.assertIn("全局总览", html)


if __name__ == "__main__":
    unittest.main()
