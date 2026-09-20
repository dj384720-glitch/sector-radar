#!/usr/bin/env python3
"""Build docs/data/latest.json from public Eastmoney market data.

The job is intentionally time-bounded: network failures should produce partial
data and still let GitHub Pages deploy instead of leaving an older page live.
"""
from __future__ import annotations

from bisect import bisect_right
from calendar import monthrange
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import json
import math
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "data" / "sectors.json"
OUT_DIR = ROOT / "docs" / "data"
OUT_PATH = OUT_DIR / "latest.json"

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"
TOKEN = "D43BF722C8E33BDC906FB84D85E326E8"

PERIODS = [
    ("近10年", ("years", 10)),
    ("近5年", ("years", 5)),
    ("近3年", ("years", 3)),
    ("近1年", ("years", 1)),
    ("近6个月", ("months", 6)),
    ("近3个月", ("months", 3)),
    ("近1个月", ("months", 1)),
    ("近1周", ("days", 7)),
]


def http_json(url: str, params: dict[str, str] | None = None, timeout: float = 5.0) -> dict:
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "application/json,text/plain,*/*",
            "Referer": "https://quote.eastmoney.com/",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def normalize(text: str) -> str:
    return (
        str(text).strip().lower()
        .replace(" ", "").replace("-", "").replace("_", "")
        .replace("（", "(").replace("）", ")")
        .replace("概念", "").replace("板块", "").replace("行业", "")
    )


def fetch_board_catalog(kind: str) -> list[dict]:
    fs = "m:90 t:3 f:!50" if kind == "concept" else "m:90 t:2 f:!50"
    hosts = ["https://79.push2.eastmoney.com", "https://17.push2.eastmoney.com"]
    params = {
        "pn": "1", "pz": "100", "po": "1", "np": "1",
        "ut": "bd1d9ddb04089700cf9c27f6f7426281",
        "fltt": "2", "invt": "2", "fid": "f12", "fs": fs, "fields": "f12,f14",
    }
    for host in hosts:
        try:
            rows: list[dict] = []
            for page in range(1, 8):
                params["pn"] = str(page)
                payload = http_json(f"{host}/api/qt/clist/get", params, timeout=4.0)
                data = payload.get("data") or {}
                diff = data.get("diff") or []
                if isinstance(diff, dict):
                    diff = list(diff.values())
                if not diff:
                    break
                for item in diff:
                    code, name = str(item.get("f12", "")).strip(), str(item.get("f14", "")).strip()
                    if code and name:
                        rows.append({"code": code, "name": name, "secid": f"90.{code}", "kind": kind})
                total = int(data.get("total") or 0)
                if (total and len(rows) >= total) or len(diff) < int(params["pz"]):
                    break
            if rows:
                return rows
        except Exception as exc:
            print(f"[warn] {kind} catalog {host}: {exc}")
    return []


def resolve_board(entry: dict, catalog: list[dict]) -> dict | None:
    aliases = [str(x) for x in (entry.get("aliases") or [entry["name"]]) if str(x).strip()]
    prefer = entry.get("prefer")
    best: tuple[int, dict] | None = None
    for row in catalog:
        rn = normalize(row["name"])
        for i, alias in enumerate(aliases):
            an = normalize(alias)
            score = -1
            if rn == an:
                score = 100 - i
            elif len(an) >= 2 and (an in rn or rn in an):
                score = 60 - i
            if score >= 0 and prefer and row["kind"] == prefer:
                score += 10
            if score >= 0 and (best is None or score > best[0]):
                best = (score, row)
    return best[1] if best else None


def direct_security(entry: dict) -> dict | None:
    if entry.get("secid"):
        return {
            "secid": str(entry["secid"]),
            "code": str(entry.get("benchmark") or str(entry["secid"]).split(".", 1)[-1]),
            "name": str(entry.get("benchmark_name") or entry["name"]),
            "kind": "security",
        }
    queries = [str(x) for x in (entry.get("queries") or []) if str(x).strip()]
    if queries:
        q = queries[0]
        if q.isdigit() and len(q) == 6:
            market = "0" if q.startswith("399") or q.startswith("899") else "1"
            return {"secid": f"{market}.{q}", "code": q, "name": entry["name"], "kind": "security"}
    return None


def search_security(entry: dict) -> dict | None:
    direct = direct_security(entry)
    if direct:
        return direct
    queries = [str(x) for x in (entry.get("queries") or [entry["name"]]) if str(x).strip()]
    for query in queries[:2]:
        try:
            payload = http_json(
                "https://searchapi.eastmoney.com/api/suggest/get",
                {"input": query, "type": "14", "token": TOKEN, "count": "10"},
                timeout=4.0,
            )
            rows = (payload.get("QuotationCodeTable") or {}).get("Data") or []
            if not rows:
                continue
            qn = normalize(query)
            candidates = []
            for row in rows:
                secid = str(row.get("QuoteID") or "").strip()
                code = str(row.get("Code") or "").strip()
                name = str(row.get("Name") or "").strip()
                if not (secid and code and name):
                    continue
                score = 0
                if code.lower() == query.lower():
                    score += 100
                if normalize(name) == qn:
                    score += 90
                if secid.startswith("90."):
                    score -= 30
                candidates.append((score, {"secid": secid, "code": code, "name": name, "kind": "security"}))
            if candidates:
                return max(candidates, key=lambda x: x[0])[1]
        except Exception as exc:
            print(f"[warn] search {entry['name']} / {query}: {exc}")
    return None


