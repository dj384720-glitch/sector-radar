#!/usr/bin/env python3
"""Build the latest Nasdaq-related fund purchase-limit table.

The fund universe comes from Eastmoney's public fund-code directory. Matching
Nasdaq/Nasdaq-100 funds are then checked against each public F10 fee/trading
page for application status and daily purchase limits. The build is fail-open:
network failures keep the previous JSON whenever possible.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
import json
import re
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "data" / "nasdaq_fund_limits.json"
UNIVERSE_URL = "https://fund.eastmoney.com/js/fundcode_search.js"
DETAIL_URL = "https://fundf10.eastmoney.com/jjfl_{code}.html"
MAX_WORKERS = 10

HEADERS = {
    "User-Agent": "Mozilla/5.0 (SectorRadar/1.0; +https://github.com/dj384720-glitch/sector-radar)",
    "Accept": "text/html,application/xhtml+xml,application/javascript,*/*;q=0.8",
    "Referer": "https://fund.eastmoney.com/",
}


def http_get(url: str, timeout: int = 10, retries: int = 2) -> bytes:
    last = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except Exception as exc:
            last = exc
            if attempt < retries:
                time.sleep(0.35 * (attempt + 1))
    raise last or RuntimeError("request failed")


def decode_bytes(raw: bytes) -> str:
    for enc in ("utf-8", "gb18030"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            pass
    return raw.decode("utf-8", errors="ignore")


def plain_text(html: str) -> str:
    html = re.sub(r"(?is)<script\b.*?</script>", " ", html)
    html = re.sub(r"(?is)<style\b.*?</style>", " ", html)
    text = unescape(re.sub(r"(?s)<[^>]+>", " ", html))
    return re.sub(r"\s+", " ", text).strip()


def fetch_universe() -> list[dict[str, str]]:
    text = decode_bytes(http_get(UNIVERSE_URL, timeout=12, retries=2))
    start = text.find("[")
    end = text.rfind("]")
    if start < 0 or end <= start:
        raise RuntimeError("fund directory payload not found")
    rows = json.loads(text[start : end + 1])
    out: list[dict[str, str]] = []
    for row in rows:
        if not isinstance(row, list) or len(row) < 4:
            continue
        code, name, fund_type = str(row[0]), str(row[2]), str(row[3])
        upper = name.upper().replace(" ", "")
        if not re.fullmatch(r"\d{6}", code):
            continue
        if not ("纳斯达克" in name or "纳指" in name or "NASDAQ" in upper):
            continue
        out.append({"code": code, "name": name, "fund_type": fund_type})
    uniq = {row["code"]: row for row in out}
    return sorted(uniq.values(), key=lambda x: (x["name"], x["code"]))


def first_match(patterns: list[str], text: str) -> re.Match[str] | None:
    for pattern in patterns:
        m = re.search(pattern, text, flags=re.I)
        if m:
            return m
    return None


def parse_limit(text: str) -> tuple[float | None, str]:
    m = first_match([
        r"日累计申购限额\s*([0-9][0-9,]*(?:\.\d+)?)\s*(元|美元)?",
        r"单日累计购买上限\s*([0-9][0-9,]*(?:\.\d+)?)\s*(元|美元)?",
        r"单日(?:单个基金账户)?(?:单笔或多笔)?申购[^0-9]{0,35}([0-9][0-9,]*(?:\.\d+)?)\s*(元|美元)",
    ], text)
    if not m:
        return None, "—"
    value = float(m.group(1).replace(",", ""))
    unit = (m.group(2) if m.lastindex and m.lastindex >= 2 else None) or "元"
    if value.is_integer():
        display = f"{int(value):,}{unit}"
    else:
        display = f"{value:,.2f}{unit}"
    return value, display


def parse_status(text: str, name: str) -> str:
    patterns = [
        r"申购状态\s*(暂停申购|限大额|开放申购|封闭期|场内交易)",
        r"交易状态\s*[:：]?\s*(暂停申购|限大额|开放申购|封闭期|场内交易)",
    ]
    m = first_match(patterns, text)
    if m:
        return m.group(1)
    window = first_match([r"交易状态\s*[:：]?\s*(.{0,90})"], text)
    snippet = window.group(1) if window else text[:800]
    for status in ("暂停申购", "限大额", "开放申购", "封闭期", "场内交易"):
        if status in snippet:
            return status
    if "ETF" in name.upper() and "联接" not in name:
        return "场内交易"
    return "待核对"


def parse_nav(text: str) -> tuple[str, str]:
    m = first_match([
        r"单位净值\s*[（(]\s*(\d{2}-\d{2})\s*[）)]\s*[:：]?\s*([0-9]+(?:\.[0-9]+)?)",
        r"单位净值\s*[（(]\s*(\d{4}-\d{2}-\d{2})\s*[）)]\s*[:：]?\s*([0-9]+(?:\.[0-9]+)?)",
    ], text)
    if not m:
        return "", ""
    return m.group(1), m.group(2)


def fetch_detail(row: dict[str, str]) -> dict[str, object]:
    code, name = row["code"], row["name"]
    url = DETAIL_URL.format(code=code)
    result: dict[str, object] = {
        **row,
        "status": "待核对",
        "daily_limit": None,
        "limit_display": "—",
        "nav_date": "",
        "nav": "",
        "source_url": url,
        "source": "天天基金基金档案",
        "checked": False,
    }
    try:
        text = plain_text(decode_bytes(http_get(url, timeout=8, retries=1)))
        status = parse_status(text, name)
        limit, limit_display = parse_limit(text)
        nav_date, nav = parse_nav(text)
        if status == "场内交易" and limit is None:
            limit_display = "场内交易"
        result.update({
            "status": status,
            "daily_limit": limit,
            "limit_display": limit_display,
            "nav_date": nav_date,
            "nav": nav,
            "checked": True,
        })
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {str(exc)[:100]}"
    return result


def sort_key(row: dict[str, object]) -> tuple[int, float, str, str]:
    status_order = {"暂停申购": 0, "限大额": 1, "开放申购": 2, "封闭期": 3, "场内交易": 4, "待核对": 5}
    limit = row.get("daily_limit")
    num = float(limit) if isinstance(limit, (int, float)) else 1e30
    return (status_order.get(str(row.get("status")), 9), num, str(row.get("name")), str(row.get("code")))


def write_payload(funds: list[dict[str, object]], universe_count: int) -> None:
    funds.sort(key=sort_key)
    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "source_note": "基金范围来自公开基金目录；申购状态和单日限额来自公开基金档案页。限额变化频繁，点击来源可进一步核对基金公司最新公告。",
        "universe_count": universe_count,
        "funds_total": len(funds),
        "checked_count": sum(bool(x.get("checked")) for x in funds),
        "limited_count": sum(x.get("status") == "限大额" for x in funds),
        "paused_count": sum(x.get("status") == "暂停申购" for x in funds),
        "open_count": sum(x.get("status") == "开放申购" for x in funds),
        "exchange_count": sum(x.get("status") == "场内交易" for x in funds),
        "funds": funds,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        "[done] Nasdaq fund limits: "
        f"funds={payload['funds_total']} checked={payload['checked_count']} "
        f"limited={payload['limited_count']} paused={payload['paused_count']}"
    )


def main() -> None:
    try:
        universe = fetch_universe()
        print(f"[nasdaq-limit] matched fund universe={len(universe)}")
        if not universe:
            raise RuntimeError("no Nasdaq-related funds found")
    except Exception as exc:
        print(f"[nasdaq-limit-warn] universe: {type(exc).__name__}: {str(exc)[:140]}")
        if OUT.exists():
            print("[nasdaq-limit-warn] keeping previous nasdaq_fund_limits.json")
            return
        write_payload([], 0)
        return

    funds: list[dict[str, object]] = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        jobs = {pool.submit(fetch_detail, row): row for row in universe}
        for fut in as_completed(jobs):
            funds.append(fut.result())
    write_payload(funds, len(universe))


if __name__ == "__main__":
    main()
