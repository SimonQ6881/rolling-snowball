from __future__ import annotations

import unittest

import pandas as pd

from src.commodity_insights import (
    build_forecast_analysis,
    build_price_analysis,
    build_revenue_analysis,
    build_supply_plan_analysis,
)


def _monthly_frame(start: str, values: list[float]) -> pd.DataFrame:
    dates = pd.date_range(start=start, periods=len(values), freq="MS")
    return pd.DataFrame(
        {
            "trade_date": [item.strftime("%Y%m%d") for item in dates],
            "close": values,
        }
    )


class CommodityInsightsTest(unittest.TestCase):
    def test_build_price_analysis_outputs_monthly_tables_and_events(self) -> None:
        price_frames = {
            "gold": _monthly_frame("2025-08-01", [700, 720, 740, 710, 760, 780, 770, 790, 805, 815, 830, 845]),
            "copper": _monthly_frame("2025-08-01", [78000, 80000, 82000, 81000, 84500, 86000, 85500, 87500, 89000, 90500, 93000, 95000]),
            "lithium": _monthly_frame("2025-08-01", [78000, 76000, 82000, 98000, 120000, 145000, 138000, 152000, 160000, 158000, 166000, 172000]),
        }
        events = [
            {"month": "2026-01", "title": "3Q盐湖一期投产", "detail": "锂项目进入放量期"},
            {"month": "2026-03", "title": "巨龙铜矿二期投产", "detail": "铜产能释放预期强化"},
        ]

        result = build_price_analysis(price_frames, events)

        self.assertEqual(len(result["labels"]), 12)
        self.assertEqual(len(result["normalized_series"]), 3)
        self.assertEqual(len(result["overview_rows"]), 3)
        self.assertGreaterEqual(len(result["turning_rows"]), 3)
        self.assertEqual(result["event_rows"][0][1], "3Q盐湖一期投产")
        self.assertEqual(len(result["monthly_tables"]["黄金"]), 12)

    def test_build_revenue_analysis_respects_disclosure_gaps(self) -> None:
        mainbiz_rows = []
        annual_gold = {2021: 1000, 2022: 1200, 2023: 1400, 2024: 1650, 2025: 1900}
        annual_copper = {2021: 600, 2022: 700, 2023: 820, 2024: 950, 2025: 1080}
        for year in range(2021, 2026):
            end_date = f"{year}1231"
            mainbiz_rows.extend(
                [
                    {"end_date": end_date, "bz_item": "矿山产金", "bz_sales": annual_gold[year] * 1e8},
                    {"end_date": end_date, "bz_item": "矿山产铜", "bz_sales": annual_copper[year] * 1e8},
                    {"end_date": end_date, "bz_item": "冶炼加工金", "bz_sales": 300 * 1e8},
                    {"end_date": end_date, "bz_item": "冶炼产铜", "bz_sales": 260 * 1e8},
                ]
            )

        mainbiz_rows.extend(
            [
                {"end_date": "20220630", "bz_item": "矿山产金", "bz_sales": 580 * 1e8},
                {"end_date": "20220630", "bz_item": "矿山产铜", "bz_sales": 340 * 1e8},
                {"end_date": "20230630", "bz_item": "矿山产金", "bz_sales": 650 * 1e8},
                {"end_date": "20230630", "bz_item": "矿山产铜", "bz_sales": 390 * 1e8},
                {"end_date": "20240630", "bz_item": "矿产品", "bz_sales": 0.0},
                {"end_date": "20250630", "bz_item": "矿产品", "bz_sales": 0.0},
            ]
        )
        mainbiz_df = pd.DataFrame(mainbiz_rows)

        income_df = pd.DataFrame(
            [
                {"end_date": "20250331", "revenue": 790 * 1e8},
                {"end_date": "20250630", "revenue": 1680 * 1e8},
                {"end_date": "20250930", "revenue": 2550 * 1e8},
                {"end_date": "20211231", "revenue": 2250 * 1e8},
                {"end_date": "20221231", "revenue": 2600 * 1e8},
                {"end_date": "20231231", "revenue": 3000 * 1e8},
                {"end_date": "20241231", "revenue": 3300 * 1e8},
                {"end_date": "20251231", "revenue": 3490 * 1e8},
                {"end_date": "20260331", "revenue": 990 * 1e8},
            ]
        )
        lithium_price_df = pd.DataFrame(
            {
                "trade_date": ["20250115", "20250415", "20250715", "20251015"],
                "close": [72000, 76000, 81000, 84000],
            }
        )
        production_targets = [
            {"product": "碳酸锂", "actual_2025": "2.55万吨", "target_2026": "12万吨"},
        ]

        result = build_revenue_analysis(mainbiz_df, income_df, lithium_price_df, production_targets)

        self.assertEqual(result["trend_labels"], ["2021", "2022", "2023", "2024", "2025"])
        self.assertEqual(result["period_labels"], ["2022H1", "2022A", "2023H1", "2023A", "2024H1", "2024A", "2025H1", "2025A"])
        self.assertEqual(len(result["current_rows"]), 3)
        self.assertEqual(result["current_rows"][0][1], "1900.00")
        self.assertEqual(result["current_rows"][1][1], "1080.00")
        self.assertEqual(result["current_rows"][0][-1], "年报矿山产品口径")
        self.assertIn("估算", result["current_rows"][2][-1])
        self.assertIsNone(result["period_series"][0]["values"][4])
        self.assertIsNone(result["period_series"][0]["values"][6])
        self.assertGreater(result["current_slices"][-1]["value"], 490.0)
        self.assertLess(result["current_slices"][-1]["value"], 490.1)

    def test_build_supply_plan_analysis_summarizes_coverage_and_gaps(self) -> None:
        records = [
            {
                "company": "Agnico Eagle",
                "commodity": "gold",
                "status": "quantified",
                "production_2026": "3.3-3.5 Moz",
                "production_2027": "3.3-3.5 Moz",
                "production_2028": "3.3-3.5 Moz",
                "current_capacity": "稳定矿山组合",
                "capacity_addition": "Hope Bay",
                "commissioning": "Hope Bay 推进",
                "source_date": "2026-02",
                "source_title": "2026-2028 Guidance",
                "source_url": "https://example.com/aem",
                "assumptions": "公司三年稳定指引",
            },
            {
                "company": "Rio Tinto",
                "commodity": "copper",
                "status": "partial",
                "production_2026": "800-870 kt",
                "production_2027": "未单列披露",
                "production_2028": "未单列披露",
                "current_capacity": "Oyu Tolgoi + Escondida权益",
                "capacity_addition": "地下矿爬坡",
                "commissioning": "Oyu Tolgoi 爬坡",
                "source_date": "2026-04",
                "source_title": "Q1 2026 Operations Review",
                "source_url": "https://example.com/rio",
                "assumptions": "仅 2026 guidance",
            },
        ]

        result = build_supply_plan_analysis(records, target_company_count=50)

        self.assertEqual(result["supply_company_coverage"], "2/50")
        self.assertEqual(result["supply_quantified_company_count"], 1)
        self.assertEqual(result["supply_partial_company_count"], 1)
        self.assertEqual(len(result["supply_summary_rows"]), 2)
        self.assertEqual(result["supply_plan_rows"][0][0], "黄金")
        self.assertEqual(result["supply_source_rows"][0][0], "Agnico Eagle")
        self.assertEqual(result["supply_gap_rows"][0][3], "2027、2028")

    def test_build_forecast_analysis_generates_two_quarters(self) -> None:
        mainbiz_df = pd.DataFrame(
            [
                {"end_date": "20211231", "bz_item": "矿山产金", "bz_sales": 1000 * 1e8},
                {"end_date": "20211231", "bz_item": "矿山产铜", "bz_sales": 600 * 1e8},
                {"end_date": "20221231", "bz_item": "矿山产金", "bz_sales": 1200 * 1e8},
                {"end_date": "20221231", "bz_item": "矿山产铜", "bz_sales": 700 * 1e8},
                {"end_date": "20231231", "bz_item": "矿山产金", "bz_sales": 1400 * 1e8},
                {"end_date": "20231231", "bz_item": "矿山产铜", "bz_sales": 820 * 1e8},
                {"end_date": "20241231", "bz_item": "矿山产金", "bz_sales": 1650 * 1e8},
                {"end_date": "20241231", "bz_item": "矿山产铜", "bz_sales": 950 * 1e8},
                {"end_date": "20251231", "bz_item": "矿山产金", "bz_sales": 1900 * 1e8},
                {"end_date": "20251231", "bz_item": "矿山产铜", "bz_sales": 1080 * 1e8},
                {"end_date": "20251231", "bz_item": "冶炼加工金", "bz_sales": 320 * 1e8},
                {"end_date": "20251231", "bz_item": "冶炼产铜", "bz_sales": 260 * 1e8},
                {"end_date": "20220630", "bz_item": "矿山产金", "bz_sales": 580 * 1e8},
                {"end_date": "20220630", "bz_item": "矿山产铜", "bz_sales": 340 * 1e8},
                {"end_date": "20230630", "bz_item": "矿山产金", "bz_sales": 650 * 1e8},
                {"end_date": "20230630", "bz_item": "矿山产铜", "bz_sales": 390 * 1e8},
                {"end_date": "20240630", "bz_item": "矿产品", "bz_sales": 0.0},
                {"end_date": "20250630", "bz_item": "矿产品", "bz_sales": 0.0},
            ]
        )
        income_df = pd.DataFrame(
            [
                {"end_date": "20250331", "revenue": 790 * 1e8},
                {"end_date": "20250630", "revenue": 1680 * 1e8},
                {"end_date": "20250930", "revenue": 2550 * 1e8},
                {"end_date": "20211231", "revenue": 2250 * 1e8},
                {"end_date": "20221231", "revenue": 2600 * 1e8},
                {"end_date": "20231231", "revenue": 3000 * 1e8},
                {"end_date": "20241231", "revenue": 3300 * 1e8},
                {"end_date": "20251231", "revenue": 3490 * 1e8},
                {"end_date": "20260331", "revenue": 990 * 1e8},
            ]
        )
        lithium_price_df = pd.DataFrame(
            {
                "trade_date": ["20250115", "20250415", "20250715", "20251015"],
                "close": [72000, 76000, 81000, 84000],
            }
        )
        production_targets = [
            {"product": "矿产金", "actual_2025": "90吨", "target_2026": "105吨"},
            {"product": "矿产铜", "actual_2025": "109万吨", "target_2026": "120万吨"},
            {"product": "碳酸锂", "actual_2025": "2.55万吨", "target_2026": "12万吨"},
        ]
        revenue_analysis = build_revenue_analysis(mainbiz_df, income_df, lithium_price_df, production_targets)
        price_frames = {
            "gold": _monthly_frame("2025-08-01", [700, 720, 740, 710, 760, 780, 770, 790, 805, 815, 830, 845]),
            "copper": _monthly_frame("2025-08-01", [78000, 80000, 82000, 81000, 84500, 86000, 85500, 87500, 89000, 90500, 93000, 95000]),
            "lithium": _monthly_frame("2025-08-01", [78000, 76000, 82000, 98000, 120000, 145000, 138000, 152000, 160000, 158000, 166000, 172000]),
        }

        result = build_forecast_analysis(revenue_analysis, price_frames, production_targets, income_df)

        self.assertEqual(result["labels"], ["2026Q3", "2026Q4"])
        self.assertEqual(len(result["series"]), 4)
        self.assertEqual(len(result["range_rows"]), 2)
        self.assertEqual(len(result["assumption_rows"]), 3)
        self.assertEqual(
            result["timeline_labels"],
            ["2025Q2", "2025Q3", "2025Q4", "2026Q1", "2026Q2", "2026Q3", "2026Q4", "2027Q1"],
        )
        self.assertEqual(len(result["timeline_series"]), 3)
        self.assertEqual(result["timeline_event_markers"][0]["x_label"], "2026Q2")
        total_series = next(item for item in result["series"] if item["label"] == "总营收")
        gold_series = next(item for item in result["series"] if item["label"] == "黄金")
        timeline_gold_series = next(item for item in result["timeline_series"] if item["label"] == "黄金")
        self.assertEqual(len(total_series["values"]), 2)
        self.assertGreater(total_series["values"][1], total_series["values"][0])
        self.assertLess(gold_series["values"][0], 1900 / 4 * 1.3)
        self.assertEqual(len(timeline_gold_series["values"]), 8)


if __name__ == "__main__":
    unittest.main()
