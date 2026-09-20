#!/usr/bin/env python3
"""Attach five concrete ETF funds to every sector with return and max-drawdown metrics.

Fund discovery uses one Sina Finance public ETF-universe request and ranks real
exchange-listed ETFs by sector-specific aliases. Price history uses the same
Tencent-backed daily pipeline as the sector charts. The five funds are
representative examples, not recommendations or a performance ranking.
"""
from __future__ import annotations

from bisect import bisect_right
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
from pathlib import Path
import json
import re

from add_daily_history import fetch_daily
from update_data import PERIODS, http_bytes, target_date

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "docs" / "data" / "latest.json"
SINA_LIST = (
    "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
    "Market_Center.getHQNodeData?page=1&num=5000&sort=symbol&asc=1&"
    "node=etf_hq_fund&symbol=&_s_r_a=auto"
)

ALIASES: dict[str, list[str]] = {
    "半导体": ["半导体", "芯片", "集成电路", "科创芯片"],
    "半导体材料设备": ["半导体设备", "半导体材料", "芯片设备", "科创芯片", "半导体"],
    "存储芯片": ["存储", "芯片", "集成电路", "半导体"],
    "机器人": ["机器人", "人形机器人", "智能制造", "高端装备"],
    "人工智能": ["人工智能", "AI", "科创AI", "智能"],
    "AI应用": ["AI应用", "人工智能", "软件", "传媒", "云计算"],
    "算力租赁": ["算力", "数据中心", "云计算", "通信", "人工智能"],
    "国产算力": ["算力", "国产芯片", "芯片", "人工智能", "半导体"],
    "云计算": ["云计算", "大数据", "软件", "计算机", "人工智能"],
    "CPO": ["光通信", "通信", "5G", "算力", "科技"],
    "PCB": ["PCB", "电子", "消费电子", "芯片", "半导体"],
    "通信": ["通信", "5G", "通信设备", "电信"],
    "消费电子": ["消费电子", "电子", "智能消费", "科技"],
    "金融科技": ["金融科技", "互联网金融", "证券", "计算机"],
    "证券保险": ["证券保险", "证券", "非银", "保险"],
    "银行": ["银行", "金融"],
    "房地产": ["房地产", "地产", "REIT", "基建"],
    "医药": ["医药", "生物医药", "医疗", "医药卫生"],
    "医疗": ["医疗", "医疗器械", "医药", "生物医药"],
    "创新药": ["创新药", "生物科技", "生物医药", "医药", "港股创新药"],
    "海外医药": ["恒生医疗", "港股创新药", "港股医药", "医疗", "医药"],
    "CXO": ["CXO", "医疗", "医药", "创新药"],
    "白酒": ["白酒", "酒", "食品饮料", "消费"],
    "食品饮料": ["食品饮料", "食品", "饮料", "消费"],
    "消费": ["消费", "消费50", "可选消费", "主要消费"],
    "煤炭": ["煤炭", "能源", "红利"],
    "有色金属": ["有色金属", "有色", "矿业", "资源"],
    "黄金": ["黄金", "黄金产业", "有色"],
    "油气资源": ["油气", "原油", "石油", "能源"],
    "电力": ["电力", "公用事业", "绿色电力", "央企"],
    "新能源": ["新能源", "新能源车", "电池", "光伏"],
    "光伏": ["光伏", "太阳能", "新能源"],
    "储能": ["储能", "电池", "新能源"],
    "固态电池": ["固态电池", "电池", "锂电", "新能源车"],
    "汽车整车": ["汽车", "汽车零部件", "智能汽车", "新能源车"],
    "军工": ["军工", "国防", "航天", "航空"],
    "商业航天": ["商业航天", "航天", "卫星", "军工", "航空"],
    "红利": ["红利", "高股息", "央企红利", "红利低波"],
    "沪深300": ["沪深300", "300ETF", "沪深300价值"],
    "中证500": ["中证500", "500ETF"],
    "上证50": ["上证50", "50ETF"],
    "科创板": ["科创50", "科创板", "科创"],
    "创业板": ["创业板", "创业板50", "创成长"],
    "北证": ["北证50", "北证", "北交所", "创新"],
    "恒生科技": ["恒生科技", "港股科技", "恒生互联网", "港股互联网"],
    "港股红利": ["港股红利", "恒生红利", "港股通红利", "港股央企红利", "高股息"],
    "纳斯达克": ["纳斯达克", "纳指", "NASDAQ", "纳斯达克100"],
    "标普500": ["标普500", "标普", "S&P500", "标普500ETF"],
}