def fetch_kline(secid: str) -> tuple[str, list[tuple[date, float]]]:
    params = {
        "secid": secid,
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": "101", "fqt": "0", "beg": "20000101", "end": "20500101",
        "smplmt": "10000", "lmt": "1000000",
    }
    last: Exception | None = None
    for host in ("https://push2his.eastmoney.com", "https://91.push2his.eastmoney.com"):
        try:
            payload = http_json(f"{host}/api/qt/stock/kline/get", params, timeout=6.0)
            data = payload.get("data")
            if not isinstance(data, dict):
                raise RuntimeError("empty data")
            lines = data.get("klines") or []
            if not lines:
                raise RuntimeError("empty klines")
            points: list[tuple[date, float]] = []
            for line in lines:
                p = str(line).split(",")
                if len(p) < 3:
                    continue
                try:
                    d = datetime.strptime(p[0], "%Y-%m-%d").date()
                    close = float(p[2])
                except (ValueError, TypeError):
                    continue
                if math.isfinite(close) and close > 0:
                    points.append((d, close))
            if not points:
                raise RuntimeError("no valid close")
            points.sort(key=lambda x: x[0])
            return str(data.get("name") or "").strip(), points
        except Exception as exc:
            last = exc
    raise RuntimeError(str(last or "kline unavailable"))


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
    dates = [x[0] for x in points]
    latest_date, latest_close = points[-1]
    result: dict[str, float | None] = {}
    for label, spec in PERIODS:
        target = target_date(latest_date, spec)
        idx = bisect_right(dates, target) - 1
        if idx < 0:
            result[label] = None
            continue
        old_date, old_close = points[idx]
        if (target - old_date).days > 14:
            result[label] = None
            continue
        result[label] = round((latest_close / old_close - 1) * 100, 2)
    return result


def placeholder_benchmark(entry: dict) -> str:
    if entry.get("benchmark_name"):
        return str(entry["benchmark_name"])
    if entry.get("aliases"):
        return str(entry["aliases"][0])
    if entry.get("queries"):
        return str(entry["queries"][0])
    return str(entry["name"])


def main() -> None:
    sectors = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(fetch_board_catalog, "concept")
        f2 = pool.submit(fetch_board_catalog, "industry")
        catalog = f1.result() + f2.result()
    print(f"[info] board catalog rows={len(catalog)}")

    resolved: list[tuple[dict, dict | None]] = []
    for entry in sectors:
        if entry.get("mode", "board") == "board":
            r = resolve_board(entry, catalog)
        else:
            r = search_security(entry)
        resolved.append((entry, r))

    secids = sorted({r["secid"] for _, r in resolved if r})
    market_data: dict[str, tuple[str, list[tuple[date, float]]] | Exception] = {}
    with ThreadPoolExecutor(max_workers=12) as pool:
        jobs = {pool.submit(fetch_kline, secid): secid for secid in secids}
        for fut in as_completed(jobs):
            secid = jobs[fut]
            try:
                market_data[secid] = fut.result()
                print(f"[ok] {secid}")
            except Exception as exc:
                market_data[secid] = exc
                print(f"[warn] {secid}: {exc}")

    items = []
    for entry, r in resolved:
        item = {
            "name": entry["name"],
            "benchmark": placeholder_benchmark(entry),
            "code": "",
            "source": entry.get("source") or "东方财富公开行情",
            "note": entry.get("note", ""),
            "status": "unavailable",
            "returns": {label: None for label, _ in PERIODS},
            "latest_date": None,
            "start_date": None,
        }
        if not r:
            item["note"] = (item["note"] + "；" if item["note"] else "") + "未自动匹配到可用公开行情"
            items.append(item)
            continue

        item["code"] = r["code"]
        if r["kind"] in {"concept", "industry"}:
            item["benchmark"] = f"{r['name']} ({r['code']})"
            item["source"] = "东方财富 · " + ("概念板块" if r["kind"] == "concept" else "行业板块")
        else:
            item["benchmark"] = f"{r['name']} ({r['code']})"

        md = market_data.get(r["secid"])
        if isinstance(md, Exception) or md is None:
            item["status"] = "error"
            item["note"] = (item["note"] + "；" if item["note"] else "") + "本次公开行情抓取失败"
            items.append(item)
            continue

        live_name, points = md
        if live_name and r["kind"] == "security":
            item["benchmark"] = f"{live_name} ({r['code']})"
        item["returns"] = calc_returns(points)
        item["latest_date"] = points[-1][0].isoformat()
        item["start_date"] = points[0][0].isoformat()
        available = sum(v is not None for v in item["returns"].values())
        item["status"] = "ok" if available == len(PERIODS) else ("partial" if available else "short_history")
        items.append(item)

    resolved_count = sum(x["status"] in {"ok", "partial", "short_history"} for x in items)
    full_count = sum(x["status"] == "ok" for x in items)
    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "periods": [x[0] for x in PERIODS],
        "summary": {"total": len(items), "resolved": resolved_count, "full_history": full_count},
        "sectors": items,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[done] wrote {OUT_PATH}; resolved={resolved_count}/{len(items)}")


if __name__ == "__main__":
    main()
