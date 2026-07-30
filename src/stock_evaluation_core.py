from __future__ import annotations

import csv
import io
import json
import os
import re
import sqlite3
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import tushare as ts


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "stock_evaluation"
DB_PATH = DATA_DIR / "stock_evaluation.db"
ENV_PATH = ROOT / ".env"
RULE_VERSION = "R_MVP_20260707"
GUIDANCE_VERSION = "G_MVP_20260707"

SUPPORTED_A_PREFIXES = ("60", "68", "00", "30")
UNSUPPORTED_A_PREFIXES = ("43", "83", "87", "88", "92")


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return ""
    return text


def as_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if pd.isna(value):
            return None
        return float(value)
    text = clean_text(value).replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def display_value(value: float | None, suffix: str = "", digits: int = 2) -> str:
    if value is None:
        return "缺失"
    return f"{value:.{digits}f}{suffix}"


def load_env_file(path: Path = ENV_PATH) -> dict[str, str]:
    payload: dict[str, str] = {}
    if not path.exists():
        return payload
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        payload[key.strip()] = value.strip().strip('"').strip("'")
    return payload


def load_tushare_token() -> str:
    token = clean_text(os.getenv("TUSHARE_TOKEN"))
    if token:
        return token
    return clean_text(load_env_file().get("TUSHARE_TOKEN"))


def latest_row(df: pd.DataFrame, date_columns: tuple[str, ...]) -> pd.Series | None:
    if df.empty:
        return None
    working = df.copy()
    sort_column = None
    for column in date_columns:
        if column in working.columns:
            working[column] = working[column].astype(str)
            sort_column = column
            break
    if sort_column:
        working = working.sort_values(sort_column)
    return working.iloc[-1]


def pick_value(row: pd.Series | None, *names: str) -> Any:
    if row is None:
        return None
    for name in names:
        if name in row.index:
            value = row.get(name)
            text = clean_text(value)
            if text:
                return value
    return None


def safe_percentile(series: pd.Series, value: float | None) -> float | None:
    if value is None:
        return None
    working = pd.to_numeric(series, errors="coerce").dropna()
    if working.empty:
        return None
    return float((working <= value).mean() * 100.0)


def linear_score_lower(value: float | None, good: float, bad: float) -> float | None:
    if value is None:
        return None
    if value <= good:
        return 100.0
    if value >= bad:
        return 0.0
    return (bad - value) / (bad - good) * 100.0


def linear_score_higher(value: float | None, bad: float, good: float) -> float | None:
    if value is None:
        return None
    if value >= good:
        return 100.0
    if value <= bad:
        return 0.0
    return (value - bad) / (good - bad) * 100.0


def range_score(value: float | None, low: float, high: float, hard_low: float, hard_high: float) -> float | None:
    if value is None:
        return None
    if low <= value <= high:
        return 100.0
    if value <= hard_low or value >= hard_high:
        return 0.0
    if value < low:
        return (value - hard_low) / (low - hard_low) * 100.0
    return (hard_high - value) / (hard_high - high) * 100.0


def average_score(items: list[float | None]) -> float | None:
    available = [item for item in items if item is not None]
    if not available:
        return None
    return sum(available) / len(available)


def weighted_average(items: list[tuple[float | None, float]]) -> float | None:
    available = [(score, weight) for score, weight in items if score is not None and weight > 0]
    if not available:
        return None
    total_weight = sum(weight for _, weight in available)
    if total_weight == 0:
        return None
    return sum(score * weight for score, weight in available) / total_weight


def score_bucket(score: float | None) -> str:
    if score is None:
        return "缺失"
    if score >= 80:
        return "强"
    if score >= 65:
        return "较强"
    if score >= 50:
        return "中性"
    if score >= 35:
        return "偏弱"
    return "弱"


def clamp_score(score: float | None) -> float | None:
    if score is None:
        return None
    return max(0.0, min(100.0, score))


@dataclass
class ValidationResult:
    input_code: str
    ok: bool
    symbol: str | None
    market: str | None
    name: str
    error_code: int | None
    error_message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "input_code": self.input_code,
            "ok": self.ok,
            "symbol": self.symbol,
            "market": self.market,
            "name": self.name,
            "error_code": self.error_code,
            "error_message": self.error_message,
        }


