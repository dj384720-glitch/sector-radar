#!/usr/bin/env python3
"""Append U.S. benchmark indices to the generated Sector Radar dataset.

Source order:
1. Stooq public historical CSV
2. FRED public CSV
3. Yahoo Finance chart API

Using multiple independent sources avoids a full failure when one provider rate-limits
GitHub-hosted runners.
"""
from __future__ import annotations

from bisect import bisect_right
from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import csv
import io
import json
import math
import urllib.parse
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

INDICES = [
    {
        "name": "纳斯达克",
        "benchmark": "纳斯达克综合指数",
        "code": "^IXIC",
        "stooq": ["^ndq", "^ixic"],
        "fred": "NASDAQCOM",
        "yahoo": "^IXIC",
    },
    {
        "name": "标普500",
        "benchmark": "标普500指数",
        "code": "^GSPC",
        "stooq": ["^spx"],
        "fred": "SP500",
        "yahoo": "^GSPC",
    },
]


def http_bytes(url: str, referer: str = "https://stooq.com/", timeout: int = 15) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "text/csv,application/json,text/plain,*/*",
            "Referer": referer,
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def parse_csv_points(raw: bytes, value_column: str) -> list[tuple[date, float]]:
    text = raw.decode("utf-8-sig", errors="ignore")
    rows = csv.DictReader(io.StringIO(text))
    out: list[tuple[date, float]] = []
    for row in rows:
        try:
            ds = row.get("Date") or row.get("DATE") or ""
            value = row.get(value_column)
            if not ds or value in (None, "", ".", "N/D"):
                continue
            d = datetime.strptime(ds[:10], "%Y-%m-%d").date()
            c = float(value)
        except Exception:
            continue
        if math.isfinite(c) and c > 0:
            out.append((d, c))
    out.sort(key=lambda x: x[0])
    return out


def fetch_stooq(symbols: list[str]) -> tuple[list[tuple[date, float]], str]:
    errors = []
    for symbol in symbols:
        try:
            url = "https://stooq.com/q/d/l/?" + urllib.parse.urlencode({"s": symbol, "i": "d"})
            points = parse_csv_points(http_bytes(url, "https://stooq.com/"), "Close")
            if len(points) >= 2:
                return points, f"Stooq公开历史行情（{symbol}）"
            errors.append(f"{symbol}: empty")
        except Exception as exc:
            errors.append(f"{symbol}: {exc}")
    raise RuntimeError("；".join(errors) or "Stooq无有效数据")


def fetch_fred(series_id: str) -> tuple[list[tuple[date, float]], str]:
    url = "https://fred.stlouisfed.org/graph/fredgraph.csv?" + urllib.parse.urlencode({"id": series_id})
    points = parse_csv_points(http_bytes(url, "https://fred.stlouisfed.org/", timeout=18), series_id)
    if len(points) < 2:
        raise RuntimeError("FRED无有效数据")
    return points, f"FRED公开历史数据（{series_id}）"


def fetch_yahoo(symbol: str) -> tuple[list[tuple[date, float]], str]:
    enc = urllib.parse.quote(symbol)
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{enc}"
        "?range=10y&interval=1d&events=div%2Csplits&includeAdjustedClose=true"
    )
    raw = http_bytes(url, "https://finance.yahoo.com/", timeout=12)
    payload = json.loads(raw.decode("utf-8", errors="ignore"))
    result = ((payload.get("chart") or {}).get("result") or [None])[0]
    if not result:
        raise RuntimeError("Yahoo chart empty")
    ts = result.get("timestamp") or []
    indicators = result.get("indicators") or {}
    adj = ((indicators.get("adjclose") or [{}])[0]).get("adjclose") or []
    close = ((indicators.get("quote") or [{}])[0]).get("close") or []
    vals = adj if len(adj) == len(ts) else close
    out: list[tuple[date, float]] = []
    for t, v in zip(ts, vals):
        if v is None:
            continue
        try:
            d = datetime.fromtimestamp(int(t), tz=timezone.utc).date()
            c = float(v)
        except Exception:
            continue
        if math.isfinite(c) and c > 0:
            out.append((d, c))
    out.sort(key=lambda x: x[0])
    if len(out) < 2:
        raise RuntimeError("Yahoo chart无有效数据")
    return out, "Yahoo Finance公开行情（备用）"


