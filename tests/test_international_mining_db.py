from __future__ import annotations

import unittest

from src.international_mining_db import parse_production_text, standardize_mining_records


class InternationalMiningDbTest(unittest.TestCase):
    def test_parse_production_text_handles_gold_copper_and_lithium_units(self) -> None:
        gold = parse_production_text("3.3-3.5 Moz", "gold")
        copper = parse_production_text("1.0 bn lb", "copper")
        lithium = parse_production_text("12 万吨 LCE", "lithium")
        spodumene = parse_production_text("680 ktpa spodumene capacity path", "lithium")

        self.assertTrue(gold.comparable)
        self.assertEqual(gold.standardized_unit, "吨")
        self.assertAlmostEqual(gold.value_mid or 0.0, (3.3 + 3.5) / 2 * 31.1034768, places=4)

        self.assertTrue(copper.comparable)
        self.assertEqual(copper.standardized_unit, "kt")
        self.assertAlmostEqual(copper.value_mid or 0.0, 453.59237, places=4)

        self.assertTrue(lithium.comparable)
        self.assertEqual(lithium.basis, "lithium_lce_kt")
        self.assertAlmostEqual(lithium.value_mid or 0.0, 120.0, places=4)

        self.assertTrue(spodumene.comparable)
        self.assertEqual(spodumene.basis, "lithium_spodumene_kt")
        self.assertAlmostEqual(spodumene.value_mid or 0.0, 680.0, places=4)

    def test_standardize_mining_records_builds_company_and_production_tables(self) -> None:
        records = [
            {
                "company": "Zijin Mining",
                "commodity": "gold",
                "country": "China",
                "status": "partial",
                "production_2026": "105 吨",
                "production_2027": "未单列披露",
                "production_2028": "130-140 吨",
                "current_capacity": "2025 实际矿产金 90 吨",
                "commissioning": "多个项目投产爬坡",
                "capacity_addition": "较 2025 年提升约 40-50 吨",
                "source_date": "2026-03",
                "source_title": "Guidance",
                "source_url": "https://example.com/zijin",
                "assumptions": "test",
            },
            {
                "company": "Rio Tinto",
                "commodity": "copper",
                "country": "UK/Australia",
                "status": "partial",
                "production_2026": "800-870 kt",
                "production_2027": "未单列披露",
                "production_2028": "未单列披露",
                "current_capacity": "按 2026 guidance 披露 consolidated basis 80-87 万吨",
                "commissioning": "地下矿继续爬坡",
                "capacity_addition": "主要来自 Oyu Tolgoi 地下矿放量",
                "source_date": "2026-04",
                "source_title": "Operations Review",
                "source_url": "https://example.com/rio",
                "assumptions": "test",
            },
        ]

        inventory_df, company_df, production_df = standardize_mining_records(records)

        self.assertEqual(len(inventory_df), 1)
        self.assertEqual(len(company_df), 2)
        self.assertEqual(len(production_df), 6)
        zijin_row = company_df.loc[company_df["company"] == "Zijin Mining"].iloc[0]
        rio_row = company_df.loc[company_df["company"] == "Rio Tinto"].iloc[0]
        self.assertEqual(zijin_row["country_primary"], "China")
        self.assertIn("Australia", rio_row["country_list"])
        self.assertEqual(zijin_row["disclosed_years"], 2)
        self.assertEqual(
            production_df[(production_df["company"] == "Zijin Mining") & (production_df["year"] == 2026)].iloc[0]["value_mid"],
            105.0,
        )


if __name__ == "__main__":
    unittest.main()
