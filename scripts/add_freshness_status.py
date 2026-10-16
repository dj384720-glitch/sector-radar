#!/usr/bin/env python3
"""Add a visible Beijing-time data freshness indicator to the built page.

This runs last in the Pages build so later UI patchers cannot remove it.  The
indicator reads docs/data/latest.json with cache bypassing, shows whether the
current build refreshed today, and separately reports the newest market date.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "docs" / "index.html"
MARKER = "SECTOR_RADAR_FRESHNESS_V1"

STYLE = r'''<style id="sector-radar-freshness-style">
/* SECTOR_RADAR_FRESHNESS_V1 */
.live.freshness-live{display:flex;align-items:flex-start;gap:9px;min-width:238px;white-space:normal}
.live.freshness-live .dot{flex:0 0 auto;margin:5px 0 0;background:#98a2b3;box-shadow:0 0 0 4px rgba(152,162,179,.12)}
.live.freshness-live.freshness-current .dot{background:#12b76a;box-shadow:0 0 0 4px rgba(18,183,106,.12)}
.live.freshness-live.freshness-waiting .dot{background:#f79009;box-shadow:0 0 0 4px rgba(247,144,9,.12)}
.live.freshness-live.freshness-error .dot{background:#f04438;box-shadow:0 0 0 4px rgba(240,68,56,.12)}
.freshness-copy{display:flex;flex-direction:column;gap:2px;line-height:1.35}
.freshness-main{font-weight:800;color:var(--ink,#172033);font-size:12px}
.freshness-sub{color:var(--muted,#667085);font-size:11px;font-variant-numeric:tabular-nums}
@media(max-width:760px){.live.freshness-live{width:100%;min-width:0;margin-top:10px;padding:10px 12px}}
</style>'''

SCRIPT = r'''<script id="sector-radar-freshness-script">
/* SECTOR_RADAR_FRESHNESS_V1 */
(()=>{
  const TZ='Asia/Shanghai';
  const sync=document.getElementById('sync');
  const live=sync?.closest('.live');
  if(!sync||!live)return;
  let expected='';
  const dayKey=(d)=>{
    const p=new Intl.DateTimeFormat('en-CA',{timeZone:TZ,year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(d);
    const x=Object.fromEntries(p.map(i=>[i.type,i.value]));
    return `${x.year}-${x.month}-${x.day}`;
  };
  const dateTime=(d)=>new Intl.DateTimeFormat('zh-CN',{timeZone:TZ,month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}).format(d);
  const newestMarketDate=(payload)=>{
    const dates=(payload?.sectors||[]).map(x=>x?.latest_date).filter(Boolean).sort();
    return dates.length?dates[dates.length-1]:'—';
  };
  const paint=(payload)=>{
    const now=new Date();
    const updated=payload?.updated_at?new Date(payload.updated_at):null;
    const updatedOK=updated&&!Number.isNaN(updated.getTime());
    const refreshedToday=updatedOK&&dayKey(updated)===dayKey(now);
    const marketDate=newestMarketDate(payload);
    live.classList.remove('freshness-current','freshness-waiting','freshness-error');
    live.classList.add('freshness-live',refreshedToday?'freshness-current':'freshness-waiting');
    const main=refreshedToday?'今日已刷新':'等待今日刷新';
    const when=updatedOK?`生成 ${dateTime(updated)} 北京时间`:'生成时间未知';
    expected=`<span class="freshness-copy"><span class="freshness-main">${main}</span><span class="freshness-sub">行情截至 ${marketDate} · ${when}</span></span>`;
    sync.innerHTML=expected;
    live.title=`${main}；行情截至 ${marketDate}；${when}`;
  };
  const paintError=()=>{
    live.classList.remove('freshness-current','freshness-waiting');
    live.classList.add('freshness-live','freshness-error');
    expected='<span class="freshness-copy"><span class="freshness-main">更新状态读取失败</span><span class="freshness-sub">请稍后刷新页面</span></span>';
    sync.innerHTML=expected;
  };
  const observer=new MutationObserver(()=>{
    if(expected&&sync.innerHTML!==expected)sync.innerHTML=expected;
  });
  observer.observe(sync,{childList:true,subtree:true,characterData:true});
  const load=()=>fetch('data/latest.json?fresh='+Date.now(),{cache:'no-store'})
    .then(r=>{if(!r.ok)throw new Error('HTTP '+r.status);return r.json()})
    .then(paint)
    .catch(paintError);
  if(document.readyState==='complete')load();
  else window.addEventListener('load',()=>setTimeout(load,120),{once:true});
})();
</script>'''


def main() -> None:
    text = INDEX.read_text(encoding="utf-8")
    if MARKER in text:
        print("[freshness] status UI already installed")
        return

    # Keep the main market payload request cache-safe even if an older base page
    # is checked out in a future build.
    text = text.replace(
        "fetch('data/latest.json').then(",
        "fetch('data/latest.json?ts='+Date.now(),{cache:'no-store'}).then(",
    )

    if "</head>" not in text or "</body>" not in text:
        raise RuntimeError("docs/index.html is missing </head> or </body>")
    text = text.replace("</head>", STYLE + "\n</head>", 1)
    text = text.replace("</body>", SCRIPT + "\n</body>", 1)
    INDEX.write_text(text, encoding="utf-8")
    print("[done] visible freshness status installed")


if __name__ == "__main__":
    main()
