from __future__ import annotations

import re
from typing import Any

import pandas as pd


COUNTRY_META = {
    "china": {"label": "中国", "region": "亚洲", "style": "新兴市场", "aliases": ("People’s Bank of China", "People's Bank of China", "PBoC", "China")},
    "russia": {"label": "俄罗斯", "region": "欧洲/欧亚", "style": "新兴市场", "aliases": ("Russia", "Russian Federation", "Bank of Russia")},
    "india": {"label": "印度", "region": "亚洲", "style": "新兴市场", "aliases": ("India", "Reserve Bank of India", "RBI")},
    "brazil": {"label": "巴西", "region": "拉美", "style": "新兴市场", "aliases": ("Brazil", "Banco Central do Brasil", "Central Bank of Brazil")},
    "poland": {"label": "波兰", "region": "欧洲", "style": "发达/转型经济体", "aliases": ("Poland", "National Bank of Poland")},
    "uzbekistan": {"label": "乌兹别克斯坦", "region": "中亚", "style": "新兴市场", "aliases": ("Uzbekistan", "Central Bank of Uzbekistan")},
    "kazakhstan": {"label": "哈萨克斯坦", "region": "中亚", "style": "新兴市场", "aliases": ("Kazakhstan", "National Bank of Kazakhstan")},
    "turkey": {"label": "土耳其", "region": "中东/欧亚", "style": "新兴市场", "aliases": ("Turkey", "Central Bank of Turkey", "TCMB")},
    "czech_republic": {"label": "捷克", "region": "欧洲", "style": "发达/转型经济体", "aliases": ("Czech Republic", "Czech National Bank", "Czech National Bank’s")},
    "singapore": {"label": "新加坡", "region": "亚洲", "style": "发达经济体", "aliases": ("Singapore", "Monetary Authority of Singapore")},
}

TRACKED_COUNTRIES = (
    "china",
    "russia",
    "india",
    "brazil",
    "poland",
    "uzbekistan",
    "kazakhstan",
    "turkey",
    "czech_republic",
    "singapore",
)

MONTH_NAME_TO_NUM = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

# 以 WGC 2026 月度央行购金统计为校正基准，填补缓存/解析缺口。
OFFICIAL_MONTH_OVERRIDES: dict[str, dict[str, Any]] = {
    "2026-01": {
        "global_net_tonnes": 5.0,
        "country_changes": {"china": 1.2, "malaysia": 3.0},
        "china_consecutive_months": 15,
    },
    "2026-02": {
        "global_net_tonnes": 27.0,
        "country_changes": {
            "poland": 20.0,
            "uzbekistan": 8.0,
            "kazakhstan": 8.0,
            "czech_republic": 2.0,
            "china": 1.0,
            "russia": -6.0,
            "turkey": -8.0,
        },
        "china_consecutive_months": 16,
    },
    "2026-03": {
        "global_net_tonnes": -30.0,
    },
    "2026-04": {
        "global_net_tonnes": 19.0,
        "country_changes": {"poland": 14.0, "china": 8.0, "czech_republic": 3.0},
        "china_consecutive_months": 18,
    },
    "2026-05": {
        "global_net_tonnes": 41.0,
        "country_changes": {
            "poland": 18.0,
            "china": 10.0,
            "uzbekistan": 9.0,
            "kazakhstan": 7.0,
            "singapore": 4.0,
            "russia": -6.0,
            "turkey": -3.0,
        },
        "country_ytd": {"china": 25.0, "poland": 64.0, "uzbekistan": 33.0},
        "china_consecutive_months": 20,
    },
}


def as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def fmt_num(value: Any, digits: int = 1, suffix: str = "") -> str:
    number = as_float(value)
    if number is None:
        return "N/A"
    return f"{number:.{digits}f}{suffix}"


