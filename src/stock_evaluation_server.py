#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import threading
import traceback
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

try:
    from src.stock_evaluation_core import ROOT, StockEvaluationService
except ModuleNotFoundError:  # pragma: no cover - script entry fallback
    from stock_evaluation_core import ROOT, StockEvaluationService


STATIC_ROOT = ROOT / "stock_evaluation"


def api_payload(code: int = 0, message: str = "success", data: object | None = None) -> dict[str, object]:
    return {
        "code": code,
        "message": message,
        "data": {} if data is None else data,
        "trace_id": str(uuid.uuid4())[:8],
    }


def safe_static_path(request_path: str) -> Path | None:
    clean = request_path.lstrip("/")
    if not clean:
        return None
    if clean.startswith("stock-evaluation/"):
        clean = clean.replace("stock-evaluation/", "stock_evaluation/", 1)
    candidate = (ROOT / clean).resolve()
    try:
        candidate.relative_to(ROOT)
    except ValueError:
        return None
    return candidate if candidate.is_file() else None


class EvaluationTaskRunner:
    def __init__(self, service: StockEvaluationService) -> None:
        self.service = service
        self._threads: dict[str, threading.Thread] = {}

    def create(self, codes: list[str]) -> str:
        task_id = str(uuid.uuid4())
        self.service.repository.create_task(task_id, len(codes))
        thread = threading.Thread(target=self._run_task, args=(task_id, codes), daemon=True)
        self._threads[task_id] = thread
        thread.start()
        return task_id

    def _run_task(self, task_id: str, codes: list[str]) -> None:
        detail: list[dict[str, object]] = []
        done_count = 0
        failed_count = 0
        self.service.repository.update_task(task_id, status="running", done_count=0, failed_count=0, detail=detail)
        for code in codes:
            try:
                result = self.service.evaluate_symbol(code)
                detail.append(
                    {
                        "symbol": result["symbol"],
                        "status": "success",
                        "evaluation_id": result["evaluation_id"],
                        "name": result["name"],
                        "rating": result["rating"],
                        "total_score": result["total_score"],
                    }
                )
                done_count += 1
            except Exception as exc:  # noqa: BLE001
                failed_count += 1
                detail.append(
                    {
                        "symbol": code,
                        "status": "failed",
                        "error_code": 30002,
                        "error_msg": str(exc),
                    }
                )
            status = "running"
            if done_count + failed_count == len(codes):
                if failed_count == len(codes):
                    status = "failed"
                elif failed_count:
                    status = "partial"
                else:
                    status = "success"
            self.service.repository.update_task(
                task_id,
                status=status,
                done_count=done_count,
                failed_count=failed_count,
                detail=detail,
            )


