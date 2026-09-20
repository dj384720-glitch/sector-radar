#!/usr/bin/env python3
"""Final UI polish: remove workspace nav/checkup and add three persistent color themes."""
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
INDEX_PATH=ROOT/'docs'/'index.html'
MARKER='THEME_SETTINGS_UI'

CSS=r'''
/* THEME_SETTINGS_UI */
:root{--bg:#f7f1e7;--paper:#fffaf2;--ink:#2a3442;--muted:#6f7782;--line:#e7dccb;--blue:#5875ae;--blue2:#eef2f8;--up:#c65b54;--down:#2d8b68;--compare:#8792a0;--shadow:0 12px 34px rgba(92,72,43,.09);--sidebar:#2a313b;--sidebar2:#343d49;--glow:rgba(112,147,211,.13);--chart:#fffdf8;--head:#f5eee3}
body[data-theme="green"]{--bg:#eef7f0;--paper:#fbfffc;--ink:#213329;--muted:#68786e;--line:#d6e8d9;--blue:#4c816d;--blue2:#e7f3eb;--up:#b75b55;--down:#267d5d;--compare:#7d8f84;--shadow:0 12px 34px rgba(43,91,61,.09);--sidebar:#263a32;--sidebar2:#30483d;--glow:rgba(89,178,137,.14);--chart:#fbfffc;--head:#edf7ef}
body[data-theme="dark"]{--bg:#08111f;--paper:#0f1d30;--ink:#e8f0fb;--muted:#8fa2b8;--line:#203853;--blue:#69a9ff;--blue2:#142945;--up:#ff7d86;--down:#47d2a0;--compare:#91a7bd;--shadow:0 18px 55px rgba(0,0,0,.28);--sidebar:#07111e;--sidebar2:#101f32;--glow:rgba(69,143,255,.22);--chart:#0b1727;--head:#10243b}
html,body{background:radial-gradient(circle at 82% -8%,var(--glow),transparent 34%),var(--bg)!important;color:var(--ink)!important;transition:background .25s ease,color .25s ease}.sidebar{background:linear-gradient(180deg,var(--sidebar),var(--sidebar2))!important;border-right:1px solid var(--line)!important;box-shadow:12px 0 36px rgba(0,0,0,.12)!important}.panel,.live{background:var(--paper)!important;color:var(--ink)!important;border-color:var(--line)!important;box-shadow:inset 0 1px 0 rgba(255,255,255,.04),var(--shadow)!important;backdrop-filter:blur(14px)}.panel:before{display:none!important}.period,.radar-summary-card,.radar-box,.radar2-box,.radar-change-box,.radar-kpi,.fund-table-wrap,.research-stat,.terminal-table-wrap{background:var(--paper)!important;border-color:var(--line)!important;color:var(--ink)!important}.period.active,.period:hover{background:var(--blue2)!important;border-color:var(--blue)!important;box-shadow:none!important}.radar-box-title,.radar-change-title,.fund-table th,.radar-table th,.terminal-table th{background:var(--head)!important;color:var(--muted)!important}.chart-wrap{background:linear-gradient(180deg,var(--chart),var(--paper))!important}.side-search input,.mobile-select select,input[type=date],.tool-btn,.compare-switch,.terminal-control select{background:var(--paper)!important;color:var(--ink)!important;border-color:var(--line)!important}.line-path{stroke:var(--blue)!important;filter:none!important}.compare-path{stroke:var(--compare)!important}.grid-line,.radar-grid{stroke:color-mix(in srgb,var(--line) 75%,transparent)!important}.zero-line,.radar-axis{stroke:var(--line)!important}.axis-label,.radar-axis-label{fill:var(--muted)!important}.radar-label{fill:var(--ink)!important}.radar-dot{fill:var(--blue)!important;filter:none!important}.radar-dot.negative{fill:var(--compare)!important}.details p,.benchmark,.subtitle,.footer,.radar-help,.fund-note,.radar2-note,.terminal-head p,.research-intro p{color:var(--muted)!important}.eyebrow,.brand-kicker{color:var(--blue)!important;text-shadow:none!important}.menu button:hover{background:rgba(255,255,255,.06)!important}.menu button.active{background:linear-gradient(90deg,color-mix(in srgb,var(--blue) 38%,transparent),transparent)!important;box-shadow:inset 2px 0 0 var(--blue)!important}.top-actions{display:flex;gap:8px;align-items:flex-start}.settings{position:relative}.settings-btn{height:38px;padding:0 12px;border:1px solid var(--line);border-radius:10px;background:var(--paper);color:var(--ink);cursor:pointer;box-shadow:var(--shadow);font-size:12px;font-weight:800}.settings-btn:hover{border-color:var(--blue)}.settings-pop{display:none;position:absolute;right:0;top:46px;z-index:40;width:190px;padding:10px;background:var(--paper);border:1px solid var(--line);border-radius:12px;box-shadow:0 18px 44px rgba(0,0,0,.18)}.settings.open .settings-pop{display:block}.settings-title{font-size:11px;color:var(--muted);margin:2px 3px 8px}.theme-choice{width:100%;border:1px solid var(--line);background:transparent;color:var(--ink);border-radius:9px;padding:9px 10px;text-align:left;cursor:pointer;margin-top:6px;display:flex;align-items:center;gap:9px;font-size:12px}.theme-choice:hover,.theme-choice.active{border-color:var(--blue);background:var(--blue2)}.theme-swatch{width:16px;height:16px;border-radius:50%;border:1px solid rgba(0,0,0,.14)}.theme-swatch.beige{background:#f3eadc}.theme-swatch.green{background:#e5f2e8}.theme-swatch.dark{background:#0d1b2d}.radar-version,.workspace-nav,.workspace-separator{display:none!important}.radar-detail{display:none!important}#marketRadarPanel,#radarChangePanel,#etfTerminalPanel,#researchHero,.detail-workspace{display:block!important}
@media(max-width:760px){.top-actions{margin-top:10px}.settings-pop{right:auto;left:0}}
'''

