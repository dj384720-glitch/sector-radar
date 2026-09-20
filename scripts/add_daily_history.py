#!/usr/bin/env python3
"""Replace chart history with daily trading-day data for interactive charts.

The base builder keeps payloads small by mixing daily/weekly/monthly points. This
post-processing step fetches roughly 11 years of DAILY Tencent K-line data in
small date windows, so users can inspect the chart at each trading day. If a
symbol cannot be refreshed, its existing history is preserved.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
from pathlib import Path
import json
import re

from update_data import PERIODS, calc_returns, http_json, parse_tencent_rows, shift_months

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "docs" / "data" / "latest.json"
SUPPORTED = re.compile(r"^(?:sh|sz|bj)\d{6}$")


def add_months(d: date, months: int) -> date:
    total = d.year * 12 + d.month - 1 + months
    y, m0 = divmod(total, 12)
    m = m0 + 1
    # day=1 is sufficient for window boundaries and avoids month-end issues.
    return date(y, m, 1)


def fetch_window(code: str, start: date, end: date) -> list[tuple[date, float]]:
    for adjusted in (True, False):
        endpoint = "fqkline/get" if adjusted else "kline/kline"
        adjust = ",qfq" if adjusted else ""
        param = f"{code},day,{start.isoformat()},{end.isoformat()},900{adjust}"
        url = f"https://web.ifzq.gtimg.cn/appstock/app/{endpoint}?param={param}"
        try:
            payload = http_json(url, timeout=10, retries=2)
            rows = parse_tencent_rows(payload, code, "day", adjusted)
            if rows:
                return rows
        except Exception:
            continue
    return []


def fetch_daily(code: str) -> list[tuple[date, float]]:
    today = date.today()
    start = shift_months(today, 132)  # 11 years gives margin around the 10y tab.
    points: dict[date, float] = {}
    cursor = date(start.year, start.month, 1)
    # 30-month windows stay comfortably below the endpoint's usual bar limits.
    while cursor <= today:
        next_cursor = add_months(cursor, 30)
        window_end = min(today, next_cursor)
        rows = fetch_window(code, cursor, window_end)
        for d, close in rows:
            if d >= start:
                points[d] = close
        cursor = next_cursor
    out = sorted(points.items())
    if len(out) < 20:
        raise RuntimeError("daily history unavailable")
    return out


def main() -> None:
    payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    sectors = payload.get("sectors") or []
    codes = sorted({str(x.get("code") or "") for x in sectors if SUPPORTED.match(str(x.get("code") or ""))})
    fetched: dict[str, list[tuple[date, float]] | Exception] = {}

    with ThreadPoolExecutor(max_workers=8) as pool:
        jobs = {pool.submit(fetch_daily, code): code for code in codes}
        for fut in as_completed(jobs):
            code = jobs[fut]
            try:
                fetched[code] = fut.result()
            except Exception as exc:
                fetched[code] = exc
                print(f"[daily-warn] {code}: {exc}")

    upgraded = 0
    for item in sectors:
        code = str(item.get("code") or "")
        result = fetched.get(code)
        if not isinstance(result, list) or len(result) < 20:
            continue
        item["history"] = [[d.isoformat(), round(c, 6)] for d, c in result]
        item["history_resolution"] = "daily"
        item["history_start_date"] = result[0][0].isoformat()
        item["latest_date"] = result[-1][0].isoformat()
        item["returns"] = calc_returns(result)
        available = sum(v is not None for v in item["returns"].values())
        item["status"] = "ok" if available == len(PERIODS) else ("partial" if available else "short_history")
        upgraded += 1

    payload["sectors"] = sectors
    payload["summary"] = {
        "total": len(sectors),
        "resolved": sum(1 for x in sectors if x.get("status") in {"ok", "partial", "short_history"}),
        "full_history": sum(1 for x in sectors if x.get("status") == "ok"),
        "daily_history": upgraded,
    }
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    DATA_PATH.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"[done] daily chart history upgraded for {upgraded}/{len(sectors)} sectors")


if __name__ == "__main__":
    main()
