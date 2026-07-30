from __future__ import annotations

import unittest

import pandas as pd

from src.central_bank_insights import build_central_bank_gold_analysis
from src.report_extra import extract_goldhub_month_entry


def _gold_frame() -> pd.DataFrame:
    dates = pd.date_range("2026-01-01", periods=90, freq="B")
    values = [700 + idx * 1.5 for idx in range(len(dates))]
    return pd.DataFrame(
        {
            "trade_date": [item.strftime("%Y%m%d") for item in dates],
            "close": values,
        }
    )


class CentralBankInsightsTest(unittest.TestCase):
    def test_extract_goldhub_month_entry_prefers_global_net_tonnes(self) -> None:
        article_html = """
        <html>
          <body>
            <h1>Central bank gold statistics: Central banks remain committed to gold</h1>
            <div>02 July, 2026</div>
            <p>Central banks bought a net 41t in May, extending the rebound from April.</p>
            <ul>
              <li>Poland added 18t in the month.</li>
              <li>People's Bank of China added 10t in May.</li>
            </ul>
          </body>
        </html>
        """
        entry = extract_goldhub_month_entry(article_html, "https://example.com")
        self.assertIsNotNone(entry)
        self.assertEqual(entry["net_tonnes"], 41.0)
        self.assertEqual(entry["direction"], "净买入")

    def test_build_central_bank_gold_analysis_outputs_country_and_china_timeline(self) -> None:
        entries = [
            {
                "date": "20260303",
                "month_label": "January",
                "title": "Central bank gold statistics: Momentum eases in January while demand base broadens",
                "summary": "",
                "highlights": [
                    "Central banks bought a net 5t in January.",
                    "People's Bank of China added 1t to its reserves.",
                ],
            },
            {
                "date": "20260402",
                "month_label": "February",
                "title": "Central Bank Gold Statistics: Central banks stay the course on gold in February",
                "summary": "",
                "highlights": [
                    "February buying: Central banks bought a net 27t in February, with activity driven by Poland (20t), Uzbekistan (8t), Kazakhstan (8t), China (1t). Net sellers this month were Turkey (8t) and Russia (6t).",
                    "China is on its 16th consecutive month of net purchases.",
                ],
            },
            {
                "date": "20260603",
                "month_label": "April",
                "title": "Central bank gold statistics: Central banks resume net buying in April",
                "summary": "",
                "highlights": [
                    "National Bank of Poland drove much of April's buying activity, having bought 14t.",
                    "People's Bank of China added 8t to its gold reserves during the month.",
                ],
            },
            {
                "date": "20260702",
                "month_label": "May",
                "title": "Central bank gold statistics: Central banks remain committed to gold",
                "summary": "",
                "highlights": [
                    "Central banks bought a net 41t in May.",
                    "In its 20th consecutive month of net buying, the People's Bank of China added 10t to its gold reserves.",
                    "Y-t-d, China has added 25t to its gold reserves.",
                ],
            },
        ]

        result = build_central_bank_gold_analysis(entries, _gold_frame())

        self.assertEqual(result["latest_month_label"], "26/05")
        self.assertEqual(result["latest_global_tonnes"], 41.0)
        self.assertEqual(result["china_ytd_tonnes"], 25.0)
        self.assertEqual(result["china_consecutive_months"], 20)
        self.assertEqual(result["china_timeline_labels"][-1], "26/05")
        self.assertEqual(result["china_timeline_values"][-1], 10.0)
        self.assertEqual(result["global_period_rows"][0][1], "41.0t")
        self.assertTrue(any(row[0] == "中国" for row in result["tracked_country_rows"]))
        self.assertIn("去美元化", result["summary_text"])


if __name__ == "__main__":
    unittest.main()
