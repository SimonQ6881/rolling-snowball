from __future__ import annotations

import io
import json
import re
import ssl
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
}


def open_url(request: urllib.request.Request, timeout: int = 20):
    try:
        return urllib.request.urlopen(request, timeout=timeout)
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", None)
        if isinstance(reason, ssl.SSLCertVerificationError):
            context = ssl._create_unverified_context()
            return urllib.request.urlopen(request, timeout=timeout, context=context)
        raise


def fetch_url_text(url: str, headers: dict[str, str] | None = None, timeout: int = 20) -> str:
    request_headers = DEFAULT_HEADERS.copy()
    if headers:
        request_headers.update(headers)
    req = urllib.request.Request(url, headers=request_headers)
    with open_url(req, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="ignore")


def fetch_url_bytes(url: str, headers: dict[str, str] | None = None, timeout: int = 20) -> bytes:
    request_headers = DEFAULT_HEADERS.copy()
    if headers:
        request_headers.update(headers)
    req = urllib.request.Request(url, headers=request_headers)
    with open_url(req, timeout=timeout) as response:
        return response.read()


def clean_text(raw: str) -> str:
    text = re.sub(r"<[^>]+>", " ", raw)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_date_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    for fmt in (
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%Y%m%d",
        "%d %B %Y",
        "%d %b %Y",
        "%d %B, %Y",
        "%d %b, %Y",
        "%B %d, %Y",
        "%b %d, %Y",
        "%a, %d %b %Y %H:%M:%S %Z",
    ):
        try:
            return datetime.strptime(text, fmt).strftime("%Y%m%d")
        except ValueError:
            continue
    return text.replace("-", "").replace("/", "")[:8]


def parse_rss_feed(xml_text: str, source: str) -> list[dict[str, str]]:
    xml_text = xml_text.lstrip("\ufeff").strip()
    root = ET.fromstring(xml_text)
    items: list[dict[str, str]] = []
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        description = (item.findtext("description") or "").strip()
        pub_date = normalize_date_text(item.findtext("pubDate"))
        category = (item.findtext("category") or "").strip()
        items.append(
            {
                "source": source,
                "title": clean_text(title),
                "link": link,
                "summary": clean_text(description),
                "date": pub_date,
                "category": clean_text(category),
            }
        )
    return items


def classify_tags(text: str) -> list[str]:
    mapping = {
        "黄金": ["黄金", "金价", "bullion", "gold"],
        "铜": ["铜", "铜价", "copper"],
        "锂": ["锂", "碳酸锂", "盐湖提锂", "lithium"],
        "美元": ["美元", "dollar", "usdcnh", "dxy"],
        "美债": ["美债", "treasury", "yield", "国债"],
        "央行政策": ["fomc", "bank rate", "monetary policy", "央行", "利率", "加息", "降息", "hold rates"],
        "AI": ["人工智能", "ai", "算力", "gpu"],
        "芯片": ["芯片", "semiconductor", "存储芯片"],
        "通信": ["通信", "5g", "光模块", "通信设备"],
        "电力": ["电力", "电网", "绿电", "发电"],
        "紫金矿业": ["紫金", "601899", "紫金矿业"],
    }
    haystack = text.lower()
    tags: list[str] = []
    for tag, keywords in mapping.items():
        if any(keyword.lower() in haystack for keyword in keywords):
            tags.append(tag)
    return tags


def cache_json_records(path: Path, records: list[dict[str, Any]], key_fields: list[str]) -> list[dict[str, Any]]:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing: list[dict[str, Any]] = []
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = []
    merged: dict[str, dict[str, Any]] = {}
    for item in existing + records:
        key = "||".join(str(item.get(field, "")) for field in key_fields)
        merged[key] = item
    output = sorted(
        merged.values(),
        key=lambda item: str(item.get("date", "")),
        reverse=True,
    )
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    return output


