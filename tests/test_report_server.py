from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path

from src import report_server


class ReportServerTest(unittest.TestCase):
    def test_safe_local_path_rejects_traversal(self) -> None:
        self.assertIsNone(report_server.safe_local_path("/../../etc/passwd"))

    def test_latest_report_path_picks_newest_file(self) -> None:
        old_root = report_server.REPORT_ROOT
        with tempfile.TemporaryDirectory() as tmpdir:
            report_server.REPORT_ROOT = Path(tmpdir)
            path_a = report_server.REPORT_ROOT / "2026" / "07" / "zijin_daily_20260704.html"
            path_b = report_server.REPORT_ROOT / "2026" / "07" / "zijin_daily_20260705.html"
            path_a.parent.mkdir(parents=True, exist_ok=True)
            path_a.write_text("a", encoding="utf-8")
            time.sleep(0.01)
            path_b.write_text("b", encoding="utf-8")
            latest = report_server.latest_report_path()
            self.assertEqual(latest, path_b)
        report_server.REPORT_ROOT = old_root

    def test_extract_summary_snapshot_reads_top_cards(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = Path(tmpdir) / "sample.html"
            report_path.write_text(
                """
                <html><body>
                <div class="cards">
                  <div class="card neutral">
                    <div class="card-title">最新收盘</div>
                    <div class="card-value">27.82</div>
                    <div class="card-subtitle">交易日 20260703</div>
                  </div>
                  <div class="card positive">
                    <div class="card-title">当前价</div>
                    <div class="card-value">28.90</div>
                    <div class="card-subtitle">20260706 10:00:47 / 昨收 27.82</div>
                  </div>
                </div>
                <div class="cards compact">
                  <div class="card neutral">
                    <div class="card-title">接口总数</div>
                    <div class="card-value">54</div>
                  </div>
                </div>
                </body></html>
                """,
                encoding="utf-8",
            )
            snapshot = report_server.extract_summary_snapshot(report_path)
            self.assertEqual(snapshot["最新收盘"]["value"], "27.82")
            self.assertEqual(snapshot["当前价"]["subtitle"], "20260706 10:00:47 / 昨收 27.82")
            self.assertNotIn("接口总数", snapshot)


if __name__ == "__main__":
    unittest.main()
