# IRMA MVP Architecture

## Goals

The MVP establishes a testable backend foundation without coupling financial calculations to market-data providers or user interfaces.

## Layers

```text
HTTP API (FastAPI)
        |
Application routing
        |
Domain models and rule engine
        |
Pure financial calculations
        |
Future provider interfaces
```

### API layer

`irma.main` creates the application and includes routes from `irma.api.routes`. The API currently exposes:

- `GET /health`
- `GET /v1/info`
- `POST /v1/recommendations`

### Domain layer

- `finance.py`: pure calculation functions with explicit input validation.
- `profile.py`: validated investor-profile schema and enums.
- `recommendation.py`: deterministic, explainable allocation rules.

The domain layer does not call external services and can be tested independently.

### Configuration

`config.py` uses `pydantic-settings`. Runtime values use the `IRMA_` environment-variable prefix and may be loaded from a local `.env` file, which is excluded from Git.

### Provider boundary

`irma.interfaces.market_data` defines a protocol for future Iranian market-data implementations. The MVP deliberately provides no live or synthetic provider.

## Recommendation design

The rule engine starts from a risk-tolerance allocation and applies bounded transfers for:

1. liquidity need;
2. monthly-income need;
3. short investment horizon;
4. maximum acceptable drawdown;
5. trading preference;
6. investment experience.

Every applied rule is returned in the response. Allocations always remain non-negative and sum to 100%.

## Security boundaries

- No secrets are stored in source control.
- No private investor records are persisted.
- No order-execution interface is implemented.
- No claimed or fabricated return data is included.
- Inputs are validated at the API boundary.

## Deployment

The container runs as a non-root user and starts Uvicorn on port 8000. GitHub Actions runs linting, formatting checks, tests, bytecode compilation, and a Docker build.

## Future architectural decisions

Persistence, authentication, data-provider selection, RAG storage, observability, and portfolio optimization require separate design records before implementation.