FALLBACK: dict[str, list[str]] = {
    "半导体材料设备": ["芯片", "半导体"], "存储芯片": ["芯片", "半导体"],
    "AI应用": ["人工智能", "计算机"], "算力租赁": ["算力", "云计算", "通信"],
    "国产算力": ["算力", "芯片", "人工智能"], "CPO": ["通信", "科技"],
    "PCB": ["电子", "消费电子"], "金融科技": ["证券", "金融"],
    "证券保险": ["证券", "金融"], "房地产": ["地产", "基建"],
    "海外医药": ["医疗", "创新药", "医药"], "CXO": ["医药", "医疗"],
    "白酒": ["食品饮料", "消费"], "煤炭": ["能源", "红利"],
    "油气资源": ["能源", "资源"], "储能": ["电池", "新能源"],
    "固态电池": ["电池", "新能源车"], "汽车整车": ["汽车", "新能源车"],
    "商业航天": ["军工", "航空"], "北证": ["北证", "创新"],
    "港股红利": ["港股", "红利"],
}


def fetch_etf_universe() -> list[dict[str, str]]:
    raw = http_bytes(SINA_LIST, timeout=12, retries=2, referer="https://vip.stock.finance.sina.com.cn/")
    text = raw.decode("utf-8", errors="ignore")
    out: list[dict[str, str]] = []
    for body in re.findall(r"\{([^{}]+)\}", text):
        sm = re.search(r'(?:^|,)symbol:\"([^\"]+)\"', body)
        nm = re.search(r'(?:^|,)name:\"([^\"]+)\"', body)
        if not sm or not nm:
            sm = re.search(r'\"symbol\"\s*:\s*\"([^\"]+)\"', body)
            nm = re.search(r'\"name\"\s*:\s*\"([^\"]+)\"', body)
        if not sm or not nm:
            continue
        symbol, name = sm.group(1).strip(), nm.group(1).strip()
        if re.fullmatch(r"(?:sh|sz)\d{6}", symbol) and name:
            out.append({"code": symbol, "name": name})
    uniq: dict[str, dict[str, str]] = {}
    for x in out:
        uniq.setdefault(x["code"], x)
    rows = list(uniq.values())
    if len(rows) < 50:
        raise RuntimeError(f"新浪ETF列表解析异常，仅得到 {len(rows)} 条")
    return rows


def score_name(name: str, sector: str, aliases: list[str]) -> int:
    up = name.upper()
    score = 0
    if sector.upper() in up:
        score += 120
    for i, alias in enumerate(aliases):
        a = alias.upper()
        if a and a in up:
            score += max(12, 60 - i * 7) + min(len(a) * 3, 18)
    if "ETF" in up:
        score += 8
    for bad in ("债", "货币", "国债", "信用", "利率", "现金"):
        if bad in name:
            score -= 100
    if sector != "黄金" and "黄金" in name:
        score -= 30
    return score


def rank_by_aliases(sector: str, aliases: list[str], universe: list[dict[str, str]], seen: set[str]) -> list[dict[str, str]]:
    ranked = []
    for x in universe:
        if x["code"] in seen:
            continue
        s = score_name(x["name"], sector, aliases)
        if s > 0:
            ranked.append((s, x["name"], x))
    ranked.sort(key=lambda z: (-z[0], z[1]))
    return [x for _, _, x in ranked]


def choose_funds(sector: str, universe: list[dict[str, str]]) -> list[dict[str, str]]:
    chosen: list[dict[str, str]] = []
    seen: set[str] = set()
    for x in rank_by_aliases(sector, ALIASES.get(sector, [sector]), universe, seen):
        chosen.append(x); seen.add(x["code"])
        if len(chosen) == 5:
            return chosen
    for x in rank_by_aliases(sector, FALLBACK.get(sector, ALIASES.get(sector, [sector])), universe, seen):
        chosen.append(x); seen.add(x["code"])
        if len(chosen) == 5:
            return chosen
    return chosen