def fetch_index(spec: dict) -> tuple[list[tuple[date, float]], str, list[str]]:
    errors: list[str] = []
    for label, fn in (
        ("Stooq", lambda: fetch_stooq(spec["stooq"])),
        ("FRED", lambda: fetch_fred(spec["fred"])),
        ("Yahoo", lambda: fetch_yahoo(spec["yahoo"])),
    ):
        try:
            points, source = fn()
            return points, source, errors
        except Exception as exc:
            errors.append(f"{label}: {exc}")
    raise RuntimeError("；".join(errors))


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
    return shift_months(latest, value * 12)


def calc_returns(points: list[tuple[date, float]]) -> dict[str, float | None]:
    dates = [d for d, _ in points]
    latest_date, latest_close = points[-1]
    out: dict[str, float | None] = {}
    for label, spec in PERIODS:
        target = target_date(latest_date, spec)
        idx = bisect_right(dates, target) - 1
        if idx < 0:
            out[label] = None
            continue
        old_date, old_close = points[idx]
        if (target - old_date).days > 16:
            out[label] = None
            continue
        out[label] = round((latest_close / old_close - 1.0) * 100.0, 2)
    return out


def chart_history(points: list[tuple[date, float]]) -> list[list[str | float]]:
    latest = points[-1][0]
    cutoff = shift_months(latest, 121)
    rows = [[d.isoformat(), round(c, 6)] for d, c in points if d >= cutoff]
    if len(rows) > 1900:
        step = max(1, len(rows) // 1800)
        sampled = rows[::step]
        if sampled[-1][0] != rows[-1][0]:
            sampled.append(rows[-1])
        rows = sampled
    return rows


def build_item(spec: dict) -> dict:
    name = spec["name"]
    try:
        points, source, earlier_errors = fetch_index(spec)
        returns = calc_returns(points)
        available = sum(v is not None for v in returns.values())
        status = "ok" if available == len(PERIODS) else ("partial" if available else "short_history")
        fallback_note = ""
        if earlier_errors:
            fallback_note = "；已自动切换备用数据源"
        return {
            "name": name,
            "benchmark": spec["benchmark"],
            "code": spec["code"],
            "source": source,
            "note": "美国主要市场指数；收益按最近可用交易日收盘价计算" + fallback_note,
            "status": status,
            "returns": returns,
            "latest_date": points[-1][0].isoformat(),
            "start_date": points[0][0].isoformat(),
            "history": chart_history(points),
        }
    except Exception as exc:
        return {
            "name": name,
            "benchmark": spec["benchmark"],
            "code": spec["code"],
            "source": "Stooq / FRED / Yahoo Finance",
            "note": f"行情抓取失败：{str(exc)[:300]}",
            "status": "error",
            "returns": {label: None for label, _ in PERIODS},
            "latest_date": None,
            "start_date": None,
            "history": [],
        }


def main() -> None:
    payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    sectors = payload.get("sectors") or []
    by_name = {x.get("name"): i for i, x in enumerate(sectors)}
    for spec in INDICES:
        item = build_item(spec)
        if spec["name"] in by_name:
            sectors[by_name[spec["name"]]] = item
        else:
            sectors.append(item)
        print(f"[us-index] {spec['name']}: {item['status']} via {item['source']}")
    payload["sectors"] = sectors
    payload["periods"] = [label for label, _ in PERIODS]
    payload["summary"] = {
        "total": len(sectors),
        "resolved": sum(1 for x in sectors if x.get("status") in {"ok", "partial", "short_history"}),
        "full_history": sum(1 for x in sectors if x.get("status") == "ok"),
    }
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    DATA_PATH.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("[done] updated Nasdaq Composite and S&P 500")


if __name__ == "__main__":
    main()
