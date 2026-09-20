#!/usr/bin/env python3
"""Build the Sector Radar dataset with chart-ready history.

Primary source: Tencent Finance public K-line endpoints.
Fallbacks: Yahoo Finance, then Sina Finance for Beijing Stock Exchange symbols.

Each configured sector is bound to an explicit public index or ETF proxy so the
result is deterministic. The output contains both multi-period returns and a
price history used by the left-navigation detail charts on GitHub Pages.
"""
from __future__ import annotations

from bisect import bisect_right
from calendar import monthrange
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import json
import math
import time
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "data" / "sectors.json"
OUT_DIR = ROOT / "docs" / "data"
OUT_PATH = OUT_DIR / "latest.json"
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

# name -> (Tencent symbol, display name, methodology)
DIRECT = {
    "半导体": ("sh512480", "半导体ETF国联安", "ETF代理"),
    "半导体材料设备": ("sz159516", "半导体设备材料ETF", "ETF代理"),
    "存储芯片": ("sh512480", "半导体ETF国联安", "半导体ETF代理"),
    "机器人": ("sh562500", "机器人ETF", "ETF代理"),
    "人工智能": ("sh515070", "人工智能ETF", "ETF代理"),
    "AI应用": ("sh515070", "人工智能ETF", "人工智能ETF代理"),
    "算力租赁": ("sz158041", "创业板算力ETF华夏", "ETF代理"),
    "国产算力": ("sh515070", "人工智能ETF", "人工智能ETF代理"),
    "云计算": ("sh516510", "云计算ETF", "ETF代理"),
    "CPO": ("sh515880", "通信ETF", "通信ETF代理"),
    "PCB": ("sh512480", "半导体ETF国联安", "电子产业ETF代理"),
    "通信": ("sh515880", "通信ETF国泰", "ETF代理"),
    "消费电子": ("sz159732", "消费电子ETF华夏", "ETF代理"),
    "金融科技": ("sz159851", "金融科技ETF华宝", "ETF代理"),
    "证券保险": ("sh512070", "证券保险ETF易方达", "ETF代理"),
    "银行": ("sh512800", "银行ETF华宝", "ETF代理"),
    "房地产": ("sz159768", "房地产ETF", "ETF代理"),
    "医药": ("sh512010", "医药ETF易方达", "ETF代理"),
    "医疗": ("sh512170", "医疗ETF华宝", "ETF代理"),
    "创新药": ("sz159992", "创新药ETF银华", "ETF代理"),
    "海外医药": ("sh513060", "恒生医疗ETF博时", "ETF代理"),
    "CXO": ("sh512170", "医疗ETF", "医疗ETF代理"),
    "白酒": ("sh512690", "酒ETF鹏华", "ETF代理"),
    "食品饮料": ("sh515170", "食品饮料ETF华夏", "ETF代理"),
    "消费": ("sz159928", "消费ETF汇添富", "ETF代理"),
    "煤炭": ("sh515220", "煤炭ETF国泰", "ETF代理"),
    "有色金属": ("sh512400", "有色金属ETF南方", "ETF代理"),
    "黄金": ("sh518880", "黄金ETF华安", "ETF代理"),
    "油气资源": ("sz159697", "油气ETF", "ETF代理"),
    "电力": ("sz159611", "电力ETF广发", "ETF代理"),
    "新能源": ("sh516160", "新能源ETF南方", "ETF代理"),
    "光伏": ("sh515790", "光伏ETF华泰柏瑞", "ETF代理"),
    "储能": ("sz159566", "储能电池ETF易方达", "ETF代理"),
    "固态电池": ("sz159755", "电池ETF", "电池ETF代理"),
    "汽车整车": ("sh516110", "汽车ETF国泰", "ETF代理"),
    "军工": ("sh512660", "军工ETF国泰", "ETF代理"),
    "商业航天": ("sh512660", "军工ETF", "军工ETF代理"),
    "红利": ("sh000922", "中证红利指数", "指数"),
    "沪深300": ("sh000300", "沪深300指数", "指数"),
    "中证500": ("sh000905", "中证500指数", "指数"),
    "上证50": ("sh000016", "上证50指数", "指数"),
    "科创板": ("sh000688", "科创50指数", "指数"),
    "创业板": ("sz399006", "创业板指", "指数"),
    "北证": ("bj899050", "北证50指数", "指数"),
    "恒生科技": ("sh513180", "恒生科技ETF华夏", "ETF代理"),
    "港股红利": ("sh513690", "港股红利ETF博时", "ETF代理"),
}


def http_bytes(url: str, timeout: float = 8.0, retries: int = 2, referer: str = "https://finance.qq.com/") -> bytes:
    last: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": UA,
                    "Accept": "application/json,text/plain,*/*",
                    "Referer": referer,
                },
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except Exception as exc:
            last = exc
            if attempt + 1 < retries:
                time.sleep(0.35 * (attempt + 1))
    raise RuntimeError(str(last))


def http_json(url: str, timeout: float = 8.0, retries: int = 2, referer: str = "https://finance.qq.com/"):
    raw = http_bytes(url, timeout=timeout, retries=retries, referer=referer)
    return json.loads(raw.decode("utf-8", errors="ignore"))