def fetch_fred_series(series_id: str, label: str) -> pd.DataFrame:
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    csv_bytes = fetch_url_bytes(url)
    df = pd.read_csv(io.BytesIO(csv_bytes))
    if df.empty or len(df.columns) < 2:
        return pd.DataFrame()
    value_column = df.columns[1]
    out = pd.DataFrame(
        {
            "trade_date": pd.to_datetime(df["DATE"], errors="coerce").dt.strftime("%Y%m%d"),
            "close": pd.to_numeric(df[value_column], errors="coerce"),
            "label": label,
        }
    )
    return out.dropna(subset=["trade_date", "close"]).reset_index(drop=True)


def fetch_treasury_curve() -> pd.DataFrame:
    years = [datetime.now().year, datetime.now().year - 1]
    frames: list[pd.DataFrame] = []
    column_map = {
        "Date": "date",
        "2 Yr": "y2",
        "10 Yr": "y10",
        "30 Yr": "y30",
        "3 Mo": "m3",
        "1 Yr": "y1",
    }
    for year in years:
        url = (
            "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
            f"TextView?type=daily_treasury_yield_curve&field_tdr_date_value={year}"
        )
        html = fetch_url_bytes(url)
        tables = pd.read_html(io.BytesIO(html))
        if not tables:
            continue
        df = tables[0].copy()
        keep_columns = [column for column in column_map if column in df.columns]
        if not keep_columns:
            continue
        out = df[keep_columns].rename(columns=column_map)
        out["trade_date"] = pd.to_datetime(out["date"], errors="coerce").dt.strftime("%Y%m%d")
        for column in ("m3", "y1", "y2", "y10", "y30"):
            if column in out.columns:
                out[column] = pd.to_numeric(out[column], errors="coerce")
        frames.append(out)
    if not frames:
        return pd.DataFrame()
    merged = pd.concat(frames, ignore_index=True)
    merged = merged.dropna(subset=["trade_date"]).sort_values("trade_date")
    return merged.drop_duplicates(subset=["trade_date"], keep="last").reset_index(drop=True)


def fetch_boe_rate_history() -> pd.DataFrame:
    page_html = fetch_url_text("https://www.bankofengland.co.uk/monetary-policy/the-interest-rate-bank-rate")
    match = re.search(r'href="([^"]*baserate\.xls)"', page_html)
    if not match:
        return pd.DataFrame()
    href = match.group(1)
    url = f"https://www.bankofengland.co.uk{href}" if href.startswith("/") else href
    xls_bytes = fetch_url_bytes(url)
    raw = pd.read_excel(io.BytesIO(xls_bytes), sheet_name="Raw Data", header=None)
    if raw.empty:
        return pd.DataFrame()
    raw.columns = raw.iloc[1].tolist()
    raw = raw.iloc[2:].copy()
    raw = raw.rename(columns={"Date": "date", "Bank Rate": "close"})
    raw["trade_date"] = pd.to_datetime(raw["date"], errors="coerce").dt.strftime("%Y%m%d")
    raw["close"] = pd.to_numeric(raw["close"], errors="coerce")
    return raw[["trade_date", "close"]].dropna().reset_index(drop=True)


def extract_policy_action(text: str) -> str:
    haystack = text.lower()
    if any(keyword in haystack for keyword in ("raise", "hike", "increased", "increase", "加息", "上调")):
        return "加息"
    if any(keyword in haystack for keyword in ("cut", "reduce", "lower", "降息", "下调")):
        return "降息"
    if any(keyword in haystack for keyword in ("maintain", "hold", "unchanged", "维持", "按兵不动")):
        return "维持"
    return "观察"


def extract_rate_value(text: str) -> str:
    match = re.search(r"(\d+(?:\.\d+)?)\s*percent", text.lower())
    if match:
        return match.group(1) + "%"
    match = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
    if match:
        return match.group(1) + "%"
    return "N/A"


def fetch_fed_policy_events(limit: int = 12) -> list[dict[str, Any]]:
    xml_text = fetch_url_text("https://www.federalreserve.gov/feeds/press_all.xml")
    rows = []
    for item in parse_rss_feed(xml_text, "美联储"):
        content = f"{item['title']} {item['summary']} {item['category']}"
        if not any(keyword in content.lower() for keyword in ("monetary", "fomc", "implementation note", "discount rate")):
            continue
        rows.append(
            {
                **item,
                "institution": "美联储",
                "action": extract_policy_action(content),
                "rate": extract_rate_value(content),
                "tags": classify_tags(content),
            }
        )
        if len(rows) >= limit:
            break
    return rows


