#!/usr/bin/env python3
"""Build current purchase-limit status for Nasdaq-related RMB off-exchange funds.

The fund universe comes from Eastmoney's public fund directory. For each matching
RMB off-exchange share, FundRateInfo provides the public purchase status (SGZT),
maximum subscription amount (MAXSG), minimum subscription (MINSG), and redemption
status (SHZT). Pure exchange ETFs and USD shares are excluded because their trading
or currency limit is not comparable with RMB off-exchange daily purchase limits.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
import json
import re
import ssl
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "data" / "nasdaq_limits.json"
TZ = timezone(timedelta(hours=8))
UA_DESKTOP = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/130 Safari/537.36"
UA_MOBILE = "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/130 Mobile Safari/537.36"
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE
UNIVERSE_URL = "https://fund.eastmoney.com/js/fundcode_search.js"
RATE_URL = "https://fundmobapi.eastmoney.com/FundMApi/FundRateInfo.ashx"
ON_EXCHANGE_PREFIX = ("15", "51", "52", "56", "58")
NASDAQ_RE = re.compile(r"纳斯达克|纳指|NASDAQ", re.I)
USD_RE = re.compile(r"美元|美汇|美钞|现汇|现钞", re.I)
SHARE_RE = re.compile(r"([ACDEFI])(?:类|份额)?(?:\(?(?:人民币)\)?)?$", re.I)
MAX_WORKERS = 8


def http_get(url: str, *, ua: str, timeout: int = 12) -> str | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": ua, "Referer": "https://fund.eastmoney.com/"})
        with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as resp:
            return resp.read().decode("utf-8", "ignore")
    except (urllib.error.URLError, OSError, TimeoutError, ValueError):
        return None


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


def share_class(name: str) -> str:
    text = name.replace("（", "(").replace("）", ")").strip()
    m = SHARE_RE.search(text)
    return m.group(1).upper() if m else "-"


def fetch_universe() -> list[dict[str, str]]:
    body = http_get(UNIVERSE_URL, ua=UA_DESKTOP, timeout=15)
    if not body:
        return []
    start, end = body.find("["), body.rfind("]")
    if start < 0 or end <= start:
        return []
    try:
        rows = json.loads(body[start : end + 1])
    except Exception:
        return []
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, list) or len(row) < 3:
            continue
        code, name = str(row[0]), str(row[2])
        if code in seen or not re.fullmatch(r"\d{6}", code):
            continue
        if not NASDAQ_RE.search(name):
            continue
        if code.startswith(ON_EXCHANGE_PREFIX):
            continue
        if USD_RE.search(name):
            continue
        seen.add(code)
        out.append({"code": code, "name": name, "share_class": share_class(name)})
    return out


def fetch_rate(entry: dict[str, str]) -> dict | None:
    params = urlencode({
        "FCODE": entry["code"],
        "deviceid": "sector-radar",
        "plat": "Android",
        "product": "EFund",
        "version": "6.5.5",
    })
    body = http_get(RATE_URL + "?" + params, ua=UA_MOBILE, timeout=10)
    if not body:
        return None
    try:
        payload = json.loads(body)
    except Exception:
        return None
    data = payload.get("Datas")
    return data if isinstance(data, dict) else None


def normalize_status(raw: str, max_buy) -> str:
    text = (raw or "").strip()
    if "暂停" in text or "封闭" in text:
        return "暂停申购"
    if "限" in text or "大额" in text:
        return "限大额"
    if max_buy is not None and 0 < max_buy < 100_000_000:
        return "限大额"
    if "开放" in text or text:
        return "开放申购" if "开放" in text else text
    return "开放申购"


def read_previous() -> dict:
    try:
        return json.loads(OUT.read_text(encoding="utf-8"))
    except Exception:
        return {}


def build_record(entry: dict[str, str], old_map: dict[str, dict]) -> tuple[dict, bool]:
    data = fetch_rate(entry)
    if not data:
        old = old_map.get(entry["code"])
        if old:
            rec = dict(old)
            rec.update(entry)
            rec["stale"] = True
            return rec, False
        return {
            **entry,
            "status": "数据暂缺",
            "max_buy": None,
            "min_buy": None,
            "min_dca": None,
            "redemption_status": "",
            "source": "天天基金公开接口",
            "source_url": f"https://fund.eastmoney.com/{entry['code']}.html",
            "stale": True,
        }, False

    max_buy = parse_number(data.get("MAXSG"))
    status = normalize_status(str(data.get("SGZT") or ""), max_buy)
    if status == "暂停申购":
        max_buy = None
    return {
        **entry,
        "status": status,
        "max_buy": max_buy,
        "min_buy": parse_number(data.get("MINSG")),
        "min_dca": parse_number(data.get("MINDT")),
        "redemption_status": str(data.get("SHZT") or ""),
        "source": "天天基金公开接口",
        "source_url": f"https://fund.eastmoney.com/{entry['code']}.html",
        "stale": False,
    }, True


def main() -> None:
    previous = read_previous()
    old_map = {str(x.get("code")): x for x in previous.get("funds", []) if isinstance(x, dict) and x.get("code")}
    universe = fetch_universe()
    if not universe:
        if previous:
            print("[nasdaq-limit-warn] fund universe unavailable; keeping previous nasdaq_limits.json")
            return
        raise SystemExit("Nasdaq fund universe unavailable and no fallback snapshot exists")

    records: list[dict] = []
    fresh_count = 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(build_record, entry, old_map): entry for entry in universe}
        for fut in as_completed(futures):
            try:
                rec, fresh = fut.result()
            except Exception:
                entry = futures[fut]
                rec = {**entry, "status": "数据暂缺", "max_buy": None, "min_buy": None, "min_dca": None,
                       "redemption_status": "", "source": "天天基金公开接口",
                       "source_url": f"https://fund.eastmoney.com/{entry['code']}.html", "stale": True}
                fresh = False
            records.append(rec)
            fresh_count += int(fresh)

    if fresh_count < max(3, int(len(universe) * 0.5)) and previous:
        print(f"[nasdaq-limit-warn] fresh coverage too low ({fresh_count}/{len(universe)}); keeping previous snapshot")
        return

    status_order = {"限大额": 0, "暂停申购": 1, "开放申购": 2, "数据暂缺": 3}
    records.sort(key=lambda x: (status_order.get(str(x.get("status")), 2), x.get("max_buy") if isinstance(x.get("max_buy"), (int, float)) else 1e30, str(x.get("name", ""))))
    payload = {
        "updated_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "source": "天天基金 / 东方财富公开基金接口",
        "scope": "名称包含“纳斯达克/纳指/NASDAQ”的人民币场外基金份额；排除纯场内ETF和美元份额",
        "fallback": False,
        "count": len(records),
        "fresh_count": fresh_count,
        "funds": records,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        "[done] Nasdaq fund limits: "
        f"total={len(records)} fresh={fresh_count} "
        f"limited={sum(x.get('status') == '限大额' for x in records)} "
        f"paused={sum(x.get('status') == '暂停申购' for x in records)}"
    )


if __name__ == "__main__":
    main()
