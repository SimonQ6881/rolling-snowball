from __future__ import annotations

import ssl
import unittest
from unittest.mock import patch
from urllib.error import URLError

import pandas as pd

from src import report_extra


class _DummyResponse:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def __enter__(self) -> "_DummyResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self) -> bytes:
        return self.payload


class ReportExtraTest(unittest.TestCase):
    def test_fetch_url_bytes_retries_with_unverified_ssl_context(self) -> None:
        ssl_error = URLError(ssl.SSLCertVerificationError("certificate verify failed"))
        insecure_context = object()

        with patch(
            "src.report_extra.urllib.request.urlopen",
            side_effect=[ssl_error, _DummyResponse(b"payload")],
        ) as mock_urlopen, patch(
            "src.report_extra.ssl._create_unverified_context",
            return_value=insecure_context,
        ) as mock_context:
            payload = report_extra.fetch_url_bytes("https://example.com")

        self.assertEqual(payload, b"payload")
        self.assertEqual(mock_urlopen.call_count, 2)
        self.assertEqual(mock_urlopen.call_args_list[1].kwargs["context"], insecure_context)
        mock_context.assert_called_once()

    def test_fetch_treasury_curve_merges_two_years_and_sorts_dates(self) -> None:
        current_year_df = pd.DataFrame(
            [
                {"Date": "2026-07-05", "2 Yr": 3.80, "10 Yr": 4.20},
                {"Date": "2026-07-06", "2 Yr": 3.85, "10 Yr": 4.25},
            ]
        )
        previous_year_df = pd.DataFrame(
            [
                {"Date": "2025-12-31", "2 Yr": 4.10, "10 Yr": 4.50},
            ]
        )

        with patch("src.report_extra.fetch_url_bytes", return_value=b"<html></html>") as mock_fetch, patch(
            "src.report_extra.pd.read_html",
            side_effect=[[current_year_df], [previous_year_df]],
        ):
            df = report_extra.fetch_treasury_curve()

        self.assertEqual(mock_fetch.call_count, 2)
        self.assertEqual(df["trade_date"].tolist(), ["20251231", "20260705", "20260706"])
        self.assertEqual(df["y2"].tolist(), [4.10, 3.80, 3.85])
        self.assertEqual(df["y10"].tolist(), [4.50, 4.20, 4.25])


if __name__ == "__main__":
    unittest.main()