def period_points(points: list[tuple[date, float]], spec: tuple[str, int]) -> list[tuple[date, float]]:
    if len(points) < 2:
        return []
    dates = [d for d, _ in points]
    start = target_date(points[-1][0], spec)
    idx = bisect_right(dates, start) - 1
    if idx < 0 or (start - dates[idx]).days > 16:
        return []
    return points[idx:]


def max_drawdown(points: list[tuple[date, float]]) -> float | None:
    if len(points) < 2:
        return None
    peak = points[0][1]
    worst = 0.0
    for _, value in points:
        peak = max(peak, value)
        if peak > 0:
            worst = min(worst, (value / peak - 1.0) * 100.0)
    return round(worst, 2)


def metrics(points: list[tuple[date, float]]) -> tuple[dict[str, float | None], dict[str, float | None]]:
    returns: dict[str, float | None] = {}
    drawdowns: dict[str, float | None] = {}
    for label, spec in PERIODS:
        rows = period_points(points, spec)
        if len(rows) < 2 or rows[0][1] <= 0:
            returns[label] = None
            drawdowns[label] = None
        else:
            returns[label] = round((rows[-1][1] / rows[0][1] - 1.0) * 100.0, 2)
            drawdowns[label] = max_drawdown(rows)
    return returns, drawdowns


def main() -> None:
    payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    sectors = payload.get("sectors") or []
    universe = fetch_etf_universe()
    print(f"[funds] Sina ETF universe: {len(universe)}")

    selections: dict[str, list[dict[str, str]]] = {}
    for item in sectors:
        name = str(item.get("name") or "")
        picked = choose_funds(name, universe)
        selections[name] = picked
        print(f"[funds-select] {name}: {len(picked)} -> " + ", ".join(f"{x['name']}({x['code'][2:]})" for x in picked))

    codes = sorted({x["code"] for rows in selections.values() for x in rows})
    histories: dict[str, list[tuple[date, float]] | Exception] = {}
    with ThreadPoolExecutor(max_workers=12) as pool:
        jobs = {pool.submit(fetch_daily, code): code for code in codes}
        for fut in as_completed(jobs):
            code = jobs[fut]
            try:
                histories[code] = fut.result()
            except Exception as exc:
                histories[code] = exc
                print(f"[funds-warn] {code}: {exc}")

    total_ok = 0
    exact_five = 0
    total_rows = 0
    for item in sectors:
        name = str(item.get("name") or "")
        fund_rows = []
        for fund in selections.get(name, []):
            result = histories.get(fund["code"])
            row = {
                "name": fund["name"], "code": fund["code"], "source": "腾讯财经公开K线",
                "status": "error", "returns": {label: None for label, _ in PERIODS},
                "drawdowns": {label: None for label, _ in PERIODS}, "latest_date": None, "start_date": None,
            }
            if isinstance(result, list) and len(result) >= 2:
                ret, dd = metrics(result)
                row.update({"status": "ok" if any(v is not None for v in ret.values()) else "short_history",
                            "returns": ret, "drawdowns": dd,
                            "latest_date": result[-1][0].isoformat(), "start_date": result[0][0].isoformat()})
                total_ok += 1
            elif isinstance(result, Exception):
                row["note"] = str(result)[:180]
            fund_rows.append(row)
        item["funds"] = fund_rows
        total_rows += len(fund_rows)
        if len(fund_rows) == 5:
            exact_five += 1

    payload["sectors"] = sectors
    payload["funds_summary"] = {
        "sector_count": len(sectors), "sectors_with_five": exact_five,
        "fund_rows": total_rows, "fund_rows_with_history": total_ok,
        "method": "Sina ETF universe + Tencent daily K-line; representative, not ranked recommendations",
    }
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    DATA_PATH.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"[done] sector funds: five={exact_five}/{len(sectors)} history={total_ok}/{total_rows} unique_codes={len(codes)}")


if __name__ == "__main__":
    main()
