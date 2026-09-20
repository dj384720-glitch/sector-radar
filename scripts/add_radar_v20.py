#!/usr/bin/env python3
"""Sector Radar 2.0: add state-change detection, proxy transparency and ETF alpha.

Runs after add_radar_v15.py. It derives 5/20 trading-day state transitions entirely
from the daily histories already present in latest.json, labels the benchmark/proxy
basis used by every sector, surfaces shared proxies, and upgrades the representative
ETF table with performance relative to the sector's displayed benchmark/proxy.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
import json
import math

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "docs" / "data" / "latest.json"
INDEX_PATH = ROOT / "docs" / "index.html"
VERSION_MARKER = "SECTOR_RADAR_V20"


def finite(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def parse_history(item):
    out = []
    for row in item.get("history") or []:
        if not isinstance(row, list) or len(row) < 2:
            continue
        d = str(row[0] or "")
        v = finite(row[1])
        if d and v is not None and v > 0:
            out.append((d, v))
    out.sort(key=lambda x: x[0])
    return out


def mean(values, n):
    return sum(values[-n:]) / n if len(values) >= n else None


def pct(a, b):
    if a is None or b is None or b <= 0:
        return None
    return (a / b - 1.0) * 100.0


def trend_state(latest, ma20, ma60, ma120, ma250, slope60):
    if ma20 and ma60 and ma120 and latest > ma20 > ma60 > ma120 and (slope60 or 0) > 0:
        return "强趋势"
    if ma60 and ma120 and latest > ma60 and ma60 >= ma120 and (slope60 or 0) >= 0:
        return "趋势上行"
    if ma60 and latest > ma60:
        return "修复"
    if ma60 and ma120 and latest < ma60 < ma120:
        return "弱势"
    if ma250 and latest > ma250:
        return "中期偏强"
    return "震荡"


def rs_at(rows, bench_rows, window):
    if not rows or not bench_rows:
        return None
    end_date = rows[-1][0]
    smap = dict(rows)
    bmap = {d: v for d, v in bench_rows if d <= end_date}
    dates = sorted(set(smap).intersection(bmap))
    if len(dates) < window + 1:
        return None
    d0, d1 = dates[-(window + 1)], dates[-1]
    s0, s1, b0, b1 = smap[d0], smap[d1], bmap[d0], bmap[d1]
    if min(s0, s1, b0, b1) <= 0:
        return None
    return round(((s1 / b1) / (s0 / b0) - 1.0) * 100.0, 2)


def snapshot(rows, bench_rows, offset):
    if offset < 0 or len(rows) <= offset:
        return None
    cut = rows[: len(rows) - offset] if offset else rows
    if len(cut) < 21:
        return None
    values = [v for _, v in cut]
    latest = values[-1]
    ma20, ma60, ma120, ma250 = (mean(values, n) for n in (20, 60, 120, 250))
    ma60_prev = sum(values[-80:-20]) / 60 if len(values) >= 80 else None
    slope60 = pct(ma60, ma60_prev)
    base_ma = ma120 or ma60 or ma20
    stack = pct(ma60, ma120) if ma60 and ma120 else 0.0
    trend_strength = round((pct(latest, base_ma) or 0.0) + 0.5 * (stack or 0.0), 2) if base_ma else None
    tail = values[-250:] if len(values) >= 250 else values
    high = max(tail) if tail else None
    dist = round((latest / high - 1.0) * 100.0, 2) if high else None
    pp = round(sum(1 for x in tail if x <= latest) / len(tail) * 100.0, 1) if tail else None
    return {
        "date": cut[-1][0],
        "trend_state": trend_state(latest, ma20, ma60, ma120, ma250, slope60),
        "trend_strength": trend_strength,
        "rs60": rs_at(cut, bench_rows, 60),
        "above_ma120": bool(ma120 is not None and latest > ma120),
        "distance_250d_high": dist,
        "price_percentile_250d": pp,
    }


def event(label, kind, direction, priority, old=None, new=None):
    out = {"label": label, "kind": kind, "direction": direction, "priority": priority}
    if old is not None:
        out["old"] = old
    if new is not None:
        out["new"] = new
    return out


def compare_events(previous, current):
    if not previous or not current:
        return []
    events = []
    ps, cs = previous.get("trend_state"), current.get("trend_state")
    if ps and cs and ps != cs:
        events.append(event(f"状态：{ps} → {cs}", "state", "change", 5, ps, cs))
    prs, crs = finite(previous.get("rs60")), finite(current.get("rs60"))
    if prs is not None and crs is not None:
        if prs <= 0 < crs:
            events.append(event("RS60由负转正", "rs_cross", "up", 4, prs, crs))
        elif prs >= 0 > crs:
            events.append(event("RS60由正转负", "rs_cross", "down", 4, prs, crs))
        delta = round(crs - prs, 2)
        if abs(delta) >= 5:
            events.append(event(f"RS60变化 {delta:+.1f}pct", "rs_delta", "up" if delta > 0 else "down", 2, prs, crs))
    pma, cma = previous.get("above_ma120"), current.get("above_ma120")
    if pma is False and cma is True:
        events.append(event("重新站上MA120", "ma120", "up", 4))
    elif pma is True and cma is False:
        events.append(event("跌破MA120", "ma120", "down", 4))
    pd, cd = finite(previous.get("distance_250d_high")), finite(current.get("distance_250d_high"))
    if pd is not None and cd is not None:
        if pd < -5 <= cd:
            events.append(event("进入250日高点5%范围", "near_high", "up", 3, pd, cd))
        elif pd >= -5 > cd:
            events.append(event("离开250日高点5%范围", "near_high", "down", 3, pd, cd))
    pp, cp = finite(previous.get("price_percentile_250d")), finite(current.get("price_percentile_250d"))
    if pp is not None and cp is not None:
        if pp < 80 <= cp:
            events.append(event("价格进入250日80%分位以上", "percentile", "up", 2, pp, cp))
        elif pp >= 80 > cp:
            events.append(event("价格跌回250日80%分位以下", "percentile", "down", 2, pp, cp))
    return sorted(events, key=lambda x: (-x["priority"], x["label"]))


def basis_meta(item, code_groups):
    name = str(item.get("name") or "")
    code = str(item.get("code") or "")
    benchmark = str(item.get("benchmark") or "")
    source = str(item.get("source") or "")
    lower = (benchmark + " " + source).lower()
    if "etf" in lower or "代理" in benchmark:
        kind = "ETF代理"
    elif code:
        kind = "指数/市场基准"
    else:
        kind = "未绑定"
    shared = [x for x in code_groups.get(code, []) if x != name] if code else []
    if kind == "ETF代理":
        relation = "名称接近" if name and name.lower() in benchmark.lower() else "主题代理"
    elif kind == "指数/市场基准":
        relation = "指数口径"
    else:
        relation = "待完善"
    note_parts = []
    if kind == "ETF代理":
        note_parts.append("当前板块曲线使用可交易ETF价格代理，不等同于完整行业指数。")
    if shared:
        note_parts.append("该价格代码还被用于：" + "、".join(shared) + "。这些板块之间的历史曲线可能高度重合。")
    if not note_parts:
        note_parts.append("当前曲线使用独立的指数/市场基准口径。")
    return {
        "type": kind,
        "relation": relation,
        "label": benchmark or "—",
        "code": code,
        "shared_with": shared,
        "note": "".join(note_parts),
    }


def patch_data():
    payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    sectors = payload.get("sectors") or []
    benchmark = next((x for x in sectors if x.get("name") == "沪深300"), None)
    bench_rows = parse_history(benchmark or {})
    code_groups = defaultdict(list)
    for item in sectors:
        code = str(item.get("code") or "")
        if code:
            code_groups[code].append(str(item.get("name") or ""))

    event_sectors_5 = event_sectors_20 = shared_proxy_sectors = 0
    for item in sectors:
        rows = parse_history(item)
        now = snapshot(rows, bench_rows, 0)
        prev5 = snapshot(rows, bench_rows, 5)
        prev20 = snapshot(rows, bench_rows, 20)
        events5 = compare_events(prev5, now)
        events20 = compare_events(prev20, now)
        basis = basis_meta(item, code_groups)
        item["radar2"] = {
            "current": now,
            "previous_5d": prev5,
            "previous_20d": prev20,
            "events_5d": events5,
            "events_20d": events20,
            "basis": basis,
        }
        if events5:
            event_sectors_5 += 1
        if events20:
            event_sectors_20 += 1
        if basis.get("shared_with"):
            shared_proxy_sectors += 1

    payload["sectors"] = sectors
    payload["radar_version"] = "2.0"
    payload["radar2_updated_at"] = datetime.now(timezone.utc).isoformat()
    payload["radar2_summary"] = {
        "event_sectors_5d": event_sectors_5,
        "event_sectors_20d": event_sectors_20,
        "shared_proxy_sectors": shared_proxy_sectors,
    }
    DATA_PATH.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return payload


CSS = r'''
/* SECTOR_RADAR_V20 */
.radar-change{padding:18px 20px;margin-bottom:14px}.radar-change-head{display:flex;justify-content:space-between;gap:16px;align-items:flex-start}.radar-change-head h3{margin:0;font-size:18px}.radar-change-head p{margin:5px 0 0;color:var(--muted);font-size:12px;line-height:1.65}.radar-change-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:12px}.radar-change-box{border:1px solid var(--line);border-radius:11px;overflow:hidden}.radar-change-title{padding:10px 12px;background:#fbfcff;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;align-items:center}.radar-change-title strong{font-size:13px}.radar-change-title span{font-size:10px;color:var(--muted)}.radar-event-list{max-height:310px;overflow:auto}.radar-event{display:grid;grid-template-columns:minmax(88px,.7fr) minmax(180px,1.5fr) auto;gap:10px;align-items:center;padding:10px 12px;border-bottom:1px solid var(--line);cursor:pointer}.radar-event:last-child{border-bottom:0}.radar-event:hover{background:#f7f9fc}.radar-event-name{font-size:12px;font-weight:800}.radar-event-label{font-size:11px;color:#475467;line-height:1.45}.radar-event-dir{font-size:10px;font-weight:850;border-radius:999px;padding:3px 7px;background:#f2f4f7;color:#667085;white-space:nowrap}.radar-event-dir.up{background:#fff1f0;color:#a33a31}.radar-event-dir.down{background:#ecfdf3;color:#087443}.radar-event-empty{padding:20px;color:var(--muted);font-size:12px}.radar2-detail{padding:16px 18px;margin:14px 0}.radar2-detail-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}.radar2-box{border:1px solid var(--line);border-radius:10px;padding:12px;background:#fbfcff}.radar2-box h4{margin:0 0 9px;font-size:13px}.radar2-row{display:flex;justify-content:space-between;gap:14px;padding:5px 0;font-size:11px;border-bottom:1px dashed #e7ebf0}.radar2-row:last-of-type{border-bottom:0}.radar2-row span{color:var(--muted)}.radar2-row strong{text-align:right}.radar2-note{margin:9px 0 0;color:#475467;font-size:11px;line-height:1.65}.radar2-events{display:flex;gap:6px;flex-wrap:wrap}.radar2-chip{display:inline-flex;padding:4px 7px;border-radius:999px;background:#f2f4f7;font-size:10px;color:#475467}.radar2-chip.up{background:#fff1f0;color:#a33a31}.radar2-chip.down{background:#ecfdf3;color:#087443}.basis-warning{display:inline-flex;margin-left:6px;padding:2px 6px;border-radius:999px;font-size:10px;background:#fff8db;color:#7a5a00;border:1px solid #f2dea2}.fund-alpha{font-weight:850;font-variant-numeric:tabular-nums}.fund-alpha.up{color:var(--up)}.fund-alpha.down{color:var(--down)}
@media(max-width:900px){.radar-change-grid,.radar2-detail-grid{grid-template-columns:1fr}.radar-event{grid-template-columns:86px 1fr auto}}
@media(max-width:560px){.radar-change{padding:15px}.radar-event{grid-template-columns:78px 1fr}.radar-event-dir{display:none}}
'''

CHANGE_HTML = r'''
    <!-- SECTOR_RADAR_V20 -->
    <section class="panel radar-change" id="radarChangePanel">
      <div class="radar-change-head"><div><h3>今日变化雷达</h3><p>优先展示“状态发生改变”的板块：趋势状态、RS60零轴、MA120与250日高位区间。变化不代表未来方向，只用于发现哪里值得进一步核对。</p></div><span class="radar-version">RADAR 2.0</span></div>
      <div class="radar-change-grid">
        <div class="radar-change-box"><div class="radar-change-title"><strong>近5个交易日</strong><span>短期状态变化</span></div><div class="radar-event-list" id="radarEvents5"></div></div>
        <div class="radar-change-box"><div class="radar-change-title"><strong>近20个交易日</strong><span>约1个月状态变化</span></div><div class="radar-event-list" id="radarEvents20"></div></div>
      </div>
    </section>
'''

DETAIL_HTML = r'''
    <section class="panel radar2-detail" id="radar2DetailPanel">
      <div class="radar2-detail-grid">
        <div class="radar2-box"><h4>状态变化</h4><div id="radar2StateChanges"></div></div>
        <div class="radar2-box"><h4>板块口径透明度</h4><div id="radar2Basis"></div></div>
      </div>
    </section>
'''

JS = r'''
// SECTOR_RADAR_V20
function radar2DirText(d){return d==='up'?'增强':d==='down'?'转弱':'变化'}
function radar2EventRows(windowKey){
  const rows=[];(sectors||[]).forEach(item=>{const evs=item?.radar2?.[windowKey]||[];evs.forEach(e=>rows.push({item,e}))});
  rows.sort((a,b)=>(Number(b.e.priority)||0)-(Number(a.e.priority)||0)||String(a.item.name).localeCompare(String(b.item.name),'zh-CN'));
  return rows;
}
function renderRadarChanges(){
  const render=(id,key)=>{const el=document.getElementById(id);if(!el)return;const rows=radar2EventRows(key).slice(0,16);if(!rows.length){el.innerHTML='<div class="radar-event-empty">该窗口内没有检测到主要状态切换。</div>';return}el.innerHTML=rows.map(({item,e})=>`<div class="radar-event" onclick="radarOpenSector('${radarEsc(item.name).replace(/'/g,'&#39;')}')"><div class="radar-event-name">${radarEsc(item.name)}</div><div class="radar-event-label">${radarEsc(e.label||'状态变化')}</div><div class="radar-event-dir ${e.direction==='up'?'up':e.direction==='down'?'down':''}">${radar2DirText(e.direction)}</div></div>`).join('')};
  render('radarEvents5','events_5d');render('radarEvents20','events_20d')
}
function renderRadar2Detail(item){
  const state=document.getElementById('radar2StateChanges'),basis=document.getElementById('radar2Basis');if(!state||!basis)return;const r2=item?.radar2||{},e5=r2.events_5d||[],e20=r2.events_20d||[],b=r2.basis||{};
  const chips=(evs)=>evs.length?`<div class="radar2-events">${evs.slice(0,6).map(e=>`<span class="radar2-chip ${e.direction==='up'?'up':e.direction==='down'?'down':''}">${radarEsc(e.label)}</span>`).join('')}</div>`:'<span class="empty">无主要状态切换</span>';
  state.innerHTML=`<div class="radar2-row"><span>近5个交易日</span><strong>${e5.length}项变化</strong></div>${chips(e5)}<div class="radar2-row" style="margin-top:8px"><span>近20个交易日</span><strong>${e20.length}项变化</strong></div>${chips(e20)}`;
  const shared=(b.shared_with||[]),warn=shared.length?`<span class="basis-warning">共享价格代理</span>`:'';basis.innerHTML=`<div class="radar2-row"><span>口径类型</span><strong>${radarEsc(b.type||'—')}${warn}</strong></div><div class="radar2-row"><span>当前基准/代理</span><strong>${radarEsc(b.label||'—')}</strong></div><div class="radar2-row"><span>代码</span><strong>${radarEsc(b.code||'—')}</strong></div><div class="radar2-row"><span>映射方式</span><strong>${radarEsc(b.relation||'—')}</strong></div><p class="radar2-note">${radarEsc(b.note||'暂无额外口径说明。')}</p>`
}
function radar2FundFmt(v){if(v===null||v===undefined||!Number.isFinite(Number(v)))return '<span class="empty">—</span>';const n=Number(v);return `<span class="fund-metric ${n>0?'up':n<0?'down':''}">${pct(n)}</span>`}
function radar2AlphaFmt(v){if(v===null||v===undefined||!Number.isFinite(Number(v)))return '<span class="empty">—</span>';const n=Number(v);return `<span class="fund-alpha ${n>0?'up':n<0?'down':''}">${pct(n)}</span>`}
function renderFunds(item){
  const funds=(item?.funds||[]).slice(0,5),wrap=$('#fundTableWrap'),period=$('#fundPeriod'),note=$('#fundNote');if(!wrap||!period||!note)return;period.textContent=activePeriod+' 指标';
  const sectorRet=Number(item?.returns?.[activePeriod]);if(customRange){note.textContent=`当前走势图使用自定义日期区间；为了避免向页面塞入240只基金的完整日线，ETF表仍按“${activePeriod}”固定周期显示。相对板块 = ETF同期涨跌 − 当前板块基准/代理同期涨跌。`}
  else{note.textContent='ETF为主题相关的代表性样本，不构成推荐或排名。相对板块 = ETF同期涨跌 − 当前板块基准/代理同期涨跌；正值仅表示该周期相对表现更强，不代表基金质量或未来收益。'}
  if(!funds.length){wrap.innerHTML='<div class="fund-empty">该板块暂未生成代表基金数据</div>';return}
  const rows=funds.map(f=>{const url=fundSourceUrl(f),name=radarEsc(f.name||'—'),code=radarEsc((f.code||'').replace(/^(sh|sz)/,'')),fr=Number(f.returns?.[activePeriod]),alpha=Number.isFinite(fr)&&Number.isFinite(sectorRet)?fr-sectorRet:null;const nameHtml=url?`<a class="fund-name fund-link" href="${radarEsc(url)}" target="_blank" rel="noopener noreferrer" title="打开腾讯财经原始行情页">${name} ↗</a>`:`<span class="fund-name">${name}</span>`,sourceHtml=url?`<a class="fund-source-link" href="${radarEsc(url)}" target="_blank" rel="noopener noreferrer">腾讯财经 ↗</a>`:'<span class="empty">—</span>';return `<tr><td>${nameHtml}<span class="fund-code">${code}</span></td><td>${radar2FundFmt(f.returns?.[activePeriod])}</td><td>${radar2AlphaFmt(alpha)}</td><td>${drawdownFmt(f.drawdowns?.[activePeriod])}</td><td>${radarEsc(f.latest_date||'—')}</td><td>${sourceHtml}</td></tr>`}).join('');
  wrap.innerHTML=`<table class="fund-table"><thead><tr><th>基金</th><th>${radarEsc(activePeriod)}涨跌</th><th>相对板块</th><th>最大回撤</th><th>数据截至</th><th>行情来源</th></tr></thead><tbody>${rows}</tbody></table>`
}
const radar2BaseRenderDetail=renderDetail;renderDetail=function(item){radar2BaseRenderDetail(item);renderRadar2Detail(item);renderRadarChanges()};
'''


def patch_html():
    text = INDEX_PATH.read_text(encoding="utf-8")
    if VERSION_MARKER in text:
        return
    if "SECTOR_RADAR_V15" not in text:
        raise RuntimeError("Radar 1.5 must run before Radar 2.0")
    if "</style>" not in text:
        raise RuntimeError("style close marker missing")
    text = text.replace("</style>", CSS + "\n</style>", 1)
    hero_marker = '    <section class="panel hero">'
    chart_marker = '    <section class="panel chart-panel">'
    js_marker = "$('#sideSearch').oninput=buildMenu;"
    if hero_marker not in text or chart_marker not in text or js_marker not in text:
        raise RuntimeError("expected HTML/JS marker missing")
    text = text.replace(hero_marker, CHANGE_HTML + "\n" + hero_marker, 1)
    text = text.replace(chart_marker, DETAIL_HTML + "\n" + chart_marker, 1)
    text = text.replace(js_marker, JS + "\n" + js_marker, 1)
    text = text.replace("RADAR 1.5", "RADAR 2.0")
    text = text.replace("板块雷达 1.5 · 市场状态与ETF研究", "板块雷达 2.0 · 状态变化与ETF研究", 1)
    text = text.replace("先用全市场雷达观察相对强弱与趋势，再进入板块详情核对历史走势、风险和代表ETF。", "先看全市场强弱，再看近5/20日状态变化；进入板块详情核对趋势、口径风险与代表ETF的相对表现。", 1)
    INDEX_PATH.write_text(text, encoding="utf-8")


def main():
    payload = patch_data()
    patch_html()
    s = payload.get("radar2_summary", {})
    print(f"[done] Sector Radar 2.0: events5={s.get('event_sectors_5d',0)} events20={s.get('event_sectors_20d',0)} shared_proxy={s.get('shared_proxy_sectors',0)}")


if __name__ == "__main__":
    main()
