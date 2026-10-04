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

Update the saved research input as well as the generated output. Preserve source URLs and missing-value semantics. Do not silently convert a dated snapshot into a mixture of old and new observations. A new research date requires coordinated financial, market, valuation, relationship and scenario review; see [Data and methodology](docs/DATA.md).

Scenario edits should explain the economic mechanism, counterargument and evidence that would change the assessment. Supply-chain participation alone does not prove a transaction between two named companies.

## Reproducible saved research

These builders use committed inputs and require no network:

```sh
python3 scripts/build_circulation.py
python3 scripts/build_scenarios.py
python3 scripts/normalize_valuation.py
git diff -- dist/circulation.json dist/scenarios.json dist/valuation.json
```

An unchanged input should reproduce an unchanged output. Fetching live inputs and rendering complete films are separate maintenance tasks, not routine prerequisites for contributing.

Contribute only material you have the right to share. Preserve third-party notices and explain the source and license of any new dependency or media asset.
