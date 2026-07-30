from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from hashlib import sha1
from pathlib import Path
from typing import Any


CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
WHITESPACE_RE = re.compile(r"\s+")
LATIN_RE = re.compile(r"[A-Za-z]")
CHINESE_RE = re.compile(r"[\u4e00-\u9fff]")


DEFAULT_GLOSSARY = {
    "Federal Reserve": "美联储",
    "FOMC": "联邦公开市场委员会",
    "Bank of Japan": "日本央行",
    "Bank of England": "英国央行",
    "rate cut": "降息",
    "rate hike": "加息",
    "gold reserves": "黄金储备",
    "central bank": "央行",
    "Treasury yields": "美国国债收益率",
    "US dollar": "美元",
    "dollar index": "美元指数",
}


@dataclass
class TranslationConfig:
    enabled: bool
    api_base_url: str
    api_key: str
    model: str
    timeout_seconds: int = 30
    max_retries: int = 3
    glossary: dict[str, str] | None = None

    @property
    def glossary_map(self) -> dict[str, str]:
        return self.glossary or DEFAULT_GLOSSARY


def load_json_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def save_json_records(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")


def normalize_text(text: str) -> str:
    sample = CONTROL_CHAR_RE.sub(" ", text or "")
    sample = sample.replace("\ufeff", " ").replace("�", " ")
    sample = sample.replace("\u00a0", " ")
    sample = WHITESPACE_RE.sub(" ", sample)
    return sample.strip()


def mostly_chinese(text: str) -> bool:
    sample = normalize_text(text)
    if not sample:
        return True
    chinese_count = len(CHINESE_RE.findall(sample))
    latin_count = len(LATIN_RE.findall(sample))
    return chinese_count >= latin_count


def build_record_key(item: dict[str, Any]) -> str:
    seed = "||".join(
        [
            str(item.get("source", "")),
            str(item.get("institution", "")),
            str(item.get("date", "")),
            str(item.get("title_original") or item.get("title") or ""),
            str(item.get("summary_original") or item.get("summary") or ""),
        ]
    )
    return sha1(seed.encode("utf-8")).hexdigest()


def apply_glossary(text: str, glossary: dict[str, str]) -> str:
    output = text
    for source_term, target_term in glossary.items():
        pattern = re.compile(re.escape(source_term), re.IGNORECASE)
        output = pattern.sub(target_term, output)
    return output


def collect_glossary_issues(original: str, translated: str, glossary: dict[str, str]) -> list[str]:
    issues: list[str] = []
    original_sample = original or ""
    translated_sample = translated or ""
    for source_term, target_term in glossary.items():
        if re.search(re.escape(source_term), original_sample, flags=re.IGNORECASE) and target_term not in translated_sample:
            issues.append(f"术语缺失：{source_term} -> {target_term}")
    return issues


class OpenAICompatibleTranslator:
    def __init__(self, config: TranslationConfig):
        self.config = config

    def translate(self, text: str) -> str:
        prompt = (
            "你是金融研究翻译助手。请将下面文本完整翻译为标准简体中文，"
            "保留数字、日期、机构名称和财经含义，不要省略，不要添加解释。\n\n"
            f"{text}"
        )
        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": "请输出标准简体中文译文。"},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
        }
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url=self.config.api_base_url.rstrip("/") + "/chat/completions",
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.config.api_key}",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
            data = json.loads(response.read().decode("utf-8"))
        choices = data.get("choices") or []
        if not choices:
            raise ValueError("翻译接口未返回 choices")
        message = choices[0].get("message") or {}
        content = str(message.get("content") or "").strip()
        if not content:
            raise ValueError("翻译接口返回空内容")
        return content


def translate_text(
    text: str,
    translator: OpenAICompatibleTranslator | None,
    config: TranslationConfig,
) -> tuple[str, str, int, list[str]]:
    cleaned = normalize_text(text)
    if not cleaned:
        return "", "empty", 0, []
    if mostly_chinese(cleaned):
        translated = apply_glossary(cleaned, config.glossary_map)
        return translated, "native", 0, collect_glossary_issues(cleaned, translated, config.glossary_map)
    if not config.enabled or translator is None:
        return cleaned, "skipped", 0, ["未配置翻译接口"]

    last_error = ""
    for attempt in range(1, config.max_retries + 1):
        try:
            translated = translator.translate(cleaned)
            translated = normalize_text(apply_glossary(translated, config.glossary_map))
            issues = collect_glossary_issues(cleaned, translated, config.glossary_map)
            return translated, "translated", attempt, issues
        except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            last_error = str(exc)
            if attempt < config.max_retries:
                time.sleep(0.5 * attempt)
    return cleaned, "failed", config.max_retries, [last_error or "翻译失败"]


def translate_entry_fields(
    item: dict[str, Any],
    config: TranslationConfig,
    translator: OpenAICompatibleTranslator | None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    out = dict(item)
    alerts: list[dict[str, Any]] = []
    for field in ("title", "summary"):
        original_value = normalize_text(str(out.get(field, "")))
        translated_value, status, attempts, issues = translate_text(original_value, translator, config)
        out[f"{field}_original"] = original_value
        out[f"{field}_zh"] = translated_value
        out[field] = translated_value
        out[f"{field}_translation_status"] = status
        out[f"{field}_translation_attempts"] = attempts
        out[f"{field}_translation_issues"] = issues
        if status == "failed":
            alerts.append(
                {
                    "record_key": build_record_key(out),
                    "field": field,
                    "title": out.get("title_original") or out.get("title"),
                    "source": out.get("source", ""),
                    "date": out.get("date", ""),
                    "error": "；".join(issues) or "翻译失败",
                }
            )
    out["translation_provider"] = "openai_compatible" if config.enabled else "disabled"
    out["translation_ready"] = all(str(out.get(f"{field}_translation_status", "")) in {"native", "translated"} for field in ("title", "summary"))
    return out, alerts


def translate_entries(
    entries: list[dict[str, Any]],
    config: TranslationConfig,
    mapping_path: Path,
    alert_path: Path | None = None,
) -> list[dict[str, Any]]:
    cache = {item.get("record_key"): item for item in load_json_records(mapping_path)}
    translator = OpenAICompatibleTranslator(config) if config.enabled else None
    merged: list[dict[str, Any]] = []
    alerts: list[dict[str, Any]] = []

    for item in entries:
        record = dict(item)
        record["record_key"] = build_record_key(record)
        cached = cache.get(record["record_key"])
        if cached and cached.get("translation_ready"):
            updated = dict(cached)
            updated.update({key: value for key, value in record.items() if value not in ("", None, [], {})})
            merged.append(updated)
            continue
        translated, item_alerts = translate_entry_fields(record, config, translator)
        merged.append(translated)
        alerts.extend(item_alerts)

    save_json_records(mapping_path, merged)
    if alert_path is not None and alerts:
        save_json_records(alert_path, alerts)
    return merged
