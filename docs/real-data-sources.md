# Real historical data source catalogue

Validated on 2026-08-13 from the agent runner. `Fixture used: false`.

## Funds — FIPIRAN

- Authority: Financial Information Processing of Iran, Tehran Securities Exchange Technology Management.
- Access: `POST https://www.fipiran.com/services/fund/fundcompare/` and `GET .../chart/getfundchart`.
- Status: **BLOCKED** in this runner.
- Evidence: bounded catalogue request returned HTTP 502 from `mitmproxy` with `Connection refused`.
- Quality: authoritative provider contract already implemented; no live record was ingested.
- Limitation: this runner result does not prove FIPIRAN is globally unavailable. Use the documented live validation command from an Iran-accessible host.

## Consumer inflation — Iran

- Authority: IMF International Financial Statistics; distributed by World Bank WDI.
- Exact source: indicator `FP.CPI.TOTL.ZG`, Iran (`IRN`), World Bank API.
- Access: `http://api.worldbank.org/v2/country/IRN/indicator/FP.CPI.TOTL.ZG?format=json&per_page=1000`.
- Observed coverage: 1960–2025, 66 non-null annual observations.
- Frequency/unit/geography: annual CPI percentage change; percent; Iran.
- License: World Bank page reports CC BY 4.0.
- Status: **VERIFIED_AND_INGESTED** into a disposable SQLite validation DB.
- Limitation: annual inflation is not a monthly CPI level and cannot support 1-week to 6-month real-return alignment.

## Official exchange rate — Iran

- Authority: IMF International Financial Statistics; distributed by World Bank WDI.
- Exact source: indicator `PA.NUS.FCRF`, Iran (`IRN`), World Bank API.
- Access: `http://api.worldbank.org/v2/country/IRN/indicator/PA.NUS.FCRF?format=json&per_page=1000`.
- Observed coverage: 1960–2023, 64 non-null annual observations.
- Frequency/unit/geography: annual average; Iranian rial per US dollar; Iran.
- License: World Bank page reports CC BY 4.0.
- Status: **VERIFIED_AND_INGESTED** into a disposable SQLite validation DB.
- Limitation: official rate is not a free-market rate. Iran's multiple-rate regimes prevent silent substitution.

## Central Bank of Iran

- Candidate pages: official advanced exchange-rate and inflation pages.
- Status: **PARTIALLY_ACCESSIBLE / BLOCKED FOR AUTOMATION**.
- Evidence: HTTP content was an anti-automation human-verification challenge, not the dataset.
- Decision: no challenge bypass, scraping, or claim of ingestion.

## TSETMC total index

- Authority: Tehran Securities Exchange Technology Management.
- Intended source: official TSETMC index history.
- Status: **BLOCKED** in this runner; bounded homepage request returned HTTP 502.
- Decision: no secondary price site was promoted to production input.

## Gold, coin, free-market FX, housing, bank products

- Status: **BLOCKED / CANDIDATE NOT SUFFICIENTLY VALIDATED**.
- No stable authoritative machine-readable contract was verified during this run.
- No observations were fabricated or ingested. Gold fund NAV may become available independently through FIPIRAN.

## Operator commands

```bash
alembic upgrade head
python scripts/import_historical_data.py --database-url sqlite:///./irma-historical.db --all
python scripts/audit_historical_data.py --database-url sqlite:///./irma-historical.db
```

For an offline/reproducible rerun, save the two exact World Bank API responses as
`inflation_annual.json` and `fx_official_annual.json`, then pass `--source-dir DIR`.
