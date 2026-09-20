#!/usr/bin/env python3
"""Backfill representative-fund rows whose market history is unavailable.

The primary selector intentionally chooses by thematic relevance first. If a
new/illiquid ETF has no usable public daily history on this run, replace that
row with the next related ETF that does have history so every displayed row can
show return and maximum drawdown metrics.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json

from add_daily_history import fetch_daily
from add_sector_funds import ALIASES, FALLBACK, fetch_etf_universe, metrics, rank_by_aliases

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "docs" / "data" / "latest.json"


def fund_from_history(candidate: dict[str, str], points) -> dict:
    returns, drawdowns = metrics(points)
    return {
        "name": candidate["name"],
        "code": candidate["code"],
        "source": "腾讯财经公开K线",
        "returns": returns,
        "drawdowns": drawdowns,
        "latest_date": points[-1][0].isoformat(),
        "start_date": points[0][0].isoformat(),
    }


def main() -> None:
    payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    sectors = payload.get("sectors") or []
    needs_repair = [x for x in sectors if sum(1 for f in (x.get("funds") or []) if f.get("latest_date")) < 5]
    if not needs_repair:
        print("[fund-repair] all sector fund rows already have history")
        return

    universe = fetch_etf_universe()
    repaired = 0

    for item in needs_repair:
        sector = str(item.get("name") or "")
        original = item.get("funds") or []
        valid = [f for f in original if f.get("latest_date")][:5]
        seen = {str(f.get("code") or "") for f in original}
        stages = [ALIASES.get(sector, [sector])]
        if FALLBACK.get(sector):
            stages.append(FALLBACK[sector])

        candidates: list[dict[str, str]] = []
        candidate_seen = set(seen)
        for aliases in stages:
            for cand in rank_by_aliases(sector, aliases, universe, candidate_seen):
                candidates.append(cand)
                candidate_seen.add(cand["code"])

        for cand in candidates:
            if len(valid) >= 5:
                break
            try:
                points = fetch_daily(cand["code"])
                if len(points) < 2:
                    continue
                valid.append(fund_from_history(cand, points))
                repaired += 1
                print(f"[fund-repair] {sector}: + {cand['name']}({cand['code'][2:]})")
            except Exception as exc:
                print(f"[fund-repair-warn] {sector} {cand['code']}: {str(exc)[:120]}")

        item["funds"] = valid[:5]

    rows = sum(len(x.get("funds") or []) for x in sectors)
    history_rows = sum(1 for x in sectors for f in (x.get("funds") or []) if f.get("latest_date"))
    five = sum(1 for x in sectors if len(x.get("funds") or []) == 5)
    summary = payload.setdefault("summary", {})
    summary["fund_sectors_with_five"] = five
    summary["fund_rows"] = rows
    summary["fund_rows_with_history"] = history_rows
    payload["funds_updated_at"] = datetime.now(timezone.utc).isoformat()
    DATA_PATH.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"[done] fund repair: replacements={repaired} five={five}/{len(sectors)} history={history_rows}/{rows}")


if __name__ == "__main__":
    main()
