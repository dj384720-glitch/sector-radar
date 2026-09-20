#!/usr/bin/env python3
"""Attach five relevant exchange-listed ETFs to every sector.

ETF discovery paginates Sina Finance's public ETF universe, then matches names
against sector-specific aliases.  Only ETFs with an actual sector-name match are
eligible; fixed-income/cash ETFs are excluded.  Price history comes from the
same daily Tencent-backed pipeline used by Sector Radar.  The five rows are
representative related funds, not recommendations or a performance ranking.
"""
from __future__ import annotations

from bisect import bisect_right
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
from pathlib import Path
import json
import re
import urllib.parse

from add_daily_history import fetch_daily
from update_data import PERIODS, http_bytes, target_date

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "docs" / "data" / "latest.json"
SINA_BASE = (
    "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
    "Market_Center.getHQNodeData"
)
PAGE_SIZE = 100
MAX_PAGES = 30

ALIASES: dict[str, list[str]] = {
    "半导体": ["半导体", "芯片", "集成电路", "科创芯片"],
    "半导体材料设备": ["半导体设备", "半导体材料", "芯片设备", "科创芯片", "半导体"],
    "存储芯片": ["存储", "芯片", "集成电路", "半导体"],
    "机器人": ["机器人", "人形机器人", "智能制造", "高端装备"],
    "人工智能": ["人工智能", "科创AI", "AI", "智能"],
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
    "白酒": ["白酒", "酒ETF", "食品饮料", "消费"],
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
    "半导体材料设备": ["芯片", "半导体"],
    "存储芯片": ["芯片", "半导体"],
    "机器人": ["智能制造", "高端装备", "机械"],
    "人工智能": ["人工智能", "软件", "计算机", "科技"],
    "AI应用": ["人工智能", "软件", "计算机", "传媒"],
    "算力租赁": ["算力", "云计算", "通信", "数据中心"],
    "国产算力": ["算力", "芯片", "人工智能", "半导体"],
    "云计算": ["计算机", "软件", "人工智能"],
    "CPO": ["通信", "5G", "科技"],
    "PCB": ["电子", "消费电子", "半导体"],
    "消费电子": ["电子", "科技"],
    "金融科技": ["证券", "金融", "计算机"],
    "证券保险": ["证券", "金融"],
    "房地产": ["地产", "基建"],
    "海外医药": ["医疗", "创新药", "医药"],
    "CXO": ["医药", "医疗", "创新药"],
    "白酒": ["食品饮料", "消费"],
    "食品饮料": ["消费"],
    "煤炭": ["能源", "红利"],
    "有色金属": ["资源", "矿业"],
    "油气资源": ["能源", "资源"],
    "电力": ["公用事业", "央企"],
    "储能": ["电池", "新能源"],
    "固态电池": ["电池", "新能源车"],
    "汽车整车": ["汽车", "新能源车"],
    "商业航天": ["军工", "航空", "国防"],
    "北证": ["北证", "创新"],
    "港股红利": ["港股", "红利", "高股息"],
    "纳斯达克": ["纳指", "美国", "海外科技"],
    "标普500": ["标普", "美国", "海外"],
}

EXCLUDE_TERMS = (
    "货币", "国债", "地方债", "政金债", "金融债", "信用债", "可转债",
    "公司债", "城投债", "债券", "短融", "利率债", "同业存单", "现金",
)


def decode_name(raw: str) -> str:
    raw = raw.strip()
    if "\\u" in raw or "\\x" in raw:
        try:
            # JSON decoding correctly converts Sina's literal \\uXXXX sequences.
            return json.loads('"' + raw.replace('"', '\\"') + '"')
        except Exception:
            pass
    return raw


def parse_page(raw: bytes) -> list[dict[str, str]]:
    text = raw.decode("utf-8", errors="ignore").strip()
    rows: list[dict[str, str]] = []
    try:
        payload = json.loads(text)
        if isinstance(payload, list):
            for row in payload:
                if not isinstance(row, dict):
                    continue
                symbol = str(row.get("symbol") or "").strip()
                name = decode_name(str(row.get("name") or ""))
                if re.fullmatch(r"(?:sh|sz)\d{6}", symbol) and name:
                    rows.append({"code": symbol, "name": name})
            if rows:
                return rows
    except Exception:
        pass

    # The endpoint sometimes returns JavaScript-like objects rather than strict JSON.
    for body in re.findall(r"\{([^{}]+)\}", text):
        sm = re.search(r'(?:^|,)\s*symbol\s*:\s*[\"\']([^\"\']+)', body)
        nm = re.search(r'(?:^|,)\s*name\s*:\s*[\"\']([^\"\']+)', body)
        if not sm or not nm:
            sm = re.search(r'[\"\']symbol[\"\']\s*:\s*[\"\']([^\"\']+)', body)
            nm = re.search(r'[\"\']name[\"\']\s*:\s*[\"\']([^\"\']+)', body)
        if not sm or not nm:
            continue
        symbol = sm.group(1).strip()
        name = decode_name(nm.group(1))
        if re.fullmatch(r"(?:sh|sz)\d{6}", symbol) and name:
            rows.append({"code": symbol, "name": name})
    return rows


def fetch_page(page: int) -> list[dict[str, str]]:
    query = urllib.parse.urlencode({
        "page": page,
        "num": PAGE_SIZE,
        "sort": "symbol",
        "asc": 1,
        "node": "etf_hq_fund",
        "symbol": "",
        "_s_r_a": "auto",
    })
    raw = http_bytes(
        SINA_BASE + "?" + query,
        timeout=12,
        retries=2,
        referer="https://vip.stock.finance.sina.com.cn/",
    )
    return parse_page(raw)


