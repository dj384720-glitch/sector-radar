#!/usr/bin/env python3
"""Make the 全部板块 secondary menu collapsible and remember its state."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "docs" / "index.html"
MARKER = "NAV_COLLAPSE_PATCH"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"{label} marker missing")
    return text.replace(old, new, 1)


def main():
    text = INDEX.read_text(encoding="utf-8")
    if MARKER in text:
        print("[skip] nav collapse patch already installed")
        return

    text = replace_once(
        text,
        "let navPage='home',navAllExpanded=true;",
        "let navPage='home',navAllExpanded=(()=>{try{return localStorage.getItem('sectorRadarNavExpanded')!=='0'}catch(_e){return true}})();",
        "nav state",
    )
    text = replace_once(
        text,
        "function openNavPage(page){navPage=['home','all','market','etf','sector'].includes(page)?page:'home';if(navPage==='all')navAllExpanded=true;applyNavVisibility();buildMenu();window.scrollTo({top:0,behavior:'smooth'})}",
        "function openNavPage(page){navPage=['home','all','market','etf','sector'].includes(page)?page:'home';applyNavVisibility();buildMenu();window.scrollTo({top:0,behavior:'smooth'})}",
        "openNavPage",
    )
    text = replace_once(
        text,
        "if(p==='all'){navAllExpanded=!navAllExpanded;openNavPage('all')}else openNavPage(p)",
        "if(p==='all'){navAllExpanded=!navAllExpanded;try{localStorage.setItem('sectorRadarNavExpanded',navAllExpanded?'1':'0')}catch(_e){}openNavPage('all')}else openNavPage(p)",
        "all toggle",
    )
    text = replace_once(
        text,
        "selectSector=function(name,push){navBaseSelectSector(name,push);navPage='sector';navAllExpanded=true;applyNavVisibility();buildMenu()};",
        "selectSector=function(name,push){navBaseSelectSector(name,push);navPage='sector';navAllExpanded=true;try{localStorage.setItem('sectorRadarNavExpanded','1')}catch(_e){}applyNavVisibility();buildMenu()};",
        "sector auto expand",
    )
    text = text.replace("</body>", f"<!-- {MARKER} -->\n</body>", 1)
    INDEX.write_text(text, encoding="utf-8")
    print("[done] collapsible sector submenu installed")


if __name__ == "__main__":
    main()
