#!/usr/bin/env python3
"""Validate financial safety invariants and independently checked issuer examples."""
import json
import math
from pathlib import Path

d=json.loads((Path(__file__).with_name('research')/'valuation-source.json').read_text())
rows={r['ticker']:r for r in d['companies']}
assert len(rows)==100
for t,r in rows.items():
 for name in ('grossDebt','cash','marketCap','financeLeases'):
  assert r[name] is None or (math.isfinite(r[name]) and r[name]>=0),(t,name)
 if r['grossDebt'] is not None:
  p=r['components']['grossDebt']
  assert len({x['tag'] for x in p})==len(p),t
  assert {x['end'] for x in p}=={r['debtDate']},t
  assert {x['currency'] for x in p}=={r['currency']},t
  assert math.isclose(sum(x['val'] for x in p),r['grossDebt'],abs_tol=.01),t
 if r['netDebt'] is not None:
  assert r['debtDate']==r['cashDate']==r['balanceDate'],t
  assert math.isclose(r['grossDebt']-r['cash'],r['netDebt'],abs_tol=.01),t
 if r['marketCap'] is not None:
  assert r['sharesDate']<=r['priceDate'],t
  assert math.isclose(r['marketCap'],r['shares']*r['price']),t
 if r['pe'] is not None:
  e=r['earnings'];assert e['basis'] in ('FY','TTM') and e['value']>0,t
  assert e['currency']==r['currency'],t
  assert math.isclose(sum(x['val']*x['sign'] for x in e['components']),e['value'],abs_tol=1e-6),t
  assert math.isclose(r['pe'],r['price']/e['value']),t
 if r['fcfYield'] is not None:
  f=r['fcfPeriod'];assert f['basis'] in ('FY','TTM'),t
  assert math.isclose(r['fcfYield'],100*f['value']/r['marketCap']),t
 if r['totalDebtIncludingFinanceLeases'] is not None:
  assert r['debtIncludesLeases'] is False,t
  assert {x['end'] for x in r['components']['financeLeases']}=={r['debtDate']},t
  assert math.isclose(r['totalDebtIncludingFinanceLeases'],r['grossDebt']+r['financeLeases']),t
 if r['leaseAdjustedNetDebt'] is not None:
  assert r['debtDate']==r['cashDate'],t
  assert math.isclose(r['leaseAdjustedNetDebt'],r['totalDebtIncludingFinanceLeases']-r['cash']),t
 for parts in r['components'].values():
  assert all(p['filed']<=d['asOf'] and p['end']<=d['asOf'] for p in parts),t
  assert all(p['source'].startswith('https://') for p in parts),t

# Independent numbers from linked consolidated statements, not formula copies.
for t,expected in {'MSFT':40294000000,'AMZN':132549000000,'IBM':61987000000,
 'AMAT':6544000000,'NOW':7517000000,'WDAY':2989000000,'NVDA':33366000000,
 'CRWV':35068000000,'ORCL':125337000000,'NBIS':8545700000}.items():
 assert rows[t]['grossDebt']==expected,(t,rows[t]['grossDebt'],expected)
assert rows['MSFT']['financeLeases']==66594000000
assert rows['MSFT']['totalDebtIncludingFinanceLeases']==106888000000
assert rows['MSFT']['leaseAdjustedNetDebt']==85953000000
assert rows['APH']['shares']==2465966914 # July count × verified September 2-for-1 distribution.
assert rows['PATH']['shares']==521155409
assert rows['WDAY']['shares']==241000000
assert rows['TSM']['marketCap'] is None and rows['TSM']['pe'] is None
assert rows['ASML']['marketCap'] is None and rows['ASML']['fcfYield'] is None
assert rows['BE']['fcfYield'] is None # quarter must not be annualized
assert rows['MDB']['grossDebt']==0 and rows['MDB']['financeLeases']==26418000
for t in ['SNPS','TEL','NOW','CRM','ADBE','MDB','WDAY','PATH']:
 assert all(rows[t][k] is not None for k in ['marketCap','pe','fcfYield','grossDebt','cash','netDebt']),t
print('PASS: 100 records; dates/currencies/arithmetic; debt components; split normalization; annual-only yield; issuer cross-checks; all 8 strict candidates.')
