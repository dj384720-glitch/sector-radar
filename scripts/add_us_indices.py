#!/usr/bin/env python3
"""Append U.S. benchmark indices to the generated Sector Radar dataset."""
from __future__ import annotations

from bisect import bisect_right
from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
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
    ("纳斯达克", "^IXIC", "纳斯达克综合指数"),
    ("标普500", "^GSPC", "标普500指数"),
]


def http_json(url: str):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "application/json,text/plain,*/*",
            "Referer": "https://finance.yahoo.com/",
        },
    )
    with urllib.request.urlopen(req, timeout=12) as resp:
        return json.loads(resp.read().decode("utf-8", errors="ignore"))


def fetch_yahoo(symbol: str) -> list[tuple[date, float]]:
    enc = urllib.parse.quote(symbol)
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{enc}"
        "?range=max&interval=1d&events=div%2Csplits&includeAdjustedClose=true"
    )
    payload = http_json(url)
    result = ((payload.get("chart") or {}).get("result") or [None])[0]
    if not result:
        raise RuntimeError("Yahoo chart empty")
    ts = result.get("timestamp") or []
    indicators = result.get("indicators") or {}
    adj = ((indicators.get("adjclose") or [{}])[0]).get("adjclose") or []
    close = ((indicators.get("quote") or [{}])[0]).get("close") or []
    vals = adj if len(adj) == len(ts) else close
    out = []
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
    return out


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
    out = {}
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


def build_item(name: str, symbol: str, benchmark: str) -> dict:
    try:
        points = fetch_yahoo(symbol)
        returns = calc_returns(points)
        available = sum(v is not None for v in returns.values())
        status = "ok" if available == len(PERIODS) else ("partial" if available else "short_history")
        return {
            "name": name,
            "benchmark": benchmark,
            "code": symbol,
            "source": "Yahoo Finance公开行情",
            "note": "美国主要市场指数；收益按最近可用交易日收盘价计算",
            "status": status,
            "returns": returns,
            "latest_date": points[-1][0].isoformat(),
            "start_date": points[0][0].isoformat(),
            "history": chart_history(points),
        }
    except Exception as exc:
        return {
            "name": name,
            "benchmark": benchmark,
            "code": symbol,
            "source": "Yahoo Finance公开行情",
            "note": f"行情抓取失败：{str(exc)[:220]}",
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
    for name, symbol, benchmark in INDICES:
        item = build_item(name, symbol, benchmark)
        if name in by_name:
            sectors[by_name[name]] = item
        else:
            sectors.append(item)
    payload["sectors"] = sectors
    payload["periods"] = [label for label, _ in PERIODS]
    payload["summary"] = {
        "total": len(sectors),
        "resolved": sum(1 for x in sectors if x.get("status") in {"ok", "partial", "short_history"}),
        "full_history": sum(1 for x in sectors if x.get("status") == "ok"),
    }
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    DATA_PATH.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("[done] added Nasdaq Composite and S&P 500")


if __name__ == "__main__":
    main()
