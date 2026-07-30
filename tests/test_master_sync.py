from __future__ import annotations

import pandas as pd

from src.rolling_snowball.master_sync import _build_sw_level1_mapping, dataframe_to_records


class _StubPro:
    def index_classify(self, *, src: str, level: str) -> pd.DataFrame:
        assert src == "SW2021"
        assert level == "L1"
        return pd.DataFrame(
            [
                {"index_code": "801780.SI", "industry_name": "银行"},
                {"index_code": "801080.SI", "industry_name": "电子"},
            ]
        )

    def index_member_all(self, *, l1_code: str) -> pd.DataFrame:
        if l1_code == "801780.SI":
            return pd.DataFrame(
                [
                    {"ts_code": "000001.SZ", "l1_name": "银行", "in_date": "19910403", "out_date": None},
                    {"ts_code": "600000.SH", "l1_name": "银行", "in_date": "19991110", "out_date": None},
                ]
            )
        if l1_code == "801080.SI":
            return pd.DataFrame(
                [
                    {"ts_code": "000021.SZ", "l1_name": "电子", "in_date": "19940202", "out_date": None},
                    {"ts_code": "000001.SZ", "l1_name": "旧行业", "in_date": "19900101", "out_date": "19910402"},
                ]
            )
        return pd.DataFrame()


def test_build_sw_level1_mapping_keeps_current_membership() -> None:
    mapping_df = _build_sw_level1_mapping(_StubPro())

    assert set(mapping_df.columns) == {"ts_code", "sw_level1_industry"}
    mapping = dict(zip(mapping_df["ts_code"], mapping_df["sw_level1_industry"]))
    assert mapping["000001.SZ"] == "银行"
    assert mapping["600000.SH"] == "银行"
    assert mapping["000021.SZ"] == "电子"


def test_dataframe_to_records_uses_sw_level1_industry_column() -> None:
    df = pd.DataFrame(
        [
            {
                "ts_code": "000001.SZ",
                "name": "平安银行",
                "market": "主板",
                "industry": "旧占位行业",
                "sw_level1_industry": "银行",
                "list_status": "L",
            }
        ]
    )

    records = dataframe_to_records(df)

    assert len(records) == 1
    assert records[0].sw_level1_industry == "银行"
