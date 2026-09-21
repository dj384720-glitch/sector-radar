#!/usr/bin/env python3
"""Compact the four sector summary cards into a horizontal grid."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "docs" / "index.html"
MARKER = "COMPACT_SECTOR_STATS"

CSS = r'''
/* COMPACT_SECTOR_STATS */
.stats.detail-workspace{
  display:grid!important;
  grid-template-columns:repeat(4,minmax(0,1fr))!important;
  gap:8px!important;
  margin:10px 0 12px!important;
}
.stats.detail-workspace .stat{
  padding:10px 12px!important;
  min-height:82px!important;
  border-radius:11px!important;
}
.stats.detail-workspace .stat span{
  font-size:11px!important;
}
.stats.detail-workspace .stat strong{
  margin-top:4px!important;
  font-size:18px!important;
  line-height:1.2!important;
}
.stats.detail-workspace .stat small{
  margin-top:3px!important;
  font-size:10px!important;
  line-height:1.35!important;
}
@media(max-width:900px){
  .stats.detail-workspace{grid-template-columns:repeat(2,minmax(0,1fr))!important;}
}
@media(max-width:520px){
  .stats.detail-workspace{gap:7px!important;}
  .stats.detail-workspace .stat{padding:9px 10px!important;min-height:76px!important;}
  .stats.detail-workspace .stat strong{font-size:16px!important;}
}
'''


def main():
    text = INDEX.read_text(encoding="utf-8")
    if MARKER in text:
        return
    if "</style>" not in text:
        raise RuntimeError("style marker missing")
    text = text.replace("</style>", CSS + "\n</style>", 1)
    INDEX.write_text(text, encoding="utf-8")
    print("[done] compact sector stats layout installed")


if __name__ == "__main__":
    main()
