from __future__ import annotations

import unittest

from src.rolling_snowball.console_service import RollingSnowballConsoleService
from src.rolling_snowball.rules import clone_rule_snapshot


class ConsoleServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = RollingSnowballConsoleService()

    def test_validate_rule_snapshot_accepts_default_snapshot(self) -> None:
        snapshot = clone_rule_snapshot()

        validated = self.service.validate_rule_snapshot(snapshot)

        self.assertEqual(validated["rule_version"], "v1.0")
        self.assertEqual(validated["pool_thresholds"]["key_watch_top_n"], 20)

    def test_validate_rule_snapshot_rejects_invalid_top_level_weights(self) -> None:
        snapshot = clone_rule_snapshot()
        snapshot["top_level_weights"]["valuation_fit"] = 0.3

        with self.assertRaisesRegex(ValueError, "一级维度权重之和必须为 1"):
            self.service.validate_rule_snapshot(snapshot)


if __name__ == "__main__":
    unittest.main()
