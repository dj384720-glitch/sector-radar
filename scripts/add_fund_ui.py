#!/usr/bin/env python3
"""Patch the static page with a representative-fund return/drawdown panel.

The script is deliberately idempotent.  On repositories that already contain
an older version of the fund panel it upgrades the renderer in-place so every
fund row links to the same Tencent Finance quote website used as the market-data
source.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "docs" / "index.html"

text = INDEX.read_text(encoding="utf-8")

css = r'''
.fund-panel{margin-top:14px;padding:18px 20px}.fund-head{display:flex;justify-content:space-between;gap:16px;align-items:flex-start;margin-bottom:12px}.fund-head h3{margin:0;font-size:17px}.fund-head p{margin:4px 0 0;color:var(--muted);font-size:12px;line-height:1.6}.fund-period{font-size:12px;color:var(--blue);font-weight:800;white-space:nowrap}.fund-table-wrap{overflow-x:auto;border:1px solid var(--line);border-radius:10px}.fund-table{width:100%;border-collapse:collapse;min-width:860px}.fund-table th,.fund-table td{padding:12px 13px;border-bottom:1px solid var(--line);text-align:left;font-size:13px;vertical-align:middle}.fund-table th{font-size:11px;color:var(--muted);font-weight:800;background:#fbfcff;letter-spacing:.02em}.fund-table tr:last-child td{border-bottom:0}.fund-name{font-weight:800;color:var(--ink)}.fund-link{text-decoration:none}.fund-link:hover{color:var(--blue);text-decoration:underline}.fund-code{display:block;margin-top:3px;font-size:11px;color:var(--muted);font-variant-numeric:tabular-nums}.fund-source-link{display:inline-flex;align-items:center;gap:4px;color:var(--blue);font-size:12px;font-weight:800;text-decoration:none;white-space:nowrap}.fund-source-link:hover{text-decoration:underline}.fund-metric{font-weight:850;font-variant-numeric:tabular-nums}.drawdown{color:var(--down)}.fund-empty{padding:24px;color:var(--muted);font-size:13px}.fund-note{margin:10px 2px 0;color:var(--muted);font-size:11px;line-height:1.6}
'''

fund_html = r'''
    <section class="panel fund-panel" id="fundPanel">
      <div class="fund-head">
        <div><h3>板块代表基金</h3><p>每个板块展示 5 只公开交易 ETF；涨跌与最大回撤随上方固定周期切换。基金名称和“腾讯财经”均可点击查看原始行情页面。</p></div>
        <div class="fund-period" id="fundPeriod">—</div>
      </div>
      <div class="fund-table-wrap" id="fundTableWrap"><div class="fund-empty">正在读取基金数据…</div></div>
      <p class="fund-note" id="fundNote">基金为主题相关的代表性样本，不构成推荐或排名。涨跌与回撤按腾讯财经公开复权价格计算；最大回撤指所选周期内从阶段高点到随后低点的最大跌幅。</p>
    </section>

'''

# First-time installation of the panel.
if 'id="fundPanel"' not in text:
    marker = '@media(max-width:1180px)'
    if marker not in text:
        raise RuntimeError("CSS marker missing")
    text = text.replace(marker, css + marker, 1)

    html_marker = '    <section class="panel details">'
    if html_marker not in text:
        raise RuntimeError("HTML marker missing")
    text = text.replace(html_marker, fund_html + html_marker, 1)

    # Ensure renderDetail invokes the fund renderer after drawing the chart.
    old = "drawChart(x,bounds)}"
    new = "drawChart(x,bounds);renderFunds(x)}"
    if old not in text:
        raise RuntimeError("renderDetail tail marker missing")
    text = text.replace(old, new, 1)
else:
    # Existing installations may have the old CSS.  Add only the link styles and
    # table width needed by the new source column.
    if '.fund-source-link{' not in text:
        marker = '@media(max-width:1180px)'
        if marker not in text:
            raise RuntimeError("CSS marker missing")
        upgrade_css = r'''
.fund-link{text-decoration:none}.fund-link:hover{color:var(--blue);text-decoration:underline}.fund-source-link{display:inline-flex;align-items:center;gap:4px;color:var(--blue);font-size:12px;font-weight:800;text-decoration:none;white-space:nowrap}.fund-source-link:hover{text-decoration:underline}
'''
        text = text.replace(marker, upgrade_css + marker, 1)

# Always install/upgrade the linked renderer exactly once.  A later function
# declaration overrides an older renderFunds definition already in the page.
if 'FUND_SOURCE_LINKS_V1' not in text:
    linked_js = r'''
// FUND_SOURCE_LINKS_V1
function fundSourceUrl(f){
  const code=String(f?.code||'').trim();
  const explicit=String(f?.source_url||'').trim();
  if(/^https:\/\/gu\.qq\.com\/(?:sh|sz)\d{6}\/gp(?:[?#].*)?$/.test(explicit))return explicit;
  if(/^(?:sh|sz)\d{6}$/.test(code))return `https://gu.qq.com/${code}/gp`;
  return '';
}
function fundFmt(v){if(v===null||v===undefined||!Number.isFinite(Number(v)))return '<span class="empty">—</span>';const n=Number(v);return `<span class="fund-metric ${n>0?'up':n<0?'down':''}">${pct(n)}</span>`}
function drawdownFmt(v){if(v===null||v===undefined||!Number.isFinite(Number(v)))return '<span class="empty">—</span>';return `<span class="fund-metric drawdown">${Number(v).toFixed(2)}%</span>`}
function renderFunds(item){
  const funds=(item?.funds||[]).slice(0,5),wrap=$('#fundTableWrap'),period=$('#fundPeriod'),note=$('#fundNote');
  period.textContent=activePeriod+' 指标';
  if(customRange){note.textContent=`当前图表为自定义日期区间；基金表仍按“${activePeriod}”固定周期显示。基金为主题相关的代表性样本，不构成推荐或排名。点击基金名称或“腾讯财经”可打开该基金的原始行情来源页。最大回撤按所选固定周期内公开复权价格计算。`}
  else{note.textContent='基金为主题相关的代表性样本，不构成推荐或排名。涨跌与回撤按腾讯财经公开复权价格计算；点击基金名称或“腾讯财经”可打开该基金的原始行情来源页。最大回撤指所选周期内从阶段高点到随后低点的最大跌幅。'}
  if(!funds.length){wrap.innerHTML='<div class="fund-empty">该板块暂未生成代表基金数据</div>';return}
  const rows=funds.map(f=>{
    const url=fundSourceUrl(f),name=esc(f.name||'—'),code=esc((f.code||'').replace(/^(sh|sz)/,''));
    const nameHtml=url?`<a class="fund-name fund-link" href="${esc(url)}" target="_blank" rel="noopener noreferrer" title="打开腾讯财经原始行情页">${name} ↗</a>`:`<span class="fund-name">${name}</span>`;
    const sourceHtml=url?`<a class="fund-source-link" href="${esc(url)}" target="_blank" rel="noopener noreferrer">腾讯财经 ↗</a>`:'<span class="empty">—</span>';
    return `<tr><td>${nameHtml}<span class="fund-code">${code}</span></td><td>${fundFmt(f.returns?.[activePeriod])}</td><td>${drawdownFmt(f.drawdowns?.[activePeriod])}</td><td>${esc(f.latest_date||'—')}</td><td>${esc(f.start_date||'—')}</td><td>${sourceHtml}</td></tr>`
  }).join('');
  wrap.innerHTML=`<table class="fund-table"><thead><tr><th>基金</th><th>${esc(activePeriod)}涨跌</th><th>最大回撤</th><th>数据截至</th><th>历史起点</th><th>行情来源</th></tr></thead><tbody>${rows}</tbody></table>`
}
'''
    js_marker = "$('#sideSearch').oninput=buildMenu;"
    if js_marker not in text:
        raise RuntimeError("JS insertion marker missing")
    text = text.replace(js_marker, linked_js + '\n' + js_marker, 1)

INDEX.write_text(text, encoding="utf-8")
print("[done] fund panel UI installed/upgraded with source links")
