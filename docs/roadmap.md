# IRMA Roadmap

## Phase 0 — Initial MVP

- [x] Python project foundation
- [x] FastAPI backend and settings
- [x] Core financial calculations
- [x] Investor profile model
- [x] Explainable rule-based allocation
- [x] Unit and smoke tests
- [x] Ruff, Pytest, GitHub Actions
- [x] Docker and Docker Compose

## Phase 1 — Curated Iranian data

- Define authoritative sources and licensing constraints.
- Implement provider adapters behind the market-data interface.
- Add provenance, timestamps, validation, and stale-data handling.
- Start with a small, reviewed dataset for funds, gold, deposits, FX, and market indices.
- Never substitute missing observations with fabricated values.

## Phase 2 — Product and portfolio analysis

- Fund comparison using fees, liquidity, risk, drawdown, and historical returns.
- Scenario analysis for low capital, monthly contributions, and inflation.
- User-visible assumptions and data-quality indicators.
- Versioned rule sets and recommendation audit logs.

## Phase 3 — Broader asset coverage

- Real-estate analysis for explicitly supported cities and data sources.
- Banking-product comparison using verified terms.
- Currency and gold analytics.
- Paper-trading and backtesting only, with clear limitations.

## Phase 4 — Retrieval and research assistant

- Document ingestion with source attribution.
- RAG evaluation datasets and grounded-answer checks.
- Iranian financial terminology normalization.
- Citation-first research responses.

## Deferred until separate approval

- Live trading or order submission
- Bank connectivity
- Financial identity verification
- Price prediction
- Live short-term trading signals
- Complex portfolio optimization
- Nationwide real-estate coverage

## Engineering priorities

1. Data provenance and correctness
2. Security and privacy
3. Explainability
4. Test coverage
5. Reproducible deployments
6. Observability and auditability
