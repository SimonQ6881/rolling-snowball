from __future__ import annotations

import json
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from .db import bootstrap_database, connect
from .rules import clone_rule_snapshot, load_rule_snapshot
from .scoring_pipeline import ScoringPipeline, ScoringRunContext
from .settings import ROOT, PostgresSettings


TASK_LOG_DIR = ROOT / "data" / "scoring_tasks"


def _now() -> datetime:
    return datetime.now()


def _normalize_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _normalize_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize_value(item) for item in value]
    return value


def _row_to_dict(row: Any) -> dict[str, Any]:
    if row is None:
        return {}
    return {key: _normalize_value(value) for key, value in dict(row).items()}


def _cursor_row_to_dict(cursor: Any, row: Any) -> dict[str, Any]:
    columns = [item.name for item in cursor.description]
    payload = {column: value for column, value in zip(columns, row)}
    return _row_to_dict(payload)


def _cursor_rows_to_dicts(cursor: Any, rows: list[Any]) -> list[dict[str, Any]]:
    return [_cursor_row_to_dict(cursor, row) for row in rows]


@dataclass(frozen=True)
class TaskRequest:
    data_version: str
    limit: int | None
    apply_mode: str
    requested_scope: dict[str, Any]
    rule_snapshot: dict[str, Any]


