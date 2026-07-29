# IRMA

**IRMA** is an early-stage, Iran-focused investment research and allocation assistant. This repository currently contains the initial backend MVP: deterministic financial calculations, an investor profile model, and a transparent rule-based allocation engine.

> IRMA does not provide personalized financial advice, execute trades, predict prices, or invent market returns. The current allocation output is an experimental rule-based suggestion for research and software validation.

## MVP capabilities

- Rial/Toman conversion
- Simple, cumulative, annualized, inflation-adjusted, and real return calculations
- Compound interest, volatility, maximum drawdown, and Sharpe ratio calculations
- Investor profile validation, starting from 1,000,000 Toman
- Explainable allocation suggestions across:
  - cash
  - deposits/fixed income
  - gold
  - equity funds
  - high-risk/trading allocation
- FastAPI health and recommendation endpoints
- Unit tests, Ruff configuration, GitHub Actions, Docker, and Docker Compose

## Requirements

- Python 3.11+
- Docker (optional)

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
cp .env.example .env
```

Run the API:

```bash
uvicorn irma.main:app --reload
```

OpenAPI documentation is available at `http://127.0.0.1:8000/docs`.

## Example request

```bash
curl -X POST http://127.0.0.1:8000/v1/recommendations \
  -H "Content-Type: application/json" \
  -d '{
    "capital_toman": 1000000,
    "monthly_contribution_toman": 0,
    "horizon_months": 24,
    "risk_tolerance": "moderate",
    "max_drawdown_tolerance": 0.2,
    "needs_monthly_income": false,
    "liquidity_need": "medium",
    "wants_trading": false,
    "experience": "beginner"
  }'
```

## Quality checks

```bash
ruff check .
ruff format --check .
pytest
python -m compileall src tests
```

## Docker

```bash
docker compose up --build
```

The API will be available at `http://localhost:8000`.

## Project documents

- [Architecture](docs/architecture.md)
- [Roadmap](docs/roadmap.md)
- [Future interfaces](docs/interfaces.md)

## Security and data handling

Do not commit `.env`, credentials, private financial data, local databases, raw large datasets, or model files. Environment variables must be documented in `.env.example`.

## Current limitations

The MVP does not fetch live Iranian market data, estimate future returns, perform optimization, analyze all real-estate markets, connect to banks, authenticate financial users, or submit orders. See the roadmap for planned phases.
