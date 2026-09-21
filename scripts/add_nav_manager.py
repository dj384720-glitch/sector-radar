#!/usr/bin/env python3
"""Add local sidebar sector ordering and hide/show management."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "docs" / "index.html"
MARKER = "SECTOR_NAV_MANAGER"

CSS = r'''
/* SECTOR_NAV_MANAGER */
.sector-manage-entry{margin:3px 0 8px 13px;padding-left:10px;border-left:1px solid rgba(255,255,255,.09)}
.sector-manage-btn{width:100%;border:1px dashed var(--line);background:color-mix(in srgb,var(--paper) 86%,transparent);color:var(--muted);border-radius:8px;padding:7px 9px;cursor:pointer;display:flex;align-items:center;justify-content:space-between;gap:8px;font-size:10px;font-weight:800}
.sector-manage-btn:hover{color:var(--ink);border-color:var(--blue);background:var(--blue2)}
.sector-manage-btn b{font-size:9px;font-weight:800;color:var(--blue)}
.sr-nav-modal{position:fixed;inset:0;z-index:10000;background:rgba(5,10,18,.48);backdrop-filter:blur(8px);display:grid;place-items:center;padding:18px}
.sr-nav-modal[hidden]{display:none}
.sr-nav-dialog{width:min(620px,96vw);max-height:min(760px,88vh);display:flex;flex-direction:column;border:1px solid var(--line);background:color-mix(in srgb,var(--paper) 94%,transparent);color:var(--ink);border-radius:18px;box-shadow:0 24px 80px rgba(0,0,0,.28);overflow:hidden}
.sr-nav-head{padding:18px 20px 12px;display:flex;align-items:flex-start;justify-content:space-between;gap:14px;border-bottom:1px solid var(--line)}
.sr-nav-head h3{margin:0 0 5px;font-size:17px}.sr-nav-head p{margin:0;color:var(--muted);font-size:10px;line-height:1.6}
.sr-nav-close{border:1px solid var(--line);background:var(--paper);color:var(--ink);border-radius:9px;width:32px;height:32px;cursor:pointer;font-size:18px}
.sr-nav-toolbar{padding:10px 16px;display:flex;gap:8px;align-items:center;justify-content:space-between;border-bottom:1px solid var(--line)}
.sr-nav-toolbar-left{font-size:10px;color:var(--muted)}.sr-nav-toolbar-actions{display:flex;gap:7px}
.sr-nav-action{border:1px solid var(--line);background:var(--paper);color:var(--ink);border-radius:8px;padding:7px 10px;cursor:pointer;font-size:10px;font-weight:800}.sr-nav-action:hover{border-color:var(--blue);background:var(--blue2)}
.sr-nav-list{padding:10px 12px 14px;overflow:auto;display:flex;flex-direction:column;gap:5px}
.sr-manage-row{display:grid;grid-template-columns:28px minmax(0,1fr) auto;gap:8px;align-items:center;border:1px solid var(--line);background:var(--paper);border-radius:10px;padding:7px 8px;transition:.15s ease}
.sr-manage-row:hover{border-color:color-mix(in srgb,var(--blue) 50%,var(--line))}.sr-manage-row.dragging{opacity:.45;transform:scale(.99)}.sr-manage-row.hidden-sector{opacity:.48}
.sr-drag{width:28px;height:28px;border:0;background:transparent;color:var(--muted);cursor:grab;font-size:15px}.sr-drag:active{cursor:grabbing}
.sr-sector-name{font-size:11px;font-weight:800;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.sr-sector-note{display:block;margin-top:2px;color:var(--muted);font-size:9px;font-weight:500}
.sr-row-actions{display:flex;gap:5px}.sr-row-btn{min-width:30px;height:28px;border:1px solid var(--line);background:var(--paper);color:var(--muted);border-radius:7px;cursor:pointer;font-size:10px;font-weight:800}.sr-row-btn:hover{color:var(--ink);border-color:var(--blue);background:var(--blue2)}.sr-row-btn.hide-toggle{min-width:52px}.sr-manage-row.hidden-sector .hide-toggle{color:var(--blue)}
.sr-nav-foot{padding:10px 16px 14px;border-top:1px solid var(--line);display:flex;justify-content:flex-end}.sr-nav-done{border:0;background:var(--blue);color:#fff;border-radius:9px;padding:9px 18px;font-size:11px;font-weight:900;cursor:pointer}
@media(max-width:620px){.sr-nav-modal{padding:8px}.sr-nav-dialog{max-height:92vh;border-radius:14px}.sr-nav-head{padding:14px}.sr-nav-toolbar{align-items:flex-start;gap:10px}.sr-nav-toolbar-actions{flex-wrap:wrap;justify-content:flex-end}.sr-manage-row{grid-template-columns:22px minmax(0,1fr) auto;padding:6px}.sr-drag{display:none}.sr-row-actions{gap:3px}.sr-row-btn{min-width:28px}.sr-row-btn.hide-toggle{min-width:46px}}
'''

JS = r'''
// SECTOR_NAV_MANAGER
const srNavOrderKey='sectorRadarSectorOrderV1';
const srNavHiddenKey='sectorRadarSectorHiddenV1';
function srAllSectorNames(){return (sectors||[]).map(s=>String(s?.name||'')).filter(Boolean)}
function srReadArray(key){try{const v=JSON.parse(localStorage.getItem(key)||'[]');return Array.isArray(v)?v.map(String):[]}catch(_e){return []}}
function srNormalizeOrder(raw){const names=srAllSectorNames(),valid=new Set(names),seen=new Set(),out=[];(raw||[]).forEach(n=>{if(valid.has(n)&&!seen.has(n)){seen.add(n);out.push(n)}});names.forEach(n=>{if(!seen.has(n))out.push(n)});return out}
let srNavOrder=srNormalizeOrder(srReadArray(srNavOrderKey));
let srNavHidden=new Set(srReadArray(srNavHiddenKey).filter(n=>srAllSectorNames().includes(n)));
function srSaveNavPrefs(){try{localStorage.setItem(srNavOrderKey,JSON.stringify(srNavOrder));localStorage.setItem(srNavHiddenKey,JSON.stringify([...srNavHidden]))}catch(_e){}}
function srHtml(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function srApplySectorNavPrefs(){
  const sub=document.getElementById('sectorSubnav');if(!sub)return;
  srNavOrder=srNormalizeOrder(srNavOrder);
  const buttons=[...sub.querySelectorAll('[data-sector-name]')],map=new Map(buttons.map(b=>[String(b.dataset.sectorName||''),b]));
  buttons.forEach(b=>{if(srNavHidden.has(String(b.dataset.sectorName||'')))b.remove()});
  srNavOrder.forEach(name=>{const b=map.get(name);if(b&&!srNavHidden.has(name)&&b.isConnected)sub.appendChild(b)});
  const old=document.querySelector('.sector-manage-entry');if(old)old.remove();
  const entry=document.createElement('div');entry.className='sector-manage-entry';entry.hidden=!navAllExpanded;
  entry.innerHTML=`<button class="sector-manage-btn" type="button"><span>☷ 管理顺序 / 隐藏</span><b>${srNavHidden.size?srNavHidden.size+' 已隐藏':'自定义'}</b></button>`;
  entry.querySelector('button').onclick=srOpenNavManager;sub.after(entry);
}
const srBaseBuildMenu=buildMenu;
buildMenu=function(){srBaseBuildMenu();srApplySectorNavPrefs()};
function srEnsureNavManager(){
  if(document.getElementById('srNavModal'))return;
  const el=document.createElement('div');el.id='srNavModal';el.className='sr-nav-modal';el.hidden=true;
  el.innerHTML=`<div class="sr-nav-dialog" role="dialog" aria-modal="true" aria-labelledby="srNavTitle"><div class="sr-nav-head"><div><h3 id="srNavTitle">管理二级板块</h3><p>桌面端可拖拽排序；手机端可用上移/下移。隐藏仅影响左侧目录，不会删除板块数据或研究内容。</p></div><button class="sr-nav-close" type="button" aria-label="关闭">×</button></div><div class="sr-nav-toolbar"><div class="sr-nav-toolbar-left" id="srNavCount">—</div><div class="sr-nav-toolbar-actions"><button class="sr-nav-action" type="button" data-sr-action="show-all">全部显示</button><button class="sr-nav-action" type="button" data-sr-action="reset">恢复默认</button></div></div><div class="sr-nav-list" id="srNavList"></div><div class="sr-nav-foot"><button class="sr-nav-done" type="button">完成</button></div></div>`;
  document.body.appendChild(el);
  el.addEventListener('click',e=>{if(e.target===el)srCloseNavManager()});
  el.querySelector('.sr-nav-close').onclick=srCloseNavManager;el.querySelector('.sr-nav-done').onclick=srCloseNavManager;
  el.querySelector('[data-sr-action="show-all"]').onclick=()=>{srNavHidden.clear();srCommitNavPrefs()};
  el.querySelector('[data-sr-action="reset"]').onclick=()=>{srNavOrder=srAllSectorNames();srNavHidden.clear();srCommitNavPrefs()};
}
function srOpenNavManager(){srEnsureNavManager();const el=document.getElementById('srNavModal');el.hidden=false;document.documentElement.style.overflow='hidden';srRenderNavManager()}
function srCloseNavManager(){const el=document.getElementById('srNavModal');if(el)el.hidden=true;document.documentElement.style.overflow='';buildMenu()}
function srCommitNavPrefs(){srNavOrder=srNormalizeOrder(srNavOrder);srSaveNavPrefs();srRenderNavManager();buildMenu()}
function srMoveSector(name,delta){const i=srNavOrder.indexOf(name),j=i+delta;if(i<0||j<0||j>=srNavOrder.length)return;[srNavOrder[i],srNavOrder[j]]=[srNavOrder[j],srNavOrder[i]];srCommitNavPrefs()}
function srDropSector(from,to){if(!from||!to||from===to)return;const a=srNavOrder.indexOf(from),b=srNavOrder.indexOf(to);if(a<0||b<0)return;srNavOrder.splice(a,1);const target=srNavOrder.indexOf(to);srNavOrder.splice(target,0,from);srCommitNavPrefs()}
function srToggleSectorHidden(name){if(srNavHidden.has(name))srNavHidden.delete(name);else srNavHidden.add(name);srCommitNavPrefs()}
let srDragSector='';
function srRenderNavManager(){
  const list=document.getElementById('srNavList');if(!list)return;srNavOrder=srNormalizeOrder(srNavOrder);
  const hiddenCount=srNavHidden.size,visible=srNavOrder.length-hiddenCount,count=document.getElementById('srNavCount');if(count)count.textContent=`显示 ${visible} · 隐藏 ${hiddenCount} · 共 ${srNavOrder.length}`;
  list.innerHTML=srNavOrder.map((name,i)=>`<div class="sr-manage-row ${srNavHidden.has(name)?'hidden-sector':''}" draggable="true" data-sr-name="${srHtml(name)}"><button class="sr-drag" type="button" title="拖拽排序">⋮⋮</button><div class="sr-sector-name">${srHtml(name)}<span class="sr-sector-note">${srNavHidden.has(name)?'已从左侧二级目录隐藏':'显示在左侧二级目录'}</span></div><div class="sr-row-actions"><button class="sr-row-btn" type="button" data-sr-move="-1" ${i===0?'disabled':''} title="上移">↑</button><button class="sr-row-btn" type="button" data-sr-move="1" ${i===srNavOrder.length-1?'disabled':''} title="下移">↓</button><button class="sr-row-btn hide-toggle" type="button" data-sr-hide="1">${srNavHidden.has(name)?'显示':'隐藏'}</button></div></div>`).join('');
  list.querySelectorAll('.sr-manage-row').forEach(row=>{
    const name=String(row.dataset.srName||'');
    row.querySelectorAll('[data-sr-move]').forEach(b=>b.onclick=()=>srMoveSector(name,Number(b.dataset.srMove)));
    const hb=row.querySelector('[data-sr-hide]');if(hb)hb.onclick=()=>srToggleSectorHidden(name);
    row.addEventListener('dragstart',()=>{srDragSector=name;row.classList.add('dragging')});
    row.addEventListener('dragend',()=>{srDragSector='';row.classList.remove('dragging')});
    row.addEventListener('dragover',e=>e.preventDefault());
    row.addEventListener('drop',e=>{e.preventDefault();srDropSector(srDragSector,name)});
  });
}
buildMenu();
'''


def main():
    text = INDEX.read_text(encoding="utf-8")
    if MARKER in text:
        print("[skip] sector nav manager already installed")
        return
    if "NAV_HOME_UI" not in text:
        raise RuntimeError("hierarchical navigation must be installed first")
    if "</body>" not in text:
        raise RuntimeError("body marker missing")
    patch = f"\n<style>{CSS}</style>\n<script>{JS}</script>\n<!-- {MARKER} -->\n"
    text = text.replace("</body>", patch + "</body>", 1)
    INDEX.write_text(text, encoding="utf-8")
    print("[done] customizable sector submenu manager installed")


if __name__ == "__main__":
    main()