class RollingSnowballConsoleService:
    def __init__(
        self,
        settings: PostgresSettings | None = None,
        *,
        log_dir: Path = TASK_LOG_DIR,
    ) -> None:
        self.settings = settings or PostgresSettings.from_env()
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._threads: dict[str, threading.Thread] = {}

    def latest_run(self) -> dict[str, Any] | None:
        sql = """
            SELECT *
            FROM scoring_runs
            WHERE run_status = 'success'
            ORDER BY started_at DESC
            LIMIT 1
        """
        with connect(self.settings) as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                row = cur.fetchone()
                return _cursor_row_to_dict(cur, row) if row else None

    def list_runs(self, *, limit: int = 20) -> list[dict[str, Any]]:
        sql = """
            SELECT r.*, s.apply_mode, s.rule_snapshot
            FROM scoring_runs r
            LEFT JOIN run_rule_snapshots s ON s.run_id = r.run_id
            ORDER BY started_at DESC
            LIMIT %s
        """
        with connect(self.settings) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (limit,))
                rows = cur.fetchall()
                return _cursor_rows_to_dicts(cur, rows)

    def get_run_summary(self, run_id: str) -> dict[str, Any] | None:
        sql = """
            SELECT r.*, s.apply_mode, s.rule_snapshot
            FROM scoring_runs r
            LEFT JOIN run_rule_snapshots s ON s.run_id = r.run_id
            WHERE r.run_id = %s
        """
        with connect(self.settings) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (run_id,))
                row = cur.fetchone()
                return _cursor_row_to_dict(cur, row) if row else None

    def get_run_quality_overview(self, run_id: str) -> dict[str, Any] | None:
        run_summary = self.get_run_summary(run_id)
        if not run_summary:
            return None

        summary_sql = """
            SELECT
                COUNT(*) AS total_stocks,
                COUNT(*) FILTER (WHERE is_filtered = false) AS passed_filter_count,
                COUNT(*) FILTER (WHERE is_filtered = true) AS filtered_count,
                COUNT(*) FILTER (WHERE current_pool = '重点观察池') AS key_watch_count,
                COUNT(*) FILTER (WHERE current_pool = '观察池') AS watch_count,
                COUNT(*) FILTER (WHERE jsonb_array_length(warning_tags) > 0) AS warning_stock_count,
                COUNT(*) FILTER (WHERE warning_tags ? 'manual_review') AS manual_review_count,
                COUNT(*) FILTER (WHERE warning_tags ? 'data_missing') AS data_missing_count,
                AVG(jsonb_array_length(warning_tags)::numeric) AS avg_warning_tags_per_stock,
                AVG(total_score) FILTER (WHERE total_score IS NOT NULL) AS avg_total_score
            FROM stock_run_scores
            WHERE run_id = %s
        """
        warning_sql = """
            SELECT
                warning_tag,
                COUNT(*) AS stock_count
            FROM (
                SELECT jsonb_array_elements_text(warning_tags) AS warning_tag
                FROM stock_run_scores
                WHERE run_id = %s
            ) exploded
            GROUP BY warning_tag
            ORDER BY stock_count DESC, warning_tag ASC
            LIMIT 8
        """
        industry_sql = """
            SELECT
                sw_level1_industry,
                COUNT(*) AS stock_count,
                COUNT(*) FILTER (WHERE is_filtered = false) AS passed_count,
                COUNT(*) FILTER (WHERE current_pool = '重点观察池') AS key_watch_count,
                COUNT(*) FILTER (WHERE current_pool = '观察池') AS watch_count,
                COUNT(*) FILTER (WHERE jsonb_array_length(warning_tags) > 0) AS warning_stock_count,
                AVG(total_score) FILTER (WHERE total_score IS NOT NULL) AS avg_total_score
            FROM stock_run_scores
            WHERE run_id = %s
            GROUP BY sw_level1_industry
            ORDER BY key_watch_count DESC, passed_count DESC, avg_total_score DESC NULLS LAST, sw_level1_industry ASC
            LIMIT 10
        """
        outlier_sql = """
            SELECT
                ts_code,
                stock_name,
                sw_level1_industry,
                current_pool,
                total_score,
                global_rank,
                warning_tags,
                jsonb_array_length(warning_tags) AS warning_count
            FROM stock_run_scores
            WHERE run_id = %s
              AND is_filtered = false
              AND jsonb_array_length(warning_tags) > 0
            ORDER BY warning_count DESC, total_score DESC NULLS LAST, global_rank ASC NULLS LAST, ts_code ASC
            LIMIT 20
        """

        with connect(self.settings) as conn:
            with conn.cursor() as cur:
                cur.execute(summary_sql, (run_id,))
                metrics = _cursor_row_to_dict(cur, cur.fetchone())

                cur.execute(warning_sql, (run_id,))
                top_warning_tags = _cursor_rows_to_dicts(cur, cur.fetchall())

                cur.execute(industry_sql, (run_id,))
                industries = _cursor_rows_to_dicts(cur, cur.fetchall())

                cur.execute(outlier_sql, (run_id,))
                warning_outliers = _cursor_rows_to_dicts(cur, cur.fetchall())

        total_stocks = int(metrics.get("total_stocks") or 0)

        def ratio(count_key: str) -> float:
            count = float(metrics.get(count_key) or 0)
            return count / total_stocks if total_stocks > 0 else 0.0

        return {
            "run_summary": run_summary,
            "metrics": {
                **metrics,
                "pass_rate": ratio("passed_filter_count"),
                "filtered_rate": ratio("filtered_count"),
                "key_watch_rate": ratio("key_watch_count"),
                "watch_rate": ratio("watch_count"),
                "warning_stock_rate": ratio("warning_stock_count"),
                "manual_review_rate": ratio("manual_review_count"),
                "data_missing_rate": ratio("data_missing_count"),
            },
            "top_warning_tags": top_warning_tags,
            "industries": industries,
            "warning_outliers": warning_outliers,
        }

    def list_stocks(
        self,
        run_id: str,
        *,
        pool: str | None = None,
        industry: str | None = None,
        is_filtered: bool | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        sql = """
            SELECT
                run_id,
                ts_code,
                stock_name,
                sw_level1_industry,
                current_pool,
                total_score,
                industry_rank,
                industry_total,
                global_rank,
                warning_tags,
                is_filtered
            FROM stock_run_scores
            WHERE run_id = %s
        """
        params: list[Any] = [run_id]
        if pool:
            sql += " AND current_pool = %s"
            params.append(pool)
        if industry:
            sql += " AND sw_level1_industry = %s"
            params.append(industry)
        if is_filtered is not None:
            sql += " AND is_filtered = %s"
            params.append(is_filtered)
        sql += """
            ORDER BY
                CASE WHEN global_rank IS NULL THEN 1 ELSE 0 END,
                global_rank ASC,
                total_score DESC NULLS LAST,
                ts_code ASC
            LIMIT %s OFFSET %s
        """
        params.extend([limit, offset])
        with connect(self.settings) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, tuple(params))
                rows = cur.fetchall()
                return _cursor_rows_to_dicts(cur, rows)

    def list_industries(self, run_id: str) -> list[dict[str, Any]]:
        sql = """
            SELECT
                sw_level1_industry,
                COUNT(*) AS stock_count,
                AVG(total_score) AS avg_total_score,
                MAX(total_score) AS max_total_score,
                COUNT(*) FILTER (WHERE current_pool = '重点观察池') AS key_watch_count,
                COUNT(*) FILTER (WHERE current_pool = '观察池') AS watch_count
            FROM stock_run_scores
            WHERE run_id = %s AND total_score IS NOT NULL
            GROUP BY sw_level1_industry
            ORDER BY max_total_score DESC NULLS LAST, avg_total_score DESC NULLS LAST, sw_level1_industry ASC
        """
        with connect(self.settings) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (run_id,))
                rows = cur.fetchall()
                return _cursor_rows_to_dicts(cur, rows)

    def get_stock_detail(self, run_id: str, ts_code: str) -> dict[str, Any] | None:
        sql = """
            SELECT *
            FROM stock_run_scores
            WHERE run_id = %s AND ts_code = %s
        """
        with connect(self.settings) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (run_id, ts_code))
                row = cur.fetchone()
                return _cursor_row_to_dict(cur, row) if row else None

    def get_stock_peers(self, run_id: str, ts_code: str, *, limit: int = 5) -> dict[str, Any] | None:
        stock = self.get_stock_detail(run_id, ts_code)
        if not stock:
            return None
        industry = stock["sw_level1_industry"]
        sql = """
            SELECT
                ts_code,
                stock_name,
                sw_level1_industry,
                total_score,
                current_pool,
                global_rank,
                industry_rank,
                biz_quality_score,
                growth_delivery_score,
                financial_quality_score,
                valuation_fit_score
            FROM stock_run_scores
            WHERE run_id = %s
              AND sw_level1_industry = %s
              AND ts_code <> %s
              AND total_score IS NOT NULL
            ORDER BY industry_rank ASC, total_score DESC, ts_code ASC
            LIMIT %s
        """
        with connect(self.settings) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (run_id, industry, ts_code, limit))
                rows = cur.fetchall()
                peers = _cursor_rows_to_dicts(cur, rows)
        return {
            "target": stock,
            "peers": peers,
        }

    def get_active_rule(self) -> dict[str, Any]:
        return clone_rule_snapshot()

    def validate_rule_snapshot(self, snapshot: dict[str, Any] | None) -> dict[str, Any]:
        candidate = clone_rule_snapshot(snapshot)
        top_level = candidate["top_level_weights"]
        if abs(sum(float(value) for value in top_level.values()) - 1.0) > 0.0001:
            raise ValueError("一级维度权重之和必须为 1")

        for dimension_name, weights in candidate["score_dimensions"].items():
            if abs(sum(float(value) for value in weights.values()) - 1.0) > 0.0001:
                raise ValueError(f"{dimension_name} 二级指标权重之和必须为 1")

        hard_filters = candidate["hard_filters"]
        if float(hard_filters["cashflow"]["exclude_cash_conversion_ratio_3y_lt"]) < 0:
            raise ValueError("现金转化率阈值不能小于 0")
        if float(hard_filters["leverage"]["exclude_asset_liability_ratio_gt"]) <= 0:
            raise ValueError("资产负债率阈值必须大于 0")
        if float(hard_filters["liquidity"]["exclude_market_cap_lt_cny"]) < 0:
            raise ValueError("市值门槛不能小于 0")
        if float(hard_filters["liquidity"]["exclude_avg_turnover_20d_lt_cny"]) < 0:
            raise ValueError("成交额门槛不能小于 0")
        pool_thresholds = candidate.get("pool_thresholds", {})
        if int(pool_thresholds.get("key_watch_top_n", 1)) <= 0:
            raise ValueError("重点观察池名额必须大于 0")
        return candidate

    def create_task(
        self,
        *,
        data_version: str,
        limit: int | None = None,
        apply_mode: str = "run_once",
        requested_scope: dict[str, Any] | None = None,
        rule_snapshot: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        bootstrap_database(self.settings)
        if apply_mode not in {"run_once", "save_as_default"}:
            raise ValueError("apply_mode 仅支持 run_once 或 save_as_default")

        normalized_snapshot = self.validate_rule_snapshot(rule_snapshot)
        task_id = str(uuid.uuid4())
        log_path = self.log_dir / f"{task_id}.log"
        requested_scope = requested_scope or {}

        sql = """
            INSERT INTO scoring_tasks (
                task_id,
                task_status,
                apply_mode,
                requested_scope,
                requested_rule_snapshot,
                log_path
            )
            VALUES (%s, 'queued', %s, %s::jsonb, %s::jsonb, %s)
        """
        with connect(self.settings) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql,
                    (
                        task_id,
                        apply_mode,
                        json.dumps(requested_scope, ensure_ascii=False),
                        json.dumps(normalized_snapshot, ensure_ascii=False),
                        str(log_path),
                    ),
                )
            conn.commit()

        request = TaskRequest(
            data_version=data_version,
            limit=limit,
            apply_mode=apply_mode,
            requested_scope=requested_scope,
            rule_snapshot=normalized_snapshot,
        )
        thread = threading.Thread(target=self._run_task, args=(task_id, request, log_path), daemon=True)
        self._threads[task_id] = thread
        thread.start()
        return self.get_task(task_id) or {"task_id": task_id}

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        sql = """
            SELECT *
            FROM scoring_tasks
            WHERE task_id = %s
        """
        with connect(self.settings) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (task_id,))
                row = cur.fetchone()
                return _cursor_row_to_dict(cur, row) if row else None

    def list_tasks(self, *, limit: int = 20) -> list[dict[str, Any]]:
        sql = """
            SELECT *
            FROM scoring_tasks
            ORDER BY created_at DESC
            LIMIT %s
        """
        with connect(self.settings) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (limit,))
                rows = cur.fetchall()
                return _cursor_rows_to_dicts(cur, rows)

    def get_task_logs(self, task_id: str, *, tail: int = 200) -> list[str]:
        task = self.get_task(task_id)
        if not task or not task.get("log_path"):
            return []
        log_path = Path(str(task["log_path"]))
        if not log_path.exists():
            return []
        lines = log_path.read_text(encoding="utf-8").splitlines()
        return lines[-tail:]

    def _append_log(self, log_path: Path, message: str) -> None:
        timestamp = _now().strftime("%Y-%m-%d %H:%M:%S")
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"[{timestamp}] {message}\n")

    def _update_task(
        self,
        task_id: str,
        *,
        run_id: str | None = None,
        task_status: str | None = None,
        progress_stage: str | None = None,
        latest_message: str | None = None,
        total_count: int | None = None,
        done_count: int | None = None,
        failed_count: int | None = None,
        error_message: str | None = None,
        set_started_at: bool = False,
        set_finished_at: bool = False,
    ) -> None:
        fields: list[str] = ["updated_at = now()"]
        params: list[Any] = []
        for name, value in (
            ("run_id", run_id),
            ("task_status", task_status),
            ("progress_stage", progress_stage),
            ("latest_message", latest_message),
            ("total_count", total_count),
            ("done_count", done_count),
            ("failed_count", failed_count),
            ("error_message", error_message),
        ):
            if value is None:
                continue
            fields.append(f"{name} = %s")
            params.append(value)
        if set_started_at:
            fields.append("started_at = now()")
        if set_finished_at:
            fields.append("finished_at = now()")
        params.append(task_id)
        sql = f"""
            UPDATE scoring_tasks
            SET {", ".join(fields)}
            WHERE task_id = %s
        """
        with connect(self.settings) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, tuple(params))
            conn.commit()

    def _run_task(self, task_id: str, request: TaskRequest, log_path: Path) -> None:
        pipeline = ScoringPipeline(self.settings)
        context: ScoringRunContext | None = None
        try:
            self._update_task(
                task_id,
                task_status="running",
                progress_stage="bootstrap",
                latest_message="初始化评分环境",
                set_started_at=True,
            )
            self._append_log(log_path, "开始初始化数据库与规则版本。")
            pipeline.bootstrap()

            context = pipeline.create_run(data_version=request.data_version)
            self._update_task(task_id, run_id=context.run_id)
            self._append_log(log_path, f"已创建 run_id={context.run_id}。")

            pipeline.save_run_rule_snapshot(
                context,
                rule_snapshot=request.rule_snapshot,
                apply_mode=request.apply_mode,
            )
            if request.apply_mode == "save_as_default":
                from .rules import write_rule_snapshot

                write_rule_snapshot(request.rule_snapshot)
                self._append_log(log_path, "已保存当前规则为新的默认规则。")

            self._update_task(task_id, progress_stage="sync_master", latest_message="同步股票主档")
            self._append_log(log_path, "开始同步股票主档。")
            total_stocks = pipeline.sync_master_stage(limit=request.limit)
            self._update_task(task_id, total_count=total_stocks)
            self._append_log(log_path, f"股票主档同步完成，总数={total_stocks}。")

            self._update_task(task_id, progress_stage="evaluate", latest_message="执行评分计算")
            self._append_log(log_path, "开始执行硬过滤、评分、分池和排名。")
            results = pipeline.evaluate_stage(context, limit=request.limit, rule_snapshot=request.rule_snapshot)
            self._append_log(log_path, f"评分计算完成，生成结果 {len(results)} 条。")

            self._update_task(task_id, progress_stage="persist", latest_message="落库结果")
            pipeline.upsert_stock_run_scores(results)
            pipeline.upsert_stock_latest_scores(results)
            self._append_log(log_path, "历史结果与最新快照已落库。")

            passed_filter_count = sum(1 for item in results if not item["is_filtered"])
            key_watch_count = sum(1 for item in results if item.get("current_pool") == "重点观察池")
            watch_count = sum(1 for item in results if item.get("current_pool") == "观察池")
            pipeline.mark_run_success(
                context,
                total_stocks=total_stocks,
                passed_filter_count=passed_filter_count,
                key_watch_count=key_watch_count,
                watch_count=watch_count,
            )
            self._update_task(
                task_id,
                task_status="success",
                progress_stage="finished",
                latest_message="运行完成",
                done_count=len(results),
                failed_count=0,
                set_finished_at=True,
            )
            self._append_log(
                log_path,
                f"运行完成：passed_filter_count={passed_filter_count}, key_watch_count={key_watch_count}, watch_count={watch_count}。",
            )
        except Exception as exc:  # noqa: BLE001
            if context is not None:
                pipeline.mark_run_failed(context, str(exc))
            self._update_task(
                task_id,
                task_status="failed",
                progress_stage="failed",
                latest_message="运行失败",
                error_message=str(exc),
                set_finished_at=True,
            )
            self._append_log(log_path, f"运行失败：{exc}")
