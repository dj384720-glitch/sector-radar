#!/usr/bin/env python3
"""Append/replace today's A-share/ETF point with a public intraday quote.

The daily K-line source may not publish today's bar until after the close. This
script runs near the end of the Pages build and uses Sina's public real-time
quote endpoint for sh/sz symbols so the site can show today's date during the
trading session. A later daily K-line build naturally replaces the provisional
point with the official end-of-day bar.
"""
from __future__ import annotations

from bisect import bisect_right
from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import json
import math
import re
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "docs" / "data" / "latest.json"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"

PERIODS = [
    ("近1周", ("days", 7)),
    ("近1个月", ("months", 1)),
    ("近3个月", ("months", 3)),
    ("近6个月", ("months", 6)),
    ("近1年", ("years", 1)),
    ("近3年", ("years", 3)),
    ("近5年", ("years", 5)),
    ("近10年", ("years", 10)),
]


def shift_months(d: date, months: int) -> date:
    total = d.year * 12 + d.month - 1 - months
    y, m0 = divmod(total, 12)
    m = m0 + 1
    return date(y, m, min(d.day, monthrange(y, m)[1]))


def target_date(latest: date, spec: tuple[str, int]) -> date:
    unit, value = spec
    if unit == "days":
        return latest - timedelta(days=value)
    if unit == "months":
        return shift_months(latest, value)
    if unit == "years":
        return shift_months(latest, value * 12)
    raise ValueError(unit)


def calc_returns(history: list[list]) -> dict[str, float | None]:
    points = []
    for row in history:
        if not isinstance(row, list) or len(row) < 2:
            continue
        try:
            d = datetime.strptime(str(row[0]), "%Y-%m-%d").date()
            c = float(row[1])
        except Exception:
            continue
        if math.isfinite(c) and c > 0:
            points.append((d, c))
    points.sort(key=lambda x: x[0])
    if len(points) < 2:
        return {label: None for label, _ in PERIODS}
    dates = [d for d, _ in points]
    latest_date, latest_close = points[-1]
    out = {}
    for label, spec in PERIODS:
        target = target_date(latest_date, spec)
        idx = bisect_right(dates, target) - 1
        if idx < 0:
            out[label] = None
            continue
        old_date, old_close = points[idx]
        if (target - old_date).days > 16 or old_close <= 0:
            out[label] = None
            continue
        out[label] = round((latest_close / old_close - 1.0) * 100.0, 2)
    return out


def fetch_sina_quotes(codes: list[str]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for start in range(0, len(codes), 80):
        chunk = codes[start:start + 80]
        url = "https://hq.sinajs.cn/list=" + ",".join(chunk)
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": UA,
                "Referer": "https://finance.sina.com.cn/",
                "Accept": "text/plain,*/*",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                text = resp.read().decode("gb18030", errors="ignore")
        except Exception as exc:
            print(f"[intraday-warn] quote chunk={start}: {str(exc)[:160]}")
            continue
        for m in re.finditer(r'var\s+hq_str_((?:sh|sz)\d{6})="([^"]*)"', text):
            code, fields = m.group(1), m.group(2).split(",")
            if len(fields) < 32:
                continue
            try:
                price = float(fields[3])
            except Exception:
                continue
            quote_date = fields[30].strip()
            quote_time = fields[31].strip()
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", quote_date):
                continue
            if not (math.isfinite(price) and price > 0):
                continue
            out[code] = {
                "price": price,
                "date": quote_date,
                "time": quote_time,
            }
    return out


def upsert_history(item: dict, quote: dict) -> bool:
    history = item.get("history")
    if not isinstance(history, list):
        return False
    qd = quote["date"]
    price = round(float(quote["price"]), 6)
    latest = str(item.get("latest_date") or "")
    if latest and qd < latest:
        return False

    replaced = False
    for row in reversed(history):
        if isinstance(row, list) and row and str(row[0]) == qd:
            if len(row) >= 2:
                row[1] = price
            else:
                row.append(price)
            replaced = True
            break
    if not replaced:
        history.append([qd, price])
        history.sort(key=lambda r: str(r[0]) if isinstance(r, list) and r else "")

    item["history"] = history
    item["latest_date"] = qd
    item["returns"] = calc_returns(history)
    item["intraday"] = {
        "provisional": True,
        "price": price,
        "quote_date": qd,
        "quote_time": quote.get("time") or "",
        "source": "新浪财经公开实时行情",
    }
    return True


def main() -> None:
    payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    sectors = payload.get("sectors") or []
    codes = sorted({
        str(item.get("code") or "")
        for item in sectors
        if re.fullmatch(r"(?:sh|sz)\d{6}", str(item.get("code") or ""))
    })
    quotes = fetch_sina_quotes(codes)
    updated = 0
    today_dates: list[str] = []
    for item in sectors:
        code = str(item.get("code") or "")
        quote = quotes.get(code)
        if quote and upsert_history(item, quote):
            updated += 1
            today_dates.append(quote["date"])

    payload["sectors"] = sectors
    payload["intraday_updated_at"] = datetime.now(timezone.utc).isoformat()
    payload["intraday_summary"] = {
        "eligible_codes": len(codes),
        "quotes_received": len(quotes),
        "sectors_updated": updated,
        "newest_quote_date": max(today_dates) if today_dates else None,
        "source": "新浪财经公开实时行情",
    }
    DATA_PATH.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"[done] intraday snapshot: quotes={len(quotes)}/{len(codes)} sectors_updated={updated} newest={max(today_dates) if today_dates else 'n/a'}")


if __name__ == "__main__":
    main()