SETTINGS_HTML=r'''<div class="top-actions"><div class="live"><span class="dot"></span><span id="sync">正在读取数据…</span></div><div class="settings" id="themeSettings"><button class="settings-btn" id="themeSettingsBtn" type="button">设置</button><div class="settings-pop"><div class="settings-title">页面颜色</div><button class="theme-choice" data-theme="beige" type="button"><span class="theme-swatch beige"></span>浅米色</button><button class="theme-choice" data-theme="green" type="button"><span class="theme-swatch green"></span>浅绿色</button><button class="theme-choice" data-theme="dark" type="button"><span class="theme-swatch dark"></span>深色</button></div></div></div>'''

JS=r'''
// THEME_SETTINGS_UI
(function(){
  const key='sectorRadarTheme';
  const saved=localStorage.getItem(key)||'beige';
  document.body.dataset.theme=saved;
  document.body.dataset.workspace='all';
  function syncThemeButtons(){document.querySelectorAll('.theme-choice').forEach(b=>b.classList.toggle('active',b.dataset.theme===document.body.dataset.theme))}
  window.addEventListener('load',()=>{
    const box=document.getElementById('themeSettings'),btn=document.getElementById('themeSettingsBtn');
    syncThemeButtons();
    btn?.addEventListener('click',e=>{e.stopPropagation();box?.classList.toggle('open')});
    document.querySelectorAll('.theme-choice').forEach(b=>b.addEventListener('click',()=>{const t=b.dataset.theme||'beige';document.body.dataset.theme=t;localStorage.setItem(key,t);syncThemeButtons();box?.classList.remove('open')}));
    document.addEventListener('click',e=>{if(box&&!box.contains(e.target))box.classList.remove('open')});
  });
})();
'''

def main():
    text=INDEX_PATH.read_text(encoding='utf-8')
    if MARKER in text:return
    text=re.sub(r'\s*<div class="workspace-nav">[\s\S]*?</div><div class="workspace-separator">[\s\S]*?</div>\s*','\n',text,count=1)
    text=re.sub(r'\s*<div class="workspace-nav">[\s\S]*?</div>\s*(?=<div class="mobile-select">)','\n',text,count=1)
    text=re.sub(r'\s*<section class="detail-workspace panel radar-detail" id="radarDetailPanel">[\s\S]*?</section>\s*','\n',text,count=1)
    text=re.sub(r'\s*<section class="panel radar-detail" id="radarDetailPanel">[\s\S]*?</section>\s*','\n',text,count=1)
    text=text.replace('板块雷达 1.5 · 市场状态与ETF研究','板块雷达 · 市场状态与ETF研究').replace('板块雷达 2.0 · 状态变化与ETF研究','板块雷达 · 状态变化与ETF研究')
    text=text.replace('RADAR 1.5','MARKET STATE').replace('RADAR 2.0','CHANGE DETECTION')
    text=text.replace('</style>',CSS+'\n</style>',1)
    live='<div class="live"><span class="dot"></span><span id="sync">正在读取数据…</span></div>'
    if live in text:text=text.replace(live,SETTINGS_HTML,1)
    else:raise RuntimeError('topbar live block not found')
    marker="$('#sideSearch').oninput=buildMenu;"
    if marker not in text:raise RuntimeError('JS insertion marker not found')
    text=text.replace(marker,JS+'\n'+marker,1)
    INDEX_PATH.write_text(text,encoding='utf-8')
    print('[done] theme settings installed; workspace nav/checkup removed')
if __name__=='__main__':main()
