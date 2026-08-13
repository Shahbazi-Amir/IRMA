# Historical market intelligence V2

IRMA stores historical series only after a verified official export is downloaded, hashed,
validated and imported. The canonical path is `source file → historical_import → normalized DB
→ historical_intelligence → API → UI`. No sample or fixture is labelled as real data.

The initial source audit identified the Central Bank's official advanced exchange-rate export,
official inflation pages and official policy-rate publication. TSETMC remains the intended
official exchange source for the Tehran market index. Housing must retain its geography: Tehran
statistics cannot be presented as national housing data. An interbank rate is not a retail bank
deposit rate and is therefore not silently substituted.

Current coverage is deliberately zero in `data/manifests/historical_sources.json`: this Agent
environment did not obtain authoritative machine-readable exports with stable contracts for all
domains. The importer is ready for UTF-8 CSV files with `observation_date,value` and optional
`publication_date`. Every import records source identity, retrieval time, observation date,
publication date, unit, frequency, geography, SHA-256, quality and exact row count.

Recommended operator workflow:

1. Download the official export without editing it.
2. Record its official URL, release/version and SHA-256 in the manifest.
3. Convert with a documented reproducible script to the canonical CSV contract.
4. Run the importer twice; the second run must write zero logical observations.
5. Verify coverage and frequency before enabling the dataset in the UI.

The analytics layer supports total return, maximum drawdown and rolling-window distributions
(median, quartiles, best/worst and positive-window ratio). Frequency must be supplied explicitly;
monthly housing observations must never be treated as daily prices. All output carries the notice
that historical evidence is neither a forecast nor a guaranteed return.

## Current V2 data audit

The repository contains providers and import contracts, but no committed production database.
A fresh/offline installation therefore has this inventory. Runtime gating can enable only an
asset and horizon backed by sufficient verified observations.

| Asset | Configured source path | Fresh coverage | Frequency | 1w | 1m | 3m | 6m | 1y | Numeric scenario |
|---|---|---:|---|---|---|---|---|---|---|
| Fixed-income funds | FIPIRAN catalogue/NAV provider | 0 | daily when fetched | withheld | withheld | withheld | withheld | withheld | after fresh sufficient NAV history |
| Gold funds | FIPIRAN catalogue/NAV provider | 0 | daily when fetched | withheld | withheld | withheld | withheld | withheld | after fresh sufficient NAV history |
| Equity/index funds | FIPIRAN catalogue/NAV provider | 0 | daily when fetched | withheld | withheld | withheld | withheld | withheld | after fresh sufficient NAV history |
| Gold | verified historical CSV contract; source pending | 0 | unknown | withheld | withheld | withheld | withheld | withheld | no |
| FX | CBI official candidate; free-market series separate and pending | 0 | unknown | withheld | withheld | withheld | withheld | withheld | no |
| Stock index | TSETMC official candidate | 0 | unknown | withheld | withheld | withheld | withheld | withheld | no |
| Inflation | CBI official candidate | 0 | monthly when imported | n/a | withheld | withheld | withheld | withheld | no |
| Housing | authoritative index source pending | 0 | unknown | n/a | withheld | withheld | withheld | withheld | no |
| Bank deposit | official product/rate import; verified current rate absent | 0 | contractual | withheld | withheld | withheld | withheld | withheld | no |

No row authorizes a return number on a fresh installation. The comparison service withholds
numbers until provenance, identity, unit, quality, freshness, frequency and minimum history pass.
