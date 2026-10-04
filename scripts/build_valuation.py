#!/usr/bin/env python3
"""Build dated, traceable valuation/debt observations from the saved SEC snapshot.

Run: python3 build_valuation.py --site /absolute/path/ai-money-map
No network requests. Null means unavailable, never zero. Currency is never converted.
"""
import argparse
import datetime as dt
import json
from pathlib import Path
from research_cache import atomic_write, cache_path, read_json, require_sec_cache

AS_OF = '2026-10-03'
FORMS = {'10-K', '10-Q', '20-F', '40-F', '6-K'}
MULTICLASS = {'GOOGL','META','CRWV','NBIS','DELL','CLS','PLTR','DDOG','NET','WDAY','PATH','AI','CRWD'}
ADR = {'BABA','BIDU','TSM','UMC','ARM','ASML','STM','SAP','INFY'}
SPLITS = {
 'APH': {'date':'2026-09-03','factor':2,'source':'https://www.sec.gov/Archives/edgar/data/820313/000110465926105485/tm2624775d1_8k.htm'},
 'CRWD': {'date':'2026-07-02','factor':4,'source':'https://www.sec.gov/Archives/edgar/data/1535527/000153552726000029/crwd-20260826xex991.htm'},
 'KLAC': {'date':'2026-06-12','factor':10,'source':'https://ir.kla.com/sec-filings/all-sec-filings/content/0001193125-26-212093/d116682dex991.htm'},
 'NOW': {'date':'2025-12-18','factor':5,'source':'https://www.sec.gov/Archives/edgar/data/1373715/000137371526000076/now-20260630.htm'},
}
LT = 'LongTermDebt'
LC = 'LongTermDebtCurrent'
LN = 'LongTermDebtNoncurrent'
DC = 'DebtCurrent'
ST = 'ShortTermBorrowings'
CP = 'CommercialPaper'
NCAP = 'LongTermDebtAndCapitalLeaseObligations'
CCAP = 'LongTermDebtAndCapitalLeaseObligationsCurrent'
# Explicit extraction recipes: component sets never overlap. These resolve
# issuer-specific uses of ShortTermBorrowings that include current maturities.
RECIPES = {
 'MSFT':[LC,LN], 'AMZN':[LC,LN,ST], 'GOOGL':[LC,LN,CP], 'META':[LT],
 'ORCL':['DebtLongtermAndShorttermCombinedAmount'],
 'AAPL':[LC,LN,CP], 'IBM':[ST,LN], 'DOCN':[LC,LN], 'NVDA':[DC,LN],
 'AMD':['DebtLongtermAndShorttermCombinedAmount'], 'AVGO':[DC,LN],
 'INTC':[DC,LN], 'MU':['DebtAndCapitalLeaseObligations'], 'TXN':[LC,LN,CP],
 'AMAT':[ST,LN], 'LRCX':[LC,LN], 'KLAC':['DebtLongtermAndShorttermCombinedAmount'],
 'SNPS':[LC,LN], 'CDNS':['UnsecuredLongTermDebt'], 'CSCO':[DC,LN],
 'DELL':[DC,LN], 'HPE':['DebtLongtermAndShorttermCombinedAmount'],
 'SMCI':['DebtLongtermAndShorttermCombinedAmount'], 'MRVL':[LC,LN,ST],
 'COHR':[LC,LN], 'LITE':['DebtLongtermAndShorttermCombinedAmount'],
 'CIEN':[LC,LN], 'JBL':[LC,LN], 'FLEX':[LC,LN], 'CLS':[NCAP,CCAP],
 'VRT':[LC,LN], 'ETN':[LT,ST], 'GEV':['LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities'],
 'PWR':[NCAP,DC], 'HUBB':[DC,LN], 'NVT':[LC,LN], 'APH':[NCAP,CCAP],
 'CEG':[LC,LN,ST], 'VST':[LT,ST], 'NEE':[LC,LN,CP,'OtherShortTermBorrowings'],
 'TLN':[LC,LN], 'ETR':[LC,LN,ST], 'BE':[LC,LN,ST], 'TT':[DC,LN],
 'CARR':[DC,LN], 'JCI':[NCAP,CCAP,ST], 'MOD':[NCAP,CCAP,ST],
 'FIX':[LC,LN], 'ACM':[NCAP,DC], 'EQIX':[LT], 'IRM':[LC,LN],
 'NOW':[LT,ST], 'CRM':[LC,LN], 'ADBE':[LT,DC],
 'NET':['ConvertibleDebtCurrent','ConvertibleDebtNoncurrent'],
 'WDC':[LC,LN], 'NTAP':[LC,LN,CP], 'SANM':[DC,LN], 'TEL':[DC,LN],
 'LFUS':[LC,LN], 'AEIS':[LC,LN], 'WDAY':[LC,LN],
 'GFS':['ifrs-full:Borrowings'], 'SAP':['ifrs-full:Borrowings'],
}
INCLUDES_LEASES = {'MU','CLS','ETN','GEV','PWR','APH','VST','JCI','MOD','ACM','EQIX','IRM','HPE'}
NOTES = {
 'IBM':'Total corporate debt includes the customer-financing business; financing assets are not netted.',
 'MSFT':'Cash-only net debt excludes substantial short-term investments. Finance leases are displayed separately and are material.',
 'NOW':'Short-term borrowings are the net carrying value of commercial paper; the commercial-paper face amount is not added again.',
 'AMAT':'ShortTermBorrowings already includes current maturities; LongTermDebtCurrent is not added again.',
 'AVGO':'Uses current plus noncurrent balance-sheet carrying values, not the higher debt-instrument/face-value total.',
 'EQIX':'Debt may include finance leases; do not add the separately displayed lease balance again. REIT P/E is less informative than FFO/AFFO, which is not estimated here.',
 'DLR':'REIT P/E is less informative than FFO/AFFO, which is not estimated here. Standard SEC tags do not provide a safe consolidated debt total.',
 'IRM':'Reported borrowing components may include financing leases. REIT P/E is less informative than FFO/AFFO.',
 'BE':'Short-term bank borrowing is separate from current maturities of long-term debt.',
 'CDNS':'Latest available standard-tag debt facts predate the June earnings release in the main dataset; acquisition financing may have changed materially.',
 'SNPS':'Debt reflects the Ansys acquisition financing. Earnings and cash flow include acquisition and integration effects.',
 'CRM':'The debt-funded accelerated share repurchase creates a large difference between current reported shares and trailing weighted-average shares.',
 'HUBB':'Available standard-tag balance sheet predates NSI acquisition financing; do not interpret it as current post-acquisition leverage.',
 'LITE':'Reported net income contains a very large loss; a negative P/E is not displayed.',
}

