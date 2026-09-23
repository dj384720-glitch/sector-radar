#!/usr/bin/env python3
"""Build a categorized daily economic-news feed from public RSS endpoints.

Only headline/source/time/link metadata is stored. Full article text is never copied.
The build is fail-open: if all providers are unavailable, the previous JSON is kept.
"""
from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "data" / "daily_news.json"
MAX_PER_CATEGORY = 10

CATEGORIES = {
    "科技": "科技 产业 财经",
    "医药": "医药 生物医药 产业 财经",
    "机器人": "机器人 人形机器人 产业 财经",
    "煤炭": "煤炭 能源 产业 财经",
    "新能源": "新能源 光伏 储能 产业 财经",
    "消费": "消费 食品饮料 零售 财经",
    "金融": "金融 银行 证券 基金 财经",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (SectorRadar/1.0; +https://github.com/dj384720-glitch/sector-radar)",
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
}


def http_get(url: str, timeout: int = 10) -> bytes:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def iso_time(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        return ""
    try:
        dt = parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except Exception:
        return raw[:80]


def clean_text(s: str) -> str:
    s = unescape(re.sub(r"<[^>]+>", " ", s or ""))
    return re.sub(r"\s+", " ", s).strip()


def parse_rss(raw: bytes, category: str) -> list[dict[str, str]]:
    root = ET.fromstring(raw)
    rows: list[dict[str, str]] = []
    for item in root.findall(".//item"):
        title = clean_text(item.findtext("title") or "")
        link = clean_text(item.findtext("link") or "")
        published = iso_time(item.findtext("pubDate") or "")
        source_el = item.find("source")
        source = clean_text(source_el.text if source_el is not None and source_el.text else "")
        if not source and " - " in title:
            maybe_title, maybe_source = title.rsplit(" - ", 1)
            if 1 <= len(maybe_source) <= 24:
                title, source = maybe_title.strip(), maybe_source.strip()
        if not title or not link.startswith(("http://", "https://")):
            continue
        rows.append({
            "category": category,
            "title": title[:180],
            "source": source[:50] or "公开财经媒体",
            "published_at": published,
            "url": link,
        })
    return rows


def provider_urls(query: str) -> list[str]:
    q = urllib.parse.quote_plus(query)
    return [
        f"https://www.bing.com/news/search?q={q}&format=rss&mkt=zh-CN",
        f"https://news.google.com/rss/search?q={q}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans",
    ]


def fetch_category(category: str, query: str) -> list[dict[str, str]]:
    combined: list[dict[str, str]] = []
    for url in provider_urls(query):
        try:
            rows = parse_rss(http_get(url), category)
            combined.extend(rows)
            if len(combined) >= MAX_PER_CATEGORY:
                break
        except Exception as exc:
            print(f"[news-warn] {category}: {type(exc).__name__}: {str(exc)[:120]}")
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for row in sorted(combined, key=lambda x: x.get("published_at") or "", reverse=True):
        key = re.sub(r"\W+", "", row["title"]).lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(row)
        if len(out) >= MAX_PER_CATEGORY:
            break
    return out


def main() -> None:
    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "source_note": "公开财经新闻RSS聚合；仅展示标题、来源、时间与原文链接。",
        "categories": {},
    }
    total = 0
    for category, query in CATEGORIES.items():
        rows = fetch_category(category, query)
        payload["categories"][category] = rows
        total += len(rows)
        print(f"[news] {category}: {len(rows)}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    if total == 0 and OUT.exists():
        print("[news-warn] all providers unavailable; keeping previous daily_news.json")
        return
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[done] daily economic news updated: {total} headlines")


if __name__ == "__main__":
    main()
