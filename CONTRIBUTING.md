# Contributing

Start with the local run instructions in [README.md](README.md). App changes need no bundler or package manager. Python 3.12+ and Node.js 22+ run the offline checks; FFmpeg verifies the films.

## A useful pull request

1. Explain the problem and the behavior after your change.
2. Keep changes focused. Use conventional commit prefixes such as `fix:`, `feat:` or `docs:`.
3. Run `python3 scripts/check.py`. Run `python3 scripts/film/verify.py` when changing media or film tooling.
4. For interface changes, inspect desktop and mobile layouts, keyboard navigation and reduced-motion behavior. For PDF layout changes, inspect rendered pages.
5. Include relevant screenshots or validation results in the pull request.

Use a pull request from your fork. Do not include credentials, `.env` files, private hosting configuration, downloaded raw financial caches or machine-specific paths.

## Research corrections

Link the issuer filing, release or other primary evidence. Include its publication date, the financial period, units, currency and the fields being corrected. Explain calculations and distinguish reported figures from your interpretation.

The current directory has **162 entities, including 132 public issuers**, while the unchanged financial snapshot covers **100 companies**. The remaining **32 public issuers await financial profiles**. The circulation map has **57 counterparties, 84 relationships and 17 cases**. Review [the coverage audit](docs/COVERAGE_AUDIT.md) before proposing additions; presence in the directory does not supply a missing financial profile or scenario rating.

Update the saved research input as well as the generated output. Preserve source URLs and missing-value semantics. Do not silently convert a dated snapshot into a mixture of old and new observations. A new research date requires coordinated financial, market, valuation, relationship and scenario review; see [Data and methodology](docs/DATA.md).

Scenario edits should explain the economic mechanism, counterargument and evidence that would change the assessment. Supply-chain participation alone does not prove a transaction between two named companies.

For directory changes, verify the legal issuer, current listing and ticker at the cutoff, aliases and parent identity. Keep listing status separate from research coverage. Do not count product aliases, historical tickers, ADRs or a subsidiary as an additional listed issuer; do not add a subsidiary's figures to its parent's consolidated accounts. Keep pending acquisitions distinct until completion is sourced. A newly listed company may lack the return history required by the hidden-candidate screen.

Record relationship changes in `scripts/research/circulation-coverage.json` and directory additions in the applicable `coverage-core.json`, `coverage-downstream.json` or `coverage-supplement.json` research input. Include source IDs, dates and limitations; preserve unknown amounts and distinguish commitments, funded investments, debt, recognized revenue, guarantees and non-cash incentives. Rebuild circulation before coverage. Financial expansion needs separately reviewed financial inputs, not copied or inferred metrics from an entity record.

## Reproducible saved research

These builders use committed inputs and require no network:

```sh
python3 scripts/build_circulation.py
python3 scripts/build_coverage.py
python3 scripts/build_scenarios.py
python3 scripts/normalize_valuation.py
git diff -- dist/circulation.json dist/coverage.json dist/scenarios.json dist/valuation.json
```

An unchanged input should reproduce an unchanged output. Fetching live inputs and rendering complete films are separate maintenance tasks, not routine prerequisites for contributing.

The committed films remain the original dated **43-counterparty / 59-relationship** edition. Do not silently relabel them with the expanded map's counts. A future film refresh should update its dated claims and undergo the media verification and visual review above.

Contribute only material you have the right to share. Preserve third-party notices and explain the source and license of any new dependency or media asset.
