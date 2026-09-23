#!/usr/bin/env python3
"""Final visual polish: glossy, technology-forward, business-like UI without changing data logic."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "docs" / "index.html"
MARKER = "PREMIUM_TECH_BUSINESS_UI"

CSS = r'''
/* PREMIUM_TECH_BUSINESS_UI */
:root{
  --premium-accent:#6b83bf;
  --premium-accent2:#8aa5e8;
  --premium-glass:rgba(255,255,255,.56);
  --premium-shine:rgba(255,255,255,.68);
  --premium-edge:rgba(91,113,158,.16);
  --premium-grid:rgba(79,100,139,.045);
  --premium-shadow:0 16px 42px rgba(45,55,75,.10),0 2px 8px rgba(45,55,75,.045);
  --premium-shadow-hover:0 22px 52px rgba(45,55,75,.14),0 5px 14px rgba(45,55,75,.07);
}
body[data-theme="green"]{
  --premium-accent:#477f70;
  --premium-accent2:#68aa94;
  --premium-glass:rgba(255,255,255,.58);
  --premium-shine:rgba(255,255,255,.72);
  --premium-edge:rgba(54,117,91,.17);
  --premium-grid:rgba(54,117,91,.045);
  --premium-shadow:0 16px 42px rgba(39,79,61,.10),0 2px 8px rgba(39,79,61,.045);
  --premium-shadow-hover:0 22px 52px rgba(39,79,61,.14),0 5px 14px rgba(39,79,61,.07);
}
body[data-theme="dark"]{
  --premium-accent:#65a8ff;
  --premium-accent2:#77d8ff;
  --premium-glass:rgba(13,29,49,.66);
  --premium-shine:rgba(255,255,255,.085);
  --premium-edge:rgba(113,177,255,.18);
  --premium-grid:rgba(116,177,255,.045);
  --premium-shadow:0 18px 54px rgba(0,0,0,.34),0 2px 10px rgba(0,0,0,.18);
  --premium-shadow-hover:0 24px 66px rgba(0,0,0,.44),0 6px 16px rgba(0,0,0,.22);
}
html{scroll-behavior:smooth}
body{position:relative;background:
  radial-gradient(circle at 82% -8%,var(--glow),transparent 32%),
  radial-gradient(circle at 12% 8%,color-mix(in srgb,var(--premium-accent) 8%,transparent),transparent 26%),
  var(--bg)!important;
}
body:before{content:"";position:fixed;inset:0;z-index:0;pointer-events:none;opacity:.72;background-image:
  linear-gradient(var(--premium-grid) 1px,transparent 1px),
  linear-gradient(90deg,var(--premium-grid) 1px,transparent 1px);
  background-size:38px 38px;mask-image:linear-gradient(to bottom,rgba(0,0,0,.72),transparent 78%)}
.app{position:relative;z-index:1}
.content{position:relative;z-index:1}
.sidebar{overflow:hidden!important;isolation:isolate}
.sidebar:before{content:"";position:absolute;inset:-120px -100px auto -100px;height:340px;z-index:-1;pointer-events:none;background:radial-gradient(circle,color-mix(in srgb,var(--premium-accent) 32%,transparent),transparent 66%);filter:blur(8px)}
.sidebar:after{content:"";position:absolute;inset:0;z-index:-1;pointer-events:none;background:linear-gradient(120deg,rgba(255,255,255,.035),transparent 34%,rgba(255,255,255,.012) 68%,transparent)}
.brand{position:relative;background:linear-gradient(135deg,rgba(255,255,255,.055),transparent 70%)}
.brand:after{content:"";position:absolute;left:20px;right:20px;bottom:-1px;height:1px;background:linear-gradient(90deg,transparent,color-mix(in srgb,var(--premium-accent2) 70%,transparent),transparent)}
.brand-kicker{letter-spacing:.18em!important;text-shadow:0 0 20px color-mix(in srgb,var(--premium-accent2) 36%,transparent)!important}
.side-search input{box-shadow:inset 0 1px 0 rgba(255,255,255,.055),0 8px 20px rgba(0,0,0,.08)!important;transition:border-color .2s ease,box-shadow .2s ease,background .2s ease}
.side-search input:focus{border-color:color-mix(in srgb,var(--premium-accent2) 65%,transparent)!important;box-shadow:0 0 0 3px color-mix(in srgb,var(--premium-accent) 14%,transparent),inset 0 1px 0 rgba(255,255,255,.07)!important}
.menu button,.primary-item,.sector-subnav button,.sr-news-subnav button{transition:transform .17s ease,background .17s ease,color .17s ease,border-color .17s ease,box-shadow .17s ease}
.menu button:hover,.primary-item:hover,.sector-subnav button:hover,.sr-news-subnav button:hover{transform:translateX(2px)}
.primary-item.active,.menu button.active{position:relative;overflow:hidden}
.primary-item.active:after,.menu button.active:after{content:"";position:absolute;inset:0;pointer-events:none;background:linear-gradient(105deg,transparent 10%,rgba(255,255,255,.08) 42%,transparent 66%)}
.topbar{position:relative;overflow:hidden;padding:17px 19px;border:1px solid var(--premium-edge);border-radius:16px;background:linear-gradient(135deg,var(--premium-glass),color-mix(in srgb,var(--paper) 84%,transparent));box-shadow:var(--premium-shadow);backdrop-filter:blur(18px) saturate(125%)}
.topbar:before{content:"";position:absolute;inset:0;pointer-events:none;background:linear-gradient(110deg,var(--premium-shine),transparent 19%,transparent 78%,color-mix(in srgb,var(--premium-accent) 7%,transparent));opacity:.42}
.topbar>*,.panel>*{position:relative;z-index:1}
.eyebrow{font-weight:900!important;letter-spacing:.16em!important}
.topbar h2{font-weight:880;letter-spacing:-.04em!important;text-wrap:balance}
.live,.settings-btn{background:linear-gradient(180deg,color-mix(in srgb,var(--paper) 95%,white),color-mix(in srgb,var(--paper) 88%,var(--blue2)))!important;border-color:var(--premium-edge)!important;box-shadow:inset 0 1px 0 var(--premium-shine),0 8px 22px rgba(35,48,71,.075)!important}
body[data-theme="dark"] .live,body[data-theme="dark"] .settings-btn{background:linear-gradient(180deg,rgba(24,44,69,.9),rgba(12,28,48,.92))!important}
.dot{box-shadow:0 0 0 4px rgba(32,166,107,.10),0 0 16px rgba(32,166,107,.45)}
.panel{position:relative;overflow:hidden!important;border-color:var(--premium-edge)!important;background:linear-gradient(145deg,color-mix(in srgb,var(--paper) 96%,white),color-mix(in srgb,var(--paper) 94%,var(--blue2)))!important;box-shadow:var(--premium-shadow)!important;backdrop-filter:blur(16px) saturate(116%);transition:transform .18s ease,border-color .18s ease,box-shadow .18s ease}
body[data-theme="dark"] .panel{background:linear-gradient(145deg,rgba(17,34,56,.96),rgba(10,25,44,.95))!important}
.panel:after{content:"";position:absolute;left:1px;right:1px;top:0;height:1px;z-index:0;pointer-events:none;background:linear-gradient(90deg,transparent,var(--premium-shine),transparent);opacity:.92}
.hero{background:
  radial-gradient(circle at 88% 0,color-mix(in srgb,var(--premium-accent) 13%,transparent),transparent 34%),
  linear-gradient(145deg,color-mix(in srgb,var(--paper) 97%,white),color-mix(in srgb,var(--paper) 93%,var(--blue2)))!important}
body[data-theme="dark"] .hero{background:radial-gradient(circle at 88% 0,rgba(80,151,255,.13),transparent 34%),linear-gradient(145deg,#122540,#0b1a2d)!important}
.sector-title{font-weight:900!important;letter-spacing:-.035em!important;text-shadow:0 7px 24px color-mix(in srgb,var(--premium-accent) 12%,transparent)}
.badge,.sr-status,.radar-event-tag{box-shadow:inset 0 1px 0 rgba(255,255,255,.5)}
.period{position:relative;overflow:hidden;background:linear-gradient(180deg,color-mix(in srgb,var(--paper) 97%,white),color-mix(in srgb,var(--paper) 91%,var(--blue2)))!important;border-color:var(--premium-edge)!important;box-shadow:inset 0 1px 0 var(--premium-shine),0 4px 12px rgba(40,52,77,.035)!important;transition:transform .16s ease,border-color .16s ease,box-shadow .16s ease}
.period:hover{transform:translateY(-2px);box-shadow:inset 0 1px 0 var(--premium-shine),0 10px 22px rgba(40,52,77,.08)!important}
.period.active{background:linear-gradient(145deg,color-mix(in srgb,var(--blue2) 78%,var(--paper)),color-mix(in srgb,var(--premium-accent) 12%,var(--paper)))!important;border-color:color-mix(in srgb,var(--premium-accent) 52%,var(--line))!important;box-shadow:inset 0 1px 0 var(--premium-shine),0 0 0 1px color-mix(in srgb,var(--premium-accent) 9%,transparent),0 10px 24px color-mix(in srgb,var(--premium-accent) 9%,transparent)!important}
.stats.detail-workspace{grid-template-columns:repeat(4,minmax(0,1fr))!important;gap:8px!important}
.stats.detail-workspace .stat{position:relative;overflow:hidden;background:linear-gradient(150deg,color-mix(in srgb,var(--paper) 97%,white),color-mix(in srgb,var(--paper) 92%,var(--blue2)))!important;border:1px solid var(--premium-edge)!important;box-shadow:inset 0 1px 0 var(--premium-shine),0 8px 20px rgba(38,49,69,.055)!important}
.stats.detail-workspace .stat:before{content:"";position:absolute;inset:0 auto 0 0;width:2px;background:linear-gradient(180deg,transparent,var(--premium-accent2),transparent);opacity:.65}
.stats.detail-workspace .stat strong{letter-spacing:-.02em}
.chart-panel,.radar-box,.radar2-box,.radar-change-box,.fund-table-wrap,.terminal-table-wrap{border-color:var(--premium-edge)!important}
.chart-wrap,.home-trend-wrap{border:1px solid color-mix(in srgb,var(--premium-edge) 88%,transparent)!important;background:
  radial-gradient(circle at 78% 0,color-mix(in srgb,var(--premium-accent) 5%,transparent),transparent 35%),
  linear-gradient(180deg,var(--chart),color-mix(in srgb,var(--paper) 98%,var(--blue2)))!important;box-shadow:inset 0 1px 0 var(--premium-shine),inset 0 -22px 48px color-mix(in srgb,var(--premium-accent) 3%,transparent)!important}
.line-path{filter:drop-shadow(0 3px 4px color-mix(in srgb,var(--premium-accent) 22%,transparent))!important;stroke-width:2.65!important}
.compare-path{opacity:.82}
.hover-point{filter:drop-shadow(0 0 5px color-mix(in srgb,var(--premium-accent) 40%,transparent))}
.chart-tooltip{border:1px solid rgba(255,255,255,.10);backdrop-filter:blur(14px);box-shadow:0 14px 38px rgba(8,15,26,.28)!important}
.tool-btn,.compare-switch,.terminal-control select,.sr-nasdaq-controls input,.sr-nasdaq-controls select,.theme-choice{box-shadow:inset 0 1px 0 var(--premium-shine),0 5px 14px rgba(37,50,73,.045);transition:transform .16s ease,border-color .16s ease,box-shadow .16s ease}
.tool-btn:hover,.compare-switch:hover,.theme-choice:hover{transform:translateY(-1px);box-shadow:inset 0 1px 0 var(--premium-shine),0 9px 20px rgba(37,50,73,.075)}
.mh-index-card,.home-kpi,.sector-card,.sr-fav-card,.sr-news-card,.research-stat,.radar-kpi,.radar-summary-card,.mh-shortcut,.home-shortcut{position:relative;overflow:hidden;border-color:var(--premium-edge)!important;box-shadow:inset 0 1px 0 var(--premium-shine),0 8px 20px rgba(39,51,74,.055)!important;transition:transform .18s ease,border-color .18s ease,box-shadow .18s ease}
.mh-index-card:before,.sector-card:before,.sr-fav-card:after,.sr-news-card:after,.research-stat:after,.radar-kpi:after,.radar-summary-card:after{content:"";position:absolute;left:0;right:0;top:0;height:1px;background:linear-gradient(90deg,transparent,var(--premium-shine),transparent);pointer-events:none}
.mh-index-card:hover,.sector-card:hover,.sr-fav-card:hover,.sr-news-card:hover,.mh-shortcut:hover,.home-shortcut:hover{transform:translateY(-2px);border-color:color-mix(in srgb,var(--premium-accent) 42%,var(--line))!important;box-shadow:var(--premium-shadow-hover)!important}
.mh-index-card:after{opacity:.72}
.mh-tabs,.home-trend-periods{box-shadow:inset 0 1px 0 var(--premium-shine)}
.mh-tab.active,.home-trend-period.active{box-shadow:inset 0 1px 0 var(--premium-shine),0 6px 16px rgba(37,50,73,.08)!important}
.mh-dist-bar{box-shadow:inset 0 1px 0 rgba(255,255,255,.38),0 6px 16px rgba(30,43,64,.10)!important}
.mh-board-row,.radar-table tbody tr,.fund-table tbody tr,.terminal-table tbody tr,.sr-nasdaq-table tbody tr{transition:background .16s ease,transform .16s ease}
.mh-board-row:hover,.radar-table tbody tr:hover,.fund-table tbody tr:hover,.terminal-table tbody tr:hover,.sr-nasdaq-table tbody tr:hover{background:color-mix(in srgb,var(--blue2) 58%,transparent)!important}
.fund-table th,.radar-table th,.terminal-table th,.sr-nasdaq-table th{backdrop-filter:blur(12px);box-shadow:inset 0 -1px 0 var(--line),inset 0 1px 0 var(--premium-shine)}
.sr-nasdaq-table-wrap,.fund-table-wrap,.terminal-table-wrap{box-shadow:inset 0 1px 0 var(--premium-shine),0 10px 25px rgba(39,51,74,.05)}
.settings-pop,.sr-nav-dialog{border-color:var(--premium-edge)!important;background:color-mix(in srgb,var(--paper) 91%,transparent)!important;backdrop-filter:blur(24px) saturate(130%);box-shadow:0 26px 70px rgba(19,27,40,.22),inset 0 1px 0 var(--premium-shine)!important}
.primary-icon{box-shadow:inset 0 1px 0 rgba(255,255,255,.06)}
::-webkit-scrollbar{width:9px;height:9px}::-webkit-scrollbar-track{background:transparent}::-webkit-scrollbar-thumb{background:color-mix(in srgb,var(--muted) 28%,transparent);border:2px solid transparent;background-clip:padding-box;border-radius:99px}::-webkit-scrollbar-thumb:hover{background:color-mix(in srgb,var(--muted) 43%,transparent);border:2px solid transparent;background-clip:padding-box}
@media(max-width:900px){.topbar{padding:15px 16px}.stats.detail-workspace{grid-template-columns:repeat(4,minmax(0,1fr))!important}.stats.detail-workspace .stat{padding:7px 8px!important}.stats.detail-workspace .stat strong{font-size:14px!important}.stats.detail-workspace .stat span{font-size:9px!important}.stats.detail-workspace .stat small{font-size:8px!important}}
@media(max-width:700px){body:before{background-size:28px 28px;opacity:.48}.topbar{border-radius:13px}.stats.detail-workspace{grid-template-columns:repeat(2,minmax(0,1fr))!important}.panel{border-radius:12px!important}.chart-wrap{border-radius:9px!important}}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}.menu button,.primary-item,.sector-subnav button,.sr-news-subnav button,.period,.panel,.mh-index-card,.sector-card,.sr-fav-card,.sr-news-card,.mh-shortcut,.home-shortcut,.tool-btn,.compare-switch,.theme-choice{transition:none!important}}
'''


def main():
    text = INDEX.read_text(encoding="utf-8")
    if MARKER in text:
        print("[skip] premium visual polish already installed")
        return
    if "THEME_SETTINGS_UI" not in text:
        raise RuntimeError("theme UI must be installed first")
    if "</body>" not in text:
        raise RuntimeError("body marker missing")
    text = text.replace("</body>", f"\n<style>{CSS}</style>\n<!-- {MARKER} -->\n</body>", 1)
    INDEX.write_text(text, encoding="utf-8")
    print("[done] premium tech-business visual polish installed")


if __name__ == "__main__":
    main()
