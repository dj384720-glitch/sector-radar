#!/usr/bin/env python3
"""Keep the theme settings popover fully visible and scrollable, especially on mobile."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "docs" / "index.html"
MARKER = "THEME_SETTINGS_POPOVER_FIX"

CSS = r'''
/* THEME_SETTINGS_POPOVER_FIX */
.topbar{overflow:visible!important}
.topbar:before{border-radius:inherit}
.top-actions{position:relative!important;z-index:500!important;overflow:visible!important}
.settings{position:relative!important;z-index:600!important;overflow:visible!important}
.settings.open{z-index:10000!important}
.settings-pop{
  z-index:10001!important;
  max-height:min(360px,calc(100vh - 96px))!important;
  overflow-x:hidden!important;
  overflow-y:auto!important;
  overscroll-behavior:contain;
  -webkit-overflow-scrolling:touch;
  touch-action:pan-y;
  scrollbar-gutter:stable;
}
.theme-choice{position:relative;z-index:1;min-height:42px}
@media(max-width:760px){
  .topbar{overflow:visible!important}
  .top-actions{width:100%;justify-content:flex-start;align-items:flex-start;overflow:visible!important}
  .settings{margin-left:0}
  .settings-pop{
    left:auto!important;
    right:0!important;
    top:44px!important;
    width:min(220px,calc(100vw - 28px))!important;
    max-height:calc(100vh - 92px)!important;
    padding-bottom:max(10px,env(safe-area-inset-bottom))!important;
  }
}
'''


def main():
    text = INDEX.read_text(encoding="utf-8")
    if MARKER in text:
        print("[skip] theme settings popover fix already installed")
        return
    if "THEME_SETTINGS_UI" not in text:
        raise RuntimeError("theme settings UI must be installed first")
    if "</body>" not in text:
        raise RuntimeError("body marker missing")
    text = text.replace("</body>", f"\n<style>{CSS}</style>\n<!-- {MARKER} -->\n</body>", 1)
    INDEX.write_text(text, encoding="utf-8")
    print("[done] theme settings popover scrolling/clipping fixed")


if __name__ == "__main__":
    main()
