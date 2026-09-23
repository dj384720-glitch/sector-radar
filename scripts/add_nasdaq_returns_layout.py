#!/usr/bin/env python3
"""Final UI refinements: Nasdaq trailing-return columns and compact sector stat cards."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "docs" / "index.html"
MARKER = "NASDAQ_RETURNS_COMPACT_STATS_V2"

CSS = r'''
/* NASDAQ_RETURNS_COMPACT_STATS_V2 */
body[data-nav-page="sector"] .stats.detail-workspace{
  display:grid!important;
  grid-template-columns:repeat(4,minmax(0,1fr))!important;
  gap:7px!important;
  margin:8px 0 10px!important;
}
body[data-nav-page="sector"] .stats.detail-workspace .stat{
  min-width:0!important;
  min-height:68px!important;
  padding:8px 10px!important;
  border-radius:9px!important;
}
body[data-nav-page="sector"] .stats.detail-workspace .stat span{
  font-size:9px!important;
  line-height:1.25!important;
}
body[data-nav-page="sector"] .stats.detail-workspace .stat strong{
  margin-top:3px!important;
  font-size:15px!important;
  line-height:1.15!important;
  white-space:normal!important;
  word-break:break-word!important;
}
body[data-nav-page="sector"] .stats.detail-workspace .stat small{
  margin-top:2px!important;
  font-size:8px!important;
  line-height:1.25!important;
  white-space:normal!important;
}
.sr-nasdaq-table{min-width:1120px!important}
.sr-nasdaq-table th,.sr-nasdaq-table td{padding:9px 9px!important}
.sr-return{font-weight:850;font-variant-numeric:tabular-nums;white-space:nowrap}
.sr-return.up{color:var(--up)}.sr-return.down{color:var(--down)}
.sr-limit-value{white-space:nowrap}
@media(max-width:700px){
  body[data-nav-page="sector"] .stats.detail-workspace{grid-template-columns:repeat(2,minmax(0,1fr))!important;gap:6px!important}
  body[data-nav-page="sector"] .stats.detail-workspace .stat{min-height:64px!important;padding:8px 9px!important}
}
'''

JS = r'''
// NASDAQ_RETURNS_COMPACT_STATS_V2
function srReturnNumber(v){const n=Number(v);return Number.isFinite(n)?n:null}
function srReturnFmt(v){const n=srReturnNumber(v);return n===null?'—':`${n>0?'+':''}${n.toFixed(2)}%`}
function srReturnCls(v){const n=srReturnNumber(v);return n===null?'':n>0?'up':n<0?'down':''}
function srLimitFmt(row){const n=srReturnNumber(row?.max_buy);if(n!==null){if(n>=100000000)return '≥1亿元';return `${Math.round(n).toLocaleString('zh-CN')}元`}if(row?.status==='开放申购')return '未披露上限';return '—'}
function srLimitTradable(row){return !['暂停申购','数据暂缺','封闭期'].includes(String(row?.status||''))}
function srLimitSortValue(row){const n=srReturnNumber(row?.max_buy);if(n!==null)return n;if(row?.status==='开放申购')return Number.POSITIVE_INFINITY;return -1}
function srEnsureNasdaqReturnHeader(){const table=document.querySelector('#srNasdaqLimitsPanel .sr-nasdaq-table');if(!table)return;const thead=table.querySelector('thead');if(thead)thead.innerHTML='<tr><th>基金</th><th>代码</th><th>份额</th><th>申购状态</th><th>单日限额</th><th>近1年</th><th>近3年</th><th>近5年</th><th>近10年</th><th>来源</th></tr>';const body=document.getElementById('srNasdaqRows');if(body&&body.querySelector('td[colspan="7"]'))body.innerHTML='<tr><td colspan="10">正在读取最新基金状态与历史收益…</td></tr>'}
if(typeof srNasdaqRows==='function'){
  const srReturnBaseRows=srNasdaqRows;
  srNasdaqRows=function(data){
    return srReturnBaseRows(data).slice().sort((a,b)=>{
      const ta=srLimitTradable(a),tb=srLimitTradable(b);if(ta!==tb)return ta?-1:1;
      const la=srLimitSortValue(a),lb=srLimitSortValue(b);if(la!==lb)return lb-la;
      return String(a?.name||'').localeCompare(String(b?.name||''),'zh-CN');
    });
  };
}
if(typeof srRenderNasdaqTable==='function'){
  srRenderNasdaqTable=function(data){
    srEnsureNasdaqReturnHeader();
    const rows=srNasdaqRows(data),body=document.getElementById('srNasdaqRows');if(!body)return;
    if(!rows.length){body.innerHTML='<tr><td colspan="10">没有匹配的基金。</td></tr>';return}
    body.innerHTML=rows.map(x=>`<tr><td class="sr-fund-name">${srNewsHtml(x.name||'—')}</td><td>${srNewsHtml(x.code||'—')}</td><td>${srNewsHtml(x.share_class||'—')}</td><td><span class="sr-status ${srNasdaqStatusClass(x.status)}">${srNewsHtml(x.status||'数据暂缺')}</span></td><td class="sr-limit-value">${srNewsHtml(srLimitFmt(x))}</td><td class="sr-return ${srReturnCls(x.return_1y)}">${srReturnFmt(x.return_1y)}</td><td class="sr-return ${srReturnCls(x.return_3y)}">${srReturnFmt(x.return_3y)}</td><td class="sr-return ${srReturnCls(x.return_5y)}">${srReturnFmt(x.return_5y)}</td><td class="sr-return ${srReturnCls(x.return_10y)}">${srReturnFmt(x.return_10y)}</td><td><a class="sr-source-link" href="${srNewsHtml(srNewsSafeUrl(x.source_url))}" target="_blank" rel="noopener noreferrer">基金档案</a></td></tr>`).join('');
  };
}
if(typeof srNewsEnsurePanels==='function'){
  const srReturnBaseEnsurePanels=srNewsEnsurePanels;
  srNewsEnsurePanels=function(){srReturnBaseEnsurePanels();srEnsureNasdaqReturnHeader()};
}
if(typeof srRenderNasdaqLimits==='function'){
  const srReturnBaseRenderLimits=srRenderNasdaqLimits;
  srRenderNasdaqLimits=async function(){await srReturnBaseRenderLimits();srEnsureNasdaqReturnHeader();const note=document.getElementById('srNasdaqNote');if(note){const data=srNasdaqData||{};note.textContent=(data.sorting||'可申购基金优先，并按单日限额从高到低排序。')+' '+(data.return_basis||'近1/3/5/10年收益按公开累计净值曲线计算，历史不足显示“—”。')+' 最终申购限制以基金公司最新公告为准。'}};
}
srEnsureNasdaqReturnHeader();
'''


def main():
    text = INDEX.read_text(encoding="utf-8")
    if MARKER in text:
        print("[skip] Nasdaq returns/compact stats already installed")
        return
    if "DAILY_NEWS_NASDAQ_LIMITS_UI" not in text:
        raise RuntimeError("news/Nasdaq limits UI must be installed first")
    if "</body>" not in text:
        raise RuntimeError("body marker missing")
    text = text.replace("</body>", f"\n<style>{CSS}</style>\n<script>{JS}</script>\n<!-- {MARKER} -->\n</body>", 1)
    INDEX.write_text(text, encoding="utf-8")
    print("[done] Nasdaq trailing returns + final compact sector cards installed")


if __name__ == "__main__":
    main()
