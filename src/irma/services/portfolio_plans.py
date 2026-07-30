"""Explainable staged-entry and rebalancing plans."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal


def staged_entry_plan(
    *,
    amount_toman: Decimal,
    risk: str,
    volatility: float | None,
    data_quality: str,
    liquidity: str,
) -> dict[str, object]:
    if amount_toman <= 0:
        raise ValueError("amount must be positive")
    if data_quality not in {"valid", "warning"} or liquidity == "low":
        return {
            "enabled": False,
            "reason": "Insufficient data quality or liquidity; no timed market entry is proposed.",
            "stages": [],
        }
    stages = 2
    if risk == "aggressive" or (volatility is not None and volatility >= 0.30):
        stages = 4
    elif volatility is not None and volatility >= 0.18:
        stages = 3
    part = (amount_toman / stages).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    amounts = [part] * stages
    amounts[-1] += amount_toman - sum(amounts)
    return {
        "enabled": True,
        "stage_count": stages,
        "interval_days": 14 if stages >= 3 else 30,
        "amounts_toman": amounts,
        "temporary_holding": "fixed_income",
        "continue_condition": "data remains fresh and the instrument remains liquid",
        "stop_condition": "data error, material liquidity loss, or urgent cash need",
        "notice": "This plan does not claim to identify a market bottom.",
    }


def rebalance_plan(
    *,
    target_weights: dict[str, float],
    current_weights: dict[str, float],
    monthly_contribution_toman: Decimal = Decimal(0),
    threshold_points: float = 5.0,
) -> dict[str, object]:
    if abs(sum(target_weights.values()) - 100) > 1e-6:
        raise ValueError("target weights must sum to 100")
    items: list[dict[str, object]] = []
    for category, target in target_weights.items():
        current = current_weights.get(category, 0.0)
        deviation = current - target
        actionable = abs(deviation) >= threshold_points or (
            target > 0 and abs(deviation) / target >= 0.20
        )
        action = "hold"
        if actionable:
            if deviation < 0 and monthly_contribution_toman > 0:
                action = "direct_new_contribution"
            elif deviation < 0:
                action = "buy"
            else:
                action = "consider_reduce"
        items.append(
            {
                "category": category,
                "target_percent": target,
                "current_percent": current,
                "deviation_points": deviation,
                "action": action,
                "cost_notice": "Check fees and taxes before selling."
                if action == "consider_reduce"
                else None,
            }
        )
    return {
        "method": "quarterly_and_threshold",
        "review_interval_months": 3,
        "threshold_points": threshold_points,
        "items": items,
        "notice": "New contributions are preferred over unnecessary sales.",
    }
