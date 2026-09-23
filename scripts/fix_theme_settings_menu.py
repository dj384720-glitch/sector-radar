#!/usr/bin/env python3
"""Make the theme settings menu a body-level portal so mobile browsers can always click it."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "docs" / "index.html"
MARKER = "THEME_SETTINGS_POPOVER_FIX_V2"

CSS = r'''
/* THEME_SETTINGS_POPOVER_FIX_V2 */
.topbar{overflow:visible!important}
.topbar:before{border-radius:inherit}
.top-actions{position:relative!important;z-index:500!important;overflow:visible!important}
.settings{position:relative!important;z-index:600!important;overflow:visible!important}

.settings-pop[data-theme-portal="1"]{
  display:none!important;
  position:fixed!important;
  z-index:2147483000!important;
  box-sizing:border-box!important;
  width:220px!important;
  max-width:calc(100vw - 24px)!important;
  max-height:calc(100dvh - 24px)!important;
  overflow-x:hidden!important;
  overflow-y:auto!important;
  overscroll-behavior:contain;
  -webkit-overflow-scrolling:touch;
  touch-action:pan-y;
  pointer-events:auto!important;
  scrollbar-gutter:stable;
  isolation:isolate;
}
.settings-pop[data-theme-portal="1"].portal-open{display:block!important}
.settings-pop[data-theme-portal="1"] .theme-choice{
  position:relative!important;
  z-index:2!important;
  min-height:46px!important;
  pointer-events:auto!important;
  touch-action:manipulation!important;
}
.settings-pop[data-theme-portal="1"]:before,
.settings-pop[data-theme-portal="1"]:after{pointer-events:none!important}

@media(max-width:760px){
  .settings-pop[data-theme-portal="1"]{
    left:12px!important;
    right:12px!important;
    top:auto!important;
    bottom:max(12px,env(safe-area-inset-bottom))!important;
    width:auto!important;
    max-width:none!important;
    max-height:min(420px,calc(100dvh - 24px - env(safe-area-inset-bottom)))!important;
    padding:12px!important;
    border-radius:16px!important;
  }
  .settings-pop[data-theme-portal="1"] .theme-choice{min-height:50px!important;font-size:13px!important}
}
'''

JS = r'''
// THEME_SETTINGS_POPOVER_FIX_V2
(function(){
  function installThemePortal(){
    const box=document.getElementById('themeSettings');
    const oldBtn=document.getElementById('themeSettingsBtn');
    const pop=box?.querySelector('.settings-pop') || document.querySelector('.settings-pop[data-theme-portal="1"]');
    if(!box||!oldBtn||!pop||pop.dataset.themePortal==='1')return;

    // Move the popover outside the glass topbar. On mobile Safari/Chromium,
    // backdrop-filter/overflow ancestors can otherwise make visible controls untappable.
    pop.dataset.themePortal='1';
    document.body.appendChild(pop);

    // Replace the button to remove the original nested-popover click listener.
    const btn=oldBtn.cloneNode(true);
    oldBtn.replaceWith(btn);
    btn.setAttribute('aria-haspopup','dialog');
    btn.setAttribute('aria-expanded','false');

    const key='sectorRadarTheme';
    const isOpen=()=>pop.classList.contains('portal-open');
    function syncButtons(){
      document.querySelectorAll('.theme-choice').forEach(b=>b.classList.toggle('active',b.dataset.theme===document.body.dataset.theme));
    }
    function positionDesktop(){
      if(window.innerWidth<=760){
        pop.style.removeProperty('top');
        pop.style.removeProperty('left');
        pop.style.removeProperty('right');
        pop.style.removeProperty('width');
        pop.style.removeProperty('max-height');
        return;
      }
      const r=btn.getBoundingClientRect();
      const vw=window.innerWidth, vh=window.innerHeight;
      const width=Math.min(220,Math.max(180,vw-24));
      const left=Math.max(12,Math.min(vw-width-12,r.right-width));
      const top=Math.max(12,Math.min(vh-80,r.bottom+8));
      pop.style.left=left+'px';
      pop.style.right='auto';
      pop.style.top=top+'px';
      pop.style.bottom='auto';
      pop.style.width=width+'px';
      pop.style.maxHeight=Math.max(140,vh-top-12)+'px';
    }
    function close(){
      pop.classList.remove('portal-open');
      box.classList.remove('open');
      btn.setAttribute('aria-expanded','false');
    }
    function open(){
      positionDesktop();
      syncButtons();
      pop.classList.add('portal-open');
      btn.setAttribute('aria-expanded','true');
    }

    btn.addEventListener('click',e=>{
      e.preventDefault();
      e.stopPropagation();
      isOpen()?close():open();
    });

    // Handle selection at the portal itself so theme choice works even if an
    // earlier listener is skipped by a mobile browser.
    pop.addEventListener('click',e=>{
      const choice=e.target.closest('.theme-choice');
      if(!choice)return;
      e.preventDefault();
      e.stopPropagation();
      const theme=choice.dataset.theme||'beige';
      document.body.dataset.theme=theme;
      try{localStorage.setItem(key,theme)}catch(_e){}
      syncButtons();
      close();
    });

    document.addEventListener('click',e=>{
      if(isOpen()&&!pop.contains(e.target)&&e.target!==btn)close();
    },true);
    window.addEventListener('resize',()=>{if(isOpen())positionDesktop()},{passive:true});
    window.addEventListener('scroll',()=>{if(isOpen()&&window.innerWidth>760)positionDesktop()},{passive:true});
    window.visualViewport?.addEventListener('resize',()=>{if(isOpen())positionDesktop()},{passive:true});
    window.visualViewport?.addEventListener('scroll',()=>{if(isOpen()&&window.innerWidth>760)positionDesktop()},{passive:true});
  }

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',installThemePortal,{once:true});
  else installThemePortal();
  window.addEventListener('load',installThemePortal,{once:true});
})();
'''


def main():
    text = INDEX.read_text(encoding="utf-8")
    if MARKER in text:
        print("[skip] theme settings portal fix already installed")
        return
    if "THEME_SETTINGS_UI" not in text:
        raise RuntimeError("theme settings UI must be installed first")
    if "</body>" not in text:
        raise RuntimeError("body marker missing")
    text = text.replace("</body>", f"\n<style>{CSS}</style>\n<script>{JS}</script>\n<!-- {MARKER} -->\n</body>", 1)
    INDEX.write_text(text, encoding="utf-8")
    print("[done] theme settings moved to tappable body-level portal")


if __name__ == "__main__":
    main()
