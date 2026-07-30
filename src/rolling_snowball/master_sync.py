from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd
import tushare as ts

from .db import connect
from .settings import env_value, PostgresSettings


@dataclass(frozen=True)
class StockMasterRecord:
    ts_code: str
    stock_name: str
    market: str
    sw_level1_industry: str
    list_status: str


def load_tushare_token() -> str:
    token = env_value("TUSHARE_TOKEN", None)
    if not token:
        raise RuntimeError("未找到 TUSHARE_TOKEN，请先在 .env 或环境变量中配置。")
    return token


def build_tushare_client() -> ts.pro.client.DataApi:
    return ts.pro_api(load_tushare_token())


def _normalize_market(value: str) -> str:
    text = (value or "").strip()
    if text in {"主板", "创业板", "科创板", "CDR", "北交所"}:
        return "A股"
    return text or "A股"


def _normalize_industry(value: object) -> str:
    text = "" if value is None else str(value).strip()
    return text or "待补充"


def _build_sw_level1_mapping(pro: ts.pro.client.DataApi) -> pd.DataFrame:
    classify_df = pro.index_classify(src="SW2021", level="L1")
    if classify_df.empty:
        return pd.DataFrame(columns=["ts_code", "sw_level1_industry"])

    frames: list[pd.DataFrame] = []
    for l1_code in classify_df["index_code"].dropna().astype(str).tolist():
        member_df = pro.index_member_all(l1_code=l1_code)
        if member_df.empty or "ts_code" not in member_df.columns or "l1_name" not in member_df.columns:
            continue
        working = member_df.copy()
        if "out_date" in working.columns:
            out_dates = working["out_date"].fillna("").astype(str).str.strip()
            working = working[out_dates.eq("")]
        if "in_date" in working.columns:
            working["in_date"] = working["in_date"].fillna("").astype(str)
            working = working.sort_values("in_date")
        working = working.drop_duplicates("ts_code", keep="last")
        frames.append(working[["ts_code", "l1_name"]])

    if not frames:
        return pd.DataFrame(columns=["ts_code", "sw_level1_industry"])

    mapping_df = pd.concat(frames, ignore_index=True)
    mapping_df = mapping_df.drop_duplicates("ts_code", keep="last").rename(
        columns={"l1_name": "sw_level1_industry"}
    )
    return mapping_df


def fetch_stock_master_dataframe(limit: int | None = None) -> pd.DataFrame:
    pro = build_tushare_client()
    stock_basic_df = pro.stock_basic(
        exchange="",
        list_status="L",
        fields="ts_code,name,market,industry,list_status",
    )
    sw_mapping_df = _build_sw_level1_mapping(pro)
    df = stock_basic_df.merge(sw_mapping_df, on="ts_code", how="left")
    df["sw_level1_industry"] = df["sw_level1_industry"].fillna(df["industry"])
    if limit is not None:
        df = df.head(limit)
    return df


def dataframe_to_records(df: pd.DataFrame) -> list[StockMasterRecord]:
    records: list[StockMasterRecord] = []
    for row in df.itertuples(index=False):
        ts_code = getattr(row, "ts_code", "").strip()
        name = getattr(row, "name", "").strip()
        if not ts_code or not name:
            continue
        records.append(
            StockMasterRecord(
                ts_code=ts_code,
                stock_name=name,
                market=_normalize_market(getattr(row, "market", "")),
                sw_level1_industry=_normalize_industry(getattr(row, "sw_level1_industry", None)),
                list_status=(getattr(row, "list_status", "") or "L").strip() or "L",
            )
        )
    return records


def upsert_stocks_master(
    records: Iterable[StockMasterRecord],
    settings: PostgresSettings | None = None,
) -> int:
    sql = """
        INSERT INTO stocks_master (
            ts_code,
            stock_name,
            market,
            sw_level1_industry,
            list_status
        )
        VALUES (%(ts_code)s, %(stock_name)s, %(market)s, %(sw_level1_industry)s, %(list_status)s)
        ON CONFLICT (ts_code) DO UPDATE
        SET stock_name = EXCLUDED.stock_name,
            market = EXCLUDED.market,
            sw_level1_industry = EXCLUDED.sw_level1_industry,
            list_status = EXCLUDED.list_status,
            updated_at = now();
    """
    payload = [
        {
            "ts_code": item.ts_code,
            "stock_name": item.stock_name,
            "market": item.market,
            "sw_level1_industry": item.sw_level1_industry,
            "list_status": item.list_status,
        }
        for item in records
    ]
    if not payload:
        return 0
    with connect(settings) as conn:
        with conn.cursor() as cur:
            cur.executemany(sql, payload)
        conn.commit()
    return len(payload)


def sync_stocks_master(
    settings: PostgresSettings | None = None,
    *,
    limit: int | None = None,
) -> int:
    df = fetch_stock_master_dataframe(limit=limit)
    records = dataframe_to_records(df)
    return upsert_stocks_master(records, settings)
