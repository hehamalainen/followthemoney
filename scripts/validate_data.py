"""Offline integrity checks for the published, dated research snapshot."""
import json
import math
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def require(condition, context):
    if not condition:
        raise ValueError(f"Invalid research data: {context}")

def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)

def validate_data(data, scenario, manual, prices):
    rows = data['companies']
    tickers = {c['ticker'] for c in rows}
    require(len(rows) == len(tickers) == 100, 'Validation failed: len(rows) == len(tickers) == 100')
    require(tickers == set(scenario['profiles']), "Validation failed: tickers == set(scenario['profiles'])")
    require(len({c['sector'] for c in rows}) == 9, "Validation failed: len({c['sector'] for c in rows}) == 9")
    require(len(scenario['scenarios']) == 3, "Validation failed: len(scenario['scenarios']) == 3")
    asof = date.fromisoformat(data['asOf'])
    for c in rows:
        t = c['ticker']
        m = c['metrics']
        require('net' in m and 'revenue' in m, t)
        require(c['sources'] and all((x['url'].startswith('https://') for x in c['sources'])), t)
        require(date.fromisoformat(c['end']) <= asof, t)
        require(c['stale'] == ((asof - date.fromisoformat(c['end'])).days > 180), t)
        for k, metric in m.items():
            require(math.isfinite(metric['value']), (t, k))
            require((metric['start'], metric['end'], metric['currency']) == (c['start'], c['end'], c['currency']), (t, k))
            require(metric['start'] <= metric['end'], (t, k))
            for x in metric.get('components', []):
                require(x.get('filed', data['asOf']) <= data['asOf'], (t, k))
        if all((k in m for k in ['ocf', 'capex', 'fcf'])) and (not c.get('fcfReported')):
            require(math.isclose(m['fcf']['value'], m['ocf']['value'] - m['capex']['value'], abs_tol=1), t)
        require(math.isclose(c['margin'], m['net']['value'] / m['revenue']['value'] * 100), t)
        if 'fcf' in m:
            require(math.isclose(c['fcfMargin'], m['fcf']['value'] / m['revenue']['value'] * 100), t)
        growth = c['revenueGrowth']
        require(growth is None or (finite(growth) and growth >= -100), (t, 'revenueGrowth range'))
        prior = c.get('growthPrior')
        if prior is not None:
            require(finite(prior['value']) and prior['value'] > 0, (t, 'growth prior revenue'))
            require(prior['currency'] == c['currency'], (t, 'growth prior currency'))
            old_start, old_end = (date.fromisoformat(prior['start']), date.fromisoformat(prior['end']))
            new_start, new_end = (date.fromisoformat(c['start']), date.fromisoformat(c['end']))
            require(old_start <= old_end < new_end, (t, 'growth prior dates'))
            require(all((351 <= (new - old).days <= 379 for new, old in [(new_start, old_start), (new_end, old_end)])), (t, 'growth comparable year'))
            require(abs((new_end - new_start).days - (old_end - old_start).days) < 10, (t, 'growth comparable duration'))
            require(finite(growth) and math.isclose(growth, 100 * (m['revenue']['value'] / prior['value'] - 1), rel_tol=1e-09, abs_tol=1e-08), (t, 'growth arithmetic'))
            require(all((x.get('filed', data['asOf']) <= data['asOf'] for x in prior.get('components', []))), (t, 'growth prior filing cutoff'))
        else:
            # Rounded reported growth and deliberate nulls use saved source inputs.
            source = manual.get(t)
            require(source is not None, (t, 'missing growth provenance'))
            require(all((c[key] == source[key] for key in ['start', 'end', 'basis', 'currency', 'revenueGrowth'])), (t, 'manual growth/source mismatch'))
        market = c['market']
        require(market['end'] <= data['asOf'] and market['start'] < market['end'], t)
        require(math.isclose(market['excess'], market['return1y'] - market['benchmarkReturn']), t)
        if market['boomComparable']:
            require('2023-01-01' <= market['boomStart'] <= '2023-01-10', t)
            require(math.isclose(market['boomExcess'], market['boomReturn'] - market['boomBenchmarkReturn']), t)
        history = market['history']
        require(isinstance(history, list) and len(history) >= 2, (t, 'market history length'))
        dates = [date.fromisoformat(point['date']) for point in history]
        require(all((a < b for a, b in zip(dates, dates[1:]))), (t, 'market history order'))
        require(history[0]['date'] == market['start'] and history[-1]['date'] == market['end'], (t, 'market history window'))
        for key, headline in [('stock', 'return1y'), ('benchmark', 'benchmarkReturn')]:
            require(all((finite(point[key]) and point[key] >= -100 for point in history)), (t, 'market history ' + key))
            require(history[0][key] == 0, (t, 'market history baseline'))
            require(finite(market[headline]) and math.isclose(history[-1][key], market[headline], rel_tol=0, abs_tol=0.005000001), (t, 'market history endpoint'))
        # Structural checks alone cannot catch plausible interior-point changes.
        require(market == prices.get(t), (t, 'market/source snapshot mismatch'))
        p = scenario['profiles'][t]
        require(len(p['scores']) == 3 and all((isinstance(n, int) and -3 <= n <= 3 for n in p['scores'])), t)
        require(len(p['scenarioNotes']) in [0, 3], t)
        require(p['mechanism'] and p['risk'] and p['watch'], t)
        require(all((s in scenario['sources'] for s in p['sources'])), t)
    for s in scenario['scenarios']:
        require(len(s['path']) == 5 and s['path'][0] == 100, "Validation failed: len(s['path']) == 5 and s['path'][0] == 100")
        require(all((t in tickers for t in s['winners'] + s['losers'] + s['hiddenPriority'])), "Validation failed: all((t in tickers for t in s['winners'] + s['losers'] + s['hiddenPriority']))")


def main():
    def read(name):
        return json.loads((ROOT/name).read_text())
    data = read('dist/data.json')
    validate_data(data, read('dist/scenarios.json'), read('scripts/manual_data.json'), read('scripts/market_data.json'))
    print(f"Validated {len(data['companies'])} companies, growth provenance, 300 scenario ratings, cash-flow arithmetic and matched market histories.")


if __name__ == '__main__':
    main()
