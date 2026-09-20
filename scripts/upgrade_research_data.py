#!/usr/bin/env python3
"""Research-data upgrade: distinct theme proxies + best-effort ETF metadata.
Runs after fund generation and before radar calculations.
"""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from bisect import bisect_right
import html as html_lib
import json, re
from add_daily_history import fetch_daily
from update_data import PERIODS, fetch_series, http_bytes, target_date

ROOT=Path(__file__).resolve().parents[1]
DATA_PATH=ROOT/'docs'/'data'/'latest.json'

PROXY_OVERRIDES={
 '存储芯片':('sh588200','科创芯片ETF嘉实','独立ETF代理·芯片产业链'),
 'PCB':('sz159732','消费电子ETF华夏','近似ETF代理·电子硬件链'),
 'AI应用':('sh562930','软件ETF易方达','独立ETF代理·软件服务方向'),
 '国产算力':('sz159558','半导体设备ETF易方达','独立ETF代理·国产芯片/设备链'),
 'CPO':('sz159583','通信设备ETF富国','独立ETF代理·通信设备方向'),
 'CXO':('sh512290','生物医药ETF国泰','近似ETF代理·生物医药产业链'),
 '商业航天':('sh563380','航空航天ETF华泰柏瑞','独立ETF代理·航空航天产业链'),
}

def calc_returns(points):
    if not points:return {}
    latest_d,latest_v=points[-1];dates=[d for d,_ in points];vals=[v for _,v in points];out={}
    for label,spec in PERIODS:
        t=target_date(latest_d,spec);i=bisect_right(dates,t)-1
        out[label]=None if i<0 or (t-dates[i]).days>16 or vals[i]<=0 else round((latest_v/vals[i]-1)*100,2)
    return out

def apply_proxies(payload):
    by={x.get('name'):x for x in payload.get('sectors') or []};changed=0
    for name,(code,label,method) in PROXY_OVERRIDES.items():
        item=by.get(name)
        if not item:continue
        try:
            pts,source=fetch_series(code)
            try:
                daily=fetch_daily(code)
                if len(daily)>=60:pts=daily
            except Exception:pass
            if len(pts)<20:raise RuntimeError('history too short')
            item.update(code=code,benchmark=label,methodology=method,source=source,latest_date=pts[-1][0].isoformat(),history_start=pts[0][0].isoformat())
            item['history']=[[d.isoformat(),round(v,6)] for d,v in pts]
            item['returns']=calc_returns(pts)
            item['note']=f'{method}。用于价格状态研究，不等同于完整行业官方指数。'
            changed+=1
        except Exception as exc:print(f'[proxy-warn] {name}: {str(exc)[:140]}')
    return changed

def strip_tags(text):
    text=re.sub(r'<script[\s\S]*?</script>',' ',text,flags=re.I);text=re.sub(r'<style[\s\S]*?</style>',' ',text,flags=re.I);text=re.sub(r'<[^>]+>',' ',text)
    return re.sub(r'\s+',' ',html_lib.unescape(text))

def fetch_meta(code):
    raw=re.sub(r'^(?:sh|sz)','',str(code))
    if not re.fullmatch(r'\d{6}',raw):return {}
    try:plain=strip_tags(http_bytes(f'https://fund.eastmoney.com/{raw}.html',timeout=7,retries=1,referer='https://fund.eastmoney.com/').decode('utf-8',errors='ignore'))
    except Exception as exc:return {'meta_error':str(exc)[:90]}
    out={'meta_source':'东方财富基金公开页面'}
    patterns={
      'scale_billion':[r'规模[:：]\s*([0-9.]+)亿元',r'基金规模[:：]?\s*([0-9.]+)\s*亿元'],
      'tracking_index':[r'跟踪标的[:：]\s*([^|]{2,40}?)(?:\s*\||\s*年化跟踪误差|\s*交易状态)',r'跟踪指数[:：]\s*([^|]{2,40}?)(?:\s*\||\s*基金)'],
      'tracking_error':[r'年化跟踪误差[:：]\s*([0-9.]+%)'],
      'management_fee':[r'管理费率[:：]?\s*([0-9.]+%)',r'管理费[:：]?\s*([0-9.]+%)'],
      'custody_fee':[r'托管费率[:：]?\s*([0-9.]+%)',r'托管费[:：]?\s*([0-9.]+%)']}
    for k,pats in patterns.items():
        for pat in pats:
            m=re.search(pat,plain,flags=re.I)
            if m:
                v=m.group(1).strip();out[k]=float(v) if k=='scale_billion' else v;break
    return out

def enrich(payload):
    funds=[f for s in payload.get('sectors') or [] for f in (s.get('funds') or []) if f.get('code')];codes=sorted({f['code'] for f in funds});meta={}
    with ThreadPoolExecutor(max_workers=12) as pool:
        jobs={pool.submit(fetch_meta,c):c for c in codes}
        for fut in as_completed(jobs):
            c=jobs[fut]
            try:meta[c]=fut.result()
            except Exception as exc:meta[c]={'meta_error':str(exc)[:90]}
    enriched=0
    for f in funds:
        m=meta.get(f.get('code')) or {};f['research_meta']=m
        if any(k in m for k in ('scale_billion','tracking_index','tracking_error','management_fee','custody_fee')):enriched+=1
    return len(codes),enriched

def main():
    payload=json.loads(DATA_PATH.read_text(encoding='utf-8'));changed=apply_proxies(payload);unique,enriched=enrich(payload)
    payload['research_data']={'updated_at':datetime.now(timezone.utc).isoformat(),'proxy_overrides':changed,'fund_meta_unique':unique,'fund_meta_enriched_rows':enriched}
    DATA_PATH.write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    print(f'[done] research data: proxy_overrides={changed} fund_meta_unique={unique} enriched_rows={enriched}')
if __name__=='__main__':main()
