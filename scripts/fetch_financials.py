"""Cache SEC inputs for the fixed snapshot; network access needs SEC_USER_AGENT."""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from research_cache import (ROOT, atomic_write, cache_path, read_json,
                            require_sec_cache, sec_user_agent, snapshot_ciks, validate_facts)
from roster import ROSTER

TICKERS_URL = 'https://www.sec.gov/files/company_tickers.json'
_request_lock = threading.Lock()
_last_request = 0.0


def download_json(url: str):
    """Throttle all workers together; cache only complete, parseable responses."""
    global _last_request
    agent = sec_user_agent()
    for attempt in range(3):
        with _request_lock:
            time.sleep(max(0, .20 - (time.monotonic() - _last_request)))
            _last_request = time.monotonic()
        try:
            request = urllib.request.Request(url, headers={'User-Agent': agent, 'Accept': 'application/json'})
            with urllib.request.urlopen(request, timeout=45) as response:
                return json.load(response)
        except (OSError, ValueError, urllib.error.URLError):
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=Path, help='SEC cache; default AI_MONEY_MAP_SEC_CACHE or .cache/sec')
    parser.add_argument('--ticker-map', type=Path, help='SEC company_tickers.json; defaults to CACHE/company_tickers.json')
    parser.add_argument('--offline', action='store_true', help='Validate/reuse saved inputs only; never access the network')
    args = parser.parse_args()
    cache = cache_path('sec', args.cache)
    ticker_path = args.ticker_map.expanduser().resolve() if args.ticker_map else cache / 'company_tickers.json'
    lookup = {}
    if ticker_path.exists():
        tickers = read_json(ticker_path)
    elif args.offline:
        tickers = {}  # The published snapshot already preserves all expected SEC CIKs.
    else:
        tickers = download_json(TICKERS_URL)
        if not isinstance(tickers, dict) or not all(isinstance(v, dict) and 'ticker' in v and 'cik_str' in v for v in tickers.values()):
            raise ValueError('SEC ticker bootstrap returned an invalid mapping; cache was not changed.')
        atomic_write(ticker_path, json.dumps(tickers, separators=(',', ':')))
    if not isinstance(tickers, dict):
        raise ValueError(f'Invalid SEC ticker mapping: {ticker_path}')
    for row in tickers.values():
        lookup[row['ticker']] = int(row['cik_str'])
    # Fixed-snapshot identities win over any later listing/ticker changes.
    lookup.update(snapshot_ciks(ROOT))
    if not args.offline and any(c['ticker'] in lookup and not (cache/(c['ticker']+'.json')).exists() for c in ROSTER):
        sec_user_agent()  # Fail before workers start if operator contact is absent.

    def fetch(company):
        ticker = company['ticker']
        cik = lookup.get(ticker)
        if not cik:
            return ticker, 'non-SEC', False
        path = cache/(ticker+'.json')
        try:
            if path.exists():
                facts = read_json(path)
            elif args.offline:
                return ticker, 'missing (offline)', True
            else:
                facts = download_json(f'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json')
                validate_facts(facts, ticker, cik)
                atomic_write(path, json.dumps(facts, separators=(',', ':')))
            validate_facts(facts, ticker, cik)
            return ticker, facts.get('entityName', 'valid cached facts'), False
        except (OSError, ValueError, KeyError, urllib.error.URLError) as exc:
            return ticker, f'failed: {exc}', True

    failures = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        for ticker, status, failed in pool.map(fetch, ROSTER):
            print(ticker, status, flush=True)
            if failed:
                failures.append(ticker)
    if failures:
        raise ValueError('SEC inputs incomplete: '+', '.join(failures)+'. Published outputs were not changed.')
    require_sec_cache(cache)
    print(f'Complete SEC cache: {cache}. Snapshot dates remain fixed at 2026-10-03.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, urllib.error.URLError) as exc:
        raise SystemExit(str(exc)) from exc
