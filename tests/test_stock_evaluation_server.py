from __future__ import annotations

import unittest

from src import stock_evaluation_server


class StockEvaluationServerTest(unittest.TestCase):
    def test_safe_static_path_rejects_traversal(self) -> None:
        self.assertIsNone(stock_evaluation_server.safe_static_path("/../../etc/passwd"))

    def test_safe_static_path_accepts_static_asset(self) -> None:
        path = stock_evaluation_server.safe_static_path("/stock_evaluation/index.html")
        self.assertIsNotNone(path)
        self.assertTrue(str(path).endswith("stock_evaluation/index.html"))

    def test_safe_static_path_accepts_hyphen_route_alias(self) -> None:
        path = stock_evaluation_server.safe_static_path("/stock-evaluation/assets.html")
        self.assertIsNotNone(path)
        self.assertTrue(str(path).endswith("stock_evaluation/assets.html"))


if __name__ == "__main__":
    unittest.main()
