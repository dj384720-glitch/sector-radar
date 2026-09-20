#!/usr/bin/env python3
"""Build docs/data/latest.json using Tencent Finance with Yahoo Finance fallback.

Primary source:
- Tencent smartbox search and public K-line endpoints.
Fallback:
- Yahoo Finance public chart/search endpoints.

Theme rows use a listed ETF proxy when no single authoritative long-history
sector index is available. The page labels the proxy and leaves unavailable
long horizons blank instead of extrapolating.
"""
from __future__ import annotations

from bisect import bisect_right
from calendar import monthrange
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import json
import math
import re
import time
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "data" / "sectors.json"
OUT_DIR = ROOT / "docs" / "data"
OUT_PATH = OUT_DIR / "latest.json"

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"

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

DIRECT = {
    "半导体": ("sh512480", "半导体ETF国联安", "ETF代理"),
    "半导体材料设备": ("sz159516", "半导体设备材料ETF", "ETF代理"),
    "机器人": ("sh562500", "机器人ETF", "ETF代理"),
    "人工智能": ("sh515070", "人工智能ETF", "ETF代理"),
    "云计算": ("sh516510", "云计算ETF", "ETF代理"),
    "房地产": ("sz159768", "房地产ETF", "ETF代理"),
    "海外医药": ("sh513060", "恒生医疗ETF博时", "ETF代理"),
    "白酒": ("sh512690", "酒ETF鹏华", "ETF代理"),
    "油气资源": ("sz159697", "油气ETF", "ETF代理"),
    "汽车整车": ("sh516110", "汽车ETF国泰", "ETF代理"),
    "红利": ("sh000922", "中证红利指数", "指数"),
    "沪深300": ("sh000300", "沪深300指数", "指数"),
    "中证500": ("sh000905", "中证500指数", "指数"),
    "上证50": ("sh000016", "上证50指数", "指数"),
    "科创板": ("sh000688", "科创50指数", "指数"),
    "创业板": ("sz399006", "创业板指", "指数"),
    "北证": ("bj899050", "北证50指数", "指数"),
}

FALLBACK_PROXY = {
    "存储芯片": ("sh512480", "半导体ETF国联安", "半导体ETF代理"),
    "AI应用": ("sh515070", "人工智能ETF", "人工智能ETF代理"),
    "算力租赁": ("sh516510", "云计算ETF", "云计算ETF代理"),
    "国产算力": ("sh515070", "人工智能ETF", "人工智能ETF代理"),
    "CPO": ("sh515880", "通信ETF", "通信ETF代理"),
    "PCB": ("sh512480", "半导体ETF国联安", "电子产业ETF代理"),
    "消费电子": ("sh512480", "半导体ETF国联安", "电子产业ETF代理"),
    "CXO": ("sh512170", "医疗ETF", "医疗ETF代理"),
    "固态电池": ("sz159755", "电池ETF", "电池ETF代理"),
    "商业航天": ("sh512660", "军工ETF", "军工ETF代理"),
    "食品饮料": ("sz159928", "消费ETF", "主要消费ETF代理"),
}


def http_bytes(url: str, timeout: float = 8.0, retries: int = 2, encoding: str | None = None):
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": UA,
                    "Accept": "application/json,text/plain,*/*",
                    "Referer": "https://finance.qq.com/",
                },
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
            if encoding:
                return raw.decode(encoding, errors="ignore")
            return raw
        except Exception as exc:
            last = exc
            if attempt + 1 < retries:
                time.sleep(0.35 * (attempt + 1))
    raise RuntimeError(str(last))


def http_json(url: str, timeout: float = 8.0, retries: int = 2):
    raw = http_bytes(url, timeout=timeout, retries=retries)
    return json.loads(raw.decode("utf-8", errors="ignore"))


def normalize(text: str) -> str:
    s = str(text or "").lower()
    for token in (" ", "-", "_", "（", "）", "(", ")", "概念", "主题", "指数", "etf", "交易型开放式", "基金"):
        s = s.replace(token, "")
    return s


def is_etf_code(market: str, code: str) -> bool:
    if market == "sh":
        return code.startswith(("51", "56", "58"))
    if market == "sz":
        return code.startswith("15")
    return False


def parse_tencent_search_rows(payload: dict) -> list[dict]:
    rows = []
    data = payload.get("data") or {}
    for key in ("stock", "fund"):
        for row in data.get(key) or []:
            if not isinstance(row, list) or len(row) < 3:
                continue
            market, code, name = str(row[0]).lower(), str(row[1]), str(row[2])
            if market in {"sh", "sz", "bj", "hk"} and code:
                rows.append({"market": market, "code": code, "name": name, "api_code": market + code})
    return rows


