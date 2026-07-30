"""Backtest execution and audit persistence."""

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from irma.persistence.models import BacktestMetric, BacktestRun
from irma.trading_engine.backtest import BacktestRequest, BacktestResult, run_backtest


def execute_backtest(
    request: BacktestRequest,
    *,
    session: Session | None = None,
) -> tuple[int | None, BacktestResult]:
    result = run_backtest(request)
    if session is None:
        return None, result
    run = BacktestRun(
        strategy_name=request.strategy,
        strategy_version="1.0",
        completed_at=datetime.now(UTC),
        parameters_json=request.model_dump(mode="json", exclude={"bars"}),
        input_hash=result.input_hash,
        warnings_json=result.warnings,
    )
    session.add(run)
    session.flush()
    metrics = {
        "total_trades": result.total_trades,
        "win_rate": result.win_rate,
        "profit_factor": result.profit_factor,
        "expectancy": result.expectancy,
        "total_return": result.total_return,
        "annualized_return": result.annualized_return,
        "maximum_drawdown": result.maximum_drawdown,
        "sharpe_ratio": result.sharpe_ratio,
        "market_exposure": result.market_exposure,
        "total_costs": result.total_costs,
    }
    for name, value in metrics.items():
        session.add(
            BacktestMetric(
                backtest_run_id=run.id,
                metric_name=name,
                value=Decimal(str(value)) if value is not None else None,
            )
        )
    session.commit()
    return run.id, result
