from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from src.pipeline_ops import archive_trading_snapshot


@dataclass
class FakeReportData:
    prices: pd.DataFrame
    research_entries: list[dict[str, str]]


class PipelineOpsTest(unittest.TestCase):
    def test_archive_snapshot_success(self) -> None:
        data = FakeReportData(
            prices=pd.DataFrame([{"trade_date": "20260705", "close": 27.8}]),
            research_entries=[{"record_id": "r1", "title": "黄金跟踪"}],
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            data_path, manifest_path = archive_trading_snapshot(
                Path(tmpdir),
                "20260705",
                data,
                [{"name": "prices", "ok": True, "detail": "1 rows"}],
            )
            self.assertTrue(data_path.exists())
            self.assertTrue(manifest_path.exists())
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertTrue(manifest["integrity_ok"])

    def test_archive_snapshot_rejects_duplicates(self) -> None:
        data = FakeReportData(
            prices=pd.DataFrame(
                [
                    {"trade_date": "20260705", "close": 27.8},
                    {"trade_date": "20260705", "close": 27.9},
                ]
            ),
            research_entries=[{"record_id": "r1", "title": "黄金跟踪"}],
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(ValueError):
                archive_trading_snapshot(
                    Path(tmpdir),
                    "20260705",
                    data,
                    [{"name": "prices", "ok": True, "detail": "2 rows"}],
                )


if __name__ == "__main__":
    unittest.main()
