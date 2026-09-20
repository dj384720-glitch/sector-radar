#!/usr/bin/env python3
"""Fill Nasdaq and S&P 500 rows with reliable Tencent-backed QDII ETF proxies.

GitHub-hosted runners are rate-limited by Yahoo and can be blocked by some U.S.
data sites. The main Sector Radar Tencent pipeline is already reliable, so these
two U.S. market rows use long-running China-listed QDII ETFs as explicit proxies:
- 513100: Guotai Nasdaq-100 ETF
- 513500: Bosera S&P 500 ETF

These are proxies, not the official index levels. Their RMB market prices can
differ from the underlying index because of FX, fees, tracking error, trading
hours and secondary-market premiums/discounts.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json

from scripts.update_data import PERIODS, calc_returns, chart_history, fetch_series

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "docs" / "data" / "latest.json"

PROXIES = [
    {
        "name": "纳斯达克",
        "code": "sh513100",
        "benchmark": "纳指ETF国泰（513100） · 纳斯达克100 ETF代理",
        "note": "代理口径：国泰纳斯达克100（QDII-ETF），人民币场内价格；与纳斯达克综合指数并非同一指数，且会受汇率、跟踪误差、交易时段及溢折价影响",
    },
    {
        "name": "标普500",
        "code": "sh513500",
        "benchmark": "标普500ETF博时（513500） · ETF代理",
        "note": "代理口径：博时标普500ETF，人民币场内价格；跟踪标普500，但会受汇率、跟踪误差、交易时段及溢折价影响",
    },
]


def build_item(spec: dict) -> dict:
    try:
        points, source = fetch_series(spec["code"])
        returns = calc_returns(points)
        available = sum(v is not None for v in returns.values())
        status = "ok" if available == len(PERIODS) else ("partial" if available else "short_history")
        return {
            "name": spec["name"],
            "benchmark": spec["benchmark"],
            "code": spec["code"],
            "source": source,
            "note": spec["note"],
            "status": status,
            "returns": returns,
            "latest_date": points[-1][0].isoformat(),
            "start_date": points[0][0].isoformat(),
            "history": chart_history(points),
        }
    except Exception as exc:
        return {
            "name": spec["name"],
            "benchmark": spec["benchmark"],
            "code": spec["code"],
            "source": "腾讯财经 / Yahoo Finance",
            "note": spec["note"] + "；行情抓取失败：" + str(exc)[:220],
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

    for spec in PROXIES:
        item = build_item(spec)
        if spec["name"] in by_name:
            sectors[by_name[spec["name"]]] = item
        else:
            sectors.append(item)
        print(f"[us-proxy] {spec['name']}: {item['status']} via {item['source']}")

    payload["sectors"] = sectors
    payload["periods"] = [label for label, _ in PERIODS]
    payload["summary"] = {
        "total": len(sectors),
        "resolved": sum(1 for x in sectors if x.get("status") in {"ok", "partial", "short_history"}),
        "full_history": sum(1 for x in sectors if x.get("status") == "ok"),
    }
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    DATA_PATH.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("[done] updated Nasdaq and S&P 500 using QDII ETF proxies")


if __name__ == "__main__":
    main()