def tencent_search(term: str) -> list[dict]:
    q = urllib.parse.quote(term)
    urls = [
        f"https://proxy.finance.qq.com/ifzqgtimg/appstock/smartbox/search/get?q={q}",
        f"https://smartbox.gtimg.cn/s3/?v=2&t=all&c=1&q={q}",
    ]
    try:
        payload = http_json(urls[0], timeout=6, retries=1)
        rows = parse_tencent_search_rows(payload)
        if rows:
            return rows
    except Exception:
        pass
    try:
        text = http_bytes(urls[1], timeout=6, retries=1, encoding="gb18030")
        m = re.search(r'v_hint="(.*)"', text)
        if not m:
            return []
        rows = []
        for chunk in m.group(1).split("^"):
            parts = chunk.split("~")
            if len(parts) >= 3 and parts[0] in {"sh", "sz", "bj", "hk"}:
                rows.append({
                    "market": parts[0],
                    "code": parts[1],
                    "name": parts[2],
                    "api_code": parts[0] + parts[1],
                })
        return rows
    except Exception:
        return []


def score_match(name: str, aliases: list[str]) -> int:
    nn = normalize(name)
    best = 0
    for idx, alias in enumerate(aliases):
        an = normalize(alias)
        if not an:
            continue
        score = 0
        if nn == an:
            score = 120
        elif an in nn:
            score = 90
        elif nn in an and len(nn) >= 2:
            score = 70
        else:
            overlap = sum(1 for ch in set(an) if ch in nn)
            score = min(40, overlap * 6)
        best = max(best, score - idx)
    if "etf" in name.lower():
        best += 15
    return best


def search_terms(entry: dict) -> list[str]:
    terms = [entry.get("name", "")]
    terms += [str(x) for x in entry.get("aliases") or []]
    terms += [str(x) for x in entry.get("queries") or [] if not str(x).isdigit()]
    seen, out = set(), []
    for t in terms:
        t = t.strip()
        if not t:
            continue
        for q in (t + "ETF", t):
            if q not in seen:
                seen.add(q)
                out.append(q)
    return out[:6]


def resolve_tencent_proxy(entry: dict) -> dict | None:
    aliases = [entry["name"]] + [str(x) for x in entry.get("aliases") or []]
    candidates = []
    for term in search_terms(entry):
        for row in tencent_search(term):
            if not is_etf_code(row["market"], row["code"]):
                continue
            score = score_match(row["name"], aliases)
            if "ETF" in term.upper():
                score += 5
            candidates.append((score, row))
        if candidates and max(x[0] for x in candidates) >= 90:
            break
    if not candidates:
        return None
    score, row = max(candidates, key=lambda x: x[0])
    if score < 20:
        return None
    return {"provider": "tencent", "code": row["api_code"], "name": row["name"], "kind": "ETF代理"}


def yahoo_search(term: str) -> list[dict]:
    url = "https://query1.finance.yahoo.com/v1/finance/search?" + urllib.parse.urlencode({
        "q": term,
        "quotesCount": "12",
        "newsCount": "0",
    })
    payload = http_json(url, timeout=7, retries=1)
    out = []
    for q in payload.get("quotes") or []:
        symbol = str(q.get("symbol") or "")
        quote_type = str(q.get("quoteType") or "").upper()
        name = str(q.get("shortname") or q.get("longname") or symbol)
        if quote_type in {"ETF", "INDEX"} and (
            symbol.endswith(".SS") or symbol.endswith(".SZ") or symbol.endswith(".BJ") or symbol.endswith(".HK")
        ):
            out.append({"symbol": symbol, "name": name, "quote_type": quote_type})
    return out


def resolve_yahoo_proxy(entry: dict) -> dict | None:
    aliases = [entry["name"]] + [str(x) for x in entry.get("aliases") or []]
    candidates = []
    for term in search_terms(entry):
        try:
            rows = yahoo_search(term)
        except Exception:
            continue
        for row in rows:
            score = score_match(row["name"], aliases)
            candidates.append((score, row))
        if candidates and max(x[0] for x in candidates) >= 90:
            break
    if not candidates:
        return None
    score, row = max(candidates, key=lambda x: x[0])
    if score < 20:
        return None
    return {"provider": "yahoo", "symbol": row["symbol"], "name": row["name"], "kind": "ETF代理"}