def date(s): return dt.date.fromisoformat(s)
def filing_url(cik, accession):
 return f'https://www.sec.gov/Archives/edgar/data/{cik}/{accession.replace("-", "")}/{accession}-index.html'

class Facts:
 def __init__(self, data): self.data = data; self.cik = data['cik']
 def all(self, tag, currency=None, instant=True):
  ns, key = tag.split(':',1) if ':' in tag else ('us-gaap',tag)
  obj = self.data.get('facts',{}).get(ns,{}).get(key,{})
  rows=[]
  for unit, facts in obj.get('units',{}).items():
   if currency and unit != currency: continue
   for f in facts:
    if f.get('filed','9999')>AS_OF or f.get('end','9999')>AS_OF or f.get('form') not in FORMS: continue
    if instant and f.get('start'): continue
    if not instant and not f.get('start'): continue
    rows.append(dict(f,tag=ns+':'+key,currency=unit,source=filing_url(self.cik,f['accn'])))
  return rows
 def get(self, tag, currency=None, end=None):
  rows=[f for f in self.all(tag,currency) if end is None or f['end']==end]
  if not rows:return None
  best=max(rows,key=lambda f:(f['end'],f['filed']))
  same=[f for f in rows if (f['end'],f['filed'])==(best['end'],best['filed'])]
  # Conflicting contexts are not silently collapsed.
  if len({f['val'] for f in same})>1:return None
  return best

def obs(f):
 if not f:return None
 return {k:f[k] for k in ('val','end','currency','tag','filed','accn','source') if k in f}

