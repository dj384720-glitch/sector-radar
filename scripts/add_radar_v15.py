#!/usr/bin/env python3
"""Sector Radar 1.5: derive price-based market-state metrics and patch the static UI.

This layer deliberately uses only the daily history already built by the project.
It adds MA trend structure, relative strength vs CSI 300, drawdown, price
percentile, volatility, an all-sector radar, and a per-sector diagnostic card.
The script is idempotent and is intended to run after add_fund_ui.py.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import math
import statistics

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "docs" / "data" / "latest.json"
INDEX_PATH = ROOT / "docs" / "index.html"
VERSION_MARKER = "SECTOR_RADAR_V15"


def finite(v):
    if v is None:
        return None
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


def mean_tail(values, n):
    if len(values) < n:
        return None
    return sum(values[-n:]) / n


def pct(a, b):
    if a is None or b is None or b <= 0:
        return None
    return (a / b - 1.0) * 100.0


def relative_strength(sector_rows, bench_rows, window):
    if not sector_rows or not bench_rows:
        return None
    smap, bmap = dict(sector_rows), dict(bench_rows)
    dates = sorted(set(smap).intersection(bmap))
    if len(dates) < window + 1:
        return None
    d0, d1 = dates[-(window + 1)], dates[-1]
    s0, s1, b0, b1 = smap[d0], smap[d1], bmap[d0], bmap[d1]
    if min(s0, s1, b0, b1) <= 0:
        return None
    return round(((s1 / b1) / (s0 / b0) - 1.0) * 100.0, 2)


def rolling_drawdown(values):
    if len(values) < 2:
        return None
    peak, worst = values[0], 0.0
    for v in values:
        peak = max(peak, v)
        if peak > 0:
            worst = min(worst, (v / peak - 1.0) * 100.0)
    return round(worst, 2)


def annualized_vol(values, window=60):
    if len(values) < window + 1:
        return None
    tail = values[-(window + 1):]
    logs = [math.log(b / a) for a, b in zip(tail, tail[1:]) if a > 0 and b > 0]
    if len(logs) < max(20, window // 2):
        return None
    return round(statistics.pstdev(logs) * math.sqrt(252) * 100.0, 2)


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


def build_radar(item, bench_rows):
    rows = parse_history(item)
    if len(rows) < 21:
        return {"available": False, "reason": "历史数据不足"}
    values = [v for _, v in rows]
    latest = values[-1]
    mas = {n: mean_tail(values, n) for n in (20, 60, 120, 250)}
    ma60_prev = sum(values[-80:-20]) / 60 if len(values) >= 80 else None
    slope60 = pct(mas[60], ma60_prev)
    base_ma = mas[120] or mas[60] or mas[20]
    stack_component = pct(mas[60], mas[120]) if mas[60] and mas[120] else 0.0
    trend_strength = round((pct(latest, base_ma) or 0.0) + 0.5 * (stack_component or 0.0), 2) if base_ma else None
    tail250 = values[-250:] if len(values) >= 250 else values
    high250 = max(tail250)
    distance_high = round((latest / high250 - 1.0) * 100.0, 2) if high250 > 0 else None
    percentile = round(sum(1 for v in tail250 if v <= latest) / len(tail250) * 100.0, 1) if tail250 else None
    all_peak = max(values)
    current_dd = round((latest / all_peak - 1.0) * 100.0, 2) if all_peak > 0 else None
    return {
        "available": True,
        "trend_state": trend_state(latest, mas[20], mas[60], mas[120], mas[250], slope60),
        "trend_strength": trend_strength,
        "ma20": round(mas[20], 6) if mas[20] is not None else None,
        "ma60": round(mas[60], 6) if mas[60] is not None else None,
        "ma120": round(mas[120], 6) if mas[120] is not None else None,
        "ma250": round(mas[250], 6) if mas[250] is not None else None,
        "ma60_slope_20d_pct": round(slope60, 2) if slope60 is not None else None,
        "rs20": relative_strength(rows, bench_rows, 20),
        "rs60": relative_strength(rows, bench_rows, 60),
        "rs120": relative_strength(rows, bench_rows, 120),
        "current_drawdown": current_dd,
        "distance_250d_high": distance_high,
        "price_percentile_250d": percentile,
        "volatility_60d_annualized": annualized_vol(values, 60),
        "max_drawdown_250d": rolling_drawdown(tail250),
        "observations": len(values),
    }


def patch_data():
    payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    sectors = payload.get("sectors") or []
    benchmark = next((x for x in sectors if x.get("name") == "沪深300"), None)
    bench_rows = parse_history(benchmark or {})
    available = rs_positive = trend_positive = near_high = 0
    for item in sectors:
        radar = build_radar(item, bench_rows)
        item["radar"] = radar
        if not radar.get("available"):
            continue
        available += 1
        if (radar.get("rs60") or 0) > 0:
            rs_positive += 1
        if radar.get("trend_state") in {"强趋势", "趋势上行", "中期偏强"}:
            trend_positive += 1
        d = radar.get("distance_250d_high")
        if d is not None and d >= -5:
            near_high += 1
    payload["sectors"] = sectors
    payload["radar_version"] = "1.5"
    payload["radar_updated_at"] = datetime.now(timezone.utc).isoformat()
    payload["radar_summary"] = {
        "available": available,
        "trend_positive": trend_positive,
        "rs60_positive": rs_positive,
        "within_5pct_of_250d_high": near_high,
    }
    DATA_PATH.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return payload


CSS = r'''
/* SECTOR_RADAR_V15 */
.radar-market{padding:18px 20px;margin-bottom:14px}.radar-head{display:flex;justify-content:space-between;gap:18px;align-items:flex-start;margin-bottom:13px}.radar-head h3{margin:0;font-size:18px}.radar-head p{margin:5px 0 0;color:var(--muted);font-size:12px;line-height:1.65}.radar-version{font-size:11px;color:var(--blue);font-weight:850;border:1px solid #c8d7ff;background:#f4f7ff;border-radius:999px;padding:5px 9px;white-space:nowrap}.radar-summary{display:grid;grid-template-columns:repeat(4,1fr);gap:9px;margin:12px 0}.radar-summary-card{border:1px solid var(--line);background:#fbfcff;border-radius:10px;padding:11px 12px}.radar-summary-card span{display:block;color:var(--muted);font-size:11px}.radar-summary-card strong{display:block;font-size:20px;margin-top:4px;font-variant-numeric:tabular-nums}.radar-layout{display:grid;grid-template-columns:minmax(420px,1.15fr) minmax(380px,.85fr);gap:14px}.radar-box{border:1px solid var(--line);border-radius:11px;overflow:hidden;background:#fff}.radar-box-title{padding:11px 13px;border-bottom:1px solid var(--line);background:#fbfcff}.radar-box-title strong{font-size:13px}.radar-box-title small{display:block;color:var(--muted);font-size:11px;margin-top:3px;line-height:1.5}.radar-scatter{height:390px;min-height:390px;position:relative}.radar-scatter svg{width:100%;height:100%;display:block}.radar-axis{stroke:#d5dce7;stroke-width:1}.radar-grid{stroke:#eef1f5;stroke-width:1}.radar-dot{fill:#2457d6;fill-opacity:.72;cursor:pointer}.radar-dot:hover{fill-opacity:1;stroke:#172033;stroke-width:1.5}.radar-dot.negative{fill:#7b8799}.radar-label{font-size:9px;fill:#475467;pointer-events:none}.radar-axis-label{font-size:10px;fill:#98a2b3}.radar-table-wrap{max-height:390px;overflow:auto}.radar-table{width:100%;border-collapse:collapse}.radar-table th,.radar-table td{padding:9px 10px;border-bottom:1px solid var(--line);font-size:11px;text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}.radar-table th{position:sticky;top:0;z-index:1;background:#fbfcff;color:var(--muted);font-size:10px}.radar-table th:first-child,.radar-table td:first-child{text-align:left}.radar-table tr{cursor:pointer}.radar-table tbody tr:hover{background:#f7f9fc}.radar-state{display:inline-flex;border-radius:999px;padding:3px 7px;font-weight:800;background:#f2f4f7;color:#475467}.radar-state.strong{background:#ecfdf3;color:#087443}.radar-state.repair{background:#fff8db;color:#7a5a00}.radar-state.weak{background:#fff1f0;color:#a33a31}.radar-detail{padding:17px 18px;margin:14px 0}.radar-detail-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}.radar-detail-head h3{margin:0;font-size:17px}.radar-detail-head p{margin:4px 0 0;color:var(--muted);font-size:11px}.radar-kpis{display:grid;grid-template-columns:repeat(6,1fr);gap:8px;margin-top:12px}.radar-kpi{border:1px solid var(--line);border-radius:10px;padding:10px;background:#fbfcff;min-width:0}.radar-kpi span{display:block;color:var(--muted);font-size:10px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.radar-kpi strong{display:block;font-size:16px;margin-top:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.radar-diagnosis{margin:11px 0 0;padding:10px 12px;border-radius:9px;background:#f7f9fc;color:#475467;font-size:12px;line-height:1.7}.radar-missing{color:var(--muted);font-size:12px;padding:12px 0}.radar-help{margin-top:8px;color:var(--muted);font-size:10px;line-height:1.6}
@media(max-width:1180px){.radar-layout{grid-template-columns:1fr}.radar-kpis{grid-template-columns:repeat(3,1fr)}}
@media(max-width:760px){.radar-market{padding:15px}.radar-summary{grid-template-columns:1fr 1fr}.radar-layout{grid-template-columns:1fr}.radar-scatter{height:310px;min-height:310px}.radar-kpis{grid-template-columns:1fr 1fr}.radar-head{display:block}.radar-version{display:inline-flex;margin-top:8px}}
'''

MARKET_HTML = r'''
    <!-- SECTOR_RADAR_V15 -->
    <section class="panel radar-market" id="marketRadarPanel">
      <div class="radar-head"><div><h3>全市场轮动雷达</h3><p>横轴为近60个共同交易日相对沪深300的强弱；纵轴为价格相对中期均线与均线结构形成的趋势强度。这里只描述市场状态，不给出买卖结论。</p></div><span class="radar-version">RADAR 1.5</span></div>
      <div class="radar-summary" id="radarSummary"><div class="loading">正在计算市场状态…</div></div>
      <div class="radar-layout">
        <div class="radar-box"><div class="radar-box-title"><strong>相对强度 × 趋势强度</strong><small>右侧=相对沪深300更强；上方=中期趋势更强。点击圆点可直接切换板块。</small></div><div class="radar-scatter" id="radarScatter"></div></div>
        <div class="radar-box"><div class="radar-box-title"><strong>板块状态表</strong><small>默认按RS60排序；用于快速发现强弱差异，不代表推荐顺序。</small></div><div class="radar-table-wrap" id="radarTableWrap"></div></div>
      </div>
      <div class="radar-help">趋势强度 = 现价相对MA120的偏离 + 0.5×MA60相对MA120的偏离；RS60 = 板块/沪深300相对价格在近60个共同交易日的变化。</div>
    </section>
'''

DETAIL_HTML = r'''
    <section class="panel radar-detail" id="radarDetailPanel">
      <div class="radar-detail-head"><div><h3>板块体检</h3><p>完全基于现有日线价格计算，避免引入不可核验的主观预测。</p></div><span class="badge" id="radarTrendBadge">—</span></div>
      <div class="radar-kpis" id="radarKpis"></div>
      <p class="radar-diagnosis" id="radarDiagnosis">正在读取状态…</p>
    </section>
'''

JS = r'''
// SECTOR_RADAR_V15
function radarNum(v,d=1){const n=Number(v);return Number.isFinite(n)?n.toFixed(d):'—'}
function radarPct(v,d=1){const n=Number(v);return Number.isFinite(n)?`${n>0?'+':''}${n.toFixed(d)}%`:'—'}
function radarEsc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function radarStateClass(s){if(['强趋势','趋势上行','中期偏强'].includes(s))return 'strong';if(s==='修复'||s==='震荡')return 'repair';if(s==='弱势')return 'weak';return ''}
function radarOpenSector(name){const item=sectors.find(x=>x.name===name);if(!item)return;activeSector=item.name;customRange=null;renderDetail(item);buildMenu();const sel=document.getElementById('mobileSector');if(sel)sel.value=item.name;const hero=document.querySelector('.hero');if(hero)hero.scrollIntoView({behavior:'smooth',block:'start'})}
function renderMarketRadar(){
  const rows=(sectors||[]).filter(x=>x?.radar?.available&&Number.isFinite(Number(x.radar.trend_strength)));
  const summary=document.getElementById('radarSummary'),scatter=document.getElementById('radarScatter'),tableWrap=document.getElementById('radarTableWrap');if(!summary||!scatter||!tableWrap)return;
  if(!rows.length){summary.innerHTML='<div class="radar-missing">暂无足够日线数据生成雷达。</div>';scatter.innerHTML='';tableWrap.innerHTML='';return}
  const trendN=rows.filter(x=>['强趋势','趋势上行','中期偏强'].includes(x.radar.trend_state)).length,rsN=rows.filter(x=>Number(x.radar.rs60)>0).length,highPct=rows.filter(x=>Number(x.radar.price_percentile_250d)>=80).length;
  summary.innerHTML=[['可计算板块',`${rows.length}`],['中期偏强',`${trendN}`],['RS60跑赢300',`${rsN}`],['250日高位区间',`${highPct}`]].map(([a,b])=>`<div class="radar-summary-card"><span>${a}</span><strong>${b}</strong></div>`).join('');
  const W=720,H=350,pad={l:48,r:18,t:18,b:38},xs=rows.map(x=>Number(x.radar.rs60)).filter(Number.isFinite),ys=rows.map(x=>Number(x.radar.trend_strength)).filter(Number.isFinite);let xAbs=Math.max(5,...xs.map(x=>Math.abs(x))),yAbs=Math.max(5,...ys.map(y=>Math.abs(y)));xAbs=Math.min(Math.ceil(xAbs*1.12),80);yAbs=Math.min(Math.ceil(yAbs*1.12),80);const xPos=x=>pad.l+(Math.max(-xAbs,Math.min(xAbs,x))+xAbs)/(2*xAbs)*(W-pad.l-pad.r),yPos=y=>H-pad.b-(Math.max(-yAbs,Math.min(yAbs,y))+yAbs)/(2*yAbs)*(H-pad.t-pad.b),x0=xPos(0),y0=yPos(0),ranked=[...rows].sort((a,b)=>(Math.abs(Number(b.radar.rs60))+Math.abs(Number(b.radar.trend_strength)))-(Math.abs(Number(a.radar.rs60))+Math.abs(Number(a.radar.trend_strength)))),labelSet=new Set(ranked.slice(0,14).map(x=>x.name));
  let svg=`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="板块相对强度与趋势强度散点图">`;for(const f of [-.5,.5])svg+=`<line class="radar-grid" x1="${xPos(xAbs*f)}" y1="${pad.t}" x2="${xPos(xAbs*f)}" y2="${H-pad.b}"/><line class="radar-grid" x1="${pad.l}" y1="${yPos(yAbs*f)}" x2="${W-pad.r}" y2="${yPos(yAbs*f)}"/>`;svg+=`<line class="radar-axis" x1="${x0}" y1="${pad.t}" x2="${x0}" y2="${H-pad.b}"/><line class="radar-axis" x1="${pad.l}" y1="${y0}" x2="${W-pad.r}" y2="${y0}"/><text class="radar-axis-label" x="${W-145}" y="${H-10}">RS60 → 相对更强</text><text class="radar-axis-label" x="8" y="14">趋势强度 ↑</text>`;
  for(const item of rows){const r=item.radar,x=Number(r.rs60),y=Number(r.trend_strength);if(!Number.isFinite(x)||!Number.isFinite(y))continue;const cx=xPos(x),cy=yPos(y),neg=(x<0||y<0)?' negative':'';svg+=`<g onclick="radarOpenSector('${radarEsc(item.name).replace(/'/g,'&#39;')}')"><title>${radarEsc(item.name)} · RS60 ${radarPct(x)} · 趋势 ${radarPct(y)}</title><circle class="radar-dot${neg}" cx="${cx.toFixed(1)}" cy="${cy.toFixed(1)}" r="5.2"/>${labelSet.has(item.name)?`<text class="radar-label" x="${(cx+7).toFixed(1)}" y="${(cy-6).toFixed(1)}">${radarEsc(item.name)}</text>`:''}</g>`}svg+='</svg>';scatter.innerHTML=svg;
  const sorted=[...rows].sort((a,b)=>(Number(b.radar.rs60)||-999)-(Number(a.radar.rs60)||-999));tableWrap.innerHTML=`<table class="radar-table"><thead><tr><th>板块</th><th>状态</th><th>RS60</th><th>距250日高点</th><th>价格分位</th><th>60日波动</th></tr></thead><tbody>${sorted.map(x=>{const r=x.radar;return `<tr onclick="radarOpenSector('${radarEsc(x.name).replace(/'/g,'&#39;')}')"><td>${radarEsc(x.name)}</td><td><span class="radar-state ${radarStateClass(r.trend_state)}">${radarEsc(r.trend_state||'—')}</span></td><td class="${Number(r.rs60)>0?'up':Number(r.rs60)<0?'down':''}">${radarPct(r.rs60)}</td><td>${radarPct(r.distance_250d_high)}</td><td>${Number.isFinite(Number(r.price_percentile_250d))?radarNum(r.price_percentile_250d,0)+'%':'—'}</td><td>${radarPct(r.volatility_60d_annualized)}</td></tr>`}).join('')}</tbody></table>`
}
function renderRadarDetail(item){
  const wrap=document.getElementById('radarKpis'),diag=document.getElementById('radarDiagnosis'),badge=document.getElementById('radarTrendBadge');if(!wrap||!diag||!badge)return;const r=item?.radar;if(!r?.available){wrap.innerHTML='<div class="radar-missing">该板块历史数据不足，暂无法生成体检。</div>';diag.textContent='等待更多日线数据。';badge.textContent='数据不足';badge.className='badge partial';return}
  badge.textContent=r.trend_state||'—';badge.className='badge '+(radarStateClass(r.trend_state)==='strong'?'ok':radarStateClass(r.trend_state)==='weak'?'error':'partial');const vals=[['趋势状态',r.trend_state||'—'],['RS60',radarPct(r.rs60)],['当前回撤',radarPct(r.current_drawdown)],['距250日高点',radarPct(r.distance_250d_high)],['250日价格分位',Number.isFinite(Number(r.price_percentile_250d))?radarNum(r.price_percentile_250d,0)+'%':'—'],['60日年化波动',radarPct(r.volatility_60d_annualized)]];wrap.innerHTML=vals.map(([a,b])=>`<div class="radar-kpi"><span>${a}</span><strong>${b}</strong></div>`).join('');
  const rs=Number(r.rs60),dist=Number(r.distance_250d_high),pp=Number(r.price_percentile_250d),vol=Number(r.volatility_60d_annualized),parts=[`${item.name}当前处于“${r.trend_state}”状态。`];if(Number.isFinite(rs))parts.push(`近60个共同交易日相对沪深300${rs>=0?'跑赢':'跑输'}约${Math.abs(rs).toFixed(1)}个百分点。`);if(Number.isFinite(dist))parts.push(`现价距离过去250个交易日高点${Math.abs(dist).toFixed(1)}%。`);if(Number.isFinite(pp))parts.push(`当前价格位于过去250个交易日约${pp.toFixed(0)}%分位。`);if(Number.isFinite(vol))parts.push(`近60日年化波动率约${vol.toFixed(1)}%。`);diag.textContent=parts.join(' ')
}
const radarBaseRenderDetail=renderDetail;renderDetail=function(item){radarBaseRenderDetail(item);renderRadarDetail(item);renderMarketRadar()};
'''


def patch_html():
    text = INDEX_PATH.read_text(encoding="utf-8")
    if VERSION_MARKER in text:
        return
    if "</style>" not in text:
        raise RuntimeError("style close marker missing")
    text = text.replace("</style>", CSS + "\n</style>", 1)
    hero_marker = '    <section class="panel hero">'
    chart_marker = '    <section class="panel chart-panel">'
    js_marker = "$('#sideSearch').oninput=buildMenu;"
    if hero_marker not in text or chart_marker not in text or js_marker not in text:
        raise RuntimeError("expected HTML/JS marker missing")
    text = text.replace(hero_marker, MARKET_HTML + "\n" + hero_marker, 1)
    text = text.replace(chart_marker, DETAIL_HTML + "\n" + chart_marker, 1)
    text = text.replace(js_marker, JS + "\n" + js_marker, 1)
    text = text.replace("板块长期涨跌雷达", "板块雷达 1.5 · 市场状态与ETF研究", 1)
    text = text.replace("左侧选板块，上方切换周期；图上移动鼠标或手指可逐日查看涨跌，并可叠加沪深300作对比。", "先用全市场雷达观察相对强弱与趋势，再进入板块详情核对历史走势、风险和代表ETF。", 1)
    INDEX_PATH.write_text(text, encoding="utf-8")


def main():
    payload = patch_data()
    patch_html()
    print(f"[done] Sector Radar 1.5: metrics={payload.get('radar_summary', {}).get('available', 0)} and UI patched")


if __name__ == "__main__":
    main()