class StockEvaluationHandler(BaseHTTPRequestHandler):
    server_version = "StockEvaluationServer/1.0"
    service = StockEvaluationService()
    task_runner = EvaluationTaskRunner(service)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        if path in {"/", "/stock-evaluation", "/stock-evaluation/", "/stock-evaluation/index.html", "/stock_evaluation/index.html"}:
            self._send_file(STATIC_ROOT / "index.html", "text/html; charset=utf-8")
            return
        if path == "/healthz":
            self._send_json(HTTPStatus.OK, api_payload(data={"ok": True}))
            return
        if path == "/api/v1/guidance/latest":
            self._send_json(HTTPStatus.OK, api_payload(data=self.service.guidance_snapshot()))
            return
        if path == "/api/v1/evaluations":
            params = parse_qs(parsed.query)
            filters = {key: values[0] for key, values in params.items() if values}
            self._send_json(HTTPStatus.OK, api_payload(data={"items": self.service.list_evaluations(filters)}))
            return
        if path.startswith("/api/v1/evaluations/tasks/"):
            task_id = path.rsplit("/", 1)[-1]
            task = self.service.repository.get_task(task_id)
            if task is None:
                self._send_json(HTTPStatus.NOT_FOUND, api_payload(code=30001, message="任务不存在"))
                return
            self._send_json(HTTPStatus.OK, api_payload(data=task))
            return
        if path.startswith("/api/v1/evaluations/"):
            evaluation_id = path.rsplit("/", 1)[-1]
            result = self.service.get_evaluation(evaluation_id)
            if result is None:
                self._send_json(HTTPStatus.NOT_FOUND, api_payload(code=30001, message="评估结果不存在"))
                return
            self._send_json(HTTPStatus.OK, api_payload(data=result))
            return
        if path.startswith("/api/v1/comparisons/history/"):
            symbol = path.rsplit("/", 1)[-1]
            self._send_json(HTTPStatus.OK, api_payload(data={"items": self.service.list_history(symbol)}))
            return
        if path == "/api/v1/groups":
            self._send_json(HTTPStatus.OK, api_payload(data={"items": self.service.list_groups()}))
            return
        if path == "/api/v1/analysis/export":
            params = parse_qs(parsed.query)
            dataset = params.get("dataset", ["evaluations"])[0]
            file_format = params.get("format", ["csv"])[0]
            try:
                data, content_type = self.service.export_dataset(dataset, file_format)
            except ValueError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, api_payload(code=10005, message=str(exc)))
                return
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Disposition", f'attachment; filename="{dataset}.{file_format}"')
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        file_path = safe_static_path(path)
        if file_path is None:
            self._send_text(HTTPStatus.NOT_FOUND, "Not Found")
            return
        if file_path.suffix == ".html":
            content_type = "text/html; charset=utf-8"
        elif file_path.suffix == ".css":
            content_type = "text/css; charset=utf-8"
        elif file_path.suffix == ".js":
            content_type = "application/javascript; charset=utf-8"
        else:
            content_type = "text/plain; charset=utf-8"
        self._send_file(file_path, content_type)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        payload = self._read_json_body()
        if payload is None:
            return

        try:
            if parsed.path == "/api/v1/validation/stock-codes":
                codes = payload.get("codes", [])
                if not isinstance(codes, list):
                    raise ValueError("codes 必须是数组")
                self._send_json(HTTPStatus.OK, api_payload(data={"items": self.service.validate_codes(codes)}))
                return

            if parsed.path == "/api/v1/evaluations/tasks":
                codes = payload.get("codes", [])
                if not isinstance(codes, list) or not codes:
                    raise ValueError("codes 不能为空")
                if len(codes) > 10:
                    self._send_json(HTTPStatus.BAD_REQUEST, api_payload(code=10004, message="单次最多评估 10 只股票"))
                    return
                task_id = self.task_runner.create(codes)
                self._send_json(HTTPStatus.OK, api_payload(data={"task_id": task_id}))
                return

            if parsed.path == "/api/v1/groups":
                name = str(payload.get("name", "")).strip()
                memo = str(payload.get("memo", "")).strip()
                if not name:
                    raise ValueError("分组名称不能为空")
                group = self.service.create_group(name, memo)
                self._send_json(HTTPStatus.OK, api_payload(data=group))
                return

            if parsed.path.startswith("/api/v1/evaluations/") and parsed.path.endswith("/tags"):
                evaluation_id = parsed.path.split("/")[-2]
                tags = payload.get("tags", [])
                if not isinstance(tags, list):
                    raise ValueError("tags 必须是数组")
                result = self.service.add_tags(evaluation_id, tags)
                self._send_json(HTTPStatus.OK, api_payload(data={"tags": result}))
                return

            if parsed.path == "/api/v1/notes":
                symbol = str(payload.get("symbol", "")).strip()
                evaluation_id = str(payload.get("evaluation_id", "")).strip()
                content = str(payload.get("content", "")).strip()
                if not content:
                    raise ValueError("笔记内容不能为空")
                note = self.service.add_note(symbol, evaluation_id, content)
                self._send_json(HTTPStatus.OK, api_payload(data=note))
                return

            self._send_text(HTTPStatus.NOT_FOUND, "Not Found")
        except ValueError as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, api_payload(code=10005, message=str(exc)))
        except Exception as exc:  # noqa: BLE001
            self._send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                api_payload(code=50000, message=f"{exc}\n{traceback.format_exc(limit=3)}"),
            )

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return

    def _read_json_body(self) -> dict[str, object] | None:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self._send_json(HTTPStatus.BAD_REQUEST, api_payload(code=10005, message="JSON 格式错误"))
            return None

    def _send_text(self, status: HTTPStatus, text: str) -> None:
        data = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, status: HTTPStatus, payload: dict[str, object]) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_file(self, path: Path, content_type: str) -> None:
        data = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="启动股票评估软件本地服务")
    parser.add_argument("--host", default="127.0.0.1", help="监听地址，默认 127.0.0.1")
    parser.add_argument("--port", type=int, default=8770, help="监听端口，默认 8770")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    server = ThreadingHTTPServer((args.host, args.port), StockEvaluationHandler)
    print(f"股票评估服务已启动: http://{args.host}:{args.port}")
    print("访问 / 或 /stock-evaluation/index.html 打开工作台。")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