def resolve(entry: dict) -> dict:
    name = entry["name"]
    if name in DIRECT:
        code, label, kind = DIRECT[name]
        return {"provider": "tencent", "code": code, "name": label, "kind": kind}
    hit = resolve_tencent_proxy(entry)
    if hit:
        return hit
    hit = resolve_yahoo_proxy(entry)
    if hit:
        return hit
    if name in FALLBACK_PROXY:
        code, label, kind = FALLBACK_PROXY[name]
        return {"provider": "tencent", "code": code, "name": label, "kind": kind, "fallback": True}
    return {"provider": "none", "name": "暂无匹配", "kind": "未匹配"}


def parse_tencent_rows(payload: dict, code: str, period: str, adjusted: bool) -> list[tuple[date, float]]:
    block = (payload.get("data") or {}).get(code) or {}
    keys = (["qfq" + period, period] if adjusted else [period])
    raw_rows = []
    for key in keys:
        if isinstance(block.get(key), list):
            raw_rows = block[key]
            break
    out = []
    for row in raw_rows:
        if not isinstance(row, list) or len(row) < 3:
            continue
        try:
            d = datetime.strptime(str(row[0]), "%Y-%m-%d").date()
            c = float(row[2])
        except Exception:
            continue
        if math.isfinite(c) and c > 0:
            out.append((d, c))
    return out


def fetch_tencent_series(code: str) -> list[tuple[date, float]]:
    all_points = {}
    failures = []
    for period, count in (("day", 500), ("week", 800), ("month", 240)):
        for adjusted in (True, False):
            endpoint = "fqkline/get" if adjusted else "kline/kline"
            adjust = ",qfq" if adjusted else ""
            url = f"https://web.ifzq.gtimg.cn/appstock/app/{endpoint}?param={code},{period},,,{count}{adjust}"
            try:
                payload = http_json(url, timeout=8, retries=1)
                rows = parse_tencent_rows(payload, code, period, adjusted)
                if rows:
                    for d, c in rows:
                        all_points[d] = c
                    break
            except Exception as exc:
                failures.append(f"{period}:{exc}")
    points = sorted(all_points.items())
    if len(points) < 2:
        raise RuntimeError("腾讯K线无有效数据" + (f" ({failures[-1]})" if failures else ""))
    return points


def code_to_yahoo(code: str) -> str | None:
    if code.startswith("sh") and len(code) == 8:
        return code[2:] + ".SS"
    if code.startswith("sz") and len(code) == 8:
        return code[2:] + ".SZ"
    if code.startswith("bj") and len(code) == 8:
        return code[2:] + ".BJ"
    if code.startswith("hk"):
        return code[2:].zfill(4) + ".HK"
    return None


def fetch_yahoo_series(symbol: str) -> list[tuple[date, float]]:
    enc = urllib.parse.quote(symbol)
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{enc}"
        "?range=10y&interval=1d&events=div%2Csplits&includeAdjustedClose=true"
    )
    payload = http_json(url, timeout=10, retries=2)
    result = ((payload.get("chart") or {}).get("result") or [None])[0]
    if not result:
        raise RuntimeError("Yahoo chart empty")
    ts = result.get("timestamp") or []
    ind = result.get("indicators") or {}
    adj = ((ind.get("adjclose") or [{}])[0]).get("adjclose") or []
    close = ((ind.get("quote") or [{}])[0]).get("close") or []
    vals = adj if len(adj) == len(ts) else close
    out = []
    for t, v in zip(ts, vals):
        if v is None:
            continue
        try:
            c = float(v)
            d = datetime.fromtimestamp(int(t), tz=timezone.utc).date()
        except Exception:
            continue
        if math.isfinite(c) and c > 0:
            out.append((d, c))
    out.sort(key=lambda x: x[0])
    if len(out) < 2:
        raise RuntimeError("Yahoo chart无有效数据")
    return out


def fetch_sina_series(symbol: str) -> list[tuple[date, float]]:
    url = "https://quotes.sina.cn/cn/api/json_v2.php/CN_MarketDataService.getKLineData?" + urllib.parse.urlencode({
        "symbol": symbol,
        "scale": "240",
        "ma": "no",
        "datalen": "1023",
    })
    payload = http_json(url, timeout=9, retries=2)
    if not isinstance(payload, list):
        raise RuntimeError("Sina K线响应异常")
    out = []
    for row in payload:
        try:
            day = str(row.get("day") or "").split(" ", 1)[0]
            d = datetime.strptime(day, "%Y-%m-%d").date()
            c = float(row.get("close"))
        except Exception:
            continue
        if math.isfinite(c) and c > 0:
            out.append((d, c))
    out.sort(key=lambda x: x[0])
    if len(out) < 2:
        raise RuntimeError("Sina K线无有效数据")
    return out


