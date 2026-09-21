#!/usr/bin/env python3
"""Restore the full-market rotation radar on the homepage."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "docs" / "index.html"
MARKER = "HOME_MARKET_RADAR_RESTORE"

CSS = r'''
/* HOME_MARKET_RADAR_RESTORE */
body[data-nav-page="home"] #marketRadarPanel{display:block!important}
'''

JS = r'''
// HOME_MARKET_RADAR_RESTORE
const homeRadarBaseRenderHome=renderHome;
renderHome=function(){
  homeRadarBaseRenderHome();
  if(typeof renderMarketRadar==='function') renderMarketRadar();
};
setTimeout(()=>{
  if(typeof navPage!=='undefined'&&navPage==='home'&&typeof renderMarketRadar==='function') renderMarketRadar();
},0);
'''

def main():
    text = INDEX.read_text(encoding="utf-8")
    if MARKER in text:
        print("[skip] homepage market radar already restored")
        return
    if "marketRadarPanel" not in text or "MARKET_HOME_DASHBOARD" not in text:
        raise RuntimeError("market radar and redesigned homepage must be installed first")
    if "</body>" not in text:
        raise RuntimeError("body marker missing")
    patch = f"\n<style>{CSS}</style>\n<script>{JS}</script>\n<!-- {MARKER} -->\n"
    text = text.replace("</body>", patch + "</body>", 1)
    INDEX.write_text(text, encoding="utf-8")
    print("[done] homepage full-market rotation radar restored")

if __name__ == "__main__":
    main()
