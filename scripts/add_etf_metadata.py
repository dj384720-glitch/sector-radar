#!/usr/bin/env python3
"""Enrich representative ETFs with public profile and latest turnover metadata."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
import json
import re
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "docs" / "data" / "latest.json"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"


class CellParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.depth = 0; self.buf = []; self.cells = []
    def handle_starttag(self, tag, attrs):
        if tag in {"td", "th"}:
            if self.depth == 0: self.buf = []
            self.depth += 1
    def handle_endtag(self, tag):
        if tag in {"td", "th"} and self.depth:
            self.depth -= 1
            if self.depth == 0:
                text = re.sub(r"\s+", " ", "".join(self.buf)).strip()
                if text: self.cells.append(unescape(text))
    def handle_data(self, data):
        if self.depth: self.buf.append(data)


def http_text(url: str, timeout: float = 8.0) -> str:
    last = None
    for attempt in range(2):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA, "Accept": "text/html,application/xhtml+xml,*/*", "Referer": "https://fund.eastmoney.com/",
            })
            with urllib.request.urlopen(req, timeout=timeout) as resp: raw = resp.read()
            for enc in ("utf-8", "gb18030"):
                text = raw.decode(enc, errors="ignore")
                if "基金" in text or "净资产" in text: return text
            return raw.decode("utf-8", errors="ignore")
        except Exception as exc:
            last = exc
            if attempt == 0: time.sleep(0.2)
    raise RuntimeError(str(last))


def next_cell(cells, label):
    for i, cell in enumerate(cells):
        compact = re.sub(r"\s+", "", cell)
        if compact == label or compact.startswith(label):
            return cells[i + 1] if i + 1 < len(cells) else ""
    return ""


def number(text):
    m = re.search(r"([0-9]+(?:\.[0-9]+)?)", str(text or "")); return float(m.group(1)) if m else None


def parse_date(text):
    m = re.search(r"(20\d{2})[年\-/](\d{1,2})[月\-/](\d{1,2})", str(text or ""))
    return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}" if m else None


def parse_profile_html(text):
    parser = CellParser(); parser.feed(text); cells = parser.cells
    size_text = next_cell(cells, "净资产规模") or next_cell(cells, "资产规模")
    mgmt_text = next_cell(cells, "管理费率"); custody_text = next_cell(cells, "托管费率")
    tracking = next_cell(cells, "跟踪标的"); manager = next_cell(cells, "基金管理人")
    size, mgmt, custody = number(size_text), number(mgmt_text), number(custody_text)
    plain = unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text)))
    if size is None:
        m = re.search(r"净资产规模[^0-9]{0,40}([0-9.]+)\s*亿元", plain); size = float(m.group(1)) if m else None
    if mgmt is None:
        m = re.search(r"管理费率[^0-9]{0,40}([0-9.]+)%", plain); mgmt = float(m.group(1)) if m else None
    if custody is None:
        m = re.search(r"托管费率[^0-9]{0,40}([0-9.]+)%", plain); custody = float(m.group(1)) if m else None
    total_fee = round(mgmt + custody, 4) if mgmt is not None and custody is not None else None
    return {
        "asset_size_yi": size, "asset_size_date": parse_date(size_text),
        "management_fee_pct": mgmt, "custody_fee_pct": custody, "total_fee_pct": total_fee,
        "tracking_index": tracking.strip() if tracking else None, "manager": manager.strip() if manager else None,
        "profile_source": "天天基金公开档案",
    }


def fetch_profile(code):
    bare = re.sub(r"^(?:sh|sz)", "", code); last = None
    for url in (f"https://fundf10.eastmoney.com/jbgk_{bare}.html", f"https://fund.eastmoney.com/data/xininfo_{bare}.html"):
        try:
            profile = parse_profile_html(http_text(url))
            if any(profile.get(k) is not None for k in ("asset_size_yi", "management_fee_pct", "tracking_index")):
                profile["profile_url"] = url; return profile
        except Exception as exc: last = exc
    raise RuntimeError(str(last or "profile unavailable"))


def fetch_sina_quotes(codes):
    out = {}
    for start in range(0, len(codes), 80):
        chunk = codes[start:start + 80]; url = "https://hq.sinajs.cn/list=" + ",".join(chunk)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": "https://finance.sina.com.cn/", "Accept": "text/plain,*/*"})
            with urllib.request.urlopen(req, timeout=10) as resp: text = resp.read().decode("gb18030", errors="ignore")
        except Exception as exc:
            print(f"[etf-quote-warn] chunk={start}: {str(exc)[:120]}"); continue
        for m in re.finditer(r'var\s+hq_str_((?:sh|sz)\d{6})="([^"]*)"', text):
            code, fields = m.group(1), m.group(2).split(",")
            if len(fields) < 10: continue
            try: amount = float(fields[9])
            except Exception: amount = None
            out[code] = {
                "latest_turnover_yi": round(amount / 1e8, 4) if amount is not None and amount >= 0 else None,
                "turnover_date": fields[30] if len(fields) > 30 and re.fullmatch(r"\d{4}-\d{2}-\d{2}", fields[30]) else None,
                "quote_source": "新浪财经公开实时行情",
            }
    return out


def main():
    payload = json.loads(DATA_PATH.read_text(encoding="utf-8")); sectors = payload.get("sectors") or []
    funds = [f for item in sectors for f in (item.get("funds") or [])]
    codes = sorted({str(f.get("code") or "") for f in funds if re.fullmatch(r"(?:sh|sz)\d{6}", str(f.get("code") or ""))})
    profiles = {}
    with ThreadPoolExecutor(max_workers=20) as pool:
        jobs = {pool.submit(fetch_profile, code): code for code in codes}
        for fut in as_completed(jobs):
            code = jobs[fut]
            try: profiles[code] = fut.result()
            except Exception as exc: profiles[code] = {"profile_error": str(exc)[:160]}
    quotes = fetch_sina_quotes(codes)
    profile_ok = sum(1 for c in codes if profiles.get(c, {}).get("asset_size_yi") is not None or profiles.get(c, {}).get("tracking_index"))
    quote_ok = sum(1 for c in codes if quotes.get(c, {}).get("latest_turnover_yi") is not None)
    rows_with_profile = 0
    for item in sectors:
        for fund in item.get("funds") or []:
            code = str(fund.get("code") or ""); meta = {}; meta.update(profiles.get(code, {})); meta.update(quotes.get(code, {})); fund["profile"] = meta
            if meta.get("asset_size_yi") is not None or meta.get("tracking_index"): rows_with_profile += 1
    payload["sectors"] = sectors
    payload["etf_metadata_updated_at"] = datetime.now(timezone.utc).isoformat()
    payload["etf_metadata_summary"] = {"unique_funds": len(codes), "profile_ok": profile_ok, "quote_ok": quote_ok, "rows_with_profile": rows_with_profile, "total_rows": len(funds)}
    DATA_PATH.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"[done] ETF metadata: profile={profile_ok}/{len(codes)} quote={quote_ok}/{len(codes)} rows={rows_with_profile}/{len(funds)}")


if __name__ == "__main__":
    main()
