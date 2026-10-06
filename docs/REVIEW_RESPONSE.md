# Adversarial review response — 6 October 2026

All seven reported mechanisms were reproduced. The fixes below address them without changing the saved 3 October research snapshot, its company ratings, or the 100 financial profiles. The existing data passes the stronger validation rules.

| Finding | Disposition | Fix and evidence |
| --- | --- | --- |
| 1. Zero money formatting | Confirmed; cosmetic for exact zero | Exact zero now renders as `$0` / `USD 0`. App and PDF formatters use base units below one thousand and reject non-finite inputs. The PDF formatter also previously erased small nonzero amounts by rounding everything below one billion to millions; regression cases cover zero, negative zero, small values, negatives, missing values and large units. |
| 2. Source-link schemes | Confirmed; defensive hardening | Company, market, valuation, scenario, circulation and directory source links share an absolute HTTP(S) URL allowlist. Invalid references are inert text or omitted from the directory's link list. PDF annotations use the same allowlist. Tests feed JavaScript, data, file, mail, relative, malformed and control-character URLs into the production functions and inspect serialized PDF annotations. All committed source URLs pass. |
| 3. FCF currency | Confirmed validation gap | FCF yield now requires matching reporting and quoted-share currency, an annual FY/TTM duration, exact correspondence to the saved financial period/value and valid arithmetic. The normalizer validates before replacing its output. A rejected input leaves the previous output untouched. Legitimate negative yields remain valid. |
| 4. Revenue growth | Confirmed validation gap | Finite values and the −100% lower bound are checked. The 77 derived records must match prior-period revenue arithmetic, currency and comparable dates. The 21 manually sourced values and two deliberate nulls must match their saved source inputs. Quarterly and half-year growth are preserved. |
| 5. Chart history | Confirmed validation gap | Histories require ordered valid dates, matching window endpoints, zero starting returns, finite values and agreement with headline returns within the saved two-decimal precision. Embedded histories must also match the saved market input. Valid 50-, 51- and 52-point histories all pass. |
| 6. PDF tests | Confirmed test gap | Tests load the actual application formatters. They validate report sections/row counts, then extract the serialized PDF's headings, representative financial amounts and source annotations. Independent input fixtures also verify case explanations and limitations, valuation methodology, scenario summaries and risks, and company definitions. All five report types are checked. Empty report bodies are rejected; a legitimate empty filter exports an explicit explanation. |
| 7. Optimized Python | Confirmed robustness gap | Both production validators now raise explicit validation errors instead of relying on `assert`. Mutation tests exercise normal Python, `-O`, and `PYTHONOPTIMIZE=1`. |

## Qualifications and pushback

- `$0K` still mathematically means zero; it is confusing presentation, not proof that the stored debt was nonzero. Small nonzero PDF amounts being rounded away was a separate, more concrete formatting defect.
- The existing valuation builder already restricted FCF yields to compatible currencies and annual periods. The missing validator checks did not establish that current yields were wrong.
- Current GitHub CI runs ordinary Python. Assertion stripping was a risk for optimized environments, not evidence that CI had been skipping validation. Explicit `-O` on a parent process is also distinct from the inherited `PYTHONOPTIMIZE` environment variable.
- Comparing output with saved research inputs catches corruption and drift; it cannot independently establish the accuracy of every source publication or catch a coordinated incorrect edit to both. Human review of source evidence remains necessary.
- PDF text/annotation checks strengthen content verification but do not replace visual inspection after layout changes. The extractor deliberately supports the current renderer's ASCII text operators; it is not a general PDF parser.
- No live financial refresh or blanket certification of all company facts was performed. Reporting dates, market closes and research limitations remain visible.

## Verification

`python3 scripts/check.py` runs the data and valuation validators, corruption/optimization tests, display and link-safety cases, existing screen/directory/spatial tests, JavaScript syntax checks and all five PDF content/annotation checks. The four saved-data builders must still reproduce the committed JSON exactly. The app's zero-debt display and browser PDF action were also exercised in the local preview.
