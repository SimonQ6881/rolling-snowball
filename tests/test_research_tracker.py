from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.research_tracker import filter_target_research, track_research_updates


class ResearchTrackerTest(unittest.TestCase):
    def test_filter_target_research(self) -> None:
        entries = [
            {"source": "Tushare研报", "institution": "中信证券", "title": "黄金价格展望", "summary": "贵金属中枢上移", "date": "20260705", "tags": ["研报"]},
            {"source": "eastmoney", "institution": "eastmoney", "title": "AI 服务器需求增长", "summary": "与本任务无关", "date": "20260705", "tags": ["资讯"]},
            {"source": "Fed", "institution": "Federal Reserve", "title": "Treasury yields move lower", "summary": "US dollar weakens", "date": "20260705", "tags": ["央行政策"]},
        ]
        filtered = filter_target_research(entries)
        self.assertEqual(len(filtered), 2)
        themes = {item["core_theme"] for item in filtered}
        self.assertIn("贵金属", themes)
        self.assertTrue(themes & {"美元利率", "央行购金"})

    def test_track_research_updates(self) -> None:
        entries = [
            {
                "record_id": "one",
                "date": "20260705",
                "core_theme": "贵金属",
                "title": "黄金价格展望",
                "institution": "中信证券",
                "credibility": "高",
                "core_view": "看多黄金",
            }
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "state.json"
            alert_path = Path(tmpdir) / "alerts.json"
            alerts = track_research_updates(entries, state_path, alert_path)
            self.assertEqual(len(alerts), 1)
            self.assertTrue(alert_path.exists())
            saved = json.loads(alert_path.read_text(encoding="utf-8"))
            self.assertEqual(saved[0]["record_id"], "one")
            second = track_research_updates(entries, state_path, alert_path)
            self.assertEqual(second, [])


if __name__ == "__main__":
    unittest.main()
