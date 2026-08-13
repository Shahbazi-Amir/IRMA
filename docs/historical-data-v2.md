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
