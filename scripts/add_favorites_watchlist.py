#!/usr/bin/env python3
"""Add a local favorites/watchlist primary page for sector navigation."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "docs" / "index.html"
MARKER = "SECTOR_FAVORITES_WATCHLIST"

CSS = r'''
/* SECTOR_FAVORITES_WATCHLIST */
.sr-favorites-panel{display:none;padding:18px 20px;margin-bottom:14px}
body[data-nav-page="favorites"] #srFavoritesPanel{display:block!important}
.sr-fav-head{display:flex;justify-content:space-between;gap:16px;align-items:flex-start;margin-bottom:14px}
.sr-fav-head h3{margin:0;font-size:18px}.sr-fav-head p{margin:5px 0 0;color:var(--muted);font-size:11px;line-height:1.65}.sr-fav-count{font-size:11px;color:var(--muted);white-space:nowrap}
.sr-fav-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}
.sr-fav-card{border:1px solid var(--line);background:var(--paper);border-radius:12px;padding:13px;box-shadow:var(--shadow);position:relative;overflow:hidden}
.sr-fav-card:before{content:"";position:absolute;inset:0 auto auto 0;width:100%;height:2px;background:linear-gradient(90deg,var(--blue),transparent);opacity:.5}
.sr-fav-card-head{display:flex;align-items:flex-start;justify-content:space-between;gap:10px;margin-bottom:11px}.sr-fav-open{border:0;background:transparent;color:var(--ink);padding:0;cursor:pointer;text-align:left;min-width:0}.sr-fav-open strong{display:block;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.sr-fav-open span{display:block;margin-top:4px;font-size:9px;color:var(--muted)}
.sr-fav-star{width:30px;height:30px;border:1px solid var(--line);background:var(--paper);color:#d69a16;border-radius:8px;cursor:pointer;font-size:16px;line-height:1}.sr-fav-star:hover{border-color:#d69a16;background:rgba(214,154,22,.08)}
.sr-fav-metrics{display:grid;grid-template-columns:repeat(2,1fr);gap:7px}.sr-fav-metric{border:1px solid var(--line);background:color-mix(in srgb,var(--paper) 88%,transparent);border-radius:9px;padding:8px}.sr-fav-metric span{display:block;color:var(--muted);font-size:9px}.sr-fav-metric b{display:block;margin-top:4px;font-size:11px;font-variant-numeric:tabular-nums;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.sr-fav-metric b.up{color:var(--up)}.sr-fav-metric b.down{color:var(--down)}
.sr-fav-event{margin-top:8px;border:1px solid var(--line);border-radius:9px;padding:8px 9px;font-size:10px;color:var(--muted);line-height:1.55}.sr-fav-event strong{color:var(--ink);font-size:10px}.sr-fav-empty{padding:34px 18px;text-align:center;border:1px dashed var(--line);border-radius:12px;color:var(--muted)}.sr-fav-empty strong{display:block;color:var(--ink);font-size:14px;margin-bottom:7px}.sr-fav-empty p{margin:0 auto 12px;max-width:520px;font-size:11px;line-height:1.65}.sr-fav-empty button{border:0;background:var(--blue);color:#fff;border-radius:9px;padding:9px 14px;font-size:11px;font-weight:850;cursor:pointer}
.sr-row-btn.favorite-toggle{min-width:34px;color:#d69a16;font-size:14px}.sr-row-btn.favorite-toggle.is-favorite{background:rgba(214,154,22,.1);border-color:rgba(214,154,22,.45)}
.primary-item[data-primary="favorites"] .primary-icon{color:#d69a16}
@media(max-width:1100px){.sr-fav-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:760px){.sr-favorites-panel{padding:14px}.sr-fav-head{display:block}.sr-fav-count{margin-top:7px}.sr-fav-grid{grid-template-columns:1fr}}
'''

JS = r'''
// SECTOR_FAVORITES_WATCHLIST
const srFavoriteKey='sectorRadarSectorFavoritesV1';
function srReadFavorites(){try{const v=JSON.parse(localStorage.getItem(srFavoriteKey)||'[]');return Array.isArray(v)?v.map(String):[]}catch(_e){return []}}
let srFavorites=new Set(srReadFavorites().filter(n=>(sectors||[]).some(s=>String(s?.name||'')===n)));
function srSaveFavorites(){try{localStorage.setItem(srFavoriteKey,JSON.stringify([...srFavorites]))}catch(_e){}}
function srFavoriteNames(){const names=(typeof srNavOrder!=='undefined'&&Array.isArray(srNavOrder)?srNavOrder:(sectors||[]).map(s=>String(s?.name||'')));const out=names.filter(n=>srFavorites.has(n));[...srFavorites].forEach(n=>{if(!out.includes(n)&&(sectors||[]).some(s=>String(s?.name||'')===n))out.push(n)});return out}
function srFavoriteSector(name){return (sectors||[]).find(s=>String(s?.name||'')===String(name))||null}
function srFavoriteEvent(s){const ev=(s?.radar2?.events_5d||[])[0];return ev?{label:String(ev.label||'状态发生变化'),direction:String(ev.direction||'')}:{label:'近5个交易日暂无主要状态变化',direction:''}}
function srFavoriteEtf(s){const f=(s?.funds||[])[0];return f?String(f.name||'—'):'—'}
function srFavoriteRs(s){const n=Number(s?.radar?.rs60);return Number.isFinite(n)?`${n>=0?'+':''}${n.toFixed(1)}%`:'—'}
function srFavoriteTrend(s){return String(s?.radar?.trend_state||s?.radar2?.current?.trend_state||'—')}
function srToggleFavorite(name){name=String(name||'');if(!name)return;if(srFavorites.has(name))srFavorites.delete(name);else srFavorites.add(name);srSaveFavorites();srRenderFavorites();if(typeof srRenderNavManager==='function'&&!document.getElementById('srNavModal')?.hidden)srRenderNavManager();buildMenu()}
function srEnsureFavoritesPanel(){if(document.getElementById('srFavoritesPanel'))return;const panel=document.createElement('section');panel.id='srFavoritesPanel';panel.className='panel sr-favorites-panel';panel.innerHTML=`<div class="sr-fav-head"><div><h3>自选观察</h3><p>只展示你加星的板块。这里汇总趋势状态、RS60、近5日状态变化和一只代表ETF，便于每天快速检查。</p></div><div class="sr-fav-count" id="srFavCount">—</div></div><div class="sr-fav-grid" id="srFavGrid"></div>`;const top=document.querySelector('.topbar');if(top)top.after(panel);else document.querySelector('.content')?.prepend(panel)}
function srRenderFavorites(){srEnsureFavoritesPanel();const grid=document.getElementById('srFavGrid');if(!grid)return;const names=srFavoriteNames(),count=document.getElementById('srFavCount');if(count)count.textContent=`${names.length} 个自选板块`;if(!names.length){grid.innerHTML=`<div class="sr-fav-empty" style="grid-column:1/-1"><strong>还没有自选板块</strong><p>打开“全部板块”下方的“管理板块”，点击 ☆ 即可加入自选。隐藏和自选互不影响。</p><button type="button" onclick="srOpenNavManager()">去添加自选</button></div>`;return}grid.innerHTML=names.map(name=>{const s=srFavoriteSector(name);if(!s)return'';const ev=srFavoriteEvent(s),rs=srFavoriteRs(s),trend=srFavoriteTrend(s),etf=srFavoriteEtf(s),rsNum=Number(s?.radar?.rs60),rsCls=Number.isFinite(rsNum)?(rsNum>0?'up':rsNum<0?'down':''):'';return `<article class="sr-fav-card"><div class="sr-fav-card-head"><button class="sr-fav-open" type="button" data-fav-open="${srHtml(name)}"><strong>${srHtml(name)}</strong><span>点击进入板块详情</span></button><button class="sr-fav-star" type="button" data-fav-remove="${srHtml(name)}" title="取消自选">★</button></div><div class="sr-fav-metrics"><div class="sr-fav-metric"><span>趋势状态</span><b>${srHtml(trend)}</b></div><div class="sr-fav-metric"><span>RS60</span><b class="${rsCls}">${srHtml(rs)}</b></div><div class="sr-fav-metric"><span>代表ETF</span><b title="${srHtml(etf)}">${srHtml(etf)}</b></div><div class="sr-fav-metric"><span>数据日期</span><b>${srHtml(s.latest_date||'—')}</b></div></div><div class="sr-fav-event"><strong>近5日：</strong>${srHtml(ev.label)}</div></article>`}).join('');grid.querySelectorAll('[data-fav-open]').forEach(b=>b.onclick=()=>selectSector(b.dataset.favOpen,true));grid.querySelectorAll('[data-fav-remove]').forEach(b=>b.onclick=()=>srToggleFavorite(b.dataset.favRemove))}
function srEnsureFavoriteMobileOption(){const m=document.getElementById('mobilePrimaryNav');if(!m)return;if(!m.querySelector('option[value="favorites"]')){const o=document.createElement('option');o.value='favorites';o.textContent='自选观察';const market=m.querySelector('option[value="market"]');market?m.insertBefore(o,market):m.appendChild(o)}if(navPage==='favorites')m.value='favorites'}
const srFavBaseApplyNavVisibility=applyNavVisibility;
applyNavVisibility=function(){if(navPage==='favorites'){document.body.dataset.navPage='favorites';srEnsureFavoriteMobileOption();const m=document.getElementById('mobilePrimaryNav');if(m)m.value='favorites';setNavHeader('自选观察','集中检查常看板块的趋势、相对强弱、状态变化和代表ETF。','WATCHLIST / FAVORITES');srRenderFavorites()}else srFavBaseApplyNavVisibility()};
const srFavBaseOpenNavPage=openNavPage;
openNavPage=function(page){if(page==='favorites'){navPage='favorites';applyNavVisibility();buildMenu();window.scrollTo({top:0,behavior:'smooth'});return}srFavBaseOpenNavPage(page)};
function srInstallFavoritePrimary(){const menu=document.getElementById('menu'),primary=menu?.querySelector('.primary-nav');if(!primary)return;const existing=primary.querySelector('[data-primary="favorites"]');if(existing)existing.remove();const market=primary.querySelector('[data-primary="market"]');const b=document.createElement('button');b.className=`primary-item ${navPage==='favorites'?'active':''}`;b.type='button';b.dataset.primary='favorites';b.innerHTML=`<span class="primary-main"><span class="primary-icon">★</span>自选观察</span><span class="primary-meta">${srFavorites.size}</span>`;b.onclick=()=>openNavPage('favorites');market?primary.insertBefore(b,market):primary.appendChild(b);primary.querySelectorAll('[data-sector-name] .mini').forEach(mini=>{const btn=mini.closest('[data-sector-name]'),name=String(btn?.dataset?.sectorName||'');if(name&&srFavorites.has(name)&&!mini.textContent.includes('★'))mini.textContent='★ '+mini.textContent})}
function srEnhanceManageEntry(){const span=document.querySelector('.sector-manage-btn span');if(span)span.textContent='☷ 管理板块';const b=document.querySelector('.sector-manage-btn b');if(b)b.textContent=srNavHidden?.size?`${srNavHidden.size} 已隐藏 · ${srFavorites.size} 自选`:`${srFavorites.size} 自选`}
const srFavBaseBuildMenu=buildMenu;
buildMenu=function(){srFavBaseBuildMenu();srInstallFavoritePrimary();srEnhanceManageEntry();srEnsureFavoriteMobileOption()};
const srFavBaseRenderNavManager=srRenderNavManager;
srRenderNavManager=function(){srFavBaseRenderNavManager();const list=document.getElementById('srNavList');if(!list)return;list.querySelectorAll('.sr-manage-row').forEach(row=>{const name=String(row.dataset.srName||''),actions=row.querySelector('.sr-row-actions');if(!actions||actions.querySelector('[data-sr-favorite]'))return;const b=document.createElement('button');b.type='button';b.className=`sr-row-btn favorite-toggle ${srFavorites.has(name)?'is-favorite':''}`;b.dataset.srFavorite='1';b.title=srFavorites.has(name)?'取消自选':'加入自选';b.textContent=srFavorites.has(name)?'★':'☆';b.onclick=()=>srToggleFavorite(name);actions.prepend(b)});const title=document.getElementById('srNavTitle');if(title)title.textContent='管理板块';const p=document.querySelector('.sr-nav-head p');if(p)p.textContent='拖拽或上移/下移调整顺序；可隐藏板块，也可点 ☆/★ 加入自选。所有设置只保存在当前浏览器。'};
const srFavBaseBuildMobile=buildMobile;
buildMobile=function(){srFavBaseBuildMobile();srEnsureFavoriteMobileOption();const p=document.getElementById('mobilePrimaryNav');if(p)p.onchange=()=>openNavPage(p.value)};
srEnsureFavoritesPanel();srEnsureFavoriteMobileOption();buildMenu();
'''


def main():
    text = INDEX.read_text(encoding="utf-8")
    if MARKER in text:
        print("[skip] favorites watchlist already installed")
        return
    if "SECTOR_NAV_MANAGER" not in text:
        raise RuntimeError("sector nav manager must be installed first")
    if "</body>" not in text:
        raise RuntimeError("body marker missing")
    patch = f"\n<style>{CSS}</style>\n<script>{JS}</script>\n<!-- {MARKER} -->\n"
    text = text.replace("</body>", patch + "</body>", 1)
    INDEX.write_text(text, encoding="utf-8")
    print("[done] favorites watchlist installed")


if __name__ == "__main__":
    main()
