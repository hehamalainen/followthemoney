import argparse,json,pathlib,datetime,math
from roster import ROSTER
from research_cache import atomic_write, cache_path, read_json, require_sec_cache
ROOT=pathlib.Path(__file__).resolve().parents[1]; ASOF='2026-10-03'
parser=argparse.ArgumentParser(description='Rebuild the fixed financial snapshot from a complete SEC cache.')
parser.add_argument('--cache',type=pathlib.Path,help='SEC cache; default AI_MONEY_MAP_SEC_CACHE or .cache/sec')
parser.add_argument('--output',type=pathlib.Path,default=ROOT/'dist/data.json')
args=parser.parse_args(); CACHE=cache_path('sec',args.cache,ROOT)
try:
 require_sec_cache(CACHE,ROOT)
except ValueError as exc:
 raise SystemExit(str(exc)) from exc
previous={c['ticker']:c for c in read_json(ROOT/'dist/data.json')['companies']}
TAGS={
'revenue':['RevenueFromContractWithCustomerExcludingAssessedTax','RevenueFromContractWithCustomerIncludingAssessedTax','Revenues','SalesRevenueNet','Revenue'],
'net':['NetIncomeLoss','ProfitLoss','NetIncomeLossAvailableToCommonStockholdersBasic','ProfitLossAttributableToOwnersOfParent'],
'ocf':['NetCashProvidedByUsedInOperatingActivities','CashFlowsFromUsedInOperatingActivities'],
'capex':['PaymentsToAcquirePropertyPlantAndEquipment','PaymentsToAcquireProductiveAssets','PurchaseOfPropertyPlantAndEquipment','PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities','PurchaseOfPropertyPlantAndEquipmentIntangibleAssetsOtherThanGoodwillInvestmentPropertyAndOtherNoncurrentAssets','PaymentsToAcquirePropertyPlantAndEquipmentAndIntangibleAssets'],
'operating':['OperatingIncomeLoss','ProfitLossFromOperatingActivities'],
}
def day(s):return datetime.date.fromisoformat(s)
def duration(x):return (day(x['end'])-day(x['start'])).days

def facts(d,key):
 out=[]
 for ns in ['us-gaap','ifrs-full']:
  for rank,tag in enumerate(TAGS[key]):
   for unit,items in d.get('facts',{}).get(ns,{}).get(tag,{}).get('units',{}).items():
    if len(unit)!=3:continue
    for i in items:
     if i.get('start') and i.get('end') and i.get('filed','9999')<=ASOF and i.get('form') in ['10-K','10-Q','20-F','40-F','10-K/A','10-Q/A','20-F/A','6-K']:
      out.append(dict(i,tag=ns+':'+tag,currency=unit,rank=rank))
 # same interval prefers newest filing, USD only if equally recent (foreign native currencies retained)
 return out

def base(x):return {k:x.get(k) for k in ['start','end','val','currency','filed','accn','tag']}
def get_exact(items,start,end,currency):
 x=[i for i in items if i['start']==start and i['end']==end and i['currency']==currency]
 return max(x,key=lambda i:(i['filed'],-i['rank'])) if x else None

def calc(items,end,currency):
 direct=[i for i in items if i['end']==end and i['currency']==currency and 330<=duration(i)<=380]
 if direct:
  x=max(direct,key=lambda i:(i['form'] in ['10-K','10-K/A','20-F','20-F/A','40-F'],i['filed'],-i['rank']));return dict(value=x['val'],start=x['start'],end=end,currency=currency,method=('Fiscal year' if x['form'] in ['10-K','10-K/A','20-F','20-F/A','40-F'] else 'TTM reported'),components=[base(x)])
 ytds=sorted([i for i in items if i['end']==end and i['currency']==currency and 45<=duration(i)<=320],key=lambda i:(duration(i),i['filed'],-i['rank']),reverse=True)
 for y in ytds:
  annuals=sorted([a for a in items if a['currency']==currency and 330<=duration(a)<=380 and 0<(day(y['start'])-day(a['end'])).days<12],key=lambda i:(i['end'],i['form'] in ['10-K','10-K/A','20-F','20-F/A','40-F'],i['filed'],-i['rank']),reverse=True)
  for a in annuals:
   prior=[p for p in items if p['currency']==currency and p['start']==a['start'] and abs(duration(p)-duration(y))<10 and 350<(day(y['end'])-day(p['end'])).days<380]
   if not prior:continue
   p=max(prior,key=lambda i:(i['filed'],-i['rank']))
   return dict(value=a['val']+y['val']-p['val'],start=(day(p['end'])+datetime.timedelta(days=1)).isoformat(),end=end,currency=currency,method='TTM: fiscal year + current YTD − prior YTD',components=[base(a),base(y),base(p)])
 return None

