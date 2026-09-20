#!/usr/bin/env python3
"""Fetch public market/sector history and build the JSON consumed by GitHub Pages.

Data source: Eastmoney public quote endpoints (no API key required).
The script prefers Eastmoney concept/industry boards for thematic sectors and
uses explicit market indices where the repository configuration supplies them.

If a series does not have enough history for a requested horizon, that horizon
is left blank rather than extrapolated.
"""
from __future__ import annotations

from bisect import bisect_right
from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import json
import math
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "data" / "sectors.json"
OUT_DIR = ROOT / "docs" / "data"
OUT_PATH = OUT_DIR / "latest.json"

UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
SUGGEST_TOKEN = "D43BF722C8E33BDC906FB84D85E326E8"
KLINE_HOSTS = [
    "https://push2his.eastmoney.com",
    "https://91.push2his.eastmoney.com",
    "https://7.push2his.eastmoney.com",
    "https://33.push2his.eastmoney.com",
]
CONCEPT_HOSTS = [
    "https://79.push2.eastmoney.com",
    "https://17.push2.eastmoney.com",
    "https://push2.eastmoney.com",
]
INDUSTRY_HOSTS = [
    "https://17.push2.eastmoney.com",
    "https://79.push2.eastmoney.com",
    "https://push2.eastmoney.com",
]

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


