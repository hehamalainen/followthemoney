"""Mutations that previously passed the publication gates must fail."""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from validate_data import validate_data
from validate_valuation_source import validate_valuation_source

ROOT = Path(__file__).resolve().parents[1]
def read(path):
    return json.loads((ROOT/path).read_text())
DATA = read('dist/data.json')
SCENARIOS = read('dist/scenarios.json')
MANUAL = read('scripts/manual_data.json')
PRICES = read('scripts/market_data.json')
VALUATION = read('scripts/research/valuation-source.json')
FINANCIAL = {c['ticker']: c for c in DATA['companies']}

class ValidationTests(unittest.TestCase):
    def test_saved_snapshot_including_nulls_negative_yields_and_calendars(self):
        validate_data(DATA, SCENARIOS, MANUAL, PRICES)
        validate_valuation_source(VALUATION, FINANCIAL)
        self.assertEqual({len(c['market']['history']) for c in DATA['companies']}, {50,51,52})
        self.assertTrue(any(r['fcfYield'] is not None and r['fcfYield'] < 0 for r in VALUATION['companies']))

    def test_growth_mutations(self):
        mutations = [
            lambda c: c.update(revenueGrowth=-999),
            lambda c: c.update(revenueGrowth=float('nan')),
            lambda c: c.update(revenueGrowth=c['revenueGrowth']+1),
            lambda c: c['growthPrior'].update(currency='EUR'),
            lambda c: c['growthPrior'].update(start='2025-01-01'),
            lambda c: c['growthPrior'].update(value=0),
            lambda c: c.update(growthPrior=None),
        ]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                data=copy.deepcopy(DATA); company=next(c for c in data['companies'] if c['ticker']=='MSFT'); mutate(company)
                with self.assertRaises(ValueError): validate_data(data,SCENARIOS,MANUAL,PRICES)
        for ticker in ['NBIS','SU.PA']:
            data=copy.deepcopy(DATA);next(c for c in data['companies'] if c['ticker']==ticker)['revenueGrowth']=12
            with self.assertRaisesRegex(ValueError,'manual growth'): validate_data(data,SCENARIOS,MANUAL,PRICES)

    def test_market_history_mutations(self):
        mutations=[
            lambda h: h.clear(), lambda h: h.reverse(),
            lambda h: h[1].update(date=h[0]['date']),
            lambda h: h[1].update(date='not-a-date'),
            lambda h: h[1].update(stock=float('nan')),
            lambda h: h[0].update(stock=999999,benchmark=-999999),
            lambda h: h[-1].update(stock=999999),
            lambda h: h[4].update(stock=h[4]['stock']+1),
        ]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                data=copy.deepcopy(DATA); mutate(data['companies'][0]['market']['history'])
                with self.assertRaises(ValueError): validate_data(data,SCENARIOS,MANUAL,PRICES)

    def test_fcf_currency_period_and_source_mutations(self):
        mutations=[
            lambda r: r['fcfPeriod'].update(currency='EUR'),
            lambda r: r['fcfPeriod'].update(start='2026-04-01'),
            lambda r: r['fcfPeriod'].update(basis='Quarter'),
            lambda r: r['fcfPeriod'].update(value=r['fcfPeriod']['value']+1000),
            lambda r: r.update(fcfYield=float('nan')),
            lambda r: r.update(marketCap=0),
        ]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                data=copy.deepcopy(VALUATION); mutate(next(r for r in data['companies'] if r['ticker']=='MSFT'))
                with self.assertRaises(ValueError): validate_valuation_source(data,FINANCIAL)
        financial=copy.deepcopy(FINANCIAL); financial['MSFT']['market']['currency']='EUR'
        with self.assertRaisesRegex(ValueError,'FCF yield currency'): validate_valuation_source(VALUATION,financial)

    def test_cli_rejects_corruption_even_when_optimized(self):
        with tempfile.TemporaryDirectory(prefix='money-map-validation-') as directory:
            base=Path(directory)
            for file in ['scripts/validate_data.py','scripts/validate_valuation_source.py','scripts/normalize_valuation.py',
                         'scripts/manual_data.json','scripts/market_data.json','dist/scenarios.json']:
                (base/file).parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/file,base/file)
            (base/'scripts/research').mkdir()
            invalid=copy.deepcopy(DATA);invalid['companies']=[]
            (base/'dist/data.json').write_text(json.dumps(invalid))
            debt=copy.deepcopy(VALUATION);debt['companies'][0]['grossDebt']=-1
            (base/'scripts/research/valuation-source.json').write_text(json.dumps(debt))
            for args,extra in [([],{}),(['-O'],{}),([],{"PYTHONOPTIMIZE":"1"})]:
                for script in ['validate_data.py','validate_valuation_source.py']:
                    # Valuation test gets an intact company universe and invalid debt.
                    (base/'dist/data.json').write_text(json.dumps(DATA if script.startswith('validate_valuation') else invalid))
                    env=os.environ.copy();env.pop('PYTHONOPTIMIZE',None);env.update(extra)
                    result=subprocess.run([sys.executable,*args,str(base/'scripts'/script)],env=env,capture_output=True,text=True)
                    self.assertNotEqual(result.returncode,0,(script,args,extra))
                    self.assertIn('ValueError',result.stderr)
            # The normalizer must reject unsafe input before overwriting saved output.
            (base/'dist/data.json').write_text(json.dumps(DATA))
            wrong=copy.deepcopy(VALUATION);next(r for r in wrong['companies'] if r['ticker']=='MSFT')['fcfPeriod']['currency']='EUR'
            (base/'scripts/research/valuation-source.json').write_text(json.dumps(wrong))
            (base/'dist/valuation.json').write_text('preserve existing output')
            result=subprocess.run([sys.executable,str(base/'scripts/normalize_valuation.py')],capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            self.assertEqual((base/'dist/valuation.json').read_text(),'preserve existing output')

if __name__=='__main__':
    unittest.main()
