from __future__ import annotations

import json
import socketserver
import tempfile
import threading
import unittest
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler
from pathlib import Path

import pandas as pd

from src.pipeline_ops import archive_trading_snapshot
from src.research_tracker import filter_target_research, track_research_updates
from src.translation_service import TranslationConfig, translate_entries


class _OkHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        self.rfile.read(int(self.headers.get("Content-Length", "0")))
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(
            json.dumps({"choices": [{"message": {"content": "黄金储备持续增加，美元利率回落。"}}]}).encode("utf-8")
        )

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return


@dataclass
class FakeBundle:
    prices: pd.DataFrame
    research_entries: list[dict[str, str]]


class PipelineIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = socketserver.TCPServer(("127.0.0.1", 0), _OkHandler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def test_translation_filter_alert_and_archive(self) -> None:
        config = TranslationConfig(
            enabled=True,
            api_base_url=f"http://127.0.0.1:{self.port}/v1",
            api_key="demo",
            model="demo",
            glossary={"gold reserves": "黄金储备", "dollar": "美元", "rates": "利率"},
        )
        entries = [
            {
                "source": "Fed",
                "institution": "Federal Reserve",
                "date": "20260705",
                "title": "Gold reserves rise",
                "summary": "Dollar rates move lower",
                "tags": ["央行政策"],
            }
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            translated = translate_entries(entries, config, Path(tmpdir) / "translation.json")
            filtered = filter_target_research(translated)
            alerts = track_research_updates(filtered, Path(tmpdir) / "state.json", Path(tmpdir) / "alerts.json")
            bundle = FakeBundle(
                prices=pd.DataFrame([{"trade_date": "20260705", "close": 27.8}]),
                research_entries=filtered,
            )
            _, manifest_path = archive_trading_snapshot(
                Path(tmpdir) / "archive",
                "20260705",
                bundle,
                [{"name": "integration", "ok": True, "detail": "ok"}],
            )
            self.assertEqual(len(alerts), 1)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertTrue(manifest["integrity_ok"])


if __name__ == "__main__":
    unittest.main()