def parse_tencent_rows(payload: dict, code: str, period: str, adjusted: bool) -> list[tuple[date, float]]:
    block = (payload.get("data") or {}).get(code) or {}
    keys = (["qfq" + period, period] if adjusted else [period])
    raw_rows = []
    for key in keys:
        if isinstance(block.get(key), list):
            raw_rows = block[key]
            break
    out: list[tuple[date, float]] = []
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
    all_points: dict[date, float] = {}
    failures: list[str] = []
    # Dense daily data for short/medium ranges, plus weekly/monthly history for 10y charts.
    for period, count in (("day", 520), ("week", 800), ("month", 240)):
        success = False
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
                    success = True
                    break
            except Exception as exc:
                failures.append(f"{period}:{exc}")
        if not success:
            continue
    points = sorted(all_points.items())
    if len(points) < 2:
        tail = f" ({failures[-1]})" if failures else ""
        raise RuntimeError("腾讯K线无有效数据" + tail)
    return points


def code_to_yahoo(code: str) -> str | None:
    if code.startswith("sh") and len(code) == 8:
        return code[2:] + ".SS"
    if code.startswith("sz") and len(code) == 8:
        return code[2:] + ".SZ"
    if code.startswith("bj") and len(code) == 8:
        return code[2:] + ".BJ"
    return None


def fetch_yahoo_series(symbol: str) -> list[tuple[date, float]]:
    enc = urllib.parse.quote(symbol)
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{enc}"
        "?range=10y&interval=1d&events=div%2Csplits&includeAdjustedClose=true"
    )
    payload = http_json(url, timeout=10, retries=2, referer="https://finance.yahoo.com/")
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
    return out


def fetch_sina_series(symbol: str) -> list[tuple[date, float]]:
    url = "https://quotes.sina.cn/cn/api/json_v2.php/CN_MarketDataService.getKLineData?" + urllib.parse.urlencode({
        "symbol": symbol,
        "scale": "240",
        "ma": "no",
        "datalen": "1023",
    })
    payload = http_json(url, timeout=9, retries=2, referer="https://finance.sina.com.cn/")
    if not isinstance(payload, list):
        raise RuntimeError("Sina K线响应异常")
    out: list[tuple[date, float]] = []
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


def fetch_series(code: str) -> tuple[list[tuple[date, float]], str]:
    errors: list[str] = []
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
    if not points:
        return []
    latest = points[-1][0]
    cutoff = shift_months(latest, 121)  # a little extra so the 10y boundary is visible
    rows = [[d.isoformat(), round(c, 6)] for d, c in points if d >= cutoff]
    # Keep the payload lean if a fallback source supplies dense 10y daily history.
    if len(rows) > 1900:
        step = max(1, len(rows) // 1800)
        sampled = rows[::step]
        if sampled[-1][0] != rows[-1][0]:
            sampled.append(rows[-1])
        rows = sampled
    return rows


def build_item(entry: dict, fetched: dict[str, tuple[list[tuple[date, float]], str] | Exception]) -> dict:
    name = entry["name"]
    binding = DIRECT.get(name)
    item = {
        "name": name,
        "benchmark": "暂无匹配",
        "code": "",
        "source": "",
        "note": entry.get("note", ""),
        "status": "unavailable",
        "returns": {label: None for label, _ in PERIODS},
        "latest_date": None,
        "start_date": None,
        "history": [],
    }
    if not binding:
        item["source"] = "未配置公开指数/ETF代理"
        item["note"] = (item["note"] + "；" if item["note"] else "") + "该板块尚未配置固定公开代理"
        return item

    code, label, kind = binding
    item["code"] = code
    item["benchmark"] = label if kind == "指数" else f"{label} · {kind}"
    result = fetched.get(code)
    if isinstance(result, Exception) or result is None:
        item["status"] = "error"
        item["source"] = "腾讯财经 / Yahoo Finance / 新浪财经"
        item["note"] = (item["note"] + "；" if item["note"] else "") + str(result or "行情抓取失败")[:260]
        return item

    points, source = result
    item["source"] = source
    item["returns"] = calc_returns(points)
    item["latest_date"] = points[-1][0].isoformat()
    item["start_date"] = points[0][0].isoformat()
    item["history"] = chart_history(points)
    available = sum(v is not None for v in item["returns"].values())
    if available == len(PERIODS):
        item["status"] = "ok"
    elif available > 0:
        item["status"] = "partial"
    else:
        item["status"] = "short_history"

    if kind != "指数":
        suffix = f"口径：{kind}，用于代表该主题的可交易公开价格序列"
        item["note"] = (item["note"] + "；" if item["note"] else "") + suffix
    return item


def main() -> None:
    sectors = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    codes = sorted({DIRECT[x["name"]][0] for x in sectors if x.get("name") in DIRECT})
    fetched: dict[str, tuple[list[tuple[date, float]], str] | Exception] = {}

    with ThreadPoolExecutor(max_workers=8) as pool:
        jobs = {pool.submit(fetch_series, code): code for code in codes}
        for fut in as_completed(jobs):
            code = jobs[fut]
            try:
                fetched[code] = fut.result()
            except Exception as exc:
                fetched[code] = exc
                print(f"[warn] {code}: {exc}")

    results = [build_item(entry, fetched) for entry in sectors]
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
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"[done] wrote {OUT_PATH}; resolved={resolved_count}/{len(results)} full={full_count}")


if __name__ == "__main__":
    main()