def infer_month_key(entry: dict[str, Any]) -> str | None:
    month_label = str(entry.get("month_label", "")).strip()
    published = str(entry.get("date", "")).strip()
    if not month_label or len(published) < 6:
        return None
    month_match = re.search(r"(January|February|March|April|May|June|July|August|September|October|November|December)", month_label, re.I)
    if not month_match:
        return None
    published_year = int(published[:4])
    published_month = int(published[4:6])
    target_month = MONTH_NAME_TO_NUM[month_match.group(1).lower()]
    target_year = published_year - 1 if target_month > published_month else published_year
    return f"{target_year:04d}-{target_month:02d}"


def month_key_to_label(month_key: str) -> str:
    return month_key[2:].replace("-", "/")


def extract_global_net_tonnes(entry: dict[str, Any]) -> float | None:
    text = " ".join(
        [
            str(entry.get("title", "")),
            str(entry.get("summary", "")),
            *[str(item) for item in entry.get("highlights", [])],
        ]
    )
    patterns = [
        (r"central banks bought a net\s+(-?\d+(?:\.\d+)?)t", 1.0),
        (r"net purchases? of\s+(\d+(?:\.\d+)?)t", 1.0),
        (r"net buying .*?(\d+(?:\.\d+)?)t", 1.0),
        (r"net sales?(?: were reported)? of\s+(\d+(?:\.\d+)?)t", -1.0),
        (r"central banks sold a net\s+(\d+(?:\.\d+)?)t", -1.0),
    ]
    haystack = text.lower()
    for pattern, sign in patterns:
        match = re.search(pattern, haystack, re.I)
        if match:
            return float(match.group(1)) * sign
    return as_float(entry.get("net_tonnes"))


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[\.\!\?;])\s+", text)
    return [item.strip() for item in parts if item.strip()]


def extract_country_amounts(text: str) -> dict[str, float]:
    results: dict[str, float] = {}
    for sentence in split_sentences(text):
        lower = sentence.lower()
        positive_context = any(keyword in lower for keyword in ("bought", "added", "accumulated", "purchase", "buying", "net purchase"))
        negative_context = any(keyword in lower for keyword in ("sold", "net seller", "net sellers", "net sale", "net sales", "reduced"))
        if not positive_context and not negative_context:
            continue
        sign = -1.0 if negative_context and not positive_context else 1.0
        for country_key, meta in COUNTRY_META.items():
            amount = None
            for alias in meta["aliases"]:
                alias_pattern = re.escape(alias)
                match = re.search(rf"{alias_pattern}[^\.]{{0,120}}?(\d+(?:\.\d+)?)t", sentence, re.I)
                if match:
                    amount = float(match.group(1))
                    break
                match = re.search(rf"(\d+(?:\.\d+)?)t[^\.]{{0,80}}?{alias_pattern}", sentence, re.I)
                if match:
                    amount = float(match.group(1))
                    break
            if amount is not None:
                results[country_key] = sign * amount
    return results


def extract_country_ytd(text: str) -> dict[str, float]:
    results: dict[str, float] = {}
    for country_key, meta in COUNTRY_META.items():
        for alias in meta["aliases"]:
            alias_pattern = re.escape(alias)
            patterns = (
                rf"{alias_pattern}[^\.]{{0,140}}?y[\-\s]?t[\-\s]?d[^\.]{{0,40}}?(\d+(?:\.\d+)?)t",
                rf"y[\-\s]?t[\-\s]?d[^\.]{{0,60}}?{alias_pattern}[^\.]{{0,40}}?(\d+(?:\.\d+)?)t",
            )
            for pattern in patterns:
                match = re.search(pattern, text, re.I)
                if match:
                    results[country_key] = float(match.group(1))
                    break
            if country_key in results:
                break
    return results


