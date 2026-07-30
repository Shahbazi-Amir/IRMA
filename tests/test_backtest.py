from datetime import date, timedelta

import pytest

from irma.trading_engine.backtest import BacktestRequest, Bar, run_backtest


def bars(count: int = 80) -> list[Bar]:
    start = date(2025, 1, 1)
    return [
        Bar(
            date=start + timedelta(days=index),
            close=100 + index * 0.5 + (index % 5),
            volume=1_000_000,
            trade_value=100_000_000,
            spread_percent=0.002,
            tradable=True,
        )
        for index in range(count)
    ]


def test_backtest_includes_costs_and_metrics() -> None:
    result = run_backtest(
        BacktestRequest(
            strategy="moving_average",
            bars=bars(),
            fast_window=5,
            slow_window=20,
            fee_percent=0.002,
            slippage_percent=0.003,
        )
    )
    assert result.research_only is True
    assert result.total_costs > 0
    assert len(result.equity_curve) == 81
    assert any("prior bars" in warning for warning in result.warnings)


def test_liquidity_filter_prevents_trading() -> None:
    result = run_backtest(
        BacktestRequest(
            strategy="momentum",
            bars=bars(),
            minimum_volume=2_000_000,
            fast_window=5,
            slow_window=20,
        )
    )
    assert result.total_trades == 0
    assert result.total_return == 0


def test_future_bar_change_does_not_change_prior_equity() -> None:
    original = bars()
    request = BacktestRequest(
        strategy="moving_average", bars=original, fast_window=5, slow_window=20
    )
    first = run_backtest(request)
    changed = bars()
    changed[-1] = changed[-1].model_copy(update={"close": changed[-1].close * 10})
    second = run_backtest(request.model_copy(update={"bars": changed}))
    assert first.equity_curve[:-1] == second.equity_curve[:-1]


def test_invalid_bar_order_is_rejected() -> None:
    data = bars()
    data[1], data[2] = data[2], data[1]
    with pytest.raises(ValueError):
        BacktestRequest(strategy="momentum", bars=data, fast_window=5, slow_window=20)
