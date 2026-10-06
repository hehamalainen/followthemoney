#!/usr/bin/env python3
"""Validate financial safety invariants and independently checked issuer examples."""
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

def validate_valuation_source(d, financial):
    rows = {r['ticker']: r for r in d['companies']}
    require(len(d['companies']) == len(rows) == len(financial) == 100, "Validation failed: len(d['companies']) == len(rows) == len(financial) == 100")
    require(set(rows) == set(financial), 'Validation failed: set(rows) == set(financial)')
    for t, r in rows.items():
        for name in ('grossDebt', 'cash', 'marketCap', 'financeLeases'):
            require(r[name] is None or (math.isfinite(r[name]) and r[name] >= 0), (t, name))
        if r['grossDebt'] is not None:
            p = r['components']['grossDebt']
            require(len({x['tag'] for x in p}) == len(p), t)
            require({x['end'] for x in p} == {r['debtDate']}, t)
            require({x['currency'] for x in p} == {r['currency']}, t)
            require(math.isclose(sum((x['val'] for x in p)), r['grossDebt'], abs_tol=0.01), t)
        if r['netDebt'] is not None:
            require(r['debtDate'] == r['cashDate'] == r['balanceDate'], t)
            require(math.isclose(r['grossDebt'] - r['cash'], r['netDebt'], abs_tol=0.01), t)
        if r['marketCap'] is not None:
            require(r['sharesDate'] <= r['priceDate'], t)
            require(math.isclose(r['marketCap'], r['shares'] * r['price']), t)
        if r['pe'] is not None:
            e = r['earnings']
            require(e['basis'] in ('FY', 'TTM') and e['value'] > 0, t)
            require(e['currency'] == r['currency'], t)
            require(math.isclose(sum((x['val'] * x['sign'] for x in e['components'])), e['value'], abs_tol=1e-06), t)
            require(math.isclose(r['pe'], r['price'] / e['value']), t)
        if r['fcfYield'] is not None:
            f = r['fcfPeriod']
            require(f['basis'] in ('FY', 'TTM'), t)
            company = financial[t]
            require(finite(r['fcfYield']) and finite(r['marketCap']) and (r['marketCap'] > 0), (t, 'FCF yield inputs'))
            require(finite(f['value']), (t, 'FCF amount'))
            require(f['currency'] == r['currency'] == company['currency'] == company['market']['currency'], (t, 'FCF yield currency'))
            start, end = (date.fromisoformat(f['start']), date.fromisoformat(f['end']))
            require(350 <= (end - start).days + 1 <= 378 and end <= date.fromisoformat(d['asOf']), (t, 'annual FCF period'))
            metric = company['metrics'].get('fcf')
            require(metric is not None and all((f[key] == metric[key] for key in ['start', 'end', 'currency', 'value'])) and (f['basis'] == company['basis']), (t, 'FCF/source snapshot mismatch'))
            require(math.isclose(r['fcfYield'], 100 * f['value'] / r['marketCap']), t)
        if r['totalDebtIncludingFinanceLeases'] is not None:
            require(r['debtIncludesLeases'] is False, t)
            require({x['end'] for x in r['components']['financeLeases']} == {r['debtDate']}, t)
            require(math.isclose(r['totalDebtIncludingFinanceLeases'], r['grossDebt'] + r['financeLeases']), t)
        if r['leaseAdjustedNetDebt'] is not None:
            require(r['debtDate'] == r['cashDate'], t)
            require(math.isclose(r['leaseAdjustedNetDebt'], r['totalDebtIncludingFinanceLeases'] - r['cash']), t)
        for parts in r['components'].values():
            require(all((p['filed'] <= d['asOf'] and p['end'] <= d['asOf'] for p in parts)), t)
            require(all((p['source'].startswith('https://') for p in parts)), t)
    # Independent figures checked against the linked consolidated statements.
    for t, expected in {'MSFT': 40294000000, 'AMZN': 132549000000, 'IBM': 61987000000, 'AMAT': 6544000000, 'NOW': 7517000000, 'WDAY': 2989000000, 'NVDA': 33366000000, 'CRWV': 35068000000, 'ORCL': 125337000000, 'NBIS': 8545700000}.items():
        require(rows[t]['grossDebt'] == expected, (t, rows[t]['grossDebt'], expected))
    require(rows['MSFT']['financeLeases'] == 66594000000, "Validation failed: rows['MSFT']['financeLeases'] == 66594000000")
    require(rows['MSFT']['totalDebtIncludingFinanceLeases'] == 106888000000, "Validation failed: rows['MSFT']['totalDebtIncludingFinanceLeases'] == 106888000000")
    require(rows['MSFT']['leaseAdjustedNetDebt'] == 85953000000, "Validation failed: rows['MSFT']['leaseAdjustedNetDebt'] == 85953000000")
    require(rows['APH']['shares'] == 2465966914, "Validation failed: rows['APH']['shares'] == 2465966914")
    require(rows['PATH']['shares'] == 521155409, "Validation failed: rows['PATH']['shares'] == 521155409")
    require(rows['WDAY']['shares'] == 241000000, "Validation failed: rows['WDAY']['shares'] == 241000000")
    require(rows['TSM']['marketCap'] is None and rows['TSM']['pe'] is None, "Validation failed: rows['TSM']['marketCap'] is None and rows['TSM']['pe'] is None")
    require(rows['ASML']['marketCap'] is None and rows['ASML']['fcfYield'] is None, "Validation failed: rows['ASML']['marketCap'] is None and rows['ASML']['fcfYield'] is None")
    require(rows['BE']['fcfYield'] is None, "Validation failed: rows['BE']['fcfYield'] is None")
    require(rows['MDB']['grossDebt'] == 0 and rows['MDB']['financeLeases'] == 26418000, "Validation failed: rows['MDB']['grossDebt'] == 0 and rows['MDB']['financeLeases'] == 26418000")
    for t in ['SNPS', 'TEL', 'NOW', 'CRM', 'ADBE', 'MDB', 'WDAY', 'PATH']:
        require(all((rows[t][k] is not None for k in ['marketCap', 'pe', 'fcfYield', 'grossDebt', 'cash', 'netDebt'])), t)


def main():
    data = json.loads((ROOT/'scripts/research/valuation-source.json').read_text())
    financial = json.loads((ROOT/'dist/data.json').read_text())
    validate_valuation_source(data, {c['ticker']: c for c in financial['companies']})
    print('PASS: 100 records; currencies/periods/source arithmetic; debt components; issuer cross-checks; validation active under optimized Python.')


if __name__ == '__main__':
    main()