def company(c):
 p=CACHE/(c['ticker']+'.json')
 if not p.exists():return dict(c,metrics={},history=[],basis='Pending verification',end=None,currency=None,sources=[])
 d=json.loads(p.read_text());fs={k:facts(d,k) for k in TAGS};cik=int(d['cik'])
 revenue=fs['revenue']; recent=sorted(set((x['end'],x['currency']) for x in fs['net']),reverse=True)
 chosen=None
 for end,currency in recent:
  net=calc(fs['net'],end,currency);rev=calc(revenue,end,currency)
  if net and rev and net['start']==rev['start']:chosen=(end,currency,net,rev);break
 if not chosen:return dict(c,metrics={},history=[],basis='Pending verification',end=None,currency=None,sources=[dict(label='SEC filings',url=f'https://www.sec.gov/edgar/browse/?CIK={cik}')])
 end,currency,net,rev=chosen
 metrics={'net':net,'revenue':rev}
 for k in ['ocf','capex','operating']:
  m=calc(fs[k],end,currency)
  if m and m['start']==net['start']:metrics[k]=m
 if metrics.get('ocf') and metrics.get('capex'):
  metrics['fcf']=dict(value=metrics['ocf']['value']-metrics['capex']['value'],start=net['start'],end=end,currency=currency,method='Operating cash flow − cash capital expenditure',components=metrics['ocf']['components']+metrics['capex']['components'])
 history=[]
 for e in sorted(set(x['end'] for x in fs['net'] if 330<=duration(x)<=380),reverse=True)[:3]:
  h={k:calc(fs[k],e,currency) for k in ['revenue','net','ocf','capex']}
  if h['net'] and h['revenue']:history.append(dict(end=e,metrics=h))
 q=sorted([x for x in fs['net'] if x['currency']==currency and 65<=duration(x)<=105],key=lambda i:(i['end'],i['form'] in ['10-K','10-K/A','20-F','20-F/A','40-F'],i['filed'],-i['rank']),reverse=True)
 latestQuarter=None
 if q:
  x=q[0];rv=get_exact(revenue,x['start'],x['end'],currency)
  latestQuarter=dict(start=x['start'],end=x['end'],net=x['val'],revenue=rv['val'] if rv else None,filed=x['filed'])
 accns=sorted(set(z['accn'] for m in metrics.values() for z in m['components'] if z.get('accn')))
 sources=[dict(label='SEC filing '+a,url=f'https://www.sec.gov/Archives/edgar/data/{cik}/{a.replace("-","")}/{a}-index.html') for a in accns]
 sources.append(dict(label='SEC structured company facts',url=f'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json'))
 return dict(c,cik=cik,metrics=metrics,end=end,currency=currency,start=net['start'],basis='TTM' if net['method'].startswith('TTM') else 'FY',history=history,latestQuarter=latestQuarter,sources=sources,fcfDefinition='OCF less cash purchases of property, plant and equipment (or broader productive assets where tagged). Excludes finance-lease principal; definitions differ by issuer.',dataNote='Standardized SEC facts. Foreign issuer interim releases may be newer than the latest structured SEC period.')
rows=[company(c) for c in ROSTER]
for c in rows:
 p=CACHE/(c['ticker']+'.json')
 if p.exists() and c.get('end') and c.get('currency'):
  fs=facts(json.loads(p.read_text()),'revenue')
  ends=sorted(set(i['end'] for i in fs if 350<(day(c['end'])-day(i['end'])).days<380),reverse=True)
  for e in ends:
   prev=calc(fs,e,c['currency'])
   if prev and prev['value']>0 and abs((day(prev['end'])-day(prev['start'])).days-(day(c['end'])-day(c['start'])).days)<10:
    c['revenueGrowth']=(c['metrics']['revenue']['value']/prev['value']-1)*100
    c['growthPrior']=prev
    break

overrides=ROOT/'scripts/manual_data.json'
if overrides.exists():
 manual=json.loads(overrides.read_text())
 for c in rows:
  if c['ticker'] in manual:c.update(manual[c['ticker']])
for c in rows:
 c['margin']=c['metrics']['net']['value']/c['metrics']['revenue']['value']*100 if c['metrics'].get('net') and c['metrics'].get('revenue') and c['metrics']['revenue']['value'] else None
 c['fcfMargin']=c['metrics']['fcf']['value']/c['metrics']['revenue']['value']*100 if c['metrics'].get('fcf') and c['metrics'].get('revenue') and c['metrics']['revenue']['value'] else None
 c['stale']=not c['end'] or (day(ASOF)-day(c['end'])).days>180
market_path=ROOT/'scripts/market_data.json'
if market_path.exists():
 market=json.loads(market_path.read_text())
 for c in rows:
  if c['ticker'] in market:c['market']=market[c['ticker']]
out=dict(asOf=ASOF,companies=rows)
# Reject missing or older input coverage before replacing the good snapshot.
problems=[]
for c in rows:
 old=previous.get(c['ticker'],{})
 for key in set(old.get('metrics',{})) | {'net','revenue'}:
  metric=c['metrics'].get(key)
  if not metric or not math.isfinite(metric.get('value',float('nan'))):problems.append(c['ticker']+': '+key)
 if not c.get('sources') or not c.get('market'):problems.append(c['ticker']+': sources/market')
 if old.get('end') and (not c.get('end') or c['end']<old['end']):problems.append(c['ticker']+': older reporting period')
 if old.get('revenueGrowth') is not None and c.get('revenueGrowth') is None:problems.append(c['ticker']+': revenue growth')
if problems:raise SystemExit('Incomplete financial inputs; saved output preserved: '+', '.join(problems))
atomic_write(args.output,json.dumps(out,separators=(',',':')))
print('Companies',len(rows),'Profit',sum('net'in c['metrics'] for c in rows),'FCF',sum('fcf'in c['metrics'] for c in rows))
for c in rows:
 if not c['metrics'].get('fcf') or c['stale']:print(c['ticker'],c['basis'],c['end'],list(c['metrics']))
