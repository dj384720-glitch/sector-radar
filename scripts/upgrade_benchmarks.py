#!/usr/bin/env python3
"""Prefer official/theme indices for sectors that previously shared rough ETF proxies.

Runs after add_daily_history.py. Each mapping is fetched independently; when an
official index is unavailable from the existing public market-data pipeline, the
current sector series is retained as a transparent fallback instead of breaking
the page.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
import json

from add_daily_history import fetch_daily
from update_data import PERIODS, calc_returns

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "docs" / "data" / "latest.json"

OFFICIAL = {
    "半导体": ("sh931081", "中证半导体产业指数", "中证指数"),
    "存储芯片": ("sz980138", "国证存储芯片产业指数", "国证指数"),
    "PCB": ("sh932666", "中证印制电路板指数", "中证指数"),
    "人工智能": ("sh931071", "中证人工智能产业指数", "中证指数"),
    "AI应用": ("sz980112", "国证AI应用指数", "国证指数"),
    "国产算力": ("sh931688", "中证算力基础设施主题指数", "中证指数"),
    "CPO": ("sh931723", "中证光通信主题指数", "中证指数"),
    "通信": ("sh931160", "中证全指通信设备指数", "中证指数"),
    "医疗": ("sz399989", "中证医疗指数", "中证指数"),
    "CXO": ("sh931750", "中证医药研发服务主题指数", "中证指数"),
    "军工": ("sz399967", "中证军工指数", "中证指数"),
    "商业航天": ("sh931594", "中证卫星产业指数", "中证指数"),
}


def clean_proxy_note(note: str) -> str:
    parts = [x.strip() for x in str(note or "").split("；") if x.strip()]
    return "；".join(x for x in parts if not ("口径：" in x and "可交易公开价格序列" in x))


def main() -> None:
    payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    sectors = payload.get("sectors") or []
    names = {str(x.get("name") or "") for x in sectors}
    targets = {name: spec for name, spec in OFFICIAL.items() if name in names}

    results = {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        jobs = {pool.submit(fetch_daily, spec[0]): name for name, spec in targets.items()}
        for fut in as_completed(jobs):
            name = jobs[fut]
            try:
                rows = fut.result()
                if len(rows) < 40:
                    raise RuntimeError(f"official history too short: {len(rows)}")
                results[name] = rows
            except Exception as exc:
                results[name] = exc

    upgraded = fallback = 0
    details = {}
    for item in sectors:
        name = str(item.get("name") or "")
        if name not in targets:
            continue
        code, label, provider = targets[name]
        previous = {"code": item.get("code"), "benchmark": item.get("benchmark"), "source": item.get("source")}
        result = results.get(name)
        if isinstance(result, list) and len(result) >= 40:
            item["code"] = code
            item["benchmark"] = label
            item["source"] = f"腾讯财经公开K线 · {provider}官方指数"
            item["history"] = [[d.isoformat(), round(v, 6)] for d, v in result]
            item["history_resolution"] = "daily"
            item["history_start_date"] = result[0][0].isoformat()
            item["start_date"] = result[0][0].isoformat()
            item["latest_date"] = result[-1][0].isoformat()
            item["returns"] = calc_returns(result)
            available = sum(v is not None for v in item["returns"].values())
            item["status"] = "ok" if available == len(PERIODS) else ("partial" if available else "short_history")
            item["note"] = clean_proxy_note(str(item.get("note") or ""))
            extra = f"当前研究口径优先使用{provider}官方指数“{label}”"
            item["note"] = (item["note"] + "；" if item["note"] else "") + extra
            item["benchmark_upgrade"] = {
                "status": "official", "provider": provider, "code": code, "label": label, "previous": previous,
            }
            upgraded += 1
            details[name] = {"status": "official", "code": code, "label": label}
            print(f"[benchmark] {name}: official {code} {label}")
        else:
            message = str(result)[:180]
            item["benchmark_upgrade"] = {
                "status": "fallback", "provider": provider, "candidate_code": code,
                "candidate_label": label, "reason": message, "previous": previous,
            }
            fallback += 1
            details[name] = {"status": "fallback", "code": code, "reason": message}
            print(f"[benchmark-fallback] {name}: {code} -> {message}")

    payload["sectors"] = sectors
    payload["benchmark_upgrade_updated_at"] = datetime.now(timezone.utc).isoformat()
    payload["benchmark_upgrade_summary"] = {
        "requested": len(targets), "official": upgraded, "fallback": fallback, "details": details,
    }
    DATA_PATH.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"[done] official benchmark upgrade: official={upgraded}/{len(targets)} fallback={fallback}")


if __name__ == "__main__":
    main()