def fetch_etf_universe() -> list[dict[str, str]]:
    pages: dict[int, list[dict[str, str]]] = {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        jobs = {pool.submit(fetch_page, page): page for page in range(1, MAX_PAGES + 1)}
        for fut in as_completed(jobs):
            page = jobs[fut]
            try:
                pages[page] = fut.result()
            except Exception as exc:
                pages[page] = []
                print(f"[funds-page-warn] page={page}: {str(exc)[:120]}")

    uniq: dict[str, dict[str, str]] = {}
    nonempty = 0
    for page in sorted(pages):
        rows = pages[page]
        if rows:
            nonempty += 1
        for row in rows:
            uniq.setdefault(row["code"], row)
    universe = list(uniq.values())
    if len(universe) < 100:
        raise RuntimeError(f"ETF universe too small: {len(universe)}")
    print(f"[funds] ETF universe={len(universe)} nonempty_pages={nonempty}")
    return universe


def matched_aliases(name: str, aliases: list[str]) -> list[tuple[int, str]]:
    upper = name.upper().replace(" ", "")
    hits: list[tuple[int, str]] = []
    for i, alias in enumerate(aliases):
        a = alias.upper().replace(" ", "")
        if a and a in upper:
            hits.append((i, alias))
    return hits


def score_name(name: str, sector: str, aliases: list[str]) -> int | None:
    if any(term in name for term in EXCLUDE_TERMS):
        return None
    hits = matched_aliases(name, aliases)
    sector_hit = sector.upper().replace(" ", "") in name.upper().replace(" ", "")
    if not hits and not sector_hit:
        return None

    score = 130 if sector_hit else 0
    for i, alias in hits:
        score += max(18, 72 - i * 8) + min(len(alias) * 3, 18)
    if "ETF" in name.upper():
        score += 8
    # Prefer plain broad/index ETFs over leveraged/commodity-like variants where possible.
    for term in ("增强", "杠杆", "反向"):
        if term in name:
            score -= 20
    return score


def rank_by_aliases(
    sector: str,
    aliases: list[str],
    universe: list[dict[str, str]],
    seen: set[str],
) -> list[dict[str, str]]:
    ranked: list[tuple[int, str, dict[str, str]]] = []
    for row in universe:
        if row["code"] in seen:
            continue
        score = score_name(row["name"], sector, aliases)
        if score is not None:
            ranked.append((score, row["name"], row))
    ranked.sort(key=lambda x: (-x[0], x[1], x[2]["code"]))
    return [row for _, _, row in ranked]


def choose_funds(sector: str, universe: list[dict[str, str]]) -> list[dict[str, str]]:
    chosen: list[dict[str, str]] = []
    seen: set[str] = set()
    stages = [ALIASES.get(sector, [sector])]
    fallback = FALLBACK.get(sector)
    if fallback:
        stages.append(fallback)

    for aliases in stages:
        for row in rank_by_aliases(sector, aliases, universe, seen):
            chosen.append(row)
            seen.add(row["code"])
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

    selections: dict[str, list[dict[str, str]]] = {}
    for item in sectors:
        sector = str(item.get("name") or "")
        picked = choose_funds(sector, universe)
        selections[sector] = picked
        print(
            f"[funds-select] {sector}: {len(picked)} -> "
            + ", ".join(f"{x['name']}({x['code'][2:]})" for x in picked)
        )

    codes = sorted({x["code"] for rows in selections.values() for x in rows})
    histories: dict[str, list[tuple[date, float]] | Exception] = {}
    with ThreadPoolExecutor(max_workers=16) as pool:
        jobs = {pool.submit(fetch_daily, code): code for code in codes}
        for fut in as_completed(jobs):
            code = jobs[fut]
            try:
                histories[code] = fut.result()
            except Exception as exc:
                histories[code] = exc
                print(f"[fund-history-warn] {code}: {str(exc)[:140]}")

    total_rows = 0
    history_rows = 0
    sectors_with_five = 0
    for item in sectors:
        sector = str(item.get("name") or "")
        funds: list[dict] = []
        for selected in selections.get(sector, []):
            result = histories.get(selected["code"])
            if isinstance(result, list) and len(result) >= 2:
                returns, drawdowns = metrics(result)
                fund = {
                    "name": selected["name"],
                    "code": selected["code"],
                    "source": "腾讯财经公开K线",
                    "returns": returns,
                    "drawdowns": drawdowns,
                    "latest_date": result[-1][0].isoformat(),
                    "start_date": result[0][0].isoformat(),
                }
                history_rows += 1
            else:
                fund = {
                    "name": selected["name"],
                    "code": selected["code"],
                    "source": "行情暂不可用",
                    "returns": {label: None for label, _ in PERIODS},
                    "drawdowns": {label: None for label, _ in PERIODS},
                    "latest_date": None,
                    "start_date": None,
                }
            funds.append(fund)
        item["funds"] = funds[:5]
        total_rows += len(item["funds"])
        if len(item["funds"]) == 5:
            sectors_with_five += 1

    payload["sectors"] = sectors
    payload["funds_updated_at"] = datetime.now(timezone.utc).isoformat()
    summary = payload.setdefault("summary", {})
    summary["fund_sectors_with_five"] = sectors_with_five
    summary["fund_rows"] = total_rows
    summary["fund_rows_with_history"] = history_rows
    DATA_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(
        f"[done] sector funds: five={sectors_with_five}/{len(sectors)} "
        f"rows={total_rows} history={history_rows}/{total_rows} unique_codes={len(codes)}"
    )


if __name__ == "__main__":
    main()