def fetch_boj_policy_events(limit: int = 12) -> list[dict[str, Any]]:
    xml_text = fetch_url_text("https://www.boj.or.jp/en/rss/whatsnew.xml")
    rows = []
    for item in parse_rss_feed(xml_text, "日本央行"):
        content = f"{item['title']} {item['summary']} {item['category']}"
        if "monetary policy" not in content.lower():
            continue
        rows.append(
            {
                **item,
                "institution": "日本央行",
                "action": extract_policy_action(content),
                "rate": extract_rate_value(content),
                "tags": classify_tags(content),
            }
        )
        if len(rows) >= limit:
            break
    return rows


def fetch_boe_policy_events(limit: int = 6) -> list[dict[str, Any]]:
    html = fetch_url_text("https://www.bankofengland.co.uk/monetary-policy/the-interest-rate-bank-rate")
    rate_match = re.search(r"Current Bank Rate\s*([0-9.]+)%", html, re.I)
    date_match = re.search(r"Published on\s*([0-9]{1,2}\s+[A-Za-z]+\s+[0-9]{4})", html, re.I)
    title_match = re.search(r"Our latest decision:([^<]+)", html, re.I)
    if not rate_match:
        return []
    title = clean_text(title_match.group(1)) if title_match else "Bank Rate latest decision"
    published = normalize_date_text(date_match.group(1)) if date_match else ""
    rate = rate_match.group(1) + "%"
    summary = clean_text(html[html.find("Key points:") : html.find("What are interest rates?")])
    return [
        {
            "source": "英国央行",
            "institution": "英国央行",
            "title": title,
            "link": "https://www.bankofengland.co.uk/monetary-policy/the-interest-rate-bank-rate",
            "summary": summary[:500],
            "date": published,
            "category": "Monetary Policy",
            "action": extract_policy_action(summary),
            "rate": rate,
            "tags": classify_tags(summary),
        }
    ][:limit]


def recent_year_months(now: datetime, months: int) -> list[tuple[int, int]]:
    year = now.year
    month = now.month
    output: list[tuple[int, int]] = []
    for _ in range(months):
        output.append((year, month))
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    return output


def parse_goldhub_archive_links(html: str) -> list[str]:
    links = re.findall(r'href="(/goldhub/gold-focus/\d{4}/\d{2}/central-bank-gold-statistics[^"]+)"', html)
    return [f"https://www.gold.org{link}" for link in links]


