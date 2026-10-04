#!/usr/bin/env python3
"""Run the project's offline checks without fetching data or changing snapshots."""
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    if not shutil.which('node'):
        raise SystemExit('Node.js 22+ is required for JavaScript and PDF checks.')
    commands = [
        [sys.executable, 'scripts/validate_data.py'],
        [sys.executable, 'scripts/validate_valuation_source.py'],
        ['node', 'scripts/test_screen.cjs'],
        ['node', 'scripts/test_coverage.cjs'],
        ['node', 'scripts/test_universe.cjs'],
        *[['node', '--check', str(p.relative_to(ROOT))]
          for p in sorted((ROOT / 'dist').glob('*.js'))],
        ['node', 'scripts/qa_pdf.cjs'],
    ]
    for command in commands:
        print('+ ' + ' '.join(command), flush=True)
        subprocess.run(command, cwd=ROOT, check=True)
    print('All offline checks passed.')


if __name__ == '__main__':
    main()
