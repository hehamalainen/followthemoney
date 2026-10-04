# Data and methodology

The saved application is a research snapshot dated **3 October 2026**, with market closes dated **2 October 2026**. It is usable offline after loading its local assets. It does not automatically update when a filing or share price changes.

## Universe and financials

The universe contains 100 selected public companies across nine sectors. Selection balances major AI buyers with chip, equipment, networking, energy, cooling, construction and software suppliers. It is neither a market-cap ranking nor proof of AI revenue exposure.

`dist/data.json` preserves source URLs, reporting periods, currencies, SEC formula components, missing fields and issuer-specific FCF definitions. Most SEC records use trailing twelve months: latest fiscal year plus current year-to-date minus comparable prior year-to-date. When unavailable, the latest usable annual period is retained. Other releases may use a quarter or half-year, explicitly labeled.

Net income measures company accounting profit. FCF generally means operating cash flow less cash capital expenditure; company-reported alternatives are labeled. These figures describe the whole company, not separately disclosed AI profit. Negative FCF may reflect expansion spending.

## Stock recognition and scenarios

The strict hidden-candidate screen requires all of:

- Scenario business advantage of at least +2 on an ordinal −3 to +3 scale.
- Revenue growth of at least 10%, positive net income and positive FCF.
- A financial period ending within 180 days of the research date.
- Price underperformance against the selected regional index both over one year and since the first common trading day in early 2023.

The alternative recent-laggard window uses one year only. Returns exclude dividends. US-listed foreign shares use a US benchmark. Missing history, listing changes and selected restructuring/spin-off cases prevent a strict comparison. Passing a screen does not establish undervaluation, market ignorance or suitability.

`dist/scenarios.json` contains three conditional futures and a rating for every company in each future. Each company has a mechanism, counterargument and evidence to monitor. More than 30 priority companies have distinct scenario narratives. Scores are authored relative business-position judgments; they are not probabilities or projected share returns. Spending paths are illustrative assumptions. The Universe timeline interpolates these assumptions; it does not reveal future cash flows.

## Money circulation

`dist/circulation.json` contains 43 counterparties, 59 sourced relationships and 11 cases. The named model labs and other private counterparties are outside the 100-public-company universe.

Relationships distinguish funded investments, announced commitments, commercial transactions, recognized revenue, guarantees, facilities, non-cash incentives and supplier relationships. Their dates, status and source links matter. A purchase commitment is not cash already paid; a guarantee is contingent support; non-cash shares are not cash receipts. The graph does not prove that identical dollars return to their origin or calculate a consolidated circular-money total.

Graph geometry, link width, node size and animation are illustrative. Companies without documented relationships do not receive invented transaction links.

## Valuation and borrowing

`scripts/research/valuation-source.json` holds calculation provenance; `dist/valuation.json` is the app's normalized view. Verified saved coverage includes:

| Metric | Companies |
| --- | ---: |
| Equity-value estimate | 66 |
| Diluted P/E | 63 |
| Annual/TTM FCF yield | 60 |
| Gross borrowing balance | 68 |
| Matched-date cash-only net debt | 64 |

Unresolved ADR, share-class and currency combinations are withheld. Equity values combine a dated share count with a dated price and are estimates. P/E and FCF yield use the labeled earnings/cash-flow periods. A quarterly figure is not simply annualized. Negative or unavailable earnings may make a multiple unavailable.

Net debt requires borrowing and cash from the same balance date. Finance leases appear separately where possible; some issuer definitions already include them, and the inclusion flags are retained. Cash-only net debt excludes investments unless the displayed definition explicitly says otherwise. Missing values are not zero. These metrics do not establish fair value or model every debt maturity.

## Rebuilding committed inputs

These commands need Python only and make no network requests:

```sh
python3 scripts/build_circulation.py
python3 scripts/build_scenarios.py
python3 scripts/normalize_valuation.py
python3 scripts/check.py
```

The final check command also requires Node.js. `build_circulation.py` uses the saved circulation research. `build_scenarios.py` authors scenario content. `normalize_valuation.py` converts the saved valuation source into the app format. All three should reproduce the committed outputs when their inputs are unchanged.

## Financial input caches and network fetching

The SEC facts and raw market downloads are not committed. Their defaults are `.cache/sec` and `.cache/prices`, ignored by Git. Override them with `AI_MONEY_MAP_SEC_CACHE` and `AI_MONEY_MAP_PRICE_CACHE` respectively. The saved app does not need these caches.

`fetch_financials.py` bootstraps the SEC ticker map and retrieves company facts. Network fetching requires a descriptive `SEC_USER_AGENT` containing your own contact information. Set it in your shell environment, then run:

```sh
python3 scripts/fetch_financials.py
```

Use `--help` for cache and ticker-map options. `fetch_prices.py` retrieves price history from the provider referenced in the saved market data. Use these fetchers only under the source's access and usage terms. Fetching today does not guarantee reconstruction of historical inputs exactly as originally downloaded.

With the required reviewed caches present:

```sh
python3 scripts/build_data.py
python3 scripts/build_valuation.py --site . --output scripts/research/valuation-source.json
python3 scripts/normalize_valuation.py
python3 scripts/check.py
```

Financial builders check for missing or invalid SEC inputs before replacing saved output. Source caches, manual overrides and prices must still be reviewed for semantic completeness. A cache passing structural validation is not evidence that every financial tag is correctly interpreted.

## Updating the research date

1. Choose a new common research date and market cutoff; update the corresponding builder constants deliberately.
2. Refresh SEC facts and prices and review non-SEC issuer releases in `scripts/manual_data.json` and `scripts/write_manual.py`.
3. Recheck share counts, splits, ADR conversions, financial periods, debt definitions and currency matching.
4. Update circulation research with primary evidence, distinguishing changed commitments from completed transactions.
5. Reassess scenarios, mechanisms, counterarguments and the screen's freshness rules.
6. Rebuild, validate, inspect changes and regenerate reports or films if their dated content changes.

Keep observed data separate from authored interpretation. Preserve source links rather than copying full publications into the repository. The project license does not grant rights to external data providers or linked research; see [Third-party notices](../THIRD_PARTY_NOTICES.md).
