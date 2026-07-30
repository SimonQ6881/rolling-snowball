from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.stock_evaluation_core import StockEvaluationRepository, StockEvaluationService


class FakeClient:
    ready = True

    def fetch_master(self, symbol: str, market: str) -> dict[str, str]:
        return {
            "symbol": symbol,
            "name": "贵州茅台" if market == "CN" else "腾讯控股",
            "industry": "白酒" if market == "CN" else "互联网",
            "board": "主板",
            "list_status": "L",
        }

    def fetch_market_snapshot(self, symbol: str, market: str):  # noqa: ANN201
        return (
            {
                "pe_ttm": 18.0,
                "pb": 5.2,
                "ps_ttm": 6.4,
                "close": 1500.0,
                "turnover_rate": 0.7,
            },
            "20260707",
        )

    def fetch_financial_snapshot(self, symbol: str):  # noqa: ANN201
        return (
            {
                "roe": 24.0,
                "gross_margin": 57.0,
                "net_margin": 31.0,
                "revenue_yoy": 15.0,
                "profit_yoy": 18.0,
                "rd_yoy": 12.0,
                "debt_to_assets": 26.0,
                "current_ratio": 1.8,
                "ocf_to_profit": 1.2,
                "rd_to_revenue": 2.5,
                "revenue": 92000000000.0,
            },
            "2026-03-31",
        )

    def fetch_industry_valuation_baseline(self, industry: str, trade_date: str) -> dict[str, float]:
        return {
            "sample_n": 16,
            "pe_ttm_median": 24.5,
            "pb_median": 6.2,
            "ps_ttm_median": 8.1,
        }


class OfflineClient:
    ready = False


class StockEvaluationCoreTest(unittest.TestCase):
    def test_validate_code_normalizes_a_share(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = StockEvaluationRepository(Path(tmpdir) / "test.db")
            service = StockEvaluationService(repository=repo, tushare_client=OfflineClient())
            result = service.validate_code("600519")
            self.assertTrue(result.ok)
            self.assertEqual(result.symbol, "600519.SH")
            self.assertEqual(result.market, "CN")

    def test_validate_code_rejects_beijing_exchange(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = StockEvaluationRepository(Path(tmpdir) / "test.db")
            service = StockEvaluationService(repository=repo, tushare_client=OfflineClient())
            result = service.validate_code("830799")
            self.assertFalse(result.ok)
            self.assertEqual(result.error_code, 10003)

    def test_evaluate_symbol_persists_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = StockEvaluationRepository(Path(tmpdir) / "test.db")
            service = StockEvaluationService(repository=repo, tushare_client=FakeClient())
            result = service.evaluate_symbol("600519")
            self.assertEqual(result["symbol"], "600519.SH")
            self.assertEqual(result["name"], "贵州茅台")
            self.assertGreater(result["total_score"], 0)
            self.assertIn("data_completeness", result)
            self.assertIn("confidence_level", result)
            self.assertTrue(result["dimension_insights"])
            self.assertIn("strengths", result)
            self.assertIn("risks", result)
            self.assertIn("watch_items", result)
            saved = service.get_evaluation(result["evaluation_id"])
            self.assertIsNotNone(saved)
            self.assertEqual(saved["symbol"], "600519.SH")
            self.assertTrue(saved["indicators"])
            self.assertEqual(saved["confidence_level"], result["confidence_level"])


if __name__ == "__main__":
    unittest.main()