def eps(facts, currency, ticker):
 """Annual EPS or annual + current YTD - prior YTD, with full provenance.
 EPS is a per-share series; comparative values use latest filings available.
 """
 rows=facts.all('EarningsPerShareDiluted',currency+'/shares',False)
 split=SPLITS.get(ticker)
 if split:
  rows=[dict(f,val=f['val']/split['factor'],splitAdjustment=split) if f['filed']<split['date'] else f for f in rows]
 if not rows:return None
 def length(f):return (date(f['end'])-date(f['start'])).days+1
 # Pick annual statement, then a newer YTD observation only when all dates match.
 ann=[f for f in rows if 350<=length(f)<=378 and f['form'] in {'10-K','20-F','40-F'}]
 if not ann:return None
 a=max(ann,key=lambda f:(f['end'],f['filed']))
 value=a['val']; parts=[dict(a,sign=1)]; start=a['start']; end=a['end']; basis='FY'
 newer=[f for f in rows if f['end']>a['end'] and 60<=length(f)<=300 and 0<(date(f['start'])-date(a['end'])).days<=10]
 if newer:
  c=max(newer,key=lambda f:(f['end'],length(f),f['filed']))
  prior=[f for f in rows if 355<=(date(c['start'])-date(f['start'])).days<=378 and 355<=(date(c['end'])-date(f['end'])).days<=378 and abs(length(c)-length(f))<=8]
  if prior:
   p=max(prior,key=lambda f:f['filed'])
   value=a['val']+c['val']-p['val']; parts=[dict(a,sign=1),dict(c,sign=1),dict(p,sign=-1)]
   start=(date(p['end'])+dt.timedelta(days=1)).isoformat();end=c['end'];basis='TTM'
 return {'value':round(value,6),'start':start,'end':end,'basis':basis,'currency':currency,
  'method':'Reported diluted EPS' if basis=='FY' else 'Latest annual diluted EPS + current fiscal YTD diluted EPS − prior fiscal YTD diluted EPS; trailing per-share approximation',
  'components':[dict(obs(p),start=p['start'],sign=p['sign'],splitAdjustment=p.get('splitAdjustment')) for p in parts]}

