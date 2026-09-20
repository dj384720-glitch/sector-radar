#!/usr/bin/env python3
"""Create a dedicated research workspace and apply a glossy technology theme."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "docs" / "index.html"
MARKER = "RESEARCH_TERMINAL_UI"

CSS = r'''
/* RESEARCH_TERMINAL_UI */
:root{--bg:#050817;--paper:rgba(11,20,39,.78);--ink:#edf7ff;--muted:#8da6c3;--line:rgba(109,175,255,.16);--blue:#5ee7ff;--blue2:rgba(50,177,255,.12);--up:#ff6f91;--down:#43e6bd;--compare:#a78bfa;--shadow:0 18px 55px rgba(0,0,0,.28),inset 0 1px 0 rgba(255,255,255,.04)}
html,body{background:#050817!important;color:var(--ink)!important}body{background:radial-gradient(circle at 18% 0%,rgba(36,126,255,.18),transparent 34%),radial-gradient(circle at 86% 12%,rgba(133,77,255,.15),transparent 31%),radial-gradient(circle at 60% 100%,rgba(0,229,190,.09),transparent 30%),#050817!important}
.sidebar{background:linear-gradient(180deg,rgba(6,14,31,.98),rgba(5,10,24,.96))!important;border-right:1px solid rgba(94,231,255,.13)!important;box-shadow:18px 0 50px rgba(0,0,0,.2)}.brand{background:linear-gradient(135deg,rgba(94,231,255,.06),rgba(167,139,250,.04));border-bottom-color:rgba(94,231,255,.12)!important}.brand-kicker,.eyebrow{color:#69e8ff!important;text-shadow:0 0 18px rgba(94,231,255,.28)}
.panel{position:relative;background:linear-gradient(145deg,rgba(16,28,51,.82),rgba(8,16,32,.76))!important;border:1px solid rgba(107,190,255,.16)!important;box-shadow:0 18px 55px rgba(0,0,0,.25),inset 0 1px 0 rgba(255,255,255,.055)!important;backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px);overflow:hidden}.panel:before{content:"";position:absolute;pointer-events:none;left:4%;right:4%;top:0;height:1px;background:linear-gradient(90deg,transparent,rgba(114,226,255,.45),rgba(196,163,255,.3),transparent)}
.live,.period,.radar-summary-card,.radar-box,.radar2-box,.radar-change-box,.radar-kpi,.fund-table-wrap{background:rgba(7,15,31,.58)!important;border-color:rgba(104,184,255,.14)!important;box-shadow:inset 0 1px 0 rgba(255,255,255,.035)}.period:hover,.period.active{border-color:rgba(94,231,255,.48)!important;background:linear-gradient(135deg,rgba(30,139,255,.17),rgba(123,92,255,.12))!important;box-shadow:0 0 22px rgba(54,193,255,.09)}
.radar-box-title,.radar-change-title,.fund-table th,.radar-table th{background:rgba(12,25,47,.9)!important;color:var(--muted)!important}.details p,.benchmark,.subtitle,.footer,.radar-help,.fund-note,.radar2-note{color:var(--muted)!important}.menu button:hover{background:rgba(70,154,255,.1)!important;color:#fff}.menu button.active{background:linear-gradient(100deg,rgba(38,132,255,.28),rgba(102,75,255,.18))!important;box-shadow:inset 2px 0 0 #5ee7ff,0 0 22px rgba(30,149,255,.08)}
.side-search input,.mobile-select select,input[type=date],.tool-btn,.compare-switch,.terminal-control select{background:rgba(6,15,31,.78)!important;color:var(--ink)!important;border-color:rgba(99,180,255,.18)!important}.grid-line,.radar-grid{stroke:#152b48!important}.zero-line,.radar-axis{stroke:#31506f!important}.axis-label,.radar-axis-label{fill:#7895b6!important}.radar-label{fill:#a9bfd7!important}.line-path{stroke:#5ee7ff!important;filter:drop-shadow(0 0 4px rgba(94,231,255,.32))}.compare-path{stroke:#a78bfa!important}.chart-wrap{background:linear-gradient(180deg,rgba(5,14,29,.76),rgba(7,16,30,.4))!important}.radar-dot{fill:#56dfff!important;filter:drop-shadow(0 0 5px rgba(86,223,255,.32))}.radar-dot.negative{fill:#7b8da5!important}
.workspace-nav{padding:13px 12px 7px;border-bottom:1px solid rgba(255,255,255,.07)}.workspace-nav button{width:100%;border:1px solid rgba(104,184,255,.14);background:rgba(11,24,45,.62);color:#a9bdd4;border-radius:10px;padding:11px 12px;margin-bottom:7px;cursor:pointer;text-align:left;font-weight:800;font-size:12px;letter-spacing:.01em;transition:.2s}.workspace-nav button:hover{border-color:rgba(94,231,255,.36);color:#fff;transform:translateY(-1px)}.workspace-nav button.active{color:#ecfbff;background:linear-gradient(100deg,rgba(34,151,255,.24),rgba(116,76,255,.18));border-color:rgba(94,231,255,.38);box-shadow:0 8px 26px rgba(19,110,212,.12),inset 2px 0 0 #5ee7ff}.workspace-nav .nav-icon{display:inline-grid;width:23px;height:23px;place-items:center;margin-right:7px;border-radius:7px;background:rgba(94,231,255,.08);color:#73eaff}.workspace-separator{padding:8px 18px 3px;color:#607b99;font-size:10px;font-weight:850;letter-spacing:.14em}
.research-hero{padding:21px 22px;margin-bottom:14px;background:linear-gradient(135deg,rgba(11,31,58,.92),rgba(22,18,52,.78))!important}.research-hero-grid{display:grid;grid-template-columns:1.4fr repeat(4,minmax(110px,.6fr));gap:10px;align-items:stretch}.research-intro{padding:6px 5px}.research-intro h3{font-size:23px;margin:3px 0 7px;letter-spacing:-.03em}.research-intro p{margin:0;color:var(--muted);font-size:12px;line-height:1.7;max-width:620px}.research-stat{border:1px solid rgba(95,183,255,.15);border-radius:12px;padding:12px;background:linear-gradient(145deg,rgba(8,20,39,.75),rgba(10,17,35,.58));box-shadow:inset 0 1px 0 rgba(255,255,255,.04)}.research-stat span{display:block;color:#7893ae;font-size:10px}.research-stat strong{display:block;margin-top:6px;font-size:20px;font-variant-numeric:tabular-nums;color:#eafaff}
.terminal-panel{padding:18px 20px;margin-bottom:14px}.terminal-head{display:flex;justify-content:space-between;gap:16px;align-items:flex-start;margin-bottom:12px}.terminal-head h3{margin:0;font-size:18px}.terminal-head p{margin:5px 0 0;color:var(--muted);font-size:12px;line-height:1.65}.terminal-controls{display:flex;gap:8px;flex-wrap:wrap}.terminal-control{display:flex;align-items:center;gap:6px}.terminal-control label{font-size:10px;color:var(--muted)}.terminal-control select{height:34px;border:1px solid var(--line);border-radius:8px;padding:0 9px;min-width:126px}.terminal-table-wrap{overflow:auto;border:1px solid rgba(100,185,255,.15);border-radius:11px;max-height:470px}.terminal-table{width:100%;border-collapse:collapse;min-width:1060px}.terminal-table th,.terminal-table td{padding:11px 12px;border-bottom:1px solid rgba(100,185,255,.1);font-size:11px;text-align:right;white-space:nowrap}.terminal-table th{position:sticky;top:0;z-index:2;background:#0b1930;color:#7f9bb9;font-size:10px}.terminal-table th:first-child,.terminal-table td:first-child,.terminal-table th:nth-child(2),.terminal-table td:nth-child(2){text-align:left}.terminal-table tbody tr:hover{background:rgba(78,166,255,.06)}.meta-track{display:block;max-width:240px;overflow:hidden;text-overflow:ellipsis;color:#b6c9dc}.meta-muted{color:#6f88a4}.meta-glow{color:#6eeaff;font-weight:850}.fee-low{color:#43e6bd}.liquidity{font-variant-numeric:tabular-nums}
#marketRadarPanel,#radarChangePanel,#etfTerminalPanel,#researchHero{display:none}body[data-workspace="research"] #marketRadarPanel,body[data-workspace="research"] #radarChangePanel,body[data-workspace="research"] #etfTerminalPanel,body[data-workspace="research"] #researchHero{display:block}body[data-workspace="research"] .detail-workspace{display:none!important}body[data-workspace="detail"] #marketRadarPanel,body[data-workspace="detail"] #radarChangePanel,body[data-workspace="detail"] #etfTerminalPanel,body[data-workspace="detail"] #researchHero{display:none!important}
@media(max-width:1180px){.research-hero-grid{grid-template-columns:1fr 1fr 1fr}.research-intro{grid-column:1/-1}}@media(max-width:760px){.workspace-nav{display:grid;grid-template-columns:1fr 1fr;gap:7px;padding:0 0 12px;border:0}.workspace-nav button{margin:0}.research-hero{padding:16px}.research-hero-grid{grid-template-columns:1fr 1fr}.research-intro{grid-column:1/-1}.terminal-head{display:block}.terminal-controls{margin-top:10px}}
'''

WORKSPACE_HTML = r'''
    <!-- RESEARCH_TERMINAL_UI -->
    <section class="panel research-hero" id="researchHero"><div class="research-hero-grid">
      <div class="research-intro"><div class="eyebrow">MARKET INTELLIGENCE / ETF LAB</div><h3>状态变化与ETF研究</h3><p>先观察板块相对强弱和状态切换，再核对研究基准是否为官方指数，最后比较同主题ETF的规模、流动性、费率、跟踪指数与同期表现。</p></div>
      <div class="research-stat"><span>官方指数升级</span><strong id="researchOfficial">—</strong></div><div class="research-stat"><span>仍使用回退口径</span><strong id="researchFallback">—</strong></div><div class="research-stat"><span>ETF档案覆盖</span><strong id="researchProfiles">—</strong></div><div class="research-stat"><span>近5日状态变化</span><strong id="researchEvents">—</strong></div>
    </div></section>
'''

TERMINAL_HTML = r'''
    <section class="panel terminal-panel" id="etfTerminalPanel"><div class="terminal-head">
      <div><h3>ETF选择终端</h3><p>同一板块下比较代表ETF。规模与费率来自公开基金档案，最新成交额来自公开实时行情；字段缺失时保持空白，不做推断。</p></div>
      <div class="terminal-controls"><div class="terminal-control"><label>板块</label><select id="terminalSector"></select></div><div class="terminal-control"><label>周期</label><select id="terminalPeriod"></select></div><div class="terminal-control"><label>排序</label><select id="terminalSort"><option value="size">规模</option><option value="turnover">成交额</option><option value="fee">费率</option><option value="return">周期涨跌</option></select></div></div>
    </div><div class="terminal-table-wrap" id="terminalTableWrap"><div class="fund-empty">正在读取ETF档案…</div></div><p class="fund-note">这里只提供工具属性和同期数据，不构成基金推荐或排名结论。规模为最近公开净资产规模；成交额为最近可获取交易日的市场成交额。</p></section>
'''

JS = r'''
// RESEARCH_TERMINAL_UI
let terminalPeriodValue='近1年';
function fmtYi(v){const n=Number(v);return Number.isFinite(n)?`${n.toFixed(n>=100?0:n>=10?1:2)}亿`:'—'}
function fmtFee(v){const n=Number(v);return Number.isFinite(n)?`${n.toFixed(2)}%`:'—'}
function terminalFundUrl(f){return typeof fundSourceUrl==='function'?fundSourceUrl(f):''}
function setWorkspace(view){const next=view==='research'?'research':'detail';document.body.dataset.workspace=next;document.querySelectorAll('[data-workspace-tab]').forEach(b=>b.classList.toggle('active',b.dataset.workspaceTab===next));const title=document.getElementById('pageTitle'),sub=document.getElementById('pageSubtitle');if(title)title.textContent=next==='research'?'状态变化与ETF研究':'板块雷达 · 板块详情';if(sub)sub.textContent=next==='research'?'观察全市场状态变化，核对官方指数口径，并比较同主题ETF的规模、流动性、费率与跟踪标的。':'选择板块查看长期走势、趋势状态、风险、研究口径和代表ETF。';if(next==='research'){renderResearchSummary();renderMarketRadar();renderRadarChanges();renderEtfTerminal()}window.scrollTo({top:0,behavior:'smooth'})}
function renderResearchSummary(){const b=window.__latestPayload?.benchmark_upgrade_summary||{},m=window.__latestPayload?.etf_metadata_summary||{},r=window.__latestPayload?.radar2_summary||{};const set=(id,v)=>{const e=document.getElementById(id);if(e)e.textContent=v};set('researchOfficial',`${b.official??'—'}/${b.requested??'—'}`);set('researchFallback',b.fallback??'—');set('researchProfiles',`${m.profile_ok??'—'}/${m.unique_funds??'—'}`);set('researchEvents',r.event_sectors_5d??'—')}
function fillTerminalControls(){const s=document.getElementById('terminalSector'),p=document.getElementById('terminalPeriod');if(!s||!p)return;if(!s.options.length){s.innerHTML=(sectors||[]).map(x=>`<option value="${radarEsc(x.name)}">${radarEsc(x.name)}</option>`).join('');const activeName=typeof activeSector==='string'?activeSector:(activeSector?.name||'');if(activeName)s.value=activeName}if(!p.options.length){p.innerHTML=(periods||[]).map(x=>`<option value="${radarEsc(x)}">${radarEsc(x)}</option>`).join('');p.value=terminalPeriodValue}}
function renderEtfTerminal(){fillTerminalControls();const s=document.getElementById('terminalSector'),p=document.getElementById('terminalPeriod'),sort=document.getElementById('terminalSort'),wrap=document.getElementById('terminalTableWrap');if(!s||!p||!sort||!wrap)return;const item=(sectors||[]).find(x=>x.name===s.value)||(sectors||[])[0];if(!item){wrap.innerHTML='<div class="fund-empty">暂无数据</div>';return}terminalPeriodValue=p.value||terminalPeriodValue;const sectorRet=Number(item?.returns?.[terminalPeriodValue]);let rows=(item.funds||[]).slice(0,5).map(f=>{const prof=f.profile||{},ret=Number(f.returns?.[terminalPeriodValue]),alpha=Number.isFinite(ret)&&Number.isFinite(sectorRet)?ret-sectorRet:null;return {f,prof,ret,alpha}});const key=sort.value;rows.sort((a,b)=>{if(key==='fee')return (Number(a.prof.total_fee_pct)||999)-(Number(b.prof.total_fee_pct)||999);if(key==='turnover')return (Number(b.prof.latest_turnover_yi)||-1)-(Number(a.prof.latest_turnover_yi)||-1);if(key==='return')return (Number(b.ret)||-999)-(Number(a.ret)||-999);return (Number(b.prof.asset_size_yi)||-1)-(Number(a.prof.asset_size_yi)||-1)});if(!rows.length){wrap.innerHTML='<div class="fund-empty">该板块暂无代表ETF数据</div>';return}wrap.innerHTML=`<table class="terminal-table"><thead><tr><th>基金</th><th>跟踪指数</th><th>规模</th><th>最新成交额</th><th>管理+托管</th><th>${radarEsc(terminalPeriodValue)}涨跌</th><th>相对板块</th><th>最大回撤</th><th>档案日期</th></tr></thead><tbody>${rows.map(({f,prof,ret,alpha})=>{const url=terminalFundUrl(f),name=radarEsc(f.name||'—'),code=radarEsc((f.code||'').replace(/^(sh|sz)/,''));return `<tr><td>${url?`<a class="fund-name fund-link" href="${radarEsc(url)}" target="_blank" rel="noopener">${name} ↗</a>`:`<span class="fund-name">${name}</span>`}<span class="fund-code">${code}</span></td><td><span class="meta-track" title="${radarEsc(prof.tracking_index||'')}">${radarEsc(prof.tracking_index||'—')}</span></td><td class="meta-glow">${fmtYi(prof.asset_size_yi)}</td><td class="liquidity">${fmtYi(prof.latest_turnover_yi)}</td><td class="${Number(prof.total_fee_pct)<=0.3?'fee-low':''}">${fmtFee(prof.total_fee_pct)}</td><td>${radar2FundFmt(f.returns?.[terminalPeriodValue])}</td><td>${radar2AlphaFmt(alpha)}</td><td>${drawdownFmt(f.drawdowns?.[terminalPeriodValue])}</td><td class="meta-muted">${radarEsc(prof.asset_size_date||prof.turnover_date||'—')}</td></tr>`}).join('')}</tbody></table>`}
function renderFunds(item){const funds=(item?.funds||[]).slice(0,5),wrap=$('#fundTableWrap'),period=$('#fundPeriod'),note=$('#fundNote');if(!wrap||!period||!note)return;period.textContent=activePeriod+' 指标';const sectorRet=Number(item?.returns?.[activePeriod]);note.textContent=customRange?`当前走势图使用自定义日期区间；ETF表仍按“${activePeriod}”固定周期显示。规模、费率和跟踪指数来自公开基金档案，成交额为最近可获取交易日公开行情。`:'ETF为主题相关代表样本，不构成推荐或排名。规模、费率和跟踪指数来自公开基金档案；成交额为最近可获取交易日公开行情。';if(!funds.length){wrap.innerHTML='<div class="fund-empty">该板块暂未生成代表基金数据</div>';return}wrap.innerHTML=`<table class="fund-table" style="min-width:1180px"><thead><tr><th>基金</th><th>跟踪指数</th><th>规模</th><th>成交额</th><th>费率</th><th>${radarEsc(activePeriod)}涨跌</th><th>相对板块</th><th>最大回撤</th></tr></thead><tbody>${funds.map(f=>{const prof=f.profile||{},url=terminalFundUrl(f),name=radarEsc(f.name||'—'),code=radarEsc((f.code||'').replace(/^(sh|sz)/,'')),fr=Number(f.returns?.[activePeriod]),alpha=Number.isFinite(fr)&&Number.isFinite(sectorRet)?fr-sectorRet:null;return `<tr><td>${url?`<a class="fund-name fund-link" href="${radarEsc(url)}" target="_blank" rel="noopener">${name} ↗</a>`:`<span class="fund-name">${name}</span>`}<span class="fund-code">${code}</span></td><td><span class="meta-track">${radarEsc(prof.tracking_index||'—')}</span></td><td class="meta-glow">${fmtYi(prof.asset_size_yi)}</td><td>${fmtYi(prof.latest_turnover_yi)}</td><td>${fmtFee(prof.total_fee_pct)}</td><td>${radar2FundFmt(f.returns?.[activePeriod])}</td><td>${radar2AlphaFmt(alpha)}</td><td>${drawdownFmt(f.drawdowns?.[activePeriod])}</td></tr>`}).join('')}</tbody></table>`}
function radarOpenSector(name){const item=sectors.find(x=>x.name===name);if(!item)return;activeSector=item.name;customRange=null;setWorkspace('detail');renderDetail(item);buildMenu();const sel=document.getElementById('mobileSector');if(sel)sel.value=item.name}
document.addEventListener('change',e=>{if(['terminalSector','terminalPeriod','terminalSort'].includes(e.target?.id))renderEtfTerminal()});
'''


def main():
    text = INDEX.read_text(encoding="utf-8")
    if MARKER in text:
        return
    if "</style>" not in text or '<div class="side-search">' not in text:
        raise RuntimeError("expected base markers missing")
    text = text.replace("</style>", CSS + "\n</style>", 1)

    nav = r'''<div class="workspace-nav"><button type="button" data-workspace-tab="detail" class="active" onclick="setWorkspace('detail')"><span class="nav-icon">◇</span>板块详情</button><button type="button" data-workspace-tab="research" onclick="setWorkspace('research')"><span class="nav-icon">◈</span>状态变化与ETF研究</button></div><div class="workspace-separator">SECTOR DIRECTORY</div>'''
    text = text.replace('<div class="side-search">', nav + '<div class="side-search">', 1)
    mobile_marker = '<div class="mobile-select"><select id="mobileSector"></select></div>'
    mobile_nav = r'''<div class="workspace-nav"><button type="button" data-workspace-tab="detail" class="active" onclick="setWorkspace('detail')">板块详情</button><button type="button" data-workspace-tab="research" onclick="setWorkspace('research')">状态变化与ETF研究</button></div>'''
    if mobile_marker in text:
        text = text.replace(mobile_marker, mobile_nav + mobile_marker, 1)

    market_marker = '    <section class="panel radar-market" id="marketRadarPanel">'
    hero_marker = '    <section class="panel hero">'
    if market_marker not in text or hero_marker not in text:
        raise RuntimeError("radar panels missing; run prior patchers first")
    text = text.replace(market_marker, WORKSPACE_HTML + "\n" + market_marker, 1)
    text = text.replace(hero_marker, TERMINAL_HTML + "\n" + hero_marker, 1)

    for snippet in [
        '<section class="panel hero">','<section class="stats">','<section class="panel radar-detail" id="radarDetailPanel">','<section class="panel radar2-detail" id="radar2DetailPanel">','<section class="panel chart-panel">','<section class="panel fund-panel" id="fundPanel">','<section class="panel details">',
    ]:
        if snippet in text:
            text = text.replace(snippet, snippet.replace('class="', 'class="detail-workspace '), 1)

    text = text.replace('<h2>板块雷达 2.0 · 状态变化与ETF研究</h2>', '<h2 id="pageTitle">板块雷达 · 板块详情</h2>', 1)
    text = text.replace('<p class="subtitle">先看全市场强弱，再看近5/20日状态变化；进入板块详情核对趋势、口径风险与代表ETF的相对表现。</p>', '<p class="subtitle" id="pageSubtitle">选择板块查看长期走势、趋势状态、风险、研究口径和代表ETF。</p>', 1)
    if 'id="pageTitle"' not in text: text = text.replace('<h2>', '<h2 id="pageTitle">', 1)
    if 'id="pageSubtitle"' not in text: text = text.replace('<p class="subtitle">', '<p class="subtitle" id="pageSubtitle">', 1)
    text = text.replace("RADAR 2.0", "LIVE SIGNALS").replace("RADAR 1.5", "LIVE SIGNALS")
    text = text.replace("板块雷达 2.0 · 状态变化与ETF研究", "板块雷达 · 板块详情").replace("板块雷达 1.5 · 市场状态与ETF研究", "板块雷达 · 板块详情")

    js_marker = "$('#sideSearch').oninput=buildMenu;"
    if js_marker not in text: raise RuntimeError("JS insertion marker missing")
    text = text.replace(js_marker, JS + "\n" + js_marker, 1)
    load_marker = ".then(payload=>{sectors=payload.sectors||[];periods=payload.periods||FALLBACK_PERIODS;"
    if load_marker in text:
        text = text.replace(load_marker, ".then(payload=>{window.__latestPayload=payload;sectors=payload.sectors||[];periods=payload.periods||FALLBACK_PERIODS;", 1)
    init_marker = "buildMenu();buildMobile();renderDetail()"
    if init_marker in text:
        text = text.replace(init_marker, "buildMenu();buildMobile();renderDetail();setWorkspace('detail')", 1)

    INDEX.write_text(text, encoding="utf-8")
    print("[done] research workspace installed; visible version labels removed; glossy theme applied")


if __name__ == "__main__":
    main()
