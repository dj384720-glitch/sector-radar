#!/usr/bin/env python3
"""Build Daily Economic News links and Nasdaq-related off-exchange fund purchase limits."""
from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlencode
import datetime as dt
import json
import re
import ssl
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "docs" / "data"
NEWS_PATH = DATA / "daily_news.json"
LIMITS_PATH = DATA / "nasdaq_limits.json"
TZ = dt.timezone(dt.timedelta(hours=8))
UA_DESKTOP = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/130 Safari/537.36"
UA_MOBILE = "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/130 Mobile Safari/537.36"
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE


def now_iso() -> str:
    return dt.datetime.now(TZ).isoformat(timespec="seconds")


def http_get(url: str, *, ua: str = UA_DESKTOP, referer: str | None = None, timeout: int = 20, retries: int = 2) -> str | None:
    headers = {"User-Agent": ua, "Accept-Language": "zh-CN,zh;q=0.9"}
    if referer:
        headers["Referer"] = referer
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as resp:
                return resp.read().decode("utf-8", "ignore")
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            if attempt < retries:
                time.sleep(0.6 * (attempt + 1))
    return None


class ArticleLinkParser(HTMLParser):
    def __init__(self, base: str):
        super().__init__(convert_charrefs=True)
        self.base = base
        self.depth = 0
        self.href = None
        self.buf: list[str] = []
        self.items: list[dict] = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            href = dict(attrs).get("href")
            if href and "/articles/" in href:
                self.href = urljoin(self.base, href)
                self.buf = []
                self.depth = 1
                return
        if self.href:
            self.depth += 1

    def handle_data(self, data):
        if self.href:
            self.buf.append(data)

    def handle_endtag(self, tag):
        if not self.href:
            return
        self.depth -= 1
        if self.depth <= 0:
            title = re.sub(r"\s+", " ", "".join(self.buf)).strip()
            if len(title) >= 8:
                m = re.search(r"/articles/(\d{4}-\d{2}-\d{2})/", self.href)
                self.items.append({"title": title, "url": self.href, "date": m.group(1) if m else ""})
            self.href = None
            self.buf = []
            self.depth = 0


def parse_nbd_links(url: str) -> list[dict]:
    text = http_get(url)
    if not text:
        return []
    p = ArticleLinkParser(url)
    try:
        p.feed(text)
    except Exception:
        return []
    out, seen = [], set()
    for item in p.items:
        key = item["url"]
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


NEWS_CONFIG = {
    "科技": {
        "sources": ["https://www.nbd.com.cn/technology/", "https://www.nbd.com.cn/columns/2409/"],
        "pattern": None,
    },
    "医药": {
        "sources": ["https://www.nbd.com.cn/columns/2093.html/", "https://m.nbd.com.cn/web_app/column/2093/"],
        "pattern": re.compile(r"医药|医疗|药|生物|创新疗法|临床|医院|器械"),
    },
    "机器人": {
        "sources": ["https://www.nbd.com.cn/technology/", "https://www.nbd.com.cn/columns/2409/"],
        "pattern": re.compile(r"机器人|具身智能|四足|机械臂|人形机器人|智能体"),
    },
    "煤炭": {
        "sources": ["https://www.nbd.com.cn/", "https://money.nbd.com.cn/columns/432.html/", "https://m.nbd.com.cn/web_app/column/317/"],
        "pattern": re.compile(r"煤炭|煤矿|煤价|原煤|焦煤|动力煤"),
    },
}


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def build_news() -> None:
    old = load_json(NEWS_PATH, {})
    categories = {}
    fetched_any = False
    cache: dict[str, list[dict]] = {}
    for name, cfg in NEWS_CONFIG.items():
        merged = []
        for url in cfg["sources"]:
            if url not in cache:
                cache[url] = parse_nbd_links(url)
            merged.extend(cache[url])
        pattern = cfg["pattern"]
        if pattern:
            merged = [x for x in merged if pattern.search(x.get("title", ""))]
        seen, items = set(), []
        for item in merged:
            if item["url"] in seen:
                continue
            seen.add(item["url"])
            items.append(item)
        items.sort(key=lambda x: x.get("date", ""), reverse=True)
        items = items[:12]
        if items:
            fetched_any = True
            categories[name] = items
        else:
            categories[name] = (old.get("categories") or {}).get(name, [])
    if not fetched_any and old:
        print("[warn] NBD news fetch failed; keeping previous snapshot")
        return
    payload = {
        "updated_at": now_iso(),
        "source": "每日经济新闻 / nbd.com.cn",
        "fallback": False,
        "categories": categories,
    }
    write_json(NEWS_PATH, payload)
    print("[done] Daily Economic News snapshot: " + ", ".join(f"{k}={len(v)}" for k, v in categories.items()))


FUND_ROWS_RE = re.compile(r"=\s*(\[.*\]);?\s*$", re.S)
USD_RE = re.compile(r"美元|美汇|美钞|现汇|现钞")
NASDAQ_RE = re.compile(r"纳斯达克|纳指")
ON_EXCHANGE_PREFIX = ("15", "51", "52", "56", "58")
SHARE_RE = re.compile(r"([ACDEFI])(?:类|份额)?(?:\(?(?:人民币)\)?)?$", re.I)