def build(company, cache):
 ticker=company['ticker']; market=company.get('market',{}); cur=company.get('currency')
 row={'ticker':ticker,'currency':cur,'priceDate':market.get('end'),'price':market.get('close'),
      'marketCap':None,'pe':None,'fcfYield':None,'grossDebt':None,'cash':None,'netDebt':None,
      'liquidFunds':None,'netDebtAfterLiquidFunds':None,'financeLeases':None,'netDebtToFcf':None,
      'totalDebtIncludingFinanceLeases':None,'leaseAdjustedNetDebt':None,'leaseAdjustedNetDebtToFcf':None,
      'balanceDate':None,'debtDate':None,'cashDate':None,'shares':None,'sharesDate':None,
      'earnings':None,'components':{},'notes':[],'missingReasons':{},'sources':[],
      'balanceStale':True,'cashStale':True,'debtIncludesLeases':None}
 if ticker in NOTES:row['notes'].append(NOTES[ticker])
 p=cache/(ticker+'.json')
 if not p.exists():
  row['missingReasons']={'balance':'No standard SEC facts in the saved source snapshot; local-exchange financial statement mapping is still required.',
   'valuation':'No verified total share count and annual earnings mapping for this listing/currency.'}
  return row
 facts=Facts(json.loads(p.read_text()))
 cash = facts.get('CashAndCashEquivalentsAtCarryingValue',cur) or facts.get('ifrs-full:CashAndCashEquivalents',cur)
 if cash and (date(AS_OF)-date(cash['end'])).days>365:
  row['missingReasons']['cash']='Latest standard-tag cash figure is over one year old and is withheld.';cash=None
 if cash:
  row['cash']=cash['val'];row['cashDate']=cash['end'];row['components']['cash']=[obs(cash)]
  row['cashStale']=(date(AS_OF)-date(cash['end'])).days>180
  liquid=facts.get('CashCashEquivalentsAndShortTermInvestments',cur,cash['end'])
  short=next((f for tag in ['ShortTermInvestments','MarketableSecuritiesCurrent','AvailableForSaleSecuritiesCurrent','AvailableForSaleSecuritiesDebtSecuritiesCurrent'] if (f:=facts.get(tag,cur,cash['end']))),None)
  if liquid:
   row['liquidFunds']=liquid['val'];row['components']['liquidFunds']=[obs(liquid)]
  elif short:
   row['liquidFunds']=cash['val']+short['val'];row['components']['liquidFunds']=[obs(cash),obs(short)]
 # Require every explicitly selected debt component at one common date.
 recipe=RECIPES.get(ticker)
 if recipe:
  common=None
  for tag in recipe:
   ends={f['end'] for f in facts.all(tag,cur)}
   common=ends if common is None else common & ends
  if common and (date(AS_OF)-date(max(common))).days<=365:
   end=max(common);parts=[facts.get(t,cur,end) for t in recipe]
   if all(parts):
    row['grossDebt']=sum(p['val'] for p in parts);row['debtDate']=end;row['components']['grossDebt']=[obs(p) for p in parts]
    row['debtDefinition']='Reported interest-bearing borrowing carrying values' + ('; selected debt presentation includes or may include finance leases' if ticker in INCLUDES_LEASES else '; separately disclosed finance leases are excluded')
    row['debtIncludesLeases']=ticker in INCLUDES_LEASES
 if ticker=='CRWV':
  src='https://www.sec.gov/Archives/edgar/data/1769628/000176962826000366/crwv-20260630.htm'
  row['grossDebt']=35068000000;row['debtDate']='2026-06-30';row['debtIncludesLeases']=False
  row['components']['grossDebt']=[{'val':v,'end':'2026-06-30','currency':'USD','tag':'Manual:'+tag,'filed':'2026-08-12','accn':'0001769628-26-000366','source':src} for tag,v in [('TotalRecourseDebtNet',31405000000),('TotalNonRecourseDebtNet',3663000000)]]
  row['debtDefinition']='Recourse plus non-recourse debt carrying values, including OEM and software-license financing; finance leases excluded.'
  row['notes'].append('Borrowing includes $4.220bn recourse and $0.882bn non-recourse OEM/software financing. Future lease commitments and purchase commitments are additional exposures, not included in this debt total.')
 if ticker=='ORCL':
  src='https://www.sec.gov/Archives/edgar/data/1341439/000119312526389274/orcl-20260831.htm'
  row['grossDebt']=125337000000;row['debtDate']='2026-08-31';row['debtIncludesLeases']=False
  row['components']['grossDebt']=[{'val':v,'end':'2026-08-31','currency':'USD','tag':'Manual:'+tag,'filed':'2026-09-11','accn':'0001193125-26-389274','source':src} for tag,v in [('NotesPayableAndOtherBorrowingsCurrent',7625000000),('NotesPayableAndOtherBorrowingsNoncurrent',117712000000)]]
  row['debtDefinition']='Current plus noncurrent notes payable and other borrowings; excludes separately disclosed finance leases and customer prepayments.'
  row['notes'].append('Quarterly operating cash flow included $11.363bn of customer prepayments with a significant financing component. These are deferred-revenue obligations outside the displayed borrowing total; also exclude preferred equity and operating leases.')
 if ticker in {'NBIS','BE','MDB','PATH'}:
  overrides={
   'NBIS':('2026-06-30','2026-08-12','0001104659-26-094844','https://www.sec.gov/Archives/edgar/data/1513845/000110465926094844/nbis-20260812xex99d2.htm',8042100000,[('DebtCurrent',46700000),('DebtNoncurrent',8499000000)]),
   'BE':('2026-06-30','2026-07-28','0001628280-26-050150','https://www.sec.gov/Archives/edgar/data/1664703/000162828026050150/ex991_q226financialresults.htm',2666859000,[('RecourseDebtCurrent',4686000),('NonrecourseDebtCurrent',2583000),('RecourseDebtNoncurrent',2470704000),('FinancingObligationsCurrent',62034000),('FinancingObligationsNoncurrent',144446000)]),
   'MDB':('2026-07-31','2026-09-01','0001628280-26-059830','https://www.sec.gov/Archives/edgar/data/1441816/000162828026059830/mdb-20260731.htm',1002401000,[('ReviewedBalanceSheetNoBorrowings',0)]),
   'PATH':('2026-07-31','2026-09-08','0001734722-26-000050','https://www.sec.gov/Archives/edgar/data/1734722/000173472226000050/path-20260731.htm',607407000,[('ReviewedBalanceSheetNoBorrowings',0)]),
  }
  end,filed,accn,src,manual_cash,debts=overrides[ticker]
  # MDB/PATH cash retains the exact standard-tag observation already selected.
  if ticker in {'NBIS','BE'}:
   row['cash']=manual_cash;row['cashDate']=end;row['cashStale']=False
   row['components']['cash']=[{'val':manual_cash,'end':end,'currency':'USD','tag':'Manual:CashAndCashEquivalents','filed':filed,'accn':accn,'source':src}]
   row['liquidFunds']=None;row['components'].pop('liquidFunds',None)
  row['grossDebt']=sum(v for tag,v in debts);row['debtDate']=end;row['debtIncludesLeases']=False
  row['components']['grossDebt']=[{'val':v,'end':end,'currency':'USD','tag':'Manual:'+tag,'filed':filed,'accn':accn,'source':src} for tag,v in debts]
  row['debtDefinition']='Reviewed balance-sheet recourse/non-recourse borrowings at carrying value; excludes operating leases.'
  if ticker=='BE':
   row['debtDefinition']='Recourse/non-recourse borrowings plus financing obligations on the issuer balance sheet. Financing obligations are included; operating leases are excluded.'
   row['notes']=[n for n in row['notes'] if not n.startswith('Short-term bank')]
  if ticker in {'MDB','PATH'}:
   row['debtDefinition']='No bank/bond borrowings reported in the reviewed consolidated balance sheet and notes; operating/finance leases and acquisition consideration are excluded.'
   row['notes'].append('Zero here means no reported bank/bond borrowing, not zero contractual obligations. Lease liabilities, cloud commitments and acquisition consideration can still exist.')
  if ticker=='NBIS':
   row['notes'].append('June balance sheet predates July secured financing and the August convertible-note offering. This is historical reported debt, not pro forma debt after those transactions.')
 if row['grossDebt'] is None:
  row['missingReasons']['debt']='A complete, non-overlapping consolidated borrowing total is not verified from the available standard tags. Missing is not zero debt.'
 if row['debtDate'] and row['debtDate']==row['cashDate']:
  row['balanceDate']=row['debtDate'];row['netDebt']=row['grossDebt']-row['cash']
  if row['liquidFunds'] is not None:row['netDebtAfterLiquidFunds']=row['grossDebt']-row['liquidFunds']
 elif row['debtDate'] and row['cashDate']:
  # A debt number and cash number from different dates are shown but never netted.
  row['missingReasons']['netDebt']='Debt and cash dates differ; net debt is withheld.'
 lease_end=row['debtDate'] or row['cashDate']
 lease=facts.get('FinanceLeaseLiability',cur,lease_end) if lease_end else None
 if lease:row['financeLeases']=lease['val'];row['components']['financeLeases']=[obs(lease)]
 elif lease_end:
  lc=facts.get('FinanceLeaseLiabilityCurrent',cur,lease_end);ln=facts.get('FinanceLeaseLiabilityNoncurrent',cur,lease_end)
  if lc and ln:row['financeLeases']=lc['val']+ln['val'];row['components']['financeLeases']=[obs(lc),obs(ln)]
 # Never add leases twice or infer missing lease balances are zero.
 if row['grossDebt'] is not None and row['financeLeases'] is not None and row.get('debtIncludesLeases') is False:
  if ticker!='BE':
   row['totalDebtIncludingFinanceLeases']=row['grossDebt']+row['financeLeases']
   if row['debtDate']==row['cashDate']:row['leaseAdjustedNetDebt']=row['totalDebtIncludingFinanceLeases']-row['cash']
   row['leaseAdjustedDefinition']='Borrowing carrying value + separately reported finance-lease liability at the same date; operating leases and other commitments remain excluded. Cash-only subtraction.'
 elif row.get('debtIncludesLeases'):
  row['missingReasons']['leaseAdjustedDebt']='Reported debt may already include finance leases; a second lease addition is withheld to avoid double counting.'
 row['balanceStale']=not row['debtDate'] or (date(AS_OF)-date(row['debtDate'])).days>180
 # No market cap for ADR/currency ambiguity or unverified multi-class totals.
 if ticker in ADR:
  row['missingReasons']['marketCap']='ADR/foreign listing: the ordinary-share or depositary ratio and FX basis have not been reconciled.'
 elif cur!=market.get('currency'):
  row['missingReasons']['marketCap']='Financial currency and quoted-share currency differ; no FX conversion is assumed.'
 elif ticker in MULTICLASS and ticker not in {'WDAY','PATH'}:
  row['missingReasons']['marketCap']='Multiple share classes: a consolidated share count and class-pricing basis have not been reconciled.'
 else:
  shares=facts.get('dei:EntityCommonStockSharesOutstanding','shares')
  if ticker=='WDAY':
   shares={'val':241000000,'end':'2026-08-25','currency':'shares','tag':'Manual:ClassA196mPlusClassB45m',
    'filed':'2026-08-27','accn':'0001327811-26-000044',
    'source':'https://www.sec.gov/Archives/edgar/data/1327811/000132781126000044/wday-20260731.htm'}
   row['notes'].append('Market cap proxy sums 196m Class A and 45m Class B shares (rounded issuer counts); identical economic rights, priced at the quoted Class A share price.')
  if ticker=='PATH':
   shares={'val':456464703+64690706,'end':'2026-09-03','currency':'shares','tag':'Manual:ClassAPlusClassBOutstanding',
    'filed':'2026-09-08','accn':'0001734722-26-000050',
    'source':'https://www.sec.gov/Archives/edgar/data/1734722/000173472226000050/path-20260731.htm'}
   row['notes'].append('Market cap proxy prices all 456,464,703 Class A and 64,690,706 Class B outstanding shares at the Class A quote. The issuer combines both classes in EPS; voting-control differences are not separately valued.')
  if ticker=='BE':
   shares={'val':293354001,'end':'2026-06-30','currency':'shares','tag':'Manual:CommonStockOutstanding',
    'filed':'2026-07-28','accn':'0001628280-26-050150',
    'source':'https://www.sec.gov/Archives/edgar/data/1664703/000162828026050150/ex991_q226financialresults.htm'}
  if shares and shares['val']>0 and 0<=(date(market['end'])-date(shares['end'])).days<=180:
   split=SPLITS.get(ticker);factor=split['factor'] if split and shares['end']<split['date'] else 1
   row['shares']=shares['val']*factor;row['sharesDate']=shares['end'];row['components']['shares']=[dict(obs(shares),splitAdjustment=split if factor!=1 else None)]
   row['marketCap']=market['close']*row['shares']
   if factor!=1:row['notes'].append(f'Share count and earlier EPS adjusted for the {factor}-for-1 stock split effective {split["date"]}.')
   row['marketCapDefinition']='Approximate equity value: 2 October close × latest reported shares; not a live market cap. Share-count date differs from price date.'
  else:row['missingReasons']['marketCap']='No positive, unambiguous total common share count within 180 days of the price observation.'
 # Valuation earnings must be annual or trailing, not an annualized quarter.
 # For multi-class common shares, the issuer's reported diluted EPS is used;
 # it does not require treating one class's share count as the entire company.
 if ticker not in ADR and cur==market.get('currency'):
  e=eps(facts,cur,ticker)
  if e and (date(AS_OF)-date(e['end'])).days<=180:
   row['earnings']=e
   if e['value']>0:row['pe']=market['close']/e['value']
   else:row['missingReasons']['pe']='Annual/trailing diluted EPS is zero or negative; P/E is not meaningful.'
  else:row['missingReasons']['pe']='No comparable annual/trailing diluted EPS ending within the last 180 days.'
 else:row['missingReasons']['pe']='ADR share-ratio or currency basis has not been reconciled.'
 fcf=company.get('metrics',{}).get('fcf')
 annual=company.get('basis') in {'FY','TTM'} and fcf and fcf.get('currency')==cur and 350<=(date(fcf['end'])-date(fcf['start'])).days+1<=378
 if annual and row['marketCap']:
  row['fcfYield']=100*fcf['value']/row['marketCap']
  row['fcfPeriod']={'start':fcf['start'],'end':fcf['end'],'basis':company['basis'],'value':fcf['value'],'currency':cur}
  row['fcfDefinition']=company.get('fcfDefinition','Operating cash flow minus cash capital expenditure')
 elif not annual:
  row['missingReasons']['fcfYield']='Available cash flow is missing or covers a quarter/half-year; it is not annualized.'
 else:row['missingReasons']['fcfYield']='A comparable market-capitalization proxy is unavailable.'
 if annual and row['netDebt'] is not None and fcf['value']>0:
  row['netDebtToFcf']=row['netDebt']/fcf['value']
  row['netDebtToFcfDefinition']='Cash-only net debt / reported annual or trailing free cash flow; a cash-generation proxy, not debt/EBITDA or a credit rating.'
 if annual and row['leaseAdjustedNetDebt'] is not None and fcf['value']>0:row['leaseAdjustedNetDebtToFcf']=row['leaseAdjustedNetDebt']/fcf['value']
 if row['pe'] is not None and row['pe']>300:row['notes'].append('P/E is extremely sensitive to a small trailing EPS denominator. Inspect profitability and cash flow instead of interpreting the multiple in isolation.')
 row['sources']=list({p['source'] for parts in row['components'].values() for p in parts} | {p['source'] for p in (row.get('earnings') or {}).get('components',[])} | ({SPLITS[ticker]['source']} if ticker in SPLITS else set()) | ({market['source']} if market.get('source') else set()))
 row['sources'].sort()
 return row

