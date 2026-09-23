#!/usr/bin/env python3
"""Build a categorized Daily Economic News (nbd.com.cn) feed.

Only title/date/link metadata is stored. Full article text is never copied.
The build is fail-open: if NBD is temporarily unavailable, keep the previous JSON.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin
import json
import re
import ssl
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "data" / "daily_news.json"
TZ = timezone(timedelta(hours=8))
MAX_PER_CATEGORY = 12
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/130 Safari/537.36"
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE


class ArticleParser(HTMLParser):
    def __init__(self, base_url: str):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.href: str | None = None
        self.depth = 0
        self.parts: list[str] = []
        self.rows: list[dict[str, str]] = []

    def handle_starttag(self, tag, attrs):
        if self.href is not None:
            if tag not in {"br", "img", "meta", "link", "input", "source", "hr"}:
                self.depth += 1
            return
        if tag != "a":
            return
        href = dict(attrs).get("href")
        if not href:
            return
        full = urljoin(self.base_url, href)
        if "/articles/" not in full or "nbd.com.cn" not in full:
            return
        self.href = full
        self.depth = 1
        self.parts = []

    def handle_data(self, data):
        if self.href is not None:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if self.href is None:
            return
        if tag not in {"br", "img", "meta", "link", "input", "source", "hr"}:
            self.depth -= 1
        if self.depth > 0:
            return
        title = re.sub(r"\s+", " ", unescape("".join(self.parts))).strip()
        href = self.href
        self.href = None
        self.parts = []
        self.depth = 0
        if len(title) < 8:
            return
        m = re.search(r"/articles/(\d{4}-\d{2}-\d{2})/", href)
        self.rows.append({"title": title[:180], "url": href, "date": m.group(1) if m else ""})


def http_get(url: str, timeout: int = 15, retries: int = 2) -> str | None:
    headers = {"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9", "Referer": "https://www.nbd.com.cn/"}
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as resp:
                return resp.read().decode("utf-8", "ignore")
        except (urllib.error.URLError, OSError, TimeoutError, ValueError):
            if attempt < retries:
                time.sleep(0.5 * (attempt + 1))
    return None


def article_links(url: str) -> list[dict[str, str]]:
    body = http_get(url)
    if not body:
        return []
    parser = ArticleParser(url)
    try:
        parser.feed(body)
    except Exception:
        return []
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for row in parser.rows:
        if row["url"] in seen:
            continue
        seen.add(row["url"])
        out.append(row)
    return out


CATEGORIES = {
    "科技": {
        "sources": ["https://www.nbd.com.cn/technology/", "https://www.nbd.com.cn/columns/2409/"],
        "pattern": None,
    },
    "医药": {
        "sources": ["https://www.nbd.com.cn/columns/2093.html/", "https://m.nbd.com.cn/web_app/column/2093/", "https://www.nbd.com.cn/"],
        "pattern": re.compile(r"医药|医疗|药品|药企|创新药|生物医药|临床|医院|医疗器械|疫苗|CXO", re.I),
    },
    "机器人": {
        "sources": ["https://www.nbd.com.cn/technology/", "https://www.nbd.com.cn/columns/2409/"],
        "pattern": re.compile(r"机器人|具身智能|四足|机械臂|人形机器人|机器狗", re.I),
    },
    "煤炭": {
        "sources": ["https://www.nbd.com.cn/", "https://money.nbd.com.cn/columns/432.html/", "https://m.nbd.com.cn/web_app/column/317/"],
        "pattern": re.compile(r"煤炭|煤矿|煤价|原煤|焦煤|焦炭|动力煤", re.I),
    },
}


def load_previous() -> dict:
    try:
        return json.loads(OUT.read_text(encoding="utf-8"))
    except Exception:
        return {}


def main() -> None:
    previous = load_previous()
    cache: dict[str, list[dict[str, str]]] = {}
    categories: dict[str, list[dict[str, str]]] = {}
    fresh_categories = 0

    for category, cfg in CATEGORIES.items():
        merged: list[dict[str, str]] = []
        for url in cfg["sources"]:
            if url not in cache:
                cache[url] = article_links(url)
            merged.extend(cache[url])
        pattern = cfg["pattern"]
        if pattern is not None:
            merged = [row for row in merged if pattern.search(row.get("title", ""))]
        seen: set[str] = set()
        rows: list[dict[str, str]] = []
        for row in sorted(merged, key=lambda x: x.get("date", ""), reverse=True):
            if row["url"] in seen:
                continue
            seen.add(row["url"])
            rows.append({
                "category": category,
                "title": row["title"],
                "url": row["url"],
                "date": row.get("date", ""),
                "published_at": (row.get("date", "") + "T00:00:00+08:00") if row.get("date") else "",
                "source": "每日经济新闻",
            })
            if len(rows) >= MAX_PER_CATEGORY:
                break
        if rows:
            fresh_categories += 1
            categories[category] = rows
        else:
            old_rows = (previous.get("categories") or {}).get(category, [])
            categories[category] = old_rows if isinstance(old_rows, list) else []
        print(f"[news] {category}: {len(categories[category])}")

    if fresh_categories == 0 and previous:
        print("[news-warn] nbd.com.cn unavailable; keeping previous daily_news.json")
        return

    payload = {
        "updated_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "source": "每日经济新闻 / nbd.com.cn",
        "source_note": "仅聚合《每日经济新闻》公开页面的标题、日期和原文链接，不复制正文。",
        "categories": categories,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("[done] Daily Economic News snapshot: " + ", ".join(f"{k}={len(v)}" for k, v in categories.items()))


if __name__ == "__main__":
    main()