def extract_goldhub_month_entry(article_html: str, url: str) -> dict[str, Any] | None:
    title_match = re.search(r"<h1[^>]*>\s*(.*?)\s*</h1>", article_html, re.S)
    date_match = re.search(r"(\d{1,2}\s+[A-Za-z]+,\s+\d{4})", article_html)
    title = clean_text(title_match.group(1)) if title_match else ""
    published = normalize_date_text(date_match.group(1)) if date_match else ""
    text = clean_text(article_html)

    month_label = ""
    title_month = re.search(r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+20\d{2}", title)
    if title_month:
        month_label = title_month.group(0)
    else:
        content_month = re.search(r"in\s+(January|February|March|April|May|June|July|August|September|October|November|December)", text)
        if content_month:
            month_label = content_month.group(1)

    net_value = None
    direction = "观察"
    patterns = [
        (r"central banks bought a net\s+(-?\d+(?:\.\d+)?)t", 1.0),
        (r"net purchases? of\s+(\d+(?:\.\d+)?)t", 1.0),
        (r"net buying .*?(\d+(?:\.\d+)?)t", 1.0),
        (r"net sales?(?: were reported)? of\s+(\d+(?:\.\d+)?)t", -1.0),
        (r"central banks sold a net\s+(\d+(?:\.\d+)?)t", -1.0),
    ]
    for pattern, sign in patterns:
        match = re.search(pattern, text, re.I)
        if not match:
            continue
        net_value = float(match.group(1)) * sign
        direction = "净卖出" if net_value < 0 else "净买入"
        break

    bullets = [clean_text(item) for item in re.findall(r"<li>(.*?)</li>", article_html, re.S)]
    highlights = [item for item in bullets if item][:6]
    if not title:
        return None
    tags = classify_tags(title + " " + " ".join(highlights))
    tags.extend(["央行购金"])
    return {
        "source": "World Gold Council",
        "title": title,
        "link": url,
        "summary": highlights[0] if highlights else clean_text(text[:180]),
        "date": published,
        "month_label": month_label,
        "net_tonnes": net_value,
        "direction": direction,
        "highlights": highlights,
        "tags": sorted(set(tags)),
    }


def fetch_goldhub_gold_purchase_entries(now: datetime, months: int = 8) -> list[dict[str, Any]]:
    article_urls: list[str] = []
    for year, month in recent_year_months(now, months):
        archive_url = f"https://www.gold.org/goldhub/gold-focus/{year}/{month:02d}"
        html = fetch_url_text(archive_url)
        for link in parse_goldhub_archive_links(html):
            if link not in article_urls:
                article_urls.append(link)

    rows: list[dict[str, Any]] = []
    for url in article_urls:
        article_html = fetch_url_text(url)
        entry = extract_goldhub_month_entry(article_html, url)
        if entry:
            rows.append(entry)
    return rows


def resample_price_frame(df: pd.DataFrame, freq: str) -> pd.DataFrame:
    if df.empty or "trade_date" not in df.columns or "close" not in df.columns:
        return pd.DataFrame()
    sample = df.copy()
    sample["dt"] = pd.to_datetime(sample["trade_date"], errors="coerce")
    sample = sample.dropna(subset=["dt"]).sort_values("dt")
    aggregations: dict[str, str] = {"close": "last"}
    for column, func in (("open", "first"), ("high", "max"), ("low", "min"), ("vol", "sum"), ("amount", "sum")):
        if column in sample.columns:
            aggregations[column] = func
    out = sample.set_index("dt").resample(freq).agg(aggregations).dropna(subset=["close"]).reset_index()
    out["trade_date"] = out["dt"].dt.strftime("%Y%m%d")
    return out.drop(columns=["dt"])


def compute_support_resistance(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df.empty or "close" not in df.columns:
        return []
    sample = df.tail(120).copy()
    if sample.empty:
        return []
    close = pd.to_numeric(sample["close"], errors="coerce").dropna()
    if close.empty:
        return []
    return [
        {"label": "20日支撑", "value": float(close.tail(20).min()), "tone": "support"},
        {"label": "60日支撑", "value": float(close.tail(60).min()), "tone": "support"},
        {"label": "20日阻力", "value": float(close.tail(20).max()), "tone": "resistance"},
        {"label": "60日阻力", "value": float(close.tail(60).max()), "tone": "resistance"},
    ]


def build_timeframe_map(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return {
        "日": df.tail(120).reset_index(drop=True),
        "周": resample_price_frame(df, "W-FRI").tail(104).reset_index(drop=True),
        "月": resample_price_frame(df, "ME").tail(72).reset_index(drop=True),
        "年": resample_price_frame(df, "YE").tail(15).reset_index(drop=True),
    }


def summarize_status_by_error(status_rows: list[dict[str, Any]]) -> list[list[str]]:
    groups: dict[str, int] = {}
    for item in status_rows:
        if item.get("ok"):
            continue
        detail = str(item.get("detail", "")).lower()
        if "权限" in detail or "permission" in detail:
            key = "权限不足"
        elif "403" in detail or "forbidden" in detail:
            key = "访问受限"
        elif "404" in detail or "not found" in detail:
            key = "地址失效"
        elif "timeout" in detail or "timed out" in detail:
            key = "请求超时"
        elif "ssl" in detail:
            key = "SSL/证书"
        else:
            key = "其他异常"
        groups[key] = groups.get(key, 0) + 1
    return [[key, str(value)] for key, value in sorted(groups.items(), key=lambda item: item[1], reverse=True)]
