#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from html.parser import HTMLParser
import subprocess
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
REPORT_ROOT = ROOT / "reports"
REFRESH_LOCK = threading.Lock()


class SummaryCardParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_top_cards = False
        self.top_cards_depth = 0
        self.current_card: dict[str, str] | None = None
        self.current_card_depth = 0
        self.current_field: str | None = None
        self.cards: list[dict[str, str]] = []
        self._finished = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self._finished or tag != "div":
            return
        attr_map = dict(attrs)
        classes = set((attr_map.get("class") or "").split())

        if not self.in_top_cards and classes == {"cards"}:
            self.in_top_cards = True
            self.top_cards_depth = 1
            return

        if not self.in_top_cards:
            return

        self.top_cards_depth += 1
        if "card" in classes and self.current_card is None:
            self.current_card = {}
            self.current_card_depth = 1
            return
        if self.current_card is not None:
            self.current_card_depth += 1
            if "card-title" in classes:
                self.current_field = "title"
            elif "card-value" in classes:
                self.current_field = "value"
            elif "card-subtitle" in classes:
                self.current_field = "subtitle"

    def handle_endtag(self, tag: str) -> None:
        if self._finished or tag != "div" or not self.in_top_cards:
            return
        if self.current_card is not None:
            self.current_card_depth -= 1
            self.current_field = None
            if self.current_card_depth == 0:
                if self.current_card.get("title") and self.current_card.get("value"):
                    self.cards.append(self.current_card)
                self.current_card = None

        self.top_cards_depth -= 1
        if self.top_cards_depth == 0:
            self.in_top_cards = False
            self._finished = True

    def handle_data(self, data: str) -> None:
        if self._finished or self.current_card is None or not self.current_field:
            return
        text = data.strip()
        if not text:
            return
        existing = self.current_card.get(self.current_field, "")
        self.current_card[self.current_field] = f"{existing}{text}" if existing else text


def extract_summary_snapshot(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    parser = SummaryCardParser()
    parser.feed(path.read_text(encoding="utf-8"))
    snapshot: dict[str, dict[str, str]] = {}
    for card in parser.cards:
        title = card.get("title", "").strip()
        if not title:
            continue
        snapshot[title] = {
            "value": card.get("value", "").strip(),
            "subtitle": card.get("subtitle", "").strip(),
        }
    return snapshot


def latest_report_path() -> Path | None:
    candidates = sorted(REPORT_ROOT.glob("*/*/zijin_daily_*.html"))
    if not candidates:
        return None
    return max(candidates, key=lambda item: (item.stat().st_mtime, str(item)))


def report_relative_path(path: Path) -> str:
    return "/" + path.relative_to(ROOT).as_posix()


def safe_local_path(request_path: str) -> Path | None:
    clean = request_path.lstrip("/")
    if not clean:
        return None
    candidate = (ROOT / clean).resolve()
    try:
        candidate.relative_to(ROOT)
    except ValueError:
        return None
    return candidate if candidate.is_file() else None


def run_refresh() -> tuple[bool, str, str | None, dict[str, dict[str, str]]]:
    command = ["bash", str(ROOT / "scripts" / "run_daily_report.sh"), "--force"]
    env = os.environ.copy()
    result = subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=900,
    )
    output = "\n".join(part for part in [result.stdout.strip(), result.stderr.strip()] if part).strip()
    if result.returncode != 0:
        return False, output or "日报生成失败", None, {}
    latest = latest_report_path()
    summary_snapshot = extract_summary_snapshot(latest) if latest else {}
    return True, output or "ok", report_relative_path(latest) if latest else None, summary_snapshot


class ReportHandler(BaseHTTPRequestHandler):
    server_version = "ZijinDailyReportServer/1.0"

    def do_HEAD(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path in {"/", "/latest"}:
            latest = latest_report_path()
            if latest is None:
                self._send_headers(HTTPStatus.NOT_FOUND, "text/plain; charset=utf-8", 0)
                return
            self._send_headers(HTTPStatus.OK, "text/html; charset=utf-8", latest.stat().st_size)
            return
        if parsed.path == "/healthz":
            payload = json.dumps({"ok": True}, ensure_ascii=False).encode("utf-8")
            self._send_headers(HTTPStatus.OK, "application/json; charset=utf-8", len(payload))
            return
        file_path = safe_local_path(parsed.path)
        if file_path is None:
            self._send_headers(HTTPStatus.NOT_FOUND, "text/plain; charset=utf-8", 0)
            return
        content_type = "text/html; charset=utf-8" if file_path.suffix == ".html" else "text/plain; charset=utf-8"
        self._send_headers(HTTPStatus.OK, content_type, file_path.stat().st_size)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path in {"/", "/latest"}:
            latest = latest_report_path()
            if latest is None:
                self._send_text(
                    HTTPStatus.NOT_FOUND,
                    "暂无已生成日报，请先运行 scripts/run_daily_report.sh --force 或使用刷新接口生成。",
                )
                return
            self._send_file(latest, "text/html; charset=utf-8")
            return
        if parsed.path == "/healthz":
            self._send_json(HTTPStatus.OK, {"ok": True})
            return
        file_path = safe_local_path(parsed.path)
        if file_path is None:
            self._send_text(HTTPStatus.NOT_FOUND, "Not Found")
            return
        content_type = "text/html; charset=utf-8" if file_path.suffix == ".html" else "text/plain; charset=utf-8"
        self._send_file(file_path, content_type)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path != "/api/refresh-report":
            self._send_text(HTTPStatus.NOT_FOUND, "Not Found")
            return

        if not REFRESH_LOCK.acquire(blocking=False):
            self._send_json(HTTPStatus.CONFLICT, {"ok": False, "error": "已有刷新任务在执行，请稍后重试。"})
            return

        try:
            ok, detail, report_path, summary_snapshot = run_refresh()
        except subprocess.TimeoutExpired:
            self._send_json(HTTPStatus.GATEWAY_TIMEOUT, {"ok": False, "error": "刷新超时，请检查接口或网络状态。"})
            return
        except Exception as exc:  # noqa: BLE001
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": str(exc)})
            return
        finally:
            REFRESH_LOCK.release()

        if not ok:
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": detail})
            return
        self._send_json(
            HTTPStatus.OK,
            {
                "ok": True,
                "detail": detail,
                "report_path": report_path or "/",
                "summary_snapshot": summary_snapshot,
            },
        )

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return

    def _send_text(self, status: HTTPStatus, text: str) -> None:
        data = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, status: HTTPStatus, payload: dict[str, object]) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send_headers(status, "application/json; charset=utf-8", len(data))
        self.wfile.write(data)

    def _send_file(self, path: Path, content_type: str) -> None:
        data = path.read_bytes()
        self._send_headers(HTTPStatus.OK, content_type, len(data))
        self.wfile.write(data)

    def _send_headers(self, status: HTTPStatus, content_type: str, content_length: int) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(content_length))
        self.end_headers()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="启动紫金矿业日报本地服务，支持页面内手动刷新数据。")
    parser.add_argument("--host", default="127.0.0.1", help="监听地址，默认 127.0.0.1")
    parser.add_argument("--port", type=int, default=8765, help="监听端口，默认 8765")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    server = ThreadingHTTPServer((args.host, args.port), ReportHandler)
    print(f"日报服务已启动: http://{args.host}:{args.port}")
    print("访问 / 可查看最新日报，页面顶部“刷新数据”按钮会触发重新抓取。")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
