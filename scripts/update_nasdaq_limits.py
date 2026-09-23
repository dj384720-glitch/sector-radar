#!/usr/bin/env python3
"""Build current purchase-limit status and trailing returns for Nasdaq-related RMB off-exchange funds.

The fund universe comes from Eastmoney's public fund directory. For each matching
RMB off-exchange share, FundRateInfo provides purchase status (SGZT), maximum
subscription amount (MAXSG), minimum subscription (MINSG), and redemption status
(SHZT). A public net-worth curve is used to calculate trailing 1/3/5/10 year
cumulative returns. Pure exchange ETFs and USD shares are excluded because their
trading/currency limits are not comparable with RMB off-exchange daily limits.
"""
from __future__ import annotations

from bisect import bisect_right
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
import json
import re
import ssl
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "data" / "nasdaq_limits.json"
TZ = timezone(timedelta(hours=8))
UA_DESKTOP = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/130 Safari/537.36"
UA_MOBILE = "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/130 Mobile Safari/537.36"
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE
UNIVERSE_URL = "https://fund.eastmoney.com/js/fundcode_search.js"
RATE_URL = "https://fundmobapi.eastmoney.com/FundMApi/FundRateInfo.ashx"
TREND_URL = "https://fund.eastmoney.com/pingzhongdata/{code}.js?v={stamp}"
ON_EXCHANGE_PREFIX = ("15", "51", "52", "56", "58")
NASDAQ_RE = re.compile(r"纳斯达克|纳指|NASDAQ", re.I)
USD_RE = re.compile(r"美元|美汇|美钞|现汇|现钞", re.I)
SHARE_RE = re.compile(r"([ACDEFI])(?:类|份额)?(?:\(?(?:人民币)\)?)?$", re.I)
MAX_WORKERS = 8
PERIODS = (1, 3, 5, 10)


def http_get(url: str, *, ua: str, timeout: int = 12) -> str | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": ua, "Referer": "https://fund.eastmoney.com/"})
        with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as resp:
            return resp.read().decode("utf-8", "ignore")
    except (urllib.error.URLError, OSError, TimeoutError, ValueError):
        return None


def parse_number(value):
    if value is None:
        return None
    text = str(value).replace(",", "").strip()
    if not text or text in {"--", "-"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def share_class(name: str) -> str:
    text = name.replace("（", "(").replace("）", ")").strip()
    m = SHARE_RE.search(text)
    return m.group(1).upper() if m else "-"


def fetch_universe() -> list[dict[str, str]]:
    body = http_get(UNIVERSE_URL, ua=UA_DESKTOP, timeout=15)
    if not body:
        return []
    start, end = body.find("["), body.rfind("]")
    if start < 0 or end <= start:
        return []
    try:
        rows = json.loads(body[start : end + 1])
    except Exception:
        return []
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, list) or len(row) < 3:
            continue
        code, name = str(row[0]), str(row[2])
        if code in seen or not re.fullmatch(r"\d{6}", code):
            continue
        if not NASDAQ_RE.search(name):
            continue
        if code.startswith(ON_EXCHANGE_PREFIX):
            continue
        if USD_RE.search(name):
            continue
        seen.add(code)
        out.append({"code": code, "name": name, "share_class": share_class(name)})
    return out


def fetch_rate(entry: dict[str, str]) -> dict | None:
    params = urlencode({
        "FCODE": entry["code"],
        "deviceid": "sector-radar",
        "plat": "Android",
        "product": "EFund",
        "version": "6.5.5",
    })
    body = http_get(RATE_URL + "?" + params, ua=UA_MOBILE, timeout=10)
    if not body:
        return None
    try:
        payload = json.loads(body)
    except Exception:
        return None
    data = payload.get("Datas")
    return data if isinstance(data, dict) else None


