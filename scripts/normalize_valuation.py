import json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
d=json.loads((root/'scripts/research/valuation-source.json').read_text());out={}
for record in d['companies']:
 v=dict(record);v['shareDate']=v.get('sharesDate');v['marketCurrency']=v.get('currency');v['ratioBasis']=(v.get('earnings')or{}).get('basis','')
 v['missingReasons']=[k+': '+val for k,val in v.get('missingReasons',{}).items()]
 v['sources']=[{'label':('Yahoo Finance price history' if 'finance.yahoo.com' in s else 'SEC filing / issuer valuation input'),'url':s}if isinstance(s,str)else s for s in v.get('sources',[])]
 out[v['ticker']]=v
d['companies']=out;(root/'dist/valuation.json').write_text(json.dumps(d,indent=2))
print('Valuation coverage',d['coverage'])
