"""Cache price inputs and rebuild only the fixed 2 October 2026 market snapshot."""
from __future__ import annotations

import argparse
import concurrent.futures
import datetime
import json
import math
import time
import urllib.parse
import urllib.request
from pathlib import Path

from research_cache import ROOT, atomic_write, cache_path, read_json
from roster import ROSTER

PRICE_DATE = '2026-10-02'
PERIOD_START = datetime.datetime(2021, 10, 2, tzinfo=datetime.timezone.utc)
PERIOD_END = datetime.datetime(2026, 10, 3, tzinfo=datetime.timezone.utc)


# Compare listed shares with a price index in the same trading currency.
# US ADRs use USD / S&P 500.
def benchmark(t):
    if t.endswith('.KS'): return '^KS11', 'KOSPI'
    if t.endswith('.TW'): return '^TWII', 'Taiwan Weighted'
    if t.endswith('.PA') or t.endswith('.DE'): return '^STOXX50E', 'EURO STOXX 50'
    if t.endswith('.SW'): return '^SSMI', 'Swiss Market Index'
    return '^GSPC', 'S&P 500'


def parse_prices(data):
    row = data['chart']['result'][0]
    closes = row['indicators']['quote'][0]['close']
    points = {}
    for ts, price in zip(row['timestamp'], closes):
        day = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).date().isoformat()
        if price is not None and math.isfinite(price) and price > 0 and day <= PRICE_DATE:
            points[day] = price
    if not points or not row['meta'].get('currency'):
        raise ValueError('No valid prices/currency at the fixed snapshot date')
    return dict(points=points, currency=row['meta']['currency'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=Path, help='Price cache; default AI_MONEY_MAP_PRICE_CACHE or .cache/prices')
    parser.add_argument('--offline', action='store_true', help='Use cached responses only; never access the network')
    parser.add_argument('--output', type=Path, default=ROOT/'scripts/market_data.json')
    args = parser.parse_args()
    cache = cache_path('prices', args.cache)
    previous = read_json(args.output) if args.output.exists() else {}

    def fetch(ticker):
        path = cache/(ticker+'.json')
        try:
            if path.exists():
                data = read_json(path)
            elif args.offline:
                return ticker, None
            else:
                query = urllib.parse.urlencode({'period1': int(PERIOD_START.timestamp()),
                                               'period2': int(PERIOD_END.timestamp()), 'interval': '1d'})
                url = 'https://query1.finance.yahoo.com/v8/finance/chart/'+urllib.parse.quote(ticker, safe='')+'?'+query
                data = None
                for attempt in range(2):
                    try:
                        request = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                        with urllib.request.urlopen(request, timeout=30) as response:
                            data = json.load(response)
                        parse_prices(data)  # Do not replace a cache with an error payload.
                        break
                    except (OSError, ValueError, KeyError, IndexError, TypeError):
                        if attempt:
                            raise
                        time.sleep(1)
                atomic_write(path, json.dumps(data, separators=(',', ':')))
            time.sleep(.2)
            return ticker, parse_prices(data)
        except (OSError, ValueError, KeyError, IndexError, TypeError) as exc:
            print(f'{ticker}: invalid/unavailable price input ({exc})', flush=True)
            return ticker, None

    symbols = [c['ticker'] for c in ROSTER]+sorted({benchmark(c['ticker'])[0] for c in ROSTER})
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        raw = dict(pool.map(fetch, symbols))
    result = {}
    for company in ROSTER:
        ticker = company['ticker']; row = raw[ticker]
        benchmark_ticker, benchmark_name = benchmark(ticker); bench = raw[benchmark_ticker]
        if not row or not bench:
            print('Missing', ticker); continue
        common = sorted(set(row['points']) & set(bench['points']))
        if not common:
            print('No common trading dates', ticker); continue
        end = common[-1]
        if end < previous.get(ticker, {}).get('end', end):
            print('Input ends before the saved snapshot', ticker); continue
        target = (datetime.date.fromisoformat(end)-datetime.timedelta(days=365)).isoformat()
        starts = [day for day in common if day <= target]
        if not starts:
            print('Short history', ticker); continue
        boom_dates = [day for day in common if day >= '2023-01-01']
        boom_start = boom_dates[0] if boom_dates else None
        boom_ok = bool(boom_start and boom_start <= '2023-01-10' and ticker not in ['NBIS','WDC','J'])
        boom_return = (row['points'][end]/row['points'][boom_start]-1)*100 if boom_start else None
        boom_benchmark = (bench['points'][end]/bench['points'][boom_start]-1)*100 if boom_start else None
        start = starts[-1]
        sr = (row['points'][end]/row['points'][start]-1)*100
        br = (bench['points'][end]/bench['points'][start]-1)*100
        points = [dict(date=day, stock=round((row['points'][day]/row['points'][start]-1)*100,2),
                       benchmark=round((bench['points'][day]/bench['points'][start]-1)*100,2))
                  for day in common if day >= start]
        result[ticker] = dict(boomStart=boom_start, boomReturn=boom_return, boomBenchmarkReturn=boom_benchmark,
          boomExcess=boom_return-boom_benchmark if boom_start else None, boomComparable=boom_ok,
          boomNote=('Comparable price window from the first common trading day of 2023.' if boom_ok else
                    'Not used in the strict boom screen: listing history, restructuring or a major spin-off limits comparability.'),
          start=start,end=end,close=row['points'][end],currency=row['currency'],return1y=sr,benchmarkReturn=br,
          excess=sr-br,benchmark=benchmark_name,benchmarkTicker=benchmark_ticker,
          history=points[::5]+([points[-1]] if points[-1] not in points[::5] else []),
          source='https://finance.yahoo.com/quote/'+urllib.parse.quote(ticker,safe='')+'/history/',
          benchmarkSource='https://finance.yahoo.com/quote/'+urllib.parse.quote(benchmark_ticker,safe='')+'/history/',
          definition='Close-to-close price return, split-adjusted by source; excludes dividends. Same trading dates and listing currency for stock and benchmark.')
    if len(result) != len(ROSTER):
        raise ValueError('Incomplete price inputs; previous market snapshot preserved.')
    atomic_write(args.output, json.dumps(result, separators=(',', ':')))
    print('Price coverage', len(result), 'of', len(ROSTER), 'through', PRICE_DATE)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
