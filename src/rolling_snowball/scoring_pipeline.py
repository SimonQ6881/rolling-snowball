from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .db import bootstrap_database, connect
from .financial_data import TushareScoringDataSource
from .master_sync import sync_stocks_master
from .rules import RULE_VERSION, load_rule_snapshot, write_rule_snapshot
from .scorecard import apply_scores_with_snapshot
from .scoring_engine import StockCandidateInput, evaluate_candidate, result_to_db_row
from .settings import PostgresSettings


@dataclass(frozen=True)
class ScoringRunContext:
    run_id: str
    rule_version: str
    data_version: str
    started_at: datetime


class ScoringPipeline:
    """
    首版评分流水线。

    当前版本已打通：
    - 数据库初始化与规则版本落库
    - 股票主档同步
    - scoring run 生命周期管理
    - 基于现有输入的硬过滤判定
    - stock_latest_scores 的基础结果回写

    当前仍未实现完整评分，total_score / 排名 / 分池暂保持为空，
    等财报、行情、分红等输入源接入后再补齐。
    """

    def __init__(self, settings: PostgresSettings | None = None) -> None:
        self.settings = settings or PostgresSettings.from_env()
        self.data_source = TushareScoringDataSource()

    def bootstrap(self) -> None:
        bootstrap_database(self.settings)

    def create_run(self, data_version: str) -> ScoringRunContext:
        context = ScoringRunContext(
            run_id=str(uuid.uuid4()),
            rule_version=RULE_VERSION,
            data_version=data_version,
            started_at=datetime.now(),
        )
        sql = """
            INSERT INTO scoring_runs (
                run_id,
                rule_version,
                data_version,
                run_status,
                started_at
            )
            VALUES (%s, %s, %s, 'running', %s);
        """
        with connect(self.settings) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql,
                    (
                        context.run_id,
                        context.rule_version,
                        context.data_version,
                        context.started_at,
                    ),
                )
            conn.commit()
        return context

    def save_run_rule_snapshot(
        self,
        context: ScoringRunContext,
        *,
        rule_snapshot: dict[str, Any] | None = None,
        apply_mode: str = "default",
    ) -> None:
        snapshot = rule_snapshot or load_rule_snapshot()
        sql = """
            INSERT INTO run_rule_snapshots (
                run_id,
                apply_mode,
                rule_snapshot
            )
            VALUES (%s, %s, %s::jsonb)
            ON CONFLICT (run_id) DO UPDATE
            SET apply_mode = EXCLUDED.apply_mode,
                rule_snapshot = EXCLUDED.rule_snapshot,
                updated_at = now();
        """
        with connect(self.settings) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql,
                    (
                        context.run_id,
                        apply_mode,
                        json.dumps(snapshot, ensure_ascii=False),
                    ),
                )
            conn.commit()

    def mark_run_success(
        self,
        context: ScoringRunContext,
        *,
        total_stocks: int,
        passed_filter_count: int = 0,
        key_watch_count: int = 0,
        watch_count: int = 0,
    ) -> None:
        sql = """
            UPDATE scoring_runs
            SET run_status = 'success',
                total_stocks = %s,
                passed_filter_count = %s,
                key_watch_count = %s,
                watch_count = %s,
                finished_at = now(),
                updated_at = now()
            WHERE run_id = %s;
        """
        with connect(self.settings) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql,
                    (
                        total_stocks,
                        passed_filter_count,
                        key_watch_count,
                        watch_count,
                        context.run_id,
                    ),
                )
            conn.commit()

    def mark_run_failed(self, context: ScoringRunContext, error_message: str) -> None:
        sql = """
            UPDATE scoring_runs
            SET run_status = 'failed',
                error_message = %s,
                finished_at = now(),
                updated_at = now()
            WHERE run_id = %s;
        """
        with connect(self.settings) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (error_message, context.run_id))
            conn.commit()

    def sync_master_stage(self, *, limit: int | None = None) -> int:
        return sync_stocks_master(self.settings, limit=limit)

    def load_candidates(self, *, limit: int | None = None) -> list[StockCandidateInput]:
        sql = """
            SELECT
                ts_code,
                stock_name,
                market,
                sw_level1_industry,
                list_status,
                latest_report_period,
                audit_opinion
            FROM stocks_master
            ORDER BY ts_code
        """
        params: tuple[object, ...] = ()
        if limit is not None:
            sql += " LIMIT %s"
            params = (limit,)

        with connect(self.settings) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()

        base_candidates = [
            StockCandidateInput(
                ts_code=row[0],
                stock_name=row[1],
                market=row[2],
                sw_level1_industry=row[3],
                list_status=row[4],
                latest_report_period=row[5],
                audit_opinion=row[6],
            )
            for row in rows
        ]
        return [self.data_source.enrich_candidate(candidate) for candidate in base_candidates]

    def upsert_stocks_master_enrichment(self, candidates: list[StockCandidateInput]) -> int:
        if not candidates:
            return 0

        sql = """
            UPDATE stocks_master
            SET latest_report_period = %(latest_report_period)s,
                audit_opinion = %(audit_opinion)s,
                updated_at = now()
            WHERE ts_code = %(ts_code)s;
        """
        payload = [
            {
                "ts_code": item.ts_code,
                "latest_report_period": item.latest_report_period,
                "audit_opinion": item.audit_opinion,
            }
            for item in candidates
        ]
        with connect(self.settings) as conn:
            with conn.cursor() as cur:
                cur.executemany(sql, payload)
            conn.commit()
        return len(payload)

    def evaluate_stage(
        self,
        context: ScoringRunContext,
        *,
        limit: int | None = None,
        rule_snapshot: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        scored_at = datetime.now()
        results: list[dict[str, Any]] = []
        candidates = self.load_candidates(limit=limit)
        self.upsert_stocks_master_enrichment(candidates)
        for candidate in candidates:
            row = result_to_db_row(
                evaluate_candidate(
                    candidate,
                    run_id=context.run_id,
                    rule_version=context.rule_version,
                    data_version=context.data_version,
                    scored_at=scored_at,
                    rule_snapshot=rule_snapshot,
                )
            )
            row.update(
                {
                    "_latest_revenue": candidate.latest_revenue,
                    "_latest_nonrec_np": candidate.latest_nonrec_np,
                    "_total_market_cap_internal": candidate.total_market_cap,
                    "shareholder_return_ratio_3y": candidate.shareholder_return_ratio_3y,
                    "dividend_sum_3y": candidate.dividend_sum_3y,
                    "buyback_sum_3y": candidate.buyback_sum_3y,
                    "parent_np_sum_3y": candidate.parent_np_sum_3y,
                    "dividend_yield_avg_3y": candidate.dividend_yield_avg_3y,
                }
            )
            results.append(row)
        return apply_scores_with_snapshot(results, snapshot=rule_snapshot)

    def _score_result_payload(self, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                **item,
                "filter_reasons": json.dumps(item["filter_reasons"], ensure_ascii=False),
                "warning_tags": json.dumps(item["warning_tags"], ensure_ascii=False),
            }
            for item in results
        ]

    def _persist_score_rows(
        self,
        *,
        table_name: str,
        conflict_target: str,
        results: list[dict[str, Any]],
    ) -> int:
        if not results:
            return 0

        sql = f"""
            INSERT INTO {table_name} (
                ts_code,
                run_id,
                stock_name,
                market,
                sw_level1_industry,
                latest_report_period,
                audit_opinion,
                current_pool,
                total_score,
                industry_rank,
                industry_total,
                global_rank,
                biz_quality_score,
                growth_delivery_score,
                financial_quality_score,
                valuation_fit_score,
                gross_margin_avg_3y,
                roe_avg_3y,
                net_margin_avg_3y,
                industry_position_score_raw,
                revenue_pct_in_industry,
                nonrec_np_pct_in_industry,
                market_cap_pct_in_industry,
                revenue_cagr_3y,
                nonrec_np_cagr_3y,
                shareholder_return_ratio_3y,
                dividend_sum_3y,
                buyback_sum_3y,
                parent_np_sum_3y,
                cash_conversion_ratio_3y,
                asset_liability_ratio_latest,
                capital_return_stability_score_raw,
                pe_ttm,
                pb_latest,
                dividend_yield_avg_3y,
                roe_std_3y,
                industry_roe_std_median_3y,
                roe_stability_gap,
                gross_margin_score,
                roe_score,
                net_margin_score,
                industry_position_score,
                revenue_cagr_score,
                nonrec_np_cagr_score,
                shareholder_return_score,
                cash_conversion_score,
                asset_liability_score,
                capital_return_stability_score,
                pe_score,
                pb_score,
                dividend_yield_score,
                manual_review_required,
                is_filtered,
                filter_reasons,
                cashflow_warning,
                short_debt_warning,
                pe_invalid,
                pb_invalid,
                data_missing,
                warning_tags,
                gross_margin_weighted_score,
                roe_weighted_score,
                net_margin_weighted_score,
                industry_position_weighted_score,
                revenue_cagr_weighted_score,
                nonrec_np_cagr_weighted_score,
                shareholder_return_weighted_score,
                cash_conversion_weighted_score,
                asset_liability_weighted_score,
                capital_return_stability_weighted_score,
                pe_weighted_score,
                pb_weighted_score,
                dividend_yield_weighted_score,
                biz_quality_weighted_score,
                growth_delivery_weighted_score,
                financial_quality_weighted_score,
                valuation_fit_weighted_score,
                rule_version,
                data_version,
                scored_at
            )
            VALUES (
                %(ts_code)s,
                %(run_id)s,
                %(stock_name)s,
                %(market)s,
                %(sw_level1_industry)s,
                %(latest_report_period)s,
                %(audit_opinion)s,
                %(current_pool)s,
                %(total_score)s,
                %(industry_rank)s,
                %(industry_total)s,
                %(global_rank)s,
                %(biz_quality_score)s,
                %(growth_delivery_score)s,
                %(financial_quality_score)s,
                %(valuation_fit_score)s,
                %(gross_margin_avg_3y)s,
                %(roe_avg_3y)s,
                %(net_margin_avg_3y)s,
                %(industry_position_score_raw)s,
                %(revenue_pct_in_industry)s,
                %(nonrec_np_pct_in_industry)s,
                %(market_cap_pct_in_industry)s,
                %(revenue_cagr_3y)s,
                %(nonrec_np_cagr_3y)s,
                %(shareholder_return_ratio_3y)s,
                %(dividend_sum_3y)s,
                %(buyback_sum_3y)s,
                %(parent_np_sum_3y)s,
                %(cash_conversion_ratio_3y)s,
                %(asset_liability_ratio_latest)s,
                %(capital_return_stability_score_raw)s,
                %(pe_ttm)s,
                %(pb_latest)s,
                %(dividend_yield_avg_3y)s,
                %(roe_std_3y)s,
                %(industry_roe_std_median_3y)s,
                %(roe_stability_gap)s,
                %(gross_margin_score)s,
                %(roe_score)s,
                %(net_margin_score)s,
                %(industry_position_score)s,
                %(revenue_cagr_score)s,
                %(nonrec_np_cagr_score)s,
                %(shareholder_return_score)s,
                %(cash_conversion_score)s,
                %(asset_liability_score)s,
                %(capital_return_stability_score)s,
                %(pe_score)s,
                %(pb_score)s,
                %(dividend_yield_score)s,
                %(manual_review_required)s,
                %(is_filtered)s,
                %(filter_reasons)s::jsonb,
                %(cashflow_warning)s,
                %(short_debt_warning)s,
                %(pe_invalid)s,
                %(pb_invalid)s,
                %(data_missing)s,
                %(warning_tags)s::jsonb,
                %(gross_margin_weighted_score)s,
                %(roe_weighted_score)s,
                %(net_margin_weighted_score)s,
                %(industry_position_weighted_score)s,
                %(revenue_cagr_weighted_score)s,
                %(nonrec_np_cagr_weighted_score)s,
                %(shareholder_return_weighted_score)s,
                %(cash_conversion_weighted_score)s,
                %(asset_liability_weighted_score)s,
                %(capital_return_stability_weighted_score)s,
                %(pe_weighted_score)s,
                %(pb_weighted_score)s,
                %(dividend_yield_weighted_score)s,
                %(biz_quality_weighted_score)s,
                %(growth_delivery_weighted_score)s,
                %(financial_quality_weighted_score)s,
                %(valuation_fit_weighted_score)s,
                %(rule_version)s,
                %(data_version)s,
                %(scored_at)s
            )
            ON CONFLICT ({conflict_target}) DO UPDATE
            SET run_id = EXCLUDED.run_id,
                stock_name = EXCLUDED.stock_name,
                market = EXCLUDED.market,
                sw_level1_industry = EXCLUDED.sw_level1_industry,
                latest_report_period = EXCLUDED.latest_report_period,
                audit_opinion = EXCLUDED.audit_opinion,
                current_pool = EXCLUDED.current_pool,
                total_score = EXCLUDED.total_score,
                industry_rank = EXCLUDED.industry_rank,
                industry_total = EXCLUDED.industry_total,
                global_rank = EXCLUDED.global_rank,
                biz_quality_score = EXCLUDED.biz_quality_score,
                growth_delivery_score = EXCLUDED.growth_delivery_score,
                financial_quality_score = EXCLUDED.financial_quality_score,
                valuation_fit_score = EXCLUDED.valuation_fit_score,
                gross_margin_avg_3y = EXCLUDED.gross_margin_avg_3y,
                roe_avg_3y = EXCLUDED.roe_avg_3y,
                net_margin_avg_3y = EXCLUDED.net_margin_avg_3y,
                industry_position_score_raw = EXCLUDED.industry_position_score_raw,
                revenue_pct_in_industry = EXCLUDED.revenue_pct_in_industry,
                nonrec_np_pct_in_industry = EXCLUDED.nonrec_np_pct_in_industry,
                market_cap_pct_in_industry = EXCLUDED.market_cap_pct_in_industry,
                revenue_cagr_3y = EXCLUDED.revenue_cagr_3y,
                nonrec_np_cagr_3y = EXCLUDED.nonrec_np_cagr_3y,
                shareholder_return_ratio_3y = EXCLUDED.shareholder_return_ratio_3y,
                dividend_sum_3y = EXCLUDED.dividend_sum_3y,
                buyback_sum_3y = EXCLUDED.buyback_sum_3y,
                parent_np_sum_3y = EXCLUDED.parent_np_sum_3y,
                cash_conversion_ratio_3y = EXCLUDED.cash_conversion_ratio_3y,
                asset_liability_ratio_latest = EXCLUDED.asset_liability_ratio_latest,
                capital_return_stability_score_raw = EXCLUDED.capital_return_stability_score_raw,
                pe_ttm = EXCLUDED.pe_ttm,
                pb_latest = EXCLUDED.pb_latest,
                dividend_yield_avg_3y = EXCLUDED.dividend_yield_avg_3y,
                roe_std_3y = EXCLUDED.roe_std_3y,
                industry_roe_std_median_3y = EXCLUDED.industry_roe_std_median_3y,
                roe_stability_gap = EXCLUDED.roe_stability_gap,
                gross_margin_score = EXCLUDED.gross_margin_score,
                roe_score = EXCLUDED.roe_score,
                net_margin_score = EXCLUDED.net_margin_score,
                industry_position_score = EXCLUDED.industry_position_score,
                revenue_cagr_score = EXCLUDED.revenue_cagr_score,
                nonrec_np_cagr_score = EXCLUDED.nonrec_np_cagr_score,
                shareholder_return_score = EXCLUDED.shareholder_return_score,
                cash_conversion_score = EXCLUDED.cash_conversion_score,
                asset_liability_score = EXCLUDED.asset_liability_score,
                capital_return_stability_score = EXCLUDED.capital_return_stability_score,
                pe_score = EXCLUDED.pe_score,
                pb_score = EXCLUDED.pb_score,
                dividend_yield_score = EXCLUDED.dividend_yield_score,
                manual_review_required = EXCLUDED.manual_review_required,
                is_filtered = EXCLUDED.is_filtered,
                filter_reasons = EXCLUDED.filter_reasons,
                cashflow_warning = EXCLUDED.cashflow_warning,
                short_debt_warning = EXCLUDED.short_debt_warning,
                pe_invalid = EXCLUDED.pe_invalid,
                pb_invalid = EXCLUDED.pb_invalid,
                data_missing = EXCLUDED.data_missing,
                warning_tags = EXCLUDED.warning_tags,
                gross_margin_weighted_score = EXCLUDED.gross_margin_weighted_score,
                roe_weighted_score = EXCLUDED.roe_weighted_score,
                net_margin_weighted_score = EXCLUDED.net_margin_weighted_score,
                industry_position_weighted_score = EXCLUDED.industry_position_weighted_score,
                revenue_cagr_weighted_score = EXCLUDED.revenue_cagr_weighted_score,
                nonrec_np_cagr_weighted_score = EXCLUDED.nonrec_np_cagr_weighted_score,
                shareholder_return_weighted_score = EXCLUDED.shareholder_return_weighted_score,
                cash_conversion_weighted_score = EXCLUDED.cash_conversion_weighted_score,
                asset_liability_weighted_score = EXCLUDED.asset_liability_weighted_score,
                capital_return_stability_weighted_score = EXCLUDED.capital_return_stability_weighted_score,
                pe_weighted_score = EXCLUDED.pe_weighted_score,
                pb_weighted_score = EXCLUDED.pb_weighted_score,
                dividend_yield_weighted_score = EXCLUDED.dividend_yield_weighted_score,
                biz_quality_weighted_score = EXCLUDED.biz_quality_weighted_score,
                growth_delivery_weighted_score = EXCLUDED.growth_delivery_weighted_score,
                financial_quality_weighted_score = EXCLUDED.financial_quality_weighted_score,
                valuation_fit_weighted_score = EXCLUDED.valuation_fit_weighted_score,
                rule_version = EXCLUDED.rule_version,
                data_version = EXCLUDED.data_version,
                scored_at = EXCLUDED.scored_at,
                updated_at = now();
        """
        payload = self._score_result_payload(results)
        with connect(self.settings) as conn:
            with conn.cursor() as cur:
                cur.executemany(sql, payload)
            conn.commit()
        return len(payload)

    def upsert_stock_latest_scores(self, results: list[dict[str, Any]]) -> int:
        return self._persist_score_rows(
            table_name="stock_latest_scores",
            conflict_target="ts_code",
            results=results,
        )

    def upsert_stock_run_scores(self, results: list[dict[str, Any]]) -> int:
        return self._persist_score_rows(
            table_name="stock_run_scores",
            conflict_target="run_id, ts_code",
            results=results,
        )

    def run_bootstrap_flow(
        self,
        *,
        data_version: str,
        limit: int | None = None,
        rule_snapshot: dict[str, Any] | None = None,
        apply_mode: str = "default",
    ) -> dict[str, Any]:
        """
        首版先实现可落库的评分骨架：
        - 初始化 schema
        - 记录 scoring run
        - 同步股票主档
        - 执行当前可用输入下的硬过滤判定
        - 把结果统一写入 stock_latest_scores
        """
        self.bootstrap()
        context = self.create_run(data_version=data_version)
        try:
            active_snapshot = rule_snapshot or load_rule_snapshot()
            self.save_run_rule_snapshot(context, rule_snapshot=active_snapshot, apply_mode=apply_mode)
            if apply_mode == "save_as_default":
                write_rule_snapshot(active_snapshot)
            total_stocks = self.sync_master_stage(limit=limit)
            results = self.evaluate_stage(context, limit=limit, rule_snapshot=active_snapshot)
            self.upsert_stock_run_scores(results)
            upserted_count = self.upsert_stock_latest_scores(results)
            passed_filter_count = sum(1 for item in results if not item["is_filtered"])
            key_watch_count = sum(1 for item in results if item.get("current_pool") == "重点观察池")
            watch_count = sum(1 for item in results if item.get("current_pool") == "观察池")
            self.mark_run_success(
                context,
                total_stocks=total_stocks,
                passed_filter_count=passed_filter_count,
                key_watch_count=key_watch_count,
                watch_count=watch_count,
            )
        except Exception as exc:  # noqa: BLE001
            self.mark_run_failed(context, str(exc))
            raise
        return {
            "run_id": context.run_id,
            "rule_version": context.rule_version,
            "data_version": context.data_version,
            "total_stocks": total_stocks,
            "upserted_count": upserted_count,
            "passed_filter_count": passed_filter_count,
            "key_watch_count": key_watch_count,
            "watch_count": watch_count,
        }