def http_json(url: str, params: dict[str, str] | None = None, retries: int = 3) -> dict:
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
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=18) as resp:
                raw = resp.read()
            return json.loads(raw.decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            last_err = exc
            if attempt + 1 < retries:
                time.sleep(0.7 * (attempt + 1))
    raise RuntimeError(f"request failed: {last_err}")


def fetch_paginated_board_catalog(kind: str) -> list[dict]:
    if kind == "concept":
        hosts = CONCEPT_HOSTS
        fs = "m:90 t:3 f:!50"
    else:
        hosts = INDUSTRY_HOSTS
        fs = "m:90 t:2 f:!50"

    params = {
        "pn": "1",
        "pz": "100",
        "po": "1",
        "np": "1",
        "ut": "bd1d9ddb04089700cf9c27f6f7426281",
        "fltt": "2",
        "invt": "2",
        "fid": "f12",
        "fs": fs,
        "fields": "f12,f14",
    }

    last_error: Exception | None = None
    for host in hosts:
        try:
            rows: list[dict] = []
            page = 1
            while True:
                params["pn"] = str(page)
                payload = http_json(f"{host}/api/qt/clist/get", params)
                data = payload.get("data") or {}
                diff = data.get("diff") or []
                if isinstance(diff, dict):
                    diff = list(diff.values())
                if not diff:
                    break
                for item in diff:
                    code = str(item.get("f12", "")).strip()
                    name = str(item.get("f14", "")).strip()
                    if code and name:
                        rows.append(
                            {
                                "code": code,
                                "name": name,
                                "secid": f"90.{code}",
                                "kind": kind,
                            }
                        )
                total = int(data.get("total") or 0)
                if len(rows) >= total or len(diff) < int(params["pz"]):
                    break
                page += 1
                if page > 20:
                    break
                time.sleep(0.08)
            if rows:
                return rows
        except Exception as exc:
            last_error = exc
    if last_error:
        print(f"[warn] {kind} board catalog unavailable: {last_error}")
    return []


def normalize(text: str) -> str:
    return (
        str(text)
        .strip()
        .lower()
        .replace(" ", "")
        .replace("-", "")
        .replace("_", "")
        .replace("（", "(")
        .replace("）", ")")
        .replace("概念", "")
        .replace("板块", "")
        .replace("行业", "")
    )


def resolve_board(entry: dict, catalog: list[dict]) -> dict | None:
    aliases = entry.get("aliases") or [entry["name"]]
    aliases = [str(x) for x in aliases if str(x).strip()]
    prefer = entry.get("prefer")

    candidates: list[tuple[int, dict]] = []
    for row in catalog:
        rn = normalize(row["name"])
        for i, alias in enumerate(aliases):
            an = normalize(alias)
            if rn == an:
                score = 100 - i
                if prefer and row["kind"] == prefer:
                    score += 10
                candidates.append((score, row))
    if candidates:
        return max(candidates, key=lambda x: x[0])[1]

    for row in catalog:
        rn = normalize(row["name"])
        for i, alias in enumerate(aliases):
            an = normalize(alias)
            if len(an) >= 2 and (an in rn or rn in an):
                score = 60 - i
                if prefer and row["kind"] == prefer:
                    score += 10
                candidates.append((score, row))
    if candidates:
        return max(candidates, key=lambda x: x[0])[1]
    return None


def search_security(query: str) -> list[dict]:
    payload = http_json(
        "https://searchapi.eastmoney.com/api/suggest/get",
        {
            "input": query,
            "type": "14",
            "token": SUGGEST_TOKEN,
            "count": "20",
        },
    )
    data = (payload.get("QuotationCodeTable") or {}).get("Data") or []
    out = []
    for row in data:
        quote_id = str(row.get("QuoteID") or "").strip()
        code = str(row.get("Code") or "").strip()
        name = str(row.get("Name") or "").strip()
        if quote_id and code and name:
            out.append(
                {
                    "secid": quote_id,
                    "code": code,
                    "name": name,
                    "kind": "security",
                }
            )
    return out


def resolve_security(entry: dict) -> dict | None:
    if entry.get("secid"):
        return {
            "secid": str(entry["secid"]),
            "code": str(entry.get("benchmark") or entry["secid"].split(".", 1)[-1]),
            "name": str(entry.get("benchmark_name") or entry["name"]),
            "kind": "security",
        }

    queries = entry.get("queries") or [entry.get("benchmark"), entry["name"]]
    queries = [str(q) for q in queries if q and str(q) != "待绑定"]
    for query in queries:
        try:
            rows = search_security(query)
        except Exception as exc:
            print(f"[warn] search failed for {entry['name']} / {query}: {exc}")
            continue
        if not rows:
            continue
        qn = normalize(query)

        def rank(row: dict) -> tuple[int, int]:
            code_exact = int(str(row["code"]).lower() == str(query).lower())
            name_exact = int(normalize(row["name"]) == qn)
            is_board = int(str(row["secid"]).startswith("90."))
            return (code_exact * 100 + name_exact * 90 - is_board * 30, -len(row["name"]))

        return max(rows, key=rank)
    return None


def fetch_kline(secid: str) -> tuple[str, list[tuple[date, float]]]:
    params = {
        "secid": secid,
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": "101",
        "fqt": "1",
        "beg": "20000101",
        "end": "20500101",
        "smplmt": "10000",
        "lmt": "1000000",
    }
    last_error: Exception | None = None
    for fqt in ("1", "0"):
        params["fqt"] = fqt
        for host in KLINE_HOSTS:
            try:
                payload = http_json(f"{host}/api/qt/stock/kline/get", params, retries=2)
                data = payload.get("data")
                if not isinstance(data, dict):
                    raise RuntimeError(payload.get("msg") or payload.get("dsc") or "empty data")
                klines = data.get("klines") or []
                if not klines:
                    raise RuntimeError("empty klines")
                points: list[tuple[date, float]] = []
                for line in klines:
                    parts = str(line).split(",")
                    if len(parts) < 3:
                        continue
                    try:
                        d = datetime.strptime(parts[0], "%Y-%m-%d").date()
                        close = float(parts[2])
                    except (ValueError, TypeError):
                        continue
                    if math.isfinite(close) and close > 0:
                        points.append((d, close))
                if not points:
                    raise RuntimeError("no valid close prices")
                points.sort(key=lambda x: x[0])
                name = str(data.get("name") or "").strip()
                return name, points
            except Exception as exc:
                last_error = exc
                time.sleep(0.15)
    raise RuntimeError(f"kline unavailable for {secid}: {last_error}")


def shift_months(d: date, months: int) -> date:
    total = d.year * 12 + (d.month - 1) - months
    y, m0 = divmod(total, 12)
    m = m0 + 1
    day = min(d.day, monthrange(y, m)[1])
    return date(y, m, day)


def target_date(latest: date, spec: tuple[str, int]) -> date:
    unit, value = spec
    if unit == "days":
        return latest - timedelta(days=value)
    if unit == "months":
        return shift_months(latest, value)
    if unit == "years":
        return shift_months(latest, value * 12)
    raise ValueError(unit)


def calc_returns(points: list[tuple[date, float]]) -> dict[str, float | None]:
    dates = [d for d, _ in points]
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
        result[label] = round((latest_close / old_close - 1.0) * 100.0, 2)
    return result


def build_item(entry: dict, catalog: list[dict], cache: dict[str, tuple[str, list[tuple[date, float]]]]) -> dict:
    mode = entry.get("mode", "board")
    resolved = resolve_board(entry, catalog) if mode == "board" else resolve_security(entry)
    base = {
        "name": entry["name"],
        "benchmark": "暂无匹配",
        "code": "",
        "source": entry.get("source") or "东方财富公开行情",
        "note": entry.get("note", ""),
        "status": "unavailable",
        "returns": {label: None for label, _ in PERIODS},
        "latest_date": None,
        "start_date": None,
    }
    if not resolved:
        base["note"] = (base["note"] + "；" if base["note"] else "") + "未找到可自动匹配的公开行情"
        return base

    secid = resolved["secid"]
    base["code"] = resolved["code"]
    if resolved["kind"] in {"concept", "industry"}:
        kind_cn = "概念板块" if resolved["kind"] == "concept" else "行业板块"
        base["benchmark"] = f"{resolved['name']} ({resolved['code']})"
        base["source"] = f"东方财富 · {kind_cn}"
    else:
        base["benchmark"] = f"{resolved['name']} ({resolved['code']})"
        if entry.get("source"):
            base["source"] = entry["source"]

    try:
        if secid not in cache:
            cache[secid] = fetch_kline(secid)
            time.sleep(0.12)
        live_name, points = cache[secid]
    except Exception as exc:
        base["status"] = "error"
        base["note"] = (base["note"] + "；" if base["note"] else "") + str(exc)
        return base

    if live_name and resolved["kind"] == "security":
        base["benchmark"] = f"{live_name} ({resolved['code']})"

    returns = calc_returns(points)
    base["returns"] = returns
    base["latest_date"] = points[-1][0].isoformat()
    base["start_date"] = points[0][0].isoformat()
    available = sum(v is not None for v in returns.values())
    if available == len(PERIODS):
        base["status"] = "ok"
    elif available > 0:
        base["status"] = "partial"
    else:
        base["status"] = "short_history"
    return base


def main() -> None:
    sectors = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    concept = fetch_paginated_board_catalog("concept")
    industry = fetch_paginated_board_catalog("industry")
    catalog = concept + industry
    print(f"[info] board catalog: concept={len(concept)}, industry={len(industry)}")

    cache: dict[str, tuple[str, list[tuple[date, float]]]] = {}
    output = []
    for idx, entry in enumerate(sectors, 1):
        item = build_item(entry, catalog, cache)
        output.append(item)
        print(
            f"[{idx:02d}/{len(sectors)}] {entry['name']}: "
            f"{item['benchmark']} / {item['status']} / {item['latest_date'] or '-'}"
        )

    successful = sum(x["status"] in {"ok", "partial", "short_history"} for x in output)
    full = sum(x["status"] == "ok" for x in output)
    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "status": "ok" if successful else "degraded",
        "periods": [label for label, _ in PERIODS],
        "summary": {
            "total": len(output),
            "resolved": successful,
            "full_history": full,
        },
        "sectors": output,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[info] wrote {OUT_PATH} ({successful}/{len(output)} resolved)")


if __name__ == "__main__":
    main()