def fetch_series(resolved: dict) -> tuple[list[tuple[date, float]], str]:
    errors = []
    if resolved.get("provider") == "tencent":
        code = resolved["code"]
        try:
            return fetch_tencent_series(code), "腾讯财经公开K线"
        except Exception as exc:
            errors.append(f"Tencent: {exc}")
        symbol = code_to_yahoo(code)
        if symbol:
            try:
                return fetch_yahoo_series(symbol), "Yahoo Finance公开行情（腾讯失败后回退）"
            except Exception as exc:
                errors.append(f"Yahoo: {exc}")
        if code.startswith("bj"):
            try:
                return fetch_sina_series(code), "新浪财经公开K线（腾讯/Yahoo失败后回退）"
            except Exception as exc:
                errors.append(f"Sina: {exc}")
    elif resolved.get("provider") == "yahoo":
        try:
            return fetch_yahoo_series(resolved["symbol"]), "Yahoo Finance公开行情"
        except Exception as exc:
            errors.append(f"Yahoo: {exc}")
    raise RuntimeError("；".join(errors) or "没有可用数据源")


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


def build_item(entry: dict) -> dict:
    resolved = resolve(entry)
    item = {
        "name": entry["name"],
        "benchmark": resolved.get("name", "暂无匹配"),
        "code": resolved.get("code") or resolved.get("symbol") or "",
        "source": "",
        "note": entry.get("note", ""),
        "status": "unavailable",
        "returns": {label: None for label, _ in PERIODS},
        "latest_date": None,
        "start_date": None,
    }
    if resolved.get("provider") == "none":
        item["source"] = "未找到可用指数/ETF代理"
        item["note"] = (item["note"] + "；" if item["note"] else "") + "腾讯与Yahoo均未匹配到合适标的"
        return item

    kind = resolved.get("kind", "")
    if kind == "ETF代理":
        item["benchmark"] = f"{resolved['name']} · ETF代理"
    elif "代理" in kind:
        item["benchmark"] = f"{resolved['name']} · {kind}"
    else:
        item["benchmark"] = resolved["name"]

    try:
        points, source = fetch_series(resolved)
        item["source"] = source
    except Exception as exc:
        item["status"] = "error"
        item["source"] = "腾讯财经 / Yahoo Finance"
        item["note"] = (item["note"] + "；" if item["note"] else "") + str(exc)[:240]
        return item

    item["returns"] = calc_returns(points)
    item["latest_date"] = points[-1][0].isoformat()
    item["start_date"] = points[0][0].isoformat()
    available = sum(v is not None for v in item["returns"].values())
    if available == len(PERIODS):
        item["status"] = "ok"
    elif available > 0:
        item["status"] = "partial"
    else:
        item["status"] = "short_history"

    if kind and kind != "指数":
        suffix = f"口径：{kind}，用于代表该主题的可交易公开价格序列"
        item["note"] = (item["note"] + "；" if item["note"] else "") + suffix
    return item


def main() -> None:
    sectors = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    results = [None] * len(sectors)
    with ThreadPoolExecutor(max_workers=8) as pool:
        jobs = {pool.submit(build_item, entry): i for i, entry in enumerate(sectors)}
        for fut in as_completed(jobs):
            idx = jobs[fut]
            try:
                results[idx] = fut.result()
            except Exception as exc:
                entry = sectors[idx]
                results[idx] = {
                    "name": entry["name"],
                    "benchmark": "暂无匹配",
                    "code": "",
                    "source": "腾讯财经 / Yahoo Finance",
                    "note": f"任务异常：{exc}",
                    "status": "error",
                    "returns": {label: None for label, _ in PERIODS},
                    "latest_date": None,
                    "start_date": None,
                }

    resolved_count = sum(1 for x in results if x["status"] in {"ok", "partial", "short_history"})
    full_count = sum(1 for x in results if x["status"] == "ok")
    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "status": "ok" if resolved_count else "source_unavailable",
        "periods": [label for label, _ in PERIODS],
        "summary": {
            "total": len(results),
            "resolved": resolved_count,
            "full_history": full_count,
        },
        "sectors": results,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[done] wrote {OUT_PATH}; resolved={resolved_count}/{len(results)} full={full_count}")


if __name__ == "__main__":
    main()