class StockEvaluationRepository:
    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS evaluation_task (
                  task_id TEXT PRIMARY KEY,
                  status TEXT NOT NULL,
                  total_count INTEGER NOT NULL,
                  done_count INTEGER NOT NULL DEFAULT 0,
                  failed_count INTEGER NOT NULL DEFAULT 0,
                  detail_json TEXT,
                  created_at TEXT NOT NULL,
                  finished_at TEXT
                );

                CREATE TABLE IF NOT EXISTS stock_evaluation (
                  evaluation_id TEXT PRIMARY KEY,
                  symbol TEXT NOT NULL,
                  name TEXT NOT NULL,
                  market TEXT NOT NULL,
                  industry TEXT,
                  total_score REAL,
                  rating TEXT,
                  rule_version TEXT NOT NULL,
                  guidance_version TEXT NOT NULL,
                  data_as_of_date TEXT,
                  report_period TEXT,
                  advice_text TEXT,
                  deductions_json TEXT NOT NULL,
                  summary_json TEXT NOT NULL,
                  created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_eval_symbol_time
                ON stock_evaluation(symbol, created_at DESC);

                CREATE TABLE IF NOT EXISTS evaluation_indicator (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  evaluation_id TEXT NOT NULL,
                  dimension_code TEXT NOT NULL,
                  dimension_name TEXT NOT NULL,
                  indicator_code TEXT NOT NULL,
                  indicator_name TEXT NOT NULL,
                  raw_value REAL,
                  display_text TEXT NOT NULL,
                  score REAL,
                  notes TEXT,
                  UNIQUE(evaluation_id, indicator_code)
                );

                CREATE TABLE IF NOT EXISTS stock_group (
                  group_id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT NOT NULL UNIQUE,
                  memo TEXT,
                  created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS stock_group_member (
                  group_id INTEGER NOT NULL,
                  symbol TEXT NOT NULL,
                  added_at TEXT NOT NULL,
                  PRIMARY KEY (group_id, symbol)
                );

                CREATE TABLE IF NOT EXISTS evaluation_tag (
                  evaluation_id TEXT NOT NULL,
                  tag TEXT NOT NULL,
                  PRIMARY KEY (evaluation_id, tag)
                );

                CREATE TABLE IF NOT EXISTS research_note (
                  note_id INTEGER PRIMARY KEY AUTOINCREMENT,
                  symbol TEXT,
                  evaluation_id TEXT,
                  content TEXT NOT NULL,
                  created_at TEXT NOT NULL
                );
                """
            )

    def create_task(self, task_id: str, total_count: int) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO evaluation_task(task_id, status, total_count, done_count, failed_count, detail_json, created_at, finished_at)
                VALUES (?, 'pending', ?, 0, 0, '[]', ?, NULL)
                """,
                (task_id, total_count, now_text()),
            )

    def update_task(self, task_id: str, *, status: str, done_count: int, failed_count: int, detail: list[dict[str, Any]]) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE evaluation_task
                SET status = ?, done_count = ?, failed_count = ?, detail_json = ?, finished_at = CASE WHEN ? IN ('success', 'partial', 'failed') THEN ? ELSE finished_at END
                WHERE task_id = ?
                """,
                (status, done_count, failed_count, json.dumps(detail, ensure_ascii=False), status, now_text(), task_id),
            )

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM evaluation_task WHERE task_id = ?", (task_id,)).fetchone()
        if row is None:
            return None
        payload = dict(row)
        payload["items"] = json.loads(payload.pop("detail_json") or "[]")
        return payload

    def save_evaluation(self, summary: dict[str, Any], indicators: list[dict[str, Any]]) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO stock_evaluation(
                  evaluation_id, symbol, name, market, industry, total_score, rating,
                  rule_version, guidance_version, data_as_of_date, report_period,
                  advice_text, deductions_json, summary_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    summary["evaluation_id"],
                    summary["symbol"],
                    summary["name"],
                    summary["market"],
                    summary.get("industry") or "",
                    summary.get("total_score"),
                    summary.get("rating"),
                    RULE_VERSION,
                    GUIDANCE_VERSION,
                    summary.get("data_as_of_date") or "",
                    summary.get("report_period") or "",
                    summary.get("advice_text") or "",
                    json.dumps(summary.get("deductions", []), ensure_ascii=False),
                    json.dumps(summary, ensure_ascii=False),
                    summary["created_at"],
                ),
            )
            conn.execute("DELETE FROM evaluation_indicator WHERE evaluation_id = ?", (summary["evaluation_id"],))
            conn.executemany(
                """
                INSERT INTO evaluation_indicator(
                  evaluation_id, dimension_code, dimension_name, indicator_code, indicator_name, raw_value, display_text, score, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        summary["evaluation_id"],
                        item["dimension_code"],
                        item["dimension_name"],
                        item["indicator_code"],
                        item["indicator_name"],
                        item.get("raw_value"),
                        item.get("display_text", ""),
                        item.get("score"),
                        item.get("notes", ""),
                    )
                    for item in indicators
                ],
            )

    def get_evaluation(self, evaluation_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM stock_evaluation WHERE evaluation_id = ?", (evaluation_id,)).fetchone()
            indicator_rows = conn.execute(
                "SELECT dimension_code, dimension_name, indicator_code, indicator_name, raw_value, display_text, score, notes FROM evaluation_indicator WHERE evaluation_id = ? ORDER BY id",
                (evaluation_id,),
            ).fetchall()
            tag_rows = conn.execute("SELECT tag FROM evaluation_tag WHERE evaluation_id = ? ORDER BY tag", (evaluation_id,)).fetchall()
            note_rows = conn.execute(
                "SELECT note_id, content, created_at FROM research_note WHERE evaluation_id = ? ORDER BY note_id DESC",
                (evaluation_id,),
            ).fetchall()
        if row is None:
            return None
        payload = json.loads(row["summary_json"])
        payload["indicators"] = [dict(item) for item in indicator_rows]
        payload["tags"] = [item["tag"] for item in tag_rows]
        payload["notes"] = [dict(item) for item in note_rows]
        return payload

    def list_evaluations(self, filters: dict[str, str]) -> list[dict[str, Any]]:
        where_parts = ["1=1"]
        params: list[Any] = []
        if filters.get("symbol"):
            where_parts.append("symbol = ?")
            params.append(filters["symbol"])
        if filters.get("rating"):
            where_parts.append("rating = ?")
            params.append(filters["rating"])
        if filters.get("industry"):
            where_parts.append("industry = ?")
            params.append(filters["industry"])
        query = f"""
            SELECT evaluation_id, symbol, name, market, industry, total_score, rating, created_at, data_as_of_date
            FROM stock_evaluation
            WHERE {' AND '.join(where_parts)}
            ORDER BY created_at DESC
            LIMIT 200
        """
        with self.connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def list_symbol_history(self, symbol: str) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT evaluation_id, created_at, total_score, rating, data_as_of_date, report_period
                FROM stock_evaluation
                WHERE symbol = ?
                ORDER BY created_at ASC
                """,
                (symbol,),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_groups(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute("SELECT group_id, name, memo, created_at FROM stock_group ORDER BY group_id DESC").fetchall()
        return [dict(row) for row in rows]

    def create_group(self, name: str, memo: str) -> dict[str, Any]:
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO stock_group(name, memo, created_at) VALUES (?, ?, ?)",
                (name, memo, now_text()),
            )
            row = conn.execute(
                "SELECT group_id, name, memo, created_at FROM stock_group WHERE name = ?",
                (name,),
            ).fetchone()
        return dict(row) if row else {}

    def add_tags(self, evaluation_id: str, tags: list[str]) -> list[str]:
        clean_tags = sorted({clean_text(tag) for tag in tags if clean_text(tag)})
        with self.connect() as conn:
            for tag in clean_tags:
                conn.execute(
                    "INSERT OR IGNORE INTO evaluation_tag(evaluation_id, tag) VALUES (?, ?)",
                    (evaluation_id, tag),
                )
            rows = conn.execute(
                "SELECT tag FROM evaluation_tag WHERE evaluation_id = ? ORDER BY tag",
                (evaluation_id,),
            ).fetchall()
        return [item["tag"] for item in rows]

    def add_note(self, symbol: str, evaluation_id: str, content: str) -> dict[str, Any]:
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO research_note(symbol, evaluation_id, content, created_at) VALUES (?, ?, ?, ?)",
                (symbol, evaluation_id, content, now_text()),
            )
            row = conn.execute(
                "SELECT note_id, symbol, evaluation_id, content, created_at FROM research_note ORDER BY note_id DESC LIMIT 1"
            ).fetchone()
        return dict(row) if row else {}

    def export_evaluations_csv(self) -> bytes:
        rows = self.list_evaluations({})
        buffer = io.StringIO()
        writer = csv.DictWriter(
            buffer,
            fieldnames=["evaluation_id", "symbol", "name", "market", "industry", "total_score", "rating", "created_at", "data_as_of_date"],
        )
        writer.writeheader()
        writer.writerows(rows)
        return buffer.getvalue().encode("utf-8-sig")


class TushareClient:
    def __init__(self, token: str | None = None) -> None:
        self.token = clean_text(token or load_tushare_token())
        self.pro = ts.pro_api(self.token) if self.token else None
        self._cache: dict[str, pd.DataFrame] = {}

    @property
    def ready(self) -> bool:
        return self.pro is not None

    def query(self, api_name: str, **kwargs: Any) -> pd.DataFrame:
        if not self.pro:
            return pd.DataFrame()
        cache_key = json.dumps({"api": api_name, "kwargs": kwargs}, sort_keys=True, ensure_ascii=False)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached.copy()
        method = getattr(self.pro, api_name, None)
        try:
            if callable(method):
                df = method(**kwargs)
            else:
                df = self.pro.query(api_name, **kwargs)
        except Exception:
            return pd.DataFrame()
        df = df if isinstance(df, pd.DataFrame) else pd.DataFrame()
        self._cache[cache_key] = df.copy()
        return df.copy()

    def fetch_master(self, symbol: str, market: str) -> dict[str, Any]:
        if market == "CN":
            df = self.query("stock_basic", ts_code=symbol, fields="ts_code,symbol,name,area,industry,market,list_status,list_date")
            row = latest_row(df, ("list_date",))
            return {
                "symbol": symbol,
                "name": clean_text(pick_value(row, "name")) or symbol,
                "market": "CN",
                "industry": clean_text(pick_value(row, "industry")),
                "board": clean_text(pick_value(row, "market")) or "A股",
                "list_status": clean_text(pick_value(row, "list_status")) or "L",
            }
        df = self.query("hk_basic", ts_code=symbol)
        row = latest_row(df, ("list_date",))
        return {
            "symbol": symbol,
            "name": clean_text(pick_value(row, "name", "fullname")) or symbol,
            "market": "HK",
            "industry": clean_text(pick_value(row, "industry")),
            "board": clean_text(pick_value(row, "market")) or "港股",
            "list_status": clean_text(pick_value(row, "list_status")) or "L",
        }

    def fetch_market_snapshot(self, symbol: str, market: str) -> tuple[dict[str, float | None], str]:
        if market == "CN":
            df = self.query("daily_basic", ts_code=symbol)
            row = latest_row(df, ("trade_date",))
            return {
                "pe_ttm": as_float(pick_value(row, "pe_ttm", "pe")),
                "pb": as_float(pick_value(row, "pb")),
                "ps_ttm": as_float(pick_value(row, "ps_ttm", "ps")),
                "close": as_float(pick_value(row, "close")),
                "turnover_rate": as_float(pick_value(row, "turnover_rate")),
            }, clean_text(pick_value(row, "trade_date"))
        df = self.query("hk_daily", ts_code=symbol)
        row = latest_row(df, ("trade_date",))
        return {
            "pe_ttm": as_float(pick_value(row, "pe_ttm", "pe")),
            "pb": as_float(pick_value(row, "pb")),
            "ps_ttm": as_float(pick_value(row, "ps_ttm", "ps")),
            "close": as_float(pick_value(row, "close")),
            "turnover_rate": as_float(pick_value(row, "turnover_rate")),
        }, clean_text(pick_value(row, "trade_date"))

    def fetch_financial_snapshot(self, symbol: str) -> tuple[dict[str, float | None], str]:
        fina_df = self.query("fina_indicator", ts_code=symbol)
        fina_row = latest_row(fina_df, ("end_date",))
        income_df = self.query("income", ts_code=symbol)
        income_row = latest_row(income_df, ("end_date",))
        cash_df = self.query("cashflow", ts_code=symbol)
        cash_row = latest_row(cash_df, ("end_date",))

        revenue = as_float(pick_value(income_row, "revenue", "total_revenue", "total_revenue_ps"))
        net_profit = as_float(pick_value(income_row, "n_income_attr_p", "n_income"))
        gross_margin = as_float(pick_value(fina_row, "grossprofit_margin", "gross_margin"))
        net_margin = as_float(pick_value(fina_row, "netprofit_margin", "net_margin"))
        operating_cash = as_float(pick_value(cash_row, "n_cashflow_act", "n_cash_flows_fnc_act"))
        rd_exp = as_float(pick_value(income_row, "rd_exp"))

        ocf_to_profit = None
        if operating_cash is not None and net_profit not in (None, 0):
            ocf_to_profit = operating_cash / net_profit
        rd_to_revenue = None
        if rd_exp is not None and revenue not in (None, 0):
            rd_to_revenue = rd_exp / revenue * 100.0

        snapshot = {
            "roe": as_float(pick_value(fina_row, "roe", "roe_dt")),
            "gross_margin": gross_margin,
            "net_margin": net_margin,
            "revenue_yoy": as_float(pick_value(fina_row, "or_yoy", "q_sales_yoy")),
            "profit_yoy": as_float(pick_value(fina_row, "netprofit_yoy", "q_netprofit_yoy")),
            "rd_yoy": as_float(pick_value(fina_row, "rd_exp_yoy")),
            "debt_to_assets": as_float(pick_value(fina_row, "debt_to_assets")),
            "current_ratio": as_float(pick_value(fina_row, "current_ratio")),
            "ocf_to_profit": ocf_to_profit,
            "rd_to_revenue": rd_to_revenue,
            "revenue": revenue,
        }
        return snapshot, clean_text(pick_value(fina_row, "end_date")) or clean_text(pick_value(income_row, "end_date"))

    def fetch_industry_valuation_baseline(self, industry: str, trade_date: str) -> dict[str, float | None]:
        if not industry or not trade_date:
            return {}
        stock_df = self.query("stock_basic", list_status="L", fields="ts_code,industry")
        if stock_df.empty:
            return {}
        peer_codes = stock_df.loc[stock_df["industry"].astype(str) == industry, "ts_code"].dropna().astype(str)
        if peer_codes.empty:
            return {}
        snap_df = self.query("daily_basic", trade_date=trade_date, fields="ts_code,pe_ttm,pb,ps_ttm")
        if snap_df.empty:
            return {}
        peer_df = snap_df[snap_df["ts_code"].astype(str).isin(set(peer_codes.tolist()))].copy()
        if peer_df.empty:
            return {}
        return {
            "sample_n": int(len(peer_df)),
            "pe_ttm_median": as_float(peer_df["pe_ttm"].median()) if "pe_ttm" in peer_df else None,
            "pb_median": as_float(peer_df["pb"].median()) if "pb" in peer_df else None,
            "ps_ttm_median": as_float(peer_df["ps_ttm"].median()) if "ps_ttm" in peer_df else None,
        }


class StockEvaluationService:
    def __init__(self, repository: StockEvaluationRepository | None = None, tushare_client: TushareClient | None = None) -> None:
        self.repository = repository or StockEvaluationRepository()
        self.client = tushare_client or TushareClient()

    def guidance_snapshot(self) -> dict[str, Any]:
        return {
            "version_id": GUIDANCE_VERSION,
            "headline": "首版工作台已接线，当前优先完成个股标准化评估与历史沉淀。",
            "macro_score": None,
            "tracks": [
                "先确定研究方向，再提交 1-10 只股票进行标准化评估。",
                "横向对比以行业参考为主，小样本排名仅作辅助。",
                "若 Tushare 返回缺失项，系统会保留记录并标注数据截止日。",
            ],
            "token_ready": self.client.ready,
            "as_of_date": now_text()[:10],
        }

    def validate_code(self, raw_code: str) -> ValidationResult:
        source = clean_text(raw_code)
        compact = source.upper().replace(" ", "")
        if not compact:
            return ValidationResult(source, False, None, None, "", 10005, "代码为空")

        if re.fullmatch(r"\d{6}\.(SH|SZ)", compact):
            symbol = compact
            market = "CN"
        elif re.fullmatch(r"\d{5}\.HK", compact):
            symbol = compact
            market = "HK"
        elif re.fullmatch(r"\d{6}", compact):
            if compact.startswith(UNSUPPORTED_A_PREFIXES):
                return ValidationResult(source, False, None, None, "", 10003, "暂不支持北交所代码")
            if compact.startswith(SUPPORTED_A_PREFIXES):
                suffix = "SH" if compact.startswith(("60", "68")) else "SZ"
                symbol = f"{compact}.{suffix}"
                market = "CN"
            else:
                return ValidationResult(source, False, None, None, "", 10001, "A 股代码前缀不受支持")
        elif re.fullmatch(r"\d{1,5}", compact):
            symbol = f"{compact.zfill(5)}.HK"
            market = "HK"
        else:
            return ValidationResult(source, False, None, None, "", 10001, "代码格式错误")

        if not self.client.ready:
            return ValidationResult(source, True, symbol, market, "", None, "")
        master = self.client.fetch_master(symbol, market)
        if not clean_text(master.get("name")):
            return ValidationResult(source, False, None, None, "", 10002, "代码不存在或接口未返回主数据")
        if clean_text(master.get("list_status")) not in {"L", ""}:
            return ValidationResult(source, False, None, None, clean_text(master.get("name")), 10002, "股票已退市或暂停上市")
        return ValidationResult(source, True, symbol, market, clean_text(master.get("name")), None, "")

    def validate_codes(self, codes: list[str]) -> list[dict[str, Any]]:
        return [self.validate_code(code).to_dict() for code in codes]

    def _indicator(
        self,
        dimension_code: str,
        dimension_name: str,
        indicator_code: str,
        indicator_name: str,
        raw_value: float | None,
        score: float | None,
        display_text_value: str,
        notes: str = "",
    ) -> dict[str, Any]:
        return {
            "dimension_code": dimension_code,
            "dimension_name": dimension_name,
            "indicator_code": indicator_code,
            "indicator_name": indicator_name,
            "raw_value": raw_value,
            "score": None if score is None else round(score, 2),
            "display_text": display_text_value,
            "notes": notes,
        }

    def evaluate_symbol(self, symbol: str) -> dict[str, Any]:
        validation = self.validate_code(symbol)
        if not validation.ok or not validation.symbol or not validation.market:
            raise ValueError(validation.error_message or "股票校验失败")

        master = self.client.fetch_master(validation.symbol, validation.market) if self.client.ready else {
            "name": validation.name or validation.symbol,
            "industry": "",
            "market": validation.market,
        }
        market_snapshot, trade_date = self.client.fetch_market_snapshot(validation.symbol, validation.market) if self.client.ready else ({}, "")
        financial_snapshot, report_period = self.client.fetch_financial_snapshot(validation.symbol) if self.client.ready and validation.market == "CN" else ({}, "")
        industry_baseline = self.client.fetch_industry_valuation_baseline(clean_text(master.get("industry")), trade_date) if validation.market == "CN" and self.client.ready else {}

        indicators: list[dict[str, Any]] = []
        deductions: list[str] = []
        strengths: list[str] = []
        risks: list[str] = []
        watch_items: list[str] = []
        signal_tags: list[str] = []
        dimension_weights = {
            "valuation": 0.18,
            "profitability": 0.28,
            "growth": 0.22,
            "financial_health": 0.18,
            "competitiveness": 0.14,
        }

        pe_score = clamp_score(linear_score_lower(market_snapshot.get("pe_ttm"), 10.0, 45.0))
        pb_score = clamp_score(linear_score_lower(market_snapshot.get("pb"), 1.0, 8.0))
        ps_score = clamp_score(linear_score_lower(market_snapshot.get("ps_ttm"), 1.0, 12.0))
        indicators.extend(
            [
                self._indicator("valuation", "估值", "pe_ttm", "市盈率 TTM", market_snapshot.get("pe_ttm"), pe_score, display_value(market_snapshot.get("pe_ttm"))),
                self._indicator("valuation", "估值", "pb", "市净率", market_snapshot.get("pb"), pb_score, display_value(market_snapshot.get("pb"))),
                self._indicator("valuation", "估值", "ps_ttm", "市销率 TTM", market_snapshot.get("ps_ttm"), ps_score, display_value(market_snapshot.get("ps_ttm"))),
            ]
        )
        valuation_score = weighted_average([(pe_score, 0.4), (pb_score, 0.3), (ps_score, 0.3)])

        roe_score = clamp_score(linear_score_higher(financial_snapshot.get("roe"), 5.0, 18.0))
        gm_score = clamp_score(linear_score_higher(financial_snapshot.get("gross_margin"), 10.0, 45.0))
        nm_score = clamp_score(linear_score_higher(financial_snapshot.get("net_margin"), 3.0, 20.0))
        indicators.extend(
            [
                self._indicator("profitability", "盈利", "roe", "ROE", financial_snapshot.get("roe"), roe_score, display_value(financial_snapshot.get("roe"), "%")),
                self._indicator("profitability", "盈利", "gross_margin", "毛利率", financial_snapshot.get("gross_margin"), gm_score, display_value(financial_snapshot.get("gross_margin"), "%")),
                self._indicator("profitability", "盈利", "net_margin", "净利率", financial_snapshot.get("net_margin"), nm_score, display_value(financial_snapshot.get("net_margin"), "%")),
            ]
        )
        profitability_score = weighted_average([(roe_score, 0.4), (gm_score, 0.3), (nm_score, 0.3)])

        rev_score = clamp_score(linear_score_higher(financial_snapshot.get("revenue_yoy"), -5.0, 25.0))
        profit_score = clamp_score(linear_score_higher(financial_snapshot.get("profit_yoy"), -10.0, 30.0))
        rd_yoy_score = clamp_score(linear_score_higher(financial_snapshot.get("rd_yoy"), 0.0, 30.0))
        indicators.extend(
            [
                self._indicator("growth", "成长", "revenue_yoy", "营收增速", financial_snapshot.get("revenue_yoy"), rev_score, display_value(financial_snapshot.get("revenue_yoy"), "%")),
                self._indicator("growth", "成长", "profit_yoy", "净利润增速", financial_snapshot.get("profit_yoy"), profit_score, display_value(financial_snapshot.get("profit_yoy"), "%")),
                self._indicator("growth", "成长", "rd_yoy", "研发投入增速", financial_snapshot.get("rd_yoy"), rd_yoy_score, display_value(financial_snapshot.get("rd_yoy"), "%"), "港股或部分公司可能缺失"),
            ]
        )
        growth_score = weighted_average([(rev_score, 0.4), (profit_score, 0.4), (rd_yoy_score, 0.2)])

        debt_score = clamp_score(linear_score_lower(financial_snapshot.get("debt_to_assets"), 25.0, 80.0))
        current_score = clamp_score(range_score(financial_snapshot.get("current_ratio"), 1.2, 2.5, 0.3, 5.0))
        ocf_score = clamp_score(range_score(financial_snapshot.get("ocf_to_profit"), 0.8, 1.6, 0.0, 3.0))
        indicators.extend(
            [
                self._indicator("financial_health", "财务健康", "debt_to_assets", "资产负债率", financial_snapshot.get("debt_to_assets"), debt_score, display_value(financial_snapshot.get("debt_to_assets"), "%")),
                self._indicator("financial_health", "财务健康", "current_ratio", "流动比率", financial_snapshot.get("current_ratio"), current_score, display_value(financial_snapshot.get("current_ratio"))),
                self._indicator("financial_health", "财务健康", "ocf_to_profit", "现金流质量", financial_snapshot.get("ocf_to_profit"), ocf_score, display_value(financial_snapshot.get("ocf_to_profit"))),
            ]
        )
        financial_health_score = weighted_average([(debt_score, 0.35), (current_score, 0.25), (ocf_score, 0.4)])

        margin_delta = None
        if financial_snapshot.get("gross_margin") is not None:
            margin_delta = financial_snapshot["gross_margin"] - 25.0
        margin_delta_score = clamp_score(linear_score_higher(margin_delta, -15.0, 15.0))
        rd_ratio_score = clamp_score(linear_score_higher(financial_snapshot.get("rd_to_revenue"), 0.0, 8.0))
        rev_scale_score = clamp_score(linear_score_higher(financial_snapshot.get("revenue"), 1_000_000_000.0, 50_000_000_000.0))
        indicators.extend(
            [
                self._indicator("competitiveness", "竞争力", "margin_delta", "毛利率优势", margin_delta, margin_delta_score, display_value(margin_delta, "pct")),
                self._indicator("competitiveness", "竞争力", "rd_to_revenue", "研发占营收比", financial_snapshot.get("rd_to_revenue"), rd_ratio_score, display_value(financial_snapshot.get("rd_to_revenue"), "%")),
                self._indicator("competitiveness", "竞争力", "revenue_scale", "营收规模代理", financial_snapshot.get("revenue"), rev_scale_score, display_value(financial_snapshot.get("revenue"), "", 0)),
            ]
        )
        competitiveness_score = weighted_average([(margin_delta_score, 0.35), (rd_ratio_score, 0.3), (rev_scale_score, 0.35)])

        dimension_scores = [
            {"code": "valuation", "name": "估值", "score": valuation_score, "weight": dimension_weights["valuation"]},
            {"code": "profitability", "name": "盈利", "score": profitability_score, "weight": dimension_weights["profitability"]},
            {"code": "growth", "name": "成长", "score": growth_score, "weight": dimension_weights["growth"]},
            {"code": "financial_health", "name": "财务健康", "score": financial_health_score, "weight": dimension_weights["financial_health"]},
            {"code": "competitiveness", "name": "竞争力", "score": competitiveness_score, "weight": dimension_weights["competitiveness"]},
        ]
        total_score = weighted_average([(item["score"], item["weight"]) for item in dimension_scores])
        rating = "D"
        if total_score is not None:
            if total_score >= 80:
                rating = "A"
            elif total_score >= 65:
                rating = "B"
            elif total_score >= 50:
                rating = "C"

        scored_indicator_count = sum(1 for item in indicators if item.get("score") is not None)
        total_indicator_count = len(indicators)
        data_completeness = round(scored_indicator_count / total_indicator_count * 100.0, 2) if total_indicator_count else 0.0
        missing_indicator_count = total_indicator_count - scored_indicator_count

        dimension_insights: list[dict[str, Any]] = []
        for item in dimension_scores:
            tone = score_bucket(item["score"])
            comment = f"{item['name']}维度当前处于{tone}区间。"
            if item["code"] == "valuation" and valuation_score is not None:
                comment = f"估值维度为{tone}，主要取决于 PE/PB/PS 与安全区间的距离。"
            elif item["code"] == "profitability" and profitability_score is not None:
                comment = f"盈利维度为{tone}，重点反映 ROE、毛利率和净利率的综合质量。"
            elif item["code"] == "growth" and growth_score is not None:
                comment = f"成长维度为{tone}，当前更看重营收与利润增速是否同步改善。"
            elif item["code"] == "financial_health" and financial_health_score is not None:
                comment = f"财务健康维度为{tone}，核心关注杠杆、流动性与现金流兑现。"
            elif item["code"] == "competitiveness" and competitiveness_score is not None:
                comment = f"竞争力维度为{tone}，反映毛利护城河、研发投入与规模代理。"
            dimension_insights.append(
                {
                    "code": item["code"],
                    "name": item["name"],
                    "score": None if item["score"] is None else round(item["score"], 2),
                    "weight": item["weight"],
                    "bucket": tone,
                    "comment": comment,
                }
            )

        if total_score is None:
            deductions.append("可用指标不足，当前仅输出结构化数据快照。")
            risks.append("核心指标缺失较多，结论可信度有限。")
        if valuation_score is not None and valuation_score >= 70:
            strengths.append("估值处于相对友好区间，当前安全边际优于一般阈值水平。")
            signal_tags.append("估值友好")
        elif valuation_score is not None and valuation_score < 45:
            deductions.append("估值压力偏高，建议优先核查当前估值与盈利兑现匹配度。")
            risks.append("估值消化要求偏高，若业绩兑现放缓容易产生压缩。")
            signal_tags.append("估值承压")

        if profitability_score is not None and profitability_score >= 70:
            strengths.append("盈利质量较好，ROE 与利润率组合具备较强稳定性。")
            signal_tags.append("高盈利质量")
        elif profitability_score is not None and profitability_score < 50:
            deductions.append("盈利质量偏弱，需要重点复核毛利率与净利率稳定性。")
            risks.append("利润率与盈利效率偏弱，抗周期波动能力一般。")

        if growth_score is not None and growth_score >= 68:
            strengths.append("成长动能较强，收入与利润保持同步扩张。")
            signal_tags.append("成长强化")
        elif growth_score is not None and growth_score < 50:
            deductions.append("成长动能一般，建议结合行业景气与订单变化判断。")
            watch_items.append("继续跟踪营收与净利润增速是否改善，避免仅靠估值修复。")

        if financial_health_score is not None and financial_health_score >= 65:
            strengths.append("财务结构较稳，现金流与流动性表现尚可。")
            signal_tags.append("现金流稳健")
        elif financial_health_score is not None and financial_health_score < 50:
            deductions.append("财务健康得分偏低，需留意负债结构与现金流兑现。")
            risks.append("财务安全边际偏弱，需特别关注负债与经营现金流质量。")
            signal_tags.append("财务压力")

        if competitiveness_score is not None and competitiveness_score >= 65:
            strengths.append("竞争力维度较优，显示出一定的毛利护城河与规模优势。")
        elif competitiveness_score is not None and competitiveness_score < 45:
            risks.append("竞争力维度较弱，可能缺少明显的产品、技术或规模护城河。")

        if missing_indicator_count >= 3:
            watch_items.append("当前缺失指标较多，建议补齐财务口径后再做二次评估。")
            signal_tags.append("数据待补齐")
        if validation.market == "HK":
            deductions.append("港股财务口径接入仍在补强，当前结果可能存在更多缺失项。")
            watch_items.append("港股财务字段建议结合公告或手工补录进一步核验。")

        if market_snapshot.get("pe_ttm") is not None and industry_baseline.get("pe_ttm_median") is not None:
            pe_gap = market_snapshot["pe_ttm"] - industry_baseline["pe_ttm_median"]
            if pe_gap <= -5:
                strengths.append("相对行业 PE 处于更低位置，存在一定相对估值折价。")
            elif pe_gap >= 8:
                risks.append("当前 PE 明显高于行业中位数，市场对未来增长已有较高预期。")
        if financial_snapshot.get("ocf_to_profit") is not None and financial_snapshot["ocf_to_profit"] < 0.8:
            watch_items.append("经营现金流对利润覆盖偏弱，需要继续跟踪回款与库存变化。")
        if financial_snapshot.get("debt_to_assets") is not None and financial_snapshot["debt_to_assets"] > 65:
            watch_items.append("资产负债率处于高位，建议结合利率环境评估资产负债表弹性。")

        strengths = strengths[:4]
        risks = risks[:4]
        watch_items = watch_items[:4]
        signal_tags = sorted(set(signal_tags))

        confidence_level = "中"
        if data_completeness >= 85 and validation.market == "CN":
            confidence_level = "高"
        elif data_completeness < 65 or validation.market == "HK":
            confidence_level = "偏低"

        action_hint = "建议继续观察。"
        if rating == "A":
            action_hint = "建议纳入核心跟踪池，重点等待更优介入窗口。"
        elif rating == "B":
            action_hint = "建议保留在重点观察名单，等待更明确的催化验证。"
        elif rating == "C":
            action_hint = "建议暂列普通观察，优先等待增长或估值条件改善。"
        elif rating == "D":
            action_hint = "建议降低优先级，除非出现强催化或基本面拐点。"

        overall_summary = f"{clean_text(master.get('name')) or validation.symbol} 当前综合评分为 {round(total_score, 2) if total_score is not None else '缺失'} 分，评级 {rating}。"
        thesis_summary = f"从结构上看，最强维度为 {max(dimension_insights, key=lambda item: item['score'] if item['score'] is not None else -1)['name']}，最弱维度为 {min(dimension_insights, key=lambda item: item['score'] if item['score'] is not None else 101)['name']}。"
        execution_summary = f"当前数据完整度为 {data_completeness:.2f}% ，结论可信度为 {confidence_level}，{action_hint}"
        conclusion_sections = [
            {"title": "总体判断", "content": overall_summary},
            {"title": "结构拆解", "content": thesis_summary},
            {"title": "操作提示", "content": execution_summary},
        ]
        advice_text = " ".join(section["content"] for section in conclusion_sections)

        evaluation_id = str(uuid.uuid4())
        summary = {
            "evaluation_id": evaluation_id,
            "symbol": validation.symbol,
            "name": clean_text(master.get("name")) or validation.symbol,
            "market": validation.market,
            "industry": clean_text(master.get("industry")),
            "total_score": None if total_score is None else round(total_score, 2),
            "rating": rating,
            "created_at": now_text(),
            "data_as_of_date": trade_date,
            "report_period": report_period,
            "rule_version": RULE_VERSION,
            "guidance_version": GUIDANCE_VERSION,
            "advice_text": advice_text,
            "deductions": deductions,
            "strengths": strengths,
            "risks": risks,
            "watch_items": watch_items,
            "signal_tags": signal_tags,
            "confidence_level": confidence_level,
            "data_completeness": data_completeness,
            "missing_indicator_count": missing_indicator_count,
            "conclusion_sections": conclusion_sections,
            "dimension_scores": [
                {
                    "code": item["code"],
                    "name": item["name"],
                    "score": None if item["score"] is None else round(item["score"], 2),
                    "weight": item["weight"],
                    "bucket": score_bucket(item["score"]),
                }
                for item in dimension_scores
            ],
            "dimension_insights": dimension_insights,
            "industry_baseline": industry_baseline,
            "quote_snapshot": market_snapshot,
            "financial_snapshot": financial_snapshot,
        }
        self.repository.save_evaluation(summary, indicators)
        summary["indicators"] = indicators
        summary["tags"] = []
        summary["notes"] = []
        return summary

    def list_evaluations(self, filters: dict[str, str]) -> list[dict[str, Any]]:
        return self.repository.list_evaluations(filters)

    def get_evaluation(self, evaluation_id: str) -> dict[str, Any] | None:
        return self.repository.get_evaluation(evaluation_id)

    def list_history(self, symbol: str) -> list[dict[str, Any]]:
        return self.repository.list_symbol_history(symbol)

    def list_groups(self) -> list[dict[str, Any]]:
        return self.repository.list_groups()

    def create_group(self, name: str, memo: str) -> dict[str, Any]:
        return self.repository.create_group(name, memo)

    def add_tags(self, evaluation_id: str, tags: list[str]) -> list[str]:
        return self.repository.add_tags(evaluation_id, tags)

    def add_note(self, symbol: str, evaluation_id: str, content: str) -> dict[str, Any]:
        return self.repository.add_note(symbol, evaluation_id, content)

    def export_dataset(self, dataset: str, file_format: str) -> tuple[bytes, str]:
        if dataset != "evaluations":
            raise ValueError("当前 MVP 仅支持导出 evaluations 数据集")
        if file_format != "csv":
            raise ValueError("当前 MVP 仅支持 CSV 导出")
        return self.repository.export_evaluations_csv(), "text/csv; charset=utf-8"
