#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .console_service import RollingSnowballConsoleService


def api_payload(data: object | None = None, *, code: int = 0, message: str = "success") -> dict[str, object]:
    return {
        "code": code,
        "message": message,
        "data": {} if data is None else data,
    }


class RollingSnowballConsoleHandler(BaseHTTPRequestHandler):
    server_version = "RollingSnowballConsoleServer/1.0"
    service = RollingSnowballConsoleService()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        try:
            if path == "/healthz":
                self._send_json(HTTPStatus.OK, api_payload({"ok": True}))
                return
            if path == "/api/runs/latest":
                latest = self.service.latest_run()
                if latest is None:
                    self._send_json(HTTPStatus.NOT_FOUND, api_payload(code=40401, message="暂无成功运行记录"))
                    return
                self._send_json(HTTPStatus.OK, api_payload(latest))
                return
            if path == "/api/runs":
                limit = int(params.get("limit", ["20"])[0])
                self._send_json(HTTPStatus.OK, api_payload({"items": self.service.list_runs(limit=limit)}))
                return
            if path.startswith("/api/runs/") and path.endswith("/summary"):
                run_id = path.split("/")[3]
                payload = self.service.get_run_summary(run_id)
                if payload is None:
                    self._send_json(HTTPStatus.NOT_FOUND, api_payload(code=40402, message="run 不存在"))
                    return
                self._send_json(HTTPStatus.OK, api_payload(payload))
                return
            if path.startswith("/api/runs/") and path.endswith("/review"):
                run_id = path.split("/")[3]
                payload = self.service.get_run_quality_overview(run_id)
                if payload is None:
                    self._send_json(HTTPStatus.NOT_FOUND, api_payload(code=40402, message="run 不存在"))
                    return
                self._send_json(HTTPStatus.OK, api_payload(payload))
                return
            if path.startswith("/api/runs/") and path.endswith("/stocks"):
                run_id = path.split("/")[3]
                pool = params.get("pool", [None])[0]
                industry = params.get("industry", [None])[0]
                limit = int(params.get("limit", ["100"])[0])
                offset = int(params.get("offset", ["0"])[0])
                is_filtered_raw = params.get("is_filtered", [None])[0]
                is_filtered = None if is_filtered_raw is None else is_filtered_raw.lower() == "true"
                items = self.service.list_stocks(
                    run_id,
                    pool=pool,
                    industry=industry,
                    is_filtered=is_filtered,
                    limit=limit,
                    offset=offset,
                )
                self._send_json(HTTPStatus.OK, api_payload({"items": items}))
                return
            if path.startswith("/api/runs/") and path.endswith("/industries"):
                run_id = path.split("/")[3]
                self._send_json(HTTPStatus.OK, api_payload({"items": self.service.list_industries(run_id)}))
                return
            if path.startswith("/api/runs/") and path.endswith("/peers"):
                parts = path.split("/")
                run_id = parts[3]
                ts_code = parts[5]
                payload = self.service.get_stock_peers(run_id, ts_code)
                if payload is None:
                    self._send_json(HTTPStatus.NOT_FOUND, api_payload(code=40403, message="股票结果不存在"))
                    return
                self._send_json(HTTPStatus.OK, api_payload(payload))
                return
            if path.startswith("/api/runs/") and "/stocks/" in path:
                parts = path.split("/")
                run_id = parts[3]
                ts_code = parts[5]
                payload = self.service.get_stock_detail(run_id, ts_code)
                if payload is None:
                    self._send_json(HTTPStatus.NOT_FOUND, api_payload(code=40403, message="股票结果不存在"))
                    return
                self._send_json(HTTPStatus.OK, api_payload(payload))
                return
            if path == "/api/rules/active":
                self._send_json(HTTPStatus.OK, api_payload(self.service.get_active_rule()))
                return
            if path == "/api/tasks":
                limit = int(params.get("limit", ["20"])[0])
                self._send_json(HTTPStatus.OK, api_payload({"items": self.service.list_tasks(limit=limit)}))
                return
            if path.startswith("/api/tasks/") and path.endswith("/logs"):
                task_id = path.split("/")[3]
                self._send_json(HTTPStatus.OK, api_payload({"items": self.service.get_task_logs(task_id)}))
                return
            if path.startswith("/api/tasks/"):
                task_id = path.split("/")[3]
                payload = self.service.get_task(task_id)
                if payload is None:
                    self._send_json(HTTPStatus.NOT_FOUND, api_payload(code=40404, message="任务不存在"))
                    return
                self._send_json(HTTPStatus.OK, api_payload(payload))
                return
            self._send_json(HTTPStatus.NOT_FOUND, api_payload(code=40400, message="接口不存在"))
        except ValueError as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, api_payload(code=40001, message=str(exc)))
        except Exception as exc:  # noqa: BLE001
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, api_payload(code=50000, message=str(exc)))

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        payload = self._read_json_body()
        if payload is None:
            return

        try:
            if parsed.path == "/api/rules/validate":
                self._send_json(HTTPStatus.OK, api_payload(self.service.validate_rule_snapshot(payload)))
                return
            if parsed.path == "/api/runs":
                data_version = str(payload.get("data_version", "")).strip()
                if not data_version:
                    raise ValueError("data_version 不能为空")
                limit = payload.get("limit")
                if limit is not None:
                    limit = int(limit)
                apply_mode = str(payload.get("apply_mode", "run_once")).strip() or "run_once"
                requested_scope = payload.get("requested_scope")
                if requested_scope is not None and not isinstance(requested_scope, dict):
                    raise ValueError("requested_scope 必须是对象")
                rule_snapshot = payload.get("rule_snapshot")
                if rule_snapshot is not None and not isinstance(rule_snapshot, dict):
                    raise ValueError("rule_snapshot 必须是对象")
                created = self.service.create_task(
                    data_version=data_version,
                    limit=limit,
                    apply_mode=apply_mode,
                    requested_scope=requested_scope,
                    rule_snapshot=rule_snapshot,
                )
                self._send_json(HTTPStatus.OK, api_payload(created))
                return
            self._send_json(HTTPStatus.NOT_FOUND, api_payload(code=40400, message="接口不存在"))
        except ValueError as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, api_payload(code=40001, message=str(exc)))
        except Exception as exc:  # noqa: BLE001
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, api_payload(code=50000, message=str(exc)))

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return

    def _read_json_body(self) -> dict[str, object] | None:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self._send_json(HTTPStatus.BAD_REQUEST, api_payload(code=40002, message="JSON 格式错误"))
            return None

    def _send_json(self, status: HTTPStatus, payload: dict[str, object]) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="启动 rolling-snowball 前端控制台后端服务。")
    parser.add_argument("--host", default="127.0.0.1", help="监听地址，默认 127.0.0.1")
    parser.add_argument("--port", type=int, default=8780, help="监听端口，默认 8780")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    server = ThreadingHTTPServer((args.host, args.port), RollingSnowballConsoleHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