def main():
 p=argparse.ArgumentParser();p.add_argument('--site',required=True,type=Path);p.add_argument('--cache',type=Path,help='SEC cache; default AI_MONEY_MAP_SEC_CACHE or SITE/.cache/sec');p.add_argument('--output',type=Path,default=Path(__file__).with_name('valuation.json'));a=p.parse_args()
 a.site=a.site.expanduser().resolve();a.cache=cache_path('sec',a.cache,a.site)
 try:require_sec_cache(a.cache,a.site)
 except ValueError as exc:raise SystemExit(str(exc)) from exc
 companies=read_json(a.site/'dist/data.json')['companies'];rows=[build(c,a.cache) for c in companies]
 reference=a.site/'scripts/research/valuation-source.json'
 if reference.exists():
  prior={r['ticker']:r for r in read_json(reference)['companies']}
  fields=('grossDebt','cash','netDebt','marketCap','pe','fcfYield','financeLeases','totalDebtIncludingFinanceLeases','leaseAdjustedNetDebt')
  lost=[r['ticker']+': '+field for r in rows for field in fields if prior.get(r['ticker'],{}).get(field) is not None and r.get(field) is None]
  if lost:raise SystemExit('Incomplete valuation inputs; saved output preserved: '+', '.join(lost))
 result={'asOf':AS_OF,'priceDate':'2026-10-02','methodology':[
  'Values are a dated research snapshot, not live prices or valuation recommendations.',
  'Debt is selected from non-overlapping SEC borrowing components at a single date. Debt/cash from different dates are not netted. Missing debt is never assumed to be zero.',
  'Cash-only net debt = selected borrowing total − unrestricted cash and equivalents. Where a comparable cash-plus-short-term-investment figure exists, a second liquidity-adjusted net debt is also shown.',
  'Finance leases are separate where reported; certain issuer debt presentations include them, flagged per record. Operating leases, purchase commitments, restricted cash, preferred equity and minority interests are not comprehensively included.',
  'Market cap is an approximation using the saved close and the latest verified reported share count. It is withheld for unresolved share-class, ADR or currency issues. Dilution and buybacks since the share-count date can change the estimate.',
  'P/E uses positive reported diluted annual or trailing EPS. Trailing EPS is annual + current YTD − prior YTD and is a per-share approximation. Unusual gains, acquisition accounting and changing diluted share counts can distort it.',
  'FCF yield uses a complete fiscal year or TTM only; quarterly and half-year cash flows are never multiplied up. Negative cash generation produces a negative yield. FCF definitions can differ between issuers.',
  'A low multiple, negative price momentum or high FCF yield alone does not establish a hidden champion. Compare growth durability, reinvestment, dilution, financing costs and customer concentration.'
 ],'companies':rows}
 result['coverage']={k:sum(r.get(k) is not None for r in rows) for k in ['grossDebt','cash','netDebt','liquidFunds','marketCap','pe','fcfYield','netDebtToFcf']}
 atomic_write(a.output,json.dumps(result,indent=2)+'\n');print(json.dumps(result['coverage']))

if __name__=='__main__':main()
