from __future__ import annotations

import json
import socketserver
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler
from pathlib import Path

from src.translation_service import TranslationConfig, normalize_text, translate_entries


class _TranslationHandler(BaseHTTPRequestHandler):
    counter = 0

    def do_POST(self) -> None:  # noqa: N802
        _TranslationHandler.counter += 1
        raw = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        payload = json.loads(raw.decode("utf-8"))
        body = payload["messages"][-1]["content"]
        if _TranslationHandler.counter == 1:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(b"fail once")
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        response = {
            "choices": [
                {
                    "message": {
                        "content": "美联储发布声明，美元指数回落。"
                    }
                }
            ]
        }
        self.wfile.write(json.dumps(response).encode("utf-8"))

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return


class TranslationServiceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = socketserver.TCPServer(("127.0.0.1", 0), _TranslationHandler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def test_normalize_text(self) -> None:
        self.assertEqual(normalize_text("A\u00a0B \n C�"), "A B C")

    def test_translate_entries_with_retry_and_cache(self) -> None:
        config = TranslationConfig(
            enabled=True,
            api_base_url=f"http://127.0.0.1:{self.port}/v1",
            api_key="demo",
            model="demo-model",
            max_retries=3,
            glossary={"Federal Reserve": "美联储", "dollar index": "美元指数"},
        )
        entries = [
            {
                "source": "Fed",
                "institution": "Federal Reserve",
                "date": "20260705",
                "title": "Federal Reserve statement",
                "summary": "The dollar index moved lower after the meeting.",
                "tags": ["央行政策"],
            }
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "translation_cache.json"
            alert_path = Path(tmpdir) / "translation_alerts.json"
            results = translate_entries(entries, config, cache_path, alert_path)
            self.assertEqual(results[0]["title_translation_status"], "translated")
            self.assertIn("美联储", results[0]["title"])
            self.assertTrue(results[0]["translation_ready"])
            self.assertTrue(cache_path.exists())
            self.assertFalse(alert_path.exists())


if __name__ == "__main__":
    unittest.main()