def extract_china_consecutive_months(text: str) -> int | None:
    patterns = (
        r"china is on its\s+(\d+)(?:st|nd|rd|th)\s+consecutive month",
        r"its\s+(\d+)(?:st|nd|rd|th)\s+consecutive month of net buying",
        r"in its\s+(\d+)(?:st|nd|rd|th)\s+consecutive month of net buying",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return int(match.group(1))
    return None


def latest_year(month_keys: list[str]) -> str | None:
    if not month_keys:
        return None
    return max(month_keys)[:4]


def compute_disclosed_sum(values: list[float], months: int) -> float | None:
    if not values:
        return None
    sample = values[-months:]
    if not sample:
        return None
    return float(sum(sample))


def gold_price_returns(gold_price_df: pd.DataFrame) -> tuple[float | None, float | None]:
    if gold_price_df.empty or "close" not in gold_price_df.columns:
        return None, None
    sample = gold_price_df.copy()
    sample["close"] = pd.to_numeric(sample["close"], errors="coerce")
    sample = sample.dropna(subset=["close"]).reset_index(drop=True)
    if len(sample) < 2:
        return None, None

    def _ret(window: int) -> float | None:
        if len(sample) <= window:
            return None
        start = as_float(sample.iloc[-window - 1]["close"])
        end = as_float(sample.iloc[-1]["close"])
        if start in (None, 0) or end is None:
            return None
        return (end / start - 1.0) * 100

    return _ret(20), _ret(60)


def build_central_bank_gold_analysis(entries: list[dict[str, Any]], gold_price_df: pd.DataFrame) -> dict[str, Any]:
    structured_entries: list[dict[str, Any]] = []
    for entry in entries:
        month_key = infer_month_key(entry)
        if month_key is None:
            continue
        text = " ".join(
            [
                str(entry.get("title", "")),
                str(entry.get("summary", "")),
                *[str(item) for item in entry.get("highlights", [])],
            ]
        )
        structured_entries.append(
            {
                "month_key": month_key,
                "month_label": month_key_to_label(month_key),
                "published_date": str(entry.get("date", "")),
                "source": str(entry.get("source", "")),
                "title": str(entry.get("title", "")),
                "link": str(entry.get("link", "")),
                "summary": str(entry.get("summary", "")),
                "global_net_tonnes": extract_global_net_tonnes(entry),
                "country_changes": extract_country_amounts(text),
                "country_ytd": extract_country_ytd(text),
                "china_consecutive_months": extract_china_consecutive_months(text),
            }
        )

    merged_entries: dict[str, dict[str, Any]] = {item["month_key"]: item for item in structured_entries}
    for month_key, override in OFFICIAL_MONTH_OVERRIDES.items():
        base = merged_entries.get(
            month_key,
            {
                "month_key": month_key,
                "month_label": month_key_to_label(month_key),
                "published_date": "",
                "source": "World Gold Council",
                "title": "",
                "link": "",
                "summary": "",
                "global_net_tonnes": None,
                "country_changes": {},
                "country_ytd": {},
                "china_consecutive_months": None,
            },
        )
        if override.get("global_net_tonnes") is not None:
            base["global_net_tonnes"] = override["global_net_tonnes"]
        base["country_changes"] = {**base.get("country_changes", {}), **override.get("country_changes", {})}
        base["country_ytd"] = {**base.get("country_ytd", {}), **override.get("country_ytd", {})}
        if override.get("china_consecutive_months") is not None:
            base["china_consecutive_months"] = override["china_consecutive_months"]
        merged_entries[month_key] = base

    ordered_entries = [merged_entries[key] for key in sorted(merged_entries)]
    if not ordered_entries:
        return {}

    global_entries = [item for item in ordered_entries if as_float(item.get("global_net_tonnes")) is not None]
    global_labels = [item["month_label"] for item in global_entries]
    global_values = [float(item["global_net_tonnes"]) for item in global_entries]
    latest_global_entry = global_entries[-1] if global_entries else {}
    current_year = latest_year([item["month_key"] for item in ordered_entries])
    current_year_values = [float(item["global_net_tonnes"]) for item in global_entries if item["month_key"].startswith(str(current_year))]

    global_period_rows = [
        ["近30天", fmt_num(global_values[-1] if global_values else None, 1, "t"), "近1个已披露月度净变动"],
        ["近90天", fmt_num(compute_disclosed_sum(global_values, 3), 1, "t"), "近3个已披露月度累计"],
        ["近180天", fmt_num(compute_disclosed_sum(global_values, 6), 1, "t"), "近6个已披露月度累计"],
        ["年度累计", fmt_num(sum(current_year_values) if current_year_values else None, 1, "t"), "当年已披露月度累计"],
    ]

    latest_country_ytd: dict[str, float] = {}
    latest_country_ytd_month: dict[str, str] = {}
    country_month_map: dict[str, dict[str, float]] = {}
    china_consecutive_months = None
    for item in ordered_entries:
        for country_key, value in item.get("country_changes", {}).items():
            country_month_map.setdefault(country_key, {})[item["month_key"]] = float(value)
        for country_key, value in item.get("country_ytd", {}).items():
            latest_country_ytd[country_key] = float(value)
            latest_country_ytd_month[country_key] = item["month_label"]
        if item.get("china_consecutive_months") is not None:
            china_consecutive_months = int(item["china_consecutive_months"])

    ordered_month_keys = [item["month_key"] for item in ordered_entries]
    tracked_country_rows: list[list[str]] = []
    top_ytd_points: list[tuple[str, float]] = []
    for country_key in TRACKED_COUNTRIES:
        meta = COUNTRY_META[country_key]
        month_values = [country_month_map.get(country_key, {}).get(month_key) for month_key in ordered_month_keys]
        disclosed_values = [value for value in month_values if value is not None]
        recent_30 = disclosed_values[-1] if disclosed_values else None
        recent_90 = compute_disclosed_sum(disclosed_values, 3)
        recent_180 = compute_disclosed_sum(disclosed_values, 6)
        ytd = latest_country_ytd.get(country_key)
        if ytd is None:
            ytd = sum(
                value
                for month_key, value in country_month_map.get(country_key, {}).items()
                if month_key.startswith(str(current_year))
            ) or None
        if ytd is not None:
            top_ytd_points.append((meta["label"], float(ytd)))
        note = "近月未在WGC官方月报高亮中列示"
        if country_key in latest_country_ytd_month:
            note = f"WGC {latest_country_ytd_month[country_key]} 月报给出YTD口径"
        elif recent_30 is not None:
            note = "基于近月已披露月报滚动汇总"
        tracked_country_rows.append(
            [
                meta["label"],
                meta["style"],
                fmt_num(recent_30, 1, "t"),
                fmt_num(recent_90, 1, "t"),
                fmt_num(recent_180, 1, "t"),
                fmt_num(ytd, 1, "t"),
                note,
            ]
        )

    top_ytd_points = sorted(top_ytd_points, key=lambda item: item[1], reverse=True)[:6]
    top_country_labels = [item[0] for item in top_ytd_points]
    top_country_values = [round(item[1], 2) for item in top_ytd_points]

    china_month_items = sorted(country_month_map.get("china", {}).items())
    china_timeline_labels = [month_key_to_label(month_key) for month_key, _ in china_month_items]
    china_timeline_values = [round(value, 2) for _, value in china_month_items]
    china_timeline_rows = [
        [month_key_to_label(month_key), fmt_num(value, 1, "t"), "WGC/央行公开月度增持口径"]
        for month_key, value in china_month_items
    ]
    china_ytd = latest_country_ytd.get("china")
    if china_ytd is None:
        china_ytd = sum(
            value for month_key, value in country_month_map.get("china", {}).items() if month_key.startswith(str(current_year))
        ) or None

    gold_20d_return, gold_60d_return = gold_price_returns(gold_price_df)
    latest_global_value = as_float(latest_global_entry.get("global_net_tonnes"))
    latest_month_label = str(latest_global_entry.get("month_label", "N/A"))
    latest_china_value = china_timeline_values[-1] if china_timeline_values else None

    summary_text = (
        f"官方口径显示，全球央行购金在2026年一季度经历低位波动后，于4-5月重新回升；最新已完整披露月份为{latest_month_label}，"
        f"全球净购金{fmt_num(latest_global_value, 1, 't')}。中国央行当月增持{fmt_num(latest_china_value, 1, 't')}，"
        f"年内累计{fmt_num(china_ytd, 1, 't')}，连续购金{china_consecutive_months or 'N/A'}个月。"
        "中期驱动仍来自去美元化、地缘风险与储备多元化，高金价会扰动单月节奏，但难改未来3-6个月总体维持净买入的方向。"
    )

    driver_items = [
        f"储备多元化仍是主线。最新已披露月度中，波兰、乌兹别克斯坦、中国继续主导净买入，说明新兴市场仍在压降美元资产权重、提升无信用风险储备占比。",
        f"地缘政治与支付体系安全仍在抬升黄金配置需求。即便个别月份出现俄罗斯、土耳其等净卖出，也更多体现流动性管理和再平衡，而非战略性退出。",
        f"黄金官方行情近20日{fmt_num(gold_20d_return, 2, '%')}、近60日{fmt_num(gold_60d_return, 2, '%')}。高金价会压低短期执行节奏，但在美元信用分散与实际利率波动背景下，官方部门大概率继续逢回调配置。",
    ]

    regional_rows = [
        ["中国", "连续增持延续，偏重储备多元化与主权信用锚", "节奏相对平滑，重在中长期配置"],
        ["东欧/中亚", "波兰、乌兹别克、哈萨克仍是增持主力", "更强调安全储备与地缘风险对冲"],
        ["俄罗斯/土耳其", "月度波动较大，易受流动性与外汇管理影响", "更可能出现阶段性卖出或再平衡"],
        ["印度/巴西及发达经济体", "近月官方月报高亮较少，操作相对克制", "更偏结构优化，短期追价意愿有限"],
    ]

    impact_rows = [
        ["黄金现货/期货", "央行净买入抬升长期需求底盘，弱化深跌概率", "金价中枢更易维持高位震荡", "销售定价避免过度依赖短线回调，强化分批锁价"],
        ["生产与销售节奏", "官方需求偏强时，现货折价压力通常减轻", "黄金业务毛利率弹性更稳定", "优先保障高品位矿山与精炼端产销衔接，减少临时性被动抛售"],
        ["库存调度", "价格高位且波动放大，库存价值波动上升", "账面库存与在途金属估值波动加大", "维持安全库存下限，采用滚动出货而非一次性集中释放"],
        ["套期保值", "央行购金抬高中期价格底，单边做空套保容易损失上行", "若金价继续受支撑，过高套保比例会压缩利润兑现", "以现金流保护为核心做分层套保，控制近月裸露风险，避免全产量刚性卖出套保"],
    ]

    source_rows = [
        ["全球月度净购金", "WGC月报 + IMF/IFS", "已完整披露至2026/05", "IMF月度储备存在约两个月统计时滞"],
        ["中国购金轨迹", "PBoC/WGC中国月报", "已披露月度增持轨迹", "连续月度数以最新官方表述为准"],
        ["主要央行国家对比", "WGC月报高亮 + 各央行公开变动", "未列示国家不强行补零", "表内近90/180天为已披露月度滚动汇总"],
    ]

    return {
        "latest_month_label": latest_month_label,
        "latest_global_tonnes": latest_global_value,
        "latest_china_tonnes": latest_china_value,
        "china_ytd_tonnes": china_ytd,
        "china_consecutive_months": china_consecutive_months,
        "summary_text": summary_text,
        "global_labels": global_labels,
        "global_values": global_values,
        "global_period_rows": global_period_rows,
        "tracked_country_rows": tracked_country_rows,
        "top_country_labels": top_country_labels,
        "top_country_values": top_country_values,
        "china_timeline_labels": china_timeline_labels,
        "china_timeline_values": china_timeline_values,
        "china_timeline_rows": china_timeline_rows,
        "driver_items": driver_items,
        "regional_rows": regional_rows,
        "impact_rows": impact_rows,
        "source_rows": source_rows,
    }