def parse_number(value):
    if value is None:
        return None
    text = str(value).replace(",", "").strip()
    if not text or text in {"--", "-"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def fund_pool() -> list[dict]:
    body = http_get("https://fund.eastmoney.com/js/fundcode_search.js", referer="https://fund.eastmoney.com/")
    if not body:
        return []
    m = FUND_ROWS_RE.search(body)
    if not m:
        return []
    try:
        rows = json.loads(m.group(1))
    except Exception:
        return []
    out = []
    for row in rows:
        if len(row) < 3:
            continue
        code, name = str(row[0]), str(row[2])
        if not NASDAQ_RE.search(name):
            continue
        if code.startswith(ON_EXCHANGE_PREFIX):
            continue
        if USD_RE.search(name):
            continue
        mclass = SHARE_RE.search(name.replace("（", "(").replace("）", ")"))
        out.append({"code": code, "name": name, "share_class": mclass.group(1).upper() if mclass else "-"})
    return out


def fund_rate_info(code: str) -> dict | None:
    params = urlencode({"FCODE": code, "deviceid": "sector-radar", "plat": "Android", "product": "EFund", "version": "6.5.5"})
    url = "https://fundmobapi.eastmoney.com/FundMApi/FundRateInfo.ashx?" + params
    body = http_get(url, ua=UA_MOBILE, referer=f"https://fund.eastmoney.com/{code}.html", timeout=18, retries=1)
    if not body:
        return None
    try:
        data = json.loads(body)
    except Exception:
        return None
    raw = data.get("Datas")
    return raw if isinstance(raw, dict) else None


def normalize_status(raw: str, max_buy) -> str:
    text = (raw or "").strip()
    if "暂停" in text:
        return "暂停申购"
    if "限" in text and "额" in text:
        return "限大额"
    if max_buy is not None and max_buy > 0:
        return "限大额" if max_buy < 100_000_000 else (text or "开放申购")
    return text or "开放申购"


def build_limits() -> None:
    old = load_json(LIMITS_PATH, {})
    old_map = {str(x.get("code")): x for x in old.get("funds", []) if x.get("code")}
    pool = fund_pool()
    if not pool:
        print("[warn] Eastmoney fund universe unavailable; keeping previous Nasdaq limits snapshot")
        return
    records, fresh_count = [], 0
    for i, entry in enumerate(pool, 1):
        raw = fund_rate_info(entry["code"])
        if raw:
            max_buy = parse_number(raw.get("MAXSG"))
            status = normalize_status(str(raw.get("SGZT") or ""), max_buy)
            if status == "暂停申购":
                max_buy = None
            rec = {
                **entry,
                "status": status,
                "max_buy": max_buy,
                "min_buy": parse_number(raw.get("MINSG")),
                "min_dca": parse_number(raw.get("MINDT")),
                "redemption_status": str(raw.get("SHZT") or ""),
                "source": "天天基金公开接口",
                "source_url": f"https://fund.eastmoney.com/{entry['code']}.html",
                "stale": False,
            }
            fresh_count += 1
        elif entry["code"] in old_map:
            rec = dict(old_map[entry["code"]])
            rec.update(entry)
            rec["stale"] = True
        else:
            rec = {**entry, "status": "数据暂缺", "max_buy": None, "min_buy": None, "min_dca": None,
                   "redemption_status": "", "source": "天天基金公开接口", "source_url": f"https://fund.eastmoney.com/{entry['code']}.html", "stale": True}
        records.append(rec)
        if i % 10 == 0:
            print(f"  Nasdaq limits {i}/{len(pool)}")
        time.sleep(0.06)
    if fresh_count < max(3, int(len(pool) * 0.5)) and old:
        print(f"[warn] Nasdaq limit fresh coverage too low ({fresh_count}/{len(pool)}); keeping previous snapshot")
        return
    order = {"开放申购": 0, "限大额": 1, "暂停申购": 2, "数据暂缺": 3}
    records.sort(key=lambda x: (order.get(x.get("status"), 1), -(x.get("max_buy") or -1), x.get("code", "")))
    payload = {
        "updated_at": now_iso(),
        "source": "天天基金 / 东方财富公开基金接口",
        "scope": "名称包含“纳斯达克”或“纳指”的人民币场外基金份额；排除纯场内ETF和美元份额",
        "count": len(records),
        "fresh_count": fresh_count,
        "fallback": False,
        "funds": records,
    }
    write_json(LIMITS_PATH, payload)
    paused = sum(x.get("status") == "暂停申购" for x in records)
    limited = sum(x.get("status") == "限大额" for x in records)
    print(f"[done] Nasdaq fund limits: total={len(records)} fresh={fresh_count} limited={limited} paused={paused}")


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    build_news()
    build_limits()


if __name__ == "__main__":
    main()
