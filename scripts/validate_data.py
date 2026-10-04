"""Offline integrity checks for the published, dated research snapshot."""
import json, math
from datetime import date
from pathlib import Path
root = Path(__file__).resolve().parents[1]
data = json.loads((root / 'dist/data.json').read_text())
scenario = json.loads((root / 'dist/scenarios.json').read_text())
rows = data['companies']; tickers = {c['ticker'] for c in rows}
assert len(rows) == len(tickers) == 100
assert tickers == set(scenario['profiles'])
assert len({c['sector'] for c in rows}) == 9
assert len(scenario['scenarios']) == 3
asof = date.fromisoformat(data['asOf'])
for c in rows:
    t = c['ticker']; m = c['metrics']
    assert 'net' in m and 'revenue' in m, t
    assert c['sources'] and all(x['url'].startswith('https://') for x in c['sources']), t
    assert date.fromisoformat(c['end']) <= asof, t
    assert c['stale'] == ((asof-date.fromisoformat(c['end'])).days > 180), t
    for k, metric in m.items():
        assert math.isfinite(metric['value']), (t,k)
        assert (metric['start'],metric['end'],metric['currency']) == (c['start'],c['end'],c['currency']), (t,k)
        assert metric['start'] <= metric['end'], (t,k)
        for x in metric.get('components',[]):
            assert x.get('filed', data['asOf']) <= data['asOf'], (t,k)
    if all(k in m for k in ['ocf','capex','fcf']) and not c.get('fcfReported'):
        assert math.isclose(m['fcf']['value'],m['ocf']['value']-m['capex']['value'],abs_tol=1), t
    assert math.isclose(c['margin'],m['net']['value']/m['revenue']['value']*100), t
    if 'fcf' in m:
        assert math.isclose(c['fcfMargin'],m['fcf']['value']/m['revenue']['value']*100), t
    market = c['market']
    assert market['end'] <= data['asOf'] and market['start'] < market['end'], t
    assert math.isclose(market['excess'],market['return1y']-market['benchmarkReturn']), t
    if market['boomComparable']:
        assert '2023-01-01' <= market['boomStart'] <= '2023-01-10', t
        assert math.isclose(market['boomExcess'],market['boomReturn']-market['boomBenchmarkReturn']), t
    p = scenario['profiles'][t]
    assert len(p['scores']) == 3 and all(isinstance(n,int) and -3 <= n <= 3 for n in p['scores']), t
    assert len(p['scenarioNotes']) in [0,3], t
    assert p['mechanism'] and p['risk'] and p['watch'], t
    assert all(s in scenario['sources'] for s in p['sources']), t
for s in scenario['scenarios']:
    assert len(s['path']) == 5 and s['path'][0] == 100
    assert all(t in tickers for t in s['winners']+s['losers']+s['hiddenPriority'])
print(f"Validated {len(rows)} companies, 300 scenario ratings, {sum('fcf' in c['metrics'] for c in rows)} FCF records and 100 matched stock/benchmark comparisons.")
