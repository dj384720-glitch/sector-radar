#!/usr/bin/env python3
"""Final UI polish: remove per-sector checkup, strip visible version labels, add theme settings."""
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
INDEX_PATH=ROOT/'docs'/'index.html'
MARKER='THEME_SETTINGS_UI'

CSS=r'''
/* THEME_SETTINGS_UI */
:root{--bg:#f7f2e8;--paper:rgba(255,252,246,.92);--ink:#273142;--muted:#6f7782;--line:#e8decf;--blue:#4d6fb3;--blue2:#edf2fb;--up:#c95850;--down:#2f8f6c;--compare:#8490a0;--shadow:0 12px 34px rgba(95,74,45,.08);--sidebar:#222a35;--sidebar2:#2c3542;--glow:rgba(112,147,211,.14)}
body[data-theme="green"]{--bg:#edf6ef;--paper:rgba(250,255,251,.92);--ink:#203328;--muted:#68796e;--line:#d7e7da;--blue:#3f7d68;--blue2:#e5f3ea;--up:#b75853;--down:#24805d;--compare:#7a8f83;--shadow:0 12px 34px rgba(46,93,64,.08);--sidebar:#20352d;--sidebar2:#29453a;--glow:rgba(92,179,138,.16)}
body[data-theme="dark"]{--bg:#08111f;--paper:rgba(13,27,46,.88);--ink:#e8f0fb;--muted:#8fa2b8;--line:rgba(143,181,222,.16);--blue:#67a8ff;--blue2:rgba(76,137,224,.16);--up:#ff7d86;--down:#46d3a0;--compare:#91a7bd;--shadow:0 18px 55px rgba(0,0,0,.28);--sidebar:#07111e;--sidebar2:#101f32;--glow:rgba(69,143,255,.24)}
html,body{background:radial-gradient(circle at 80% -8%,var(--glow),transparent 34%),var(--bg);transition:background .25s ease,color .25s ease}.panel,.live{backdrop-filter:blur(16px);box-shadow:inset 0 1px 0 rgba(255,255,255,.035),var(--shadow)}.sidebar{background:linear-gradient(180deg,var(--sidebar),var(--sidebar2));box-shadow:12px 0 36px rgba(0,0,0,.12)}.period,.date-box input,.tool-btn,.compare-switch,.mobile-select select{background:var(--paper)!important;color:var(--ink)!important;border-color:var(--line)!important}.chart-wrap{background:linear-gradient(180deg,color-mix(in srgb,var(--paper) 88%,transparent),var(--paper))}.top-actions{display:flex;gap:8px;align-items:flex-start}.settings{position:relative}.settings-btn{height:38px;padding:0 12px;border:1px solid var(--line);border-radius:10px;background:var(--paper);color:var(--ink);cursor:pointer;box-shadow:var(--shadow);font-size:12px;font-weight:800}.settings-btn:hover{border-color:var(--blue)}.settings-pop{display:none;position:absolute;right:0;top:46px;z-index:20;width:190px;padding:10px;background:var(--paper);border:1px solid var(--line);border-radius:12px;box-shadow:0 18px 44px rgba(0,0,0,.18);backdrop-filter:blur(18px)}.settings.open .settings-pop{display:block}.settings-title{font-size:11px;color:var(--muted);margin:2px 3px 8px}.theme-choice{width:100%;border:1px solid var(--line);background:transparent;color:var(--ink);border-radius:9px;padding:9px 10px;text-align:left;cursor:pointer;margin-top:6px;display:flex;align-items:center;gap:9px;font-size:12px}.theme-choice:hover,.theme-choice.active{border-color:var(--blue);background:var(--blue2)}.theme-swatch{width:16px;height:16px;border-radius:50%;border:1px solid rgba(0,0,0,.12);box-shadow:inset 0 1px 2px rgba(255,255,255,.6)}.theme-swatch.beige{background:#f3eadc}.theme-swatch.green{background:#e7f2e9}.theme-swatch.dark{background:#0d1b2d}.radar-version{display:none!important}.radar-detail{display:none!important}
@media(max-width:760px){.top-actions{margin-top:10px}.settings-pop{right:auto;left:0}}
'''

SETTINGS_HTML=r'''<div class="top-actions"><div class="live"><span class="dot"></span><span id="sync">正在读取数据…</span></div><div class="settings" id="themeSettings"><button class="settings-btn" id="themeSettingsBtn" type="button">设置</button><div class="settings-pop"><div class="settings-title">页面颜色</div><button class="theme-choice" data-theme="beige" type="button"><span class="theme-swatch beige"></span>浅米色</button><button class="theme-choice" data-theme="green" type="button"><span class="theme-swatch green"></span>浅绿色</button><button class="theme-choice" data-theme="dark" type="button"><span class="theme-swatch dark"></span>深色</button></div></div></div>'''

JS=r'''
// THEME_SETTINGS_UI
(function(){
  const key='sectorRadarTheme';
  const saved=localStorage.getItem(key)||'beige';
  document.body.dataset.theme=saved;
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
    # Remove the per-sector diagnostic/checkup card injected by the radar script.
    text=re.sub(r'\s*<section class="panel radar-detail" id="radarDetailPanel">[\s\S]*?</section>\s*','\n',text,count=1)
    # Remove visible version wording without touching internal script markers.
    text=text.replace('板块雷达 1.5 · 市场状态与ETF研究','板块雷达 · 市场状态与ETF研究')
    text=text.replace('板块雷达 2.0 · 状态变化与ETF研究','板块雷达 · 状态变化与ETF研究')
    text=text.replace('RADAR 1.5','MARKET STATE').replace('RADAR 2.0','CHANGE DETECTION')
    text=text.replace('</style>',CSS+'\n</style>',1)
    live='<div class="live"><span class="dot"></span><span id="sync">正在读取数据…</span></div>'
    if live in text:text=text.replace(live,SETTINGS_HTML,1)
    else:raise RuntimeError('topbar live block not found')
    marker="$('#sideSearch').oninput=buildMenu;"
    if marker not in text:raise RuntimeError('JS insertion marker not found')
    text=text.replace(marker,JS+'\n'+marker,1)
    INDEX_PATH.write_text(text,encoding='utf-8')
    print('[done] theme settings installed; per-sector checkup removed')
if __name__=='__main__':main()
