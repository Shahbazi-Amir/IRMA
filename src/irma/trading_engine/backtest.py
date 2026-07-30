"""Explainable, long-only research backtests with next-period execution."""

from __future__ import annotations

import hashlib
import json
import math
import statistics
from dataclasses import dataclass
from datetime import date

from pydantic import BaseModel, ConfigDict, Field, model_validator

from irma.domain.finance import maximum_drawdown


class Bar(BaseModel):
    model_config = ConfigDict(extra="forbid")
    date: date
    close: float = Field(gt=0)
    volume: float = Field(ge=0)
    trade_value: float = Field(ge=0)
    spread_percent: float = Field(default=0.0, ge=0, le=1)
    tradable: bool = True


class BacktestRequest(BaseModel):
    strategy: str = Field(pattern="^(moving_average|momentum|mean_reversion|breakout)$")
    bars: list[Bar]
    initial_capital: float = Field(default=1_000_000, gt=0)
    fee_percent: float = Field(default=0.001, ge=0, le=0.1)
    slippage_percent: float = Field(default=0.001, ge=0, le=0.1)
    fast_window: int = Field(default=5, ge=2, le=100)
    slow_window: int = Field(default=20, ge=3, le=300)
    minimum_volume: float = Field(default=0, ge=0)
    minimum_trade_value: float = Field(default=0, ge=0)
    maximum_spread_percent: float = Field(default=0.05, ge=0, le=1)

    @model_validator(mode="after")
    def validate_windows(self) -> "BacktestRequest":
        if self.fast_window >= self.slow_window:
            raise ValueError("fast_window must be less than slow_window")
        if len(self.bars) <= self.slow_window + 2:
            raise ValueError("not enough bars for the selected windows")
        dates = [bar.date for bar in self.bars]
        if dates != sorted(dates) or len(set(dates)) != len(dates):
            raise ValueError("bars must have unique ascending dates")
        return self


class BacktestResult(BaseModel):
    research_only: bool = True
    strategy: str
    total_trades: int
    win_rate: float | None
    average_win: float | None
    average_loss: float | None
    profit_factor: float | None
    expectancy: float | None
    total_return: float
    annualized_return: float | None
    maximum_drawdown: float
    sharpe_ratio: float | None
    market_exposure: float
    total_costs: float
    input_hash: str
    equity_curve: list[float]
    warnings: list[str]


@dataclass(slots=True)
class Position:
    entry_price: float
    quantity: float
    entry_cost: float


def _signal(strategy: str, closes: list[float], fast: int, slow: int) -> bool:
    if len(closes) < slow:
        return False
    fast_mean = statistics.mean(closes[-fast:])
    slow_mean = statistics.mean(closes[-slow:])
    if strategy == "moving_average":
        return fast_mean > slow_mean
    if strategy == "momentum":
        return closes[-1] > closes[-fast]
    if strategy == "mean_reversion":
        return closes[-1] < slow_mean * 0.97
    if strategy == "breakout":
        return closes[-1] >= max(closes[-slow:-1])
    return False


def run_backtest(request: BacktestRequest) -> BacktestResult:
    payload = request.model_dump(mode="json")
    input_hash = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    cash = request.initial_capital
    position: Position | None = None
    equity_curve = [cash]
    trade_returns: list[float] = []
    total_costs = 0.0
    invested_periods = 0
    closes_seen: list[float] = []

    for index, bar in enumerate(request.bars):
        # The decision for this bar is calculated only from closes available before this bar.
        desired_position = _signal(
            request.strategy, closes_seen, request.fast_window, request.slow_window
        )
        liquid = (
            bar.tradable
            and bar.volume >= request.minimum_volume
            and bar.trade_value >= request.minimum_trade_value
            and bar.spread_percent <= request.maximum_spread_percent
        )
        cost_rate = request.fee_percent + request.slippage_percent + bar.spread_percent / 2
        if liquid and desired_position and position is None:
            execution_price = bar.close * (1 + request.slippage_percent + bar.spread_percent / 2)
            entry_cost = cash * request.fee_percent
            quantity = (cash - entry_cost) / execution_price
            total_costs += entry_cost + quantity * (execution_price - bar.close)
            position = Position(execution_price, quantity, entry_cost)
            cash = 0.0
        elif liquid and not desired_position and position is not None:
            execution_price = bar.close * (1 - request.slippage_percent - bar.spread_percent / 2)
            gross = position.quantity * execution_price
            exit_fee = gross * request.fee_percent
            cash = gross - exit_fee
            total_costs += exit_fee + position.quantity * (bar.close - execution_price)
            trade_returns.append(cash / (position.quantity * position.entry_price + position.entry_cost) - 1)
            position = None
        equity = cash if position is None else position.quantity * bar.close
        if position is not None:
            invested_periods += 1
        equity_curve.append(equity)
        closes_seen.append(bar.close)

    if position is not None:
        last = request.bars[-1]
        execution_price = last.close * (1 - request.slippage_percent - last.spread_percent / 2)
        gross = position.quantity * execution_price
        exit_fee = gross * request.fee_percent
        cash = gross - exit_fee
        total_costs += exit_fee + position.quantity * (last.close - execution_price)
        trade_returns.append(cash / (position.quantity * position.entry_price + position.entry_cost) - 1)
        equity_curve[-1] = cash

    total_return = equity_curve[-1] / request.initial_capital - 1
    years = (request.bars[-1].date - request.bars[0].date).days / 365.25
    annualized = (1 + total_return) ** (1 / years) - 1 if years > 0 and total_return > -1 else None
    wins = [item for item in trade_returns if item > 0]
    losses = [item for item in trade_returns if item < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    period_returns = [
        equity_curve[index] / equity_curve[index - 1] - 1
        for index in range(1, len(equity_curve))
        if equity_curve[index - 1] > 0
    ]
    sharpe = None
    if len(period_returns) >= 2 and not math.isclose(statistics.stdev(period_returns), 0.0):
        sharpe = statistics.mean(period_returns) / statistics.stdev(period_returns) * math.sqrt(252)
    return BacktestResult(
        strategy=request.strategy,
        total_trades=len(trade_returns),
        win_rate=len(wins) / len(trade_returns) if trade_returns else None,
        average_win=statistics.mean(wins) if wins else None,
        average_loss=statistics.mean(losses) if losses else None,
        profit_factor=gross_profit / gross_loss if gross_loss else None,
        expectancy=statistics.mean(trade_returns) if trade_returns else None,
        total_return=total_return,
        annualized_return=annualized,
        maximum_drawdown=maximum_drawdown([max(1e-12, item) for item in equity_curve]),
        sharpe_ratio=sharpe,
        market_exposure=invested_periods / len(request.bars),
        total_costs=total_costs,
        input_hash=input_hash,
        equity_curve=equity_curve,
        warnings=[
            "Research and paper-trading only; no order is sent.",
            "Results depend on data quality and do not remove survivorship bias by themselves.",
            "Signals use only prior bars and execute on the next available bar.",
        ],
    )
