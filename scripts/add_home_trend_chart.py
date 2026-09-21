#!/usr/bin/env python3
"""Add a normalized multi-index trend chart to the homepage."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "docs" / "index.html"
MARKER = "HOME_TREND_CHART"

CSS = r'''
/* HOME_TREND_CHART */
.home-trend-panel{padding:18px 20px 16px;overflow:hidden}
.home-trend-head{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;margin-bottom:10px}
.home-trend-head h3{margin:0;font-size:17px}.home-trend-head p{margin:5px 0 0;color:var(--muted);font-size:11px;line-height:1.6}
.home-trend-periods{display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end}
.home-trend-period{border:1px solid var(--line);background:var(--paper);color:var(--muted);border-radius:8px;padding:6px 9px;font-size:10px;font-weight:800;cursor:pointer}
.home-trend-period:hover{border-color:var(--blue);color:var(--ink)}.home-trend-period.active{border-color:var(--blue);background:var(--blue2);color:var(--blue)}
.home-trend-legend{display:flex;align-items:center;gap:8px 12px;flex-wrap:wrap;margin:0 0 8px;min-height:24px}
.home-trend-legend button{border:0;background:transparent;color:var(--ink);padding:3px 2px;cursor:pointer;font-size:10px;display:inline-flex;align-items:center;gap:6px;opacity:.95}
.home-trend-legend button.off{opacity:.35}.home-trend-swatch{width:18px;height:3px;border-radius:999px;display:inline-block}.home-trend-ret{font-variant-numeric:tabular-nums;font-weight:850}
.home-trend-wrap{position:relative;height:360px;border:1px solid var(--line);border-radius:12px;overflow:hidden;background:linear-gradient(180deg,color-mix(in srgb,var(--paper) 96%,var(--blue2)),var(--paper))}
.home-trend-svg{width:100%;height:100%;display:block}.home-trend-grid{stroke:var(--line);stroke-width:1}.home-trend-zero{stroke:color-mix(in srgb,var(--muted) 55%,transparent);stroke-width:1;stroke-dasharray:4 4}.home-trend-axis{fill:var(--muted);font-size:10px}.home-trend-line{fill:none;stroke-width:2.3;stroke-linecap:round;stroke-linejoin:round}.home-trend-dot{fill:var(--paper);stroke-width:2}.home-trend-cross{stroke:color-mix(in srgb,var(--muted) 55%,transparent);stroke-width:1;stroke-dasharray:3 3}.home-trend-hit{fill:transparent;cursor:crosshair}
.home-trend-tip{position:absolute;z-index:5;display:none;min-width:185px;max-width:250px;padding:9px 10px;border-radius:10px;background:rgba(15,23,42,.94);color:#fff;box-shadow:0 10px 30px rgba(0,0,0,.22);font-size:10px;line-height:1.55;pointer-events:none}.home-trend-tip strong{display:block;font-size:11px;margin-bottom:4px}.home-trend-tip-row{display:flex;align-items:center;justify-content:space-between;gap:12px}.home-trend-tip-row span:first-child{display:flex;align-items:center;gap:5px}.home-trend-tip-dot{width:7px;height:7px;border-radius:50%;display:inline-block}
.home-trend-empty{height:100%;display:grid;place-items:center;color:var(--muted);font-size:12px}
@media(max-width:760px){.home-trend-panel{padding:15px 12px}.home-trend-head{display:block}.home-trend-periods{justify-content:flex-start;margin-top:10px}.home-trend-wrap{height:300px}.home-trend-legend{gap:6px 9px}.home-trend-legend button{font-size:9px}}
'''

JS = r'''
// HOME_TREND_CHART
const homeTrendNames=['沪深300','中证500','创业板','科创板','恒生科技'];
const homeTrendColors={'沪深300':'#4f7cff','中证500':'#16a085','创业板':'#f59e0b','科创板':'#a855f7','恒生科技':'#ef5da8'};
const homeTrendPeriods=[['3m','3个月',92],['6m','6个月',184],['1y','1年',366],['3y','3年',1098],['5y','5年',1830]];
let homeTrendPeriod='1y';
let homeTrendHidden=new Set();
function htRows(s){return (s?.history||[]).filter(r=>Array.isArray(r)&&r.length>=2&&r[0]&&Number.isFinite(Number(r[1]))&&Number(r[1])>0).map(r=>[String(r[0]),Number(r[1])]).sort((a,b)=>a[0].localeCompare(b[0]))}
function htWindowRows(rows,days){if(!rows.length)return[];const end=new Date(rows[rows.length-1][0]+'T00:00:00');const start=new Date(end);start.setDate(start.getDate()-days);const key=start.toISOString().slice(0,10);const out=rows.filter(r=>r[0]>=key);return out.length>=2?out:rows.slice(-Math.min(rows.length,2))}
function htPct(v){if(!Number.isFinite(v))return '—';return `${v>=0?'+':''}${v.toFixed(1)}%`}
function htSeries(){const days=(homeTrendPeriods.find(x=>x[0]===homeTrendPeriod)||homeTrendPeriods[2])[2];return homeTrendNames.map(name=>{const s=(sectors||[]).find(x=>x?.name===name),rows=htWindowRows(htRows(s),days);if(rows.length<2)return{name,rows:[],ret:null};const base=rows[0][1];return{name,rows:rows.map(r=>[r[0],(r[1]/base-1)*100]),ret:(rows[rows.length-1][1]/base-1)*100}}).filter(x=>x.rows.length>=2)}
function htEnsurePanel(){if(document.getElementById('homeTrendPanel'))return;const home=document.getElementById('homePanel');if(!home)return;const panel=document.createElement('section');panel.className='panel home-trend-panel';panel.id='homeTrendPanel';panel.innerHTML=`<div class="home-trend-head"><div><h3>主要指数趋势</h3><p>所选周期起点统一归一为 0%，用于比较市场风格与相对强弱。点击图例可隐藏/显示单条曲线。</p></div><div class="home-trend-periods" id="homeTrendPeriods"></div></div><div class="home-trend-legend" id="homeTrendLegend"></div><div class="home-trend-wrap" id="homeTrendWrap"><div class="home-trend-empty">正在生成趋势图…</div><div class="home-trend-tip" id="homeTrendTip"></div></div>`;const hero=home.querySelector('.home-hero');if(hero)hero.after(panel);else home.prepend(panel);const periods=document.getElementById('homeTrendPeriods');periods.innerHTML=homeTrendPeriods.map(x=>`<button type="button" class="home-trend-period ${x[0]===homeTrendPeriod?'active':''}" data-ht-period="${x[0]}">${x[1]}</button>`).join('');periods.querySelectorAll('[data-ht-period]').forEach(b=>b.onclick=()=>{homeTrendPeriod=b.dataset.htPeriod;periods.querySelectorAll('[data-ht-period]').forEach(x=>x.classList.toggle('active',x.dataset.htPeriod===homeTrendPeriod));renderHomeTrend()});window.addEventListener('resize',()=>{if(navPage==='home')renderHomeTrend()})}
function renderHomeTrend(){htEnsurePanel();const wrap=document.getElementById('homeTrendWrap'),legend=document.getElementById('homeTrendLegend');if(!wrap||!legend)return;const series=htSeries();legend.innerHTML=series.map(s=>`<button type="button" class="${homeTrendHidden.has(s.name)?'off':''}" data-ht-name="${s.name}"><i class="home-trend-swatch" style="background:${homeTrendColors[s.name]}"></i><span>${s.name}</span><b class="home-trend-ret">${htPct(s.ret)}</b></button>`).join('');legend.querySelectorAll('[data-ht-name]').forEach(b=>b.onclick=()=>{const n=b.dataset.htName;if(homeTrendHidden.has(n))homeTrendHidden.delete(n);else homeTrendHidden.add(n);renderHomeTrend()});const active=series.filter(s=>!homeTrendHidden.has(s.name));if(!active.length){wrap.innerHTML='<div class="home-trend-empty">请至少保留一条趋势线</div><div class="home-trend-tip" id="homeTrendTip"></div>';return}const all=active.flatMap(s=>s.rows.map(r=>({d:r[0],v:r[1]})));if(!all.length){wrap.innerHTML='<div class="home-trend-empty">暂无足够历史数据</div><div class="home-trend-tip" id="homeTrendTip"></div>';return}const width=Math.max(640,wrap.clientWidth||900),height=Math.max(280,wrap.clientHeight||360),pad={l:50,r:18,t:14,b:30};const dates=all.map(x=>x.d).sort(),d0=dates[0],d1=dates[dates.length-1],t0=new Date(d0+'T00:00:00').getTime(),t1=new Date(d1+'T00:00:00').getTime(),vals=all.map(x=>x.v),rawMin=Math.min(...vals,0),rawMax=Math.max(...vals,0),span=Math.max(5,rawMax-rawMin),yMin=Math.floor((rawMin-span*.08)/5)*5,yMax=Math.ceil((rawMax+span*.08)/5)*5,x=d=>pad.l+(new Date(d+'T00:00:00').getTime()-t0)/(Math.max(1,t1-t0))*(width-pad.l-pad.r),y=v=>pad.t+(yMax-v)/(Math.max(1,yMax-yMin))*(height-pad.t-pad.b);const ticks=[];for(let i=0;i<=4;i++)ticks.push(yMin+(yMax-yMin)*i/4);const dateTicks=[0,.25,.5,.75,1].map(f=>new Date(t0+(t1-t0)*f)).map(d=>d.toISOString().slice(0,10));const paths=active.map(s=>`<path class="home-trend-line" data-ht-line="${s.name}" stroke="${homeTrendColors[s.name]}" d="${s.rows.map((r,i)=>`${i?'L':'M'}${x(r[0]).toFixed(2)},${y(r[1]).toFixed(2)}`).join(' ')}"/>`).join('');const grid=ticks.map(v=>`<line class="home-trend-grid" x1="${pad.l}" x2="${width-pad.r}" y1="${y(v)}" y2="${y(v)}"/><text class="home-trend-axis" x="${pad.l-8}" y="${y(v)+3}" text-anchor="end">${v.toFixed(0)}%</text>`).join('');const dx=dateTicks.map((d,i)=>`<text class="home-trend-axis" x="${x(d)}" y="${height-9}" text-anchor="${i===0?'start':i===dateTicks.length-1?'end':'middle'}">${d.slice(2,7)}</text>`).join('');const zero=(yMin<=0&&yMax>=0)?`<line class="home-trend-zero" x1="${pad.l}" x2="${width-pad.r}" y1="${y(0)}" y2="${y(0)}"/>`:'';wrap.innerHTML=`<svg class="home-trend-svg" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none">${grid}${zero}${paths}${dx}<line id="homeTrendCross" class="home-trend-cross" x1="0" x2="0" y1="${pad.t}" y2="${height-pad.b}" visibility="hidden"/><g id="homeTrendDots"></g><rect id="homeTrendHit" class="home-trend-hit" x="${pad.l}" y="${pad.t}" width="${width-pad.l-pad.r}" height="${height-pad.t-pad.b}"/></svg><div class="home-trend-tip" id="homeTrendTip"></div>`;const hit=document.getElementById('homeTrendHit'),cross=document.getElementById('homeTrendCross'),dots=document.getElementById('homeTrendDots'),tip=document.getElementById('homeTrendTip');function nearest(rows,target){let lo=0,hi=rows.length-1;while(lo<hi){const mid=Math.floor((lo+hi)/2);if(rows[mid][0]<target)lo=mid+1;else hi=mid}const a=rows[lo],b=rows[Math.max(0,lo-1)];if(!b)return a;return Math.abs(new Date(a[0])-new Date(target))<Math.abs(new Date(b[0])-new Date(target))?a:b}function move(ev){const rect=hit.getBoundingClientRect(),px=Math.max(0,Math.min(rect.width,ev.clientX-rect.left)),tt=t0+(px/Math.max(1,rect.width))*(t1-t0),target=new Date(tt).toISOString().slice(0,10),rows=active.map(s=>({s,r:nearest(s.rows,target)})).filter(z=>z.r),showDate=rows[0]?.r?.[0]||target,cx=x(showDate);cross.setAttribute('x1',cx);cross.setAttribute('x2',cx);cross.setAttribute('visibility','visible');dots.innerHTML=rows.map(z=>`<circle class="home-trend-dot" cx="${x(z.r[0])}" cy="${y(z.r[1])}" r="3.5" stroke="${homeTrendColors[z.s.name]}"/>`).join('');tip.innerHTML=`<strong>${showDate}</strong>`+rows.map(z=>`<div class="home-trend-tip-row"><span><i class="home-trend-tip-dot" style="background:${homeTrendColors[z.s.name]}"></i>${z.s.name}</span><b>${htPct(z.r[1])}</b></div>`).join('');tip.style.display='block';const left=Math.min(Math.max(8,ev.clientX-wrap.getBoundingClientRect().left+12),Math.max(8,wrap.clientWidth-220)),top=Math.max(8,ev.clientY-wrap.getBoundingClientRect().top-18);tip.style.left=left+'px';tip.style.top=top+'px'}hit.addEventListener('pointermove',move);hit.addEventListener('pointerleave',()=>{cross.setAttribute('visibility','hidden');dots.innerHTML='';tip.style.display='none'})}
const htBaseRenderHome=renderHome;
renderHome=function(){htBaseRenderHome();renderHomeTrend()};
setTimeout(()=>{if(typeof navPage!=='undefined'&&navPage==='home')renderHomeTrend()},0);
'''


def main():
    text = INDEX.read_text(encoding="utf-8")
    if MARKER in text:
        print("[skip] home trend chart already installed")
        return
    if "NAV_HOME_UI" not in text:
        raise RuntimeError("homepage navigation must be installed first")
    if "</body>" not in text:
        raise RuntimeError("body marker missing")
    patch = f"\n<style>{CSS}</style>\n<script>{JS}</script>\n<!-- {MARKER} -->\n"
    text = text.replace("</body>", patch + "</body>", 1)
    INDEX.write_text(text, encoding="utf-8")
    print("[done] homepage trend chart installed")


if __name__ == "__main__":
    main()