def extract_js_array(body: str, name: str):
    """Extract one JavaScript array assignment with bracket matching.

    Eastmoney's accumulated-NAV series is an array of arrays, so a non-greedy
    regular expression would stop at the first inner closing bracket.
    """
    if not body:
        return None
    m = re.search(rf"(?:var\s+)?{re.escape(name)}\s*=\s*", body)
    if not m:
        return None
    start = body.find("[", m.end())
    if start < 0:
        return None
    depth = 0
    in_string = False
    escape = False
    quote = ""
    end = -1
    for i in range(start, len(body)):
        ch = body[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == quote:
                in_string = False
            continue
        if ch in {'"', "'"}:
            in_string = True
            quote = ch
            continue
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end <= start:
        return None
    try:
        return json.loads(body[start:end])
    except Exception:
        return None


def fetch_curve(code: str) -> list[tuple[int, float]]:
    body = http_get(
        TREND_URL.format(code=code, stamp=int(datetime.now().timestamp() * 1000)),
        ua=UA_DESKTOP,
        timeout=12,
    )
    if not body:
        return []
    # Accumulated NAV is preferred because it handles cash distributions better.
    ac = extract_js_array(body, "Data_ACWorthTrend")
    points: list[tuple[int, float]] = []
    if isinstance(ac, list):
        for item in ac:
            if isinstance(item, list) and len(item) >= 2:
                try:
                    ts, value = int(item[0]), float(item[1])
                    if value > 0:
                        points.append((ts, value))
                except (TypeError, ValueError):
                    pass
    if not points:
        nw = extract_js_array(body, "Data_netWorthTrend")
        if isinstance(nw, list):
            for item in nw:
                if not isinstance(item, dict):
                    continue
                try:
                    ts, value = int(item.get("x")), float(item.get("y"))
                    if value > 0:
                        points.append((ts, value))
                except (TypeError, ValueError):
                    pass
    points.sort(key=lambda x: x[0])
    dedup: dict[int, float] = {}
    for ts, value in points:
        dedup[ts] = value
    return sorted(dedup.items())


def years_ago(dt: datetime, years: int) -> datetime:
    try:
        return dt.replace(year=dt.year - years)
    except ValueError:
        return dt.replace(year=dt.year - years, day=28)


def trailing_returns(points: list[tuple[int, float]]) -> dict[str, float | None]:
    out = {f"return_{y}y": None for y in PERIODS}
    if len(points) < 2:
        return out
    latest_ts, latest_value = points[-1]
    if latest_value <= 0:
        return out
    dates = [x[0] for x in points]
    latest_dt = datetime.fromtimestamp(latest_ts / 1000, tz=timezone.utc)
    first_dt = datetime.fromtimestamp(points[0][0] / 1000, tz=timezone.utc)
    for years in PERIODS:
        target = years_ago(latest_dt, years)
        # Do not label a shorter history as a full N-year return.
        if first_dt > target + timedelta(days=31):
            continue
        target_ts = int(target.timestamp() * 1000)
        idx = bisect_right(dates, target_ts) - 1
        if idx < 0:
            continue
        base_ts, base_value = points[idx]
        # A very stale predecessor would distort the trailing-period label.
        if target_ts - base_ts > 45 * 86400 * 1000 or base_value <= 0:
            continue
        out[f"return_{years}y"] = round((latest_value / base_value - 1.0) * 100.0, 2)
    out["curve_latest_date"] = latest_dt.astimezone(TZ).strftime("%Y-%m-%d")
    out["curve_latest_value"] = round(latest_value, 6)
    return out


def normalize_status(raw: str, max_buy) -> str:
    text = (raw or "").strip()
    if "暂停" in text or "封闭" in text:
        return "暂停申购"
    if "限" in text or "大额" in text:
        return "限大额"
    if max_buy is not None and 0 < max_buy < 100_000_000:
        return "限大额"
    if "开放" in text:
        return "开放申购"
    if text:
        return text
    return "开放申购"


def read_previous() -> dict:
    try:
        return json.loads(OUT.read_text(encoding="utf-8"))
    except Exception:
        return {}


def build_record(entry: dict[str, str], old_map: dict[str, dict]) -> tuple[dict, bool]:
    data = fetch_rate(entry)
    old = old_map.get(entry["code"], {})
    if not data:
        if old:
            rec = dict(old)
            rec.update(entry)
            rec["stale"] = True
            return rec, False
        return {
            **entry,
            "status": "数据暂缺",
            "max_buy": None,
            "min_buy": None,
            "min_dca": None,
            "redemption_status": "",
            "source": "天天基金公开接口",
            "source_url": f"https://fund.eastmoney.com/{entry['code']}.html",
            "stale": True,
            **{f"return_{y}y": None for y in PERIODS},
        }, False

    max_buy = parse_number(data.get("MAXSG"))
    status = normalize_status(str(data.get("SGZT") or ""), max_buy)
    if status == "暂停申购":
        max_buy = None
    perf = trailing_returns(fetch_curve(entry["code"]))
    if not any(perf.get(f"return_{y}y") is not None for y in PERIODS) and old:
        # Keep the previous valid curve metrics if the trend endpoint times out.
        for y in PERIODS:
            key = f"return_{y}y"
            if old.get(key) is not None:
                perf[key] = old.get(key)
        if old.get("curve_latest_date"):
            perf["curve_latest_date"] = old.get("curve_latest_date")
            perf["curve_latest_value"] = old.get("curve_latest_value")
    return {
        **entry,
        "status": status,
        "max_buy": max_buy,
        "min_buy": parse_number(data.get("MINSG")),
        "min_dca": parse_number(data.get("MINDT")),
        "redemption_status": str(data.get("SHZT") or ""),
        "source": "天天基金公开接口",
        "source_url": f"https://fund.eastmoney.com/{entry['code']}.html",
        "stale": False,
        **perf,
    }, True


def tradable(row: dict) -> bool:
    return str(row.get("status") or "") not in {"暂停申购", "数据暂缺", "封闭期"}


def sort_key(row: dict):
    can_buy = tradable(row)
    value = row.get("max_buy")
    if isinstance(value, (int, float)):
        limit_rank = -float(value)
    elif str(row.get("status")) == "开放申购":
        # Open with no disclosed ceiling is treated as the least restrictive.
        limit_rank = float("-inf")
    else:
        limit_rank = float("inf")
    status_rank = {"开放申购": 0, "限大额": 1, "暂停申购": 2, "数据暂缺": 3}.get(str(row.get("status")), 1)
    return (0 if can_buy else 1, limit_rank, status_rank, str(row.get("name", "")), str(row.get("code", "")))


def main() -> None:
    previous = read_previous()
    old_map = {str(x.get("code")): x for x in previous.get("funds", []) if isinstance(x, dict) and x.get("code")}
    universe = fetch_universe()
    if not universe:
        if previous:
            print("[nasdaq-limit-warn] fund universe unavailable; keeping previous nasdaq_limits.json")
            return
        raise SystemExit("Nasdaq fund universe unavailable and no fallback snapshot exists")

    records: list[dict] = []
    fresh_count = 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(build_record, entry, old_map): entry for entry in universe}
        for fut in as_completed(futures):
            try:
                rec, fresh = fut.result()
            except Exception:
                entry = futures[fut]
                rec = {**entry, "status": "数据暂缺", "max_buy": None, "min_buy": None, "min_dca": None,
                       "redemption_status": "", "source": "天天基金公开接口",
                       "source_url": f"https://fund.eastmoney.com/{entry['code']}.html", "stale": True,
                       **{f"return_{y}y": None for y in PERIODS}}
                fresh = False
            records.append(rec)
            fresh_count += int(fresh)

    if fresh_count < max(3, int(len(universe) * 0.5)) and previous:
        print(f"[nasdaq-limit-warn] fresh coverage too low ({fresh_count}/{len(universe)}); keeping previous snapshot")
        return

    records.sort(key=sort_key)
    payload = {
        "updated_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "source": "天天基金 / 东方财富公开基金接口",
        "scope": "名称包含“纳斯达克/纳指/NASDAQ”的人民币场外基金份额；排除纯场内ETF和美元份额",
        "sorting": "可申购基金优先；同为可申购时按公开单日限额从高到低；开放且未披露上限视为限制最少",
        "return_basis": "公开累计净值曲线计算近1/3/5/10年累计收益；历史不足显示空值",
        "fallback": False,
        "count": len(records),
        "fresh_count": fresh_count,
        "tradable_count": sum(tradable(x) for x in records),
        "limited_count": sum(x.get("status") == "限大额" for x in records),
        "paused_count": sum(x.get("status") == "暂停申购" for x in records),
        "funds": records,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        "[done] Nasdaq fund limits + returns: "
        f"total={len(records)} fresh={fresh_count} tradable={payload['tradable_count']} "
        f"limited={payload['limited_count']} paused={payload['paused_count']}"
    )


if __name__ == "__main__":
    main()
