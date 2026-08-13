"""Beginner-facing investment decision contract backed by the auditable rule engine."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from irma.domain.profile import Horizon, InvestorProfile, RiskTolerance
from irma.persistence.models import DataSource, Fund, FundNavHistory
from irma.presentation import ASSET_LABELS, HORIZON_LABELS, LIQUIDITY_LABELS, RISK_LABELS
from irma.services.asset_comparison import compare_assets
from irma.services.recommendations import create_recommendation


class SimpleDecisionRequest(BaseModel):
    capital_toman: Decimal = Field(ge=Decimal("1000000"), le=Decimal("1000000000000000"))
    horizon: Horizon
    risk: RiskTolerance
    monthly_contribution_toman: Decimal = Field(default=Decimal(0), ge=0)
    goal: str = Field(default="capital_growth", max_length=80)
    selected_assets: list[str] = Field(default_factory=list)
    horizon_days: int | None = Field(default=None, ge=7, le=3650)


def _profile(request: SimpleDecisionRequest) -> InvestorProfile:
    drawdown = {
        RiskTolerance.CONSERVATIVE: 0.10,
        RiskTolerance.MODERATE: 0.20,
        RiskTolerance.AGGRESSIVE: 0.40,
    }[request.risk]
    return InvestorProfile(
        capital_toman=request.capital_toman,
        monthly_contribution_toman=request.monthly_contribution_toman,
        horizon=request.horizon,
        risk_tolerance=request.risk,
        max_drawdown_tolerance=drawdown,
        liquidity_need="medium",
        experience="beginner",
        trading_experience="none",
        investment_style="balanced",
        wants_trading=False,
        max_trading_percent=0,
        has_emergency_fund=False,
        goal=request.goal,
        current_assets=[],
    )


def create_simple_decision(request: SimpleDecisionRequest, session: Session) -> dict[str, Any]:
    recommendation = create_recommendation(_profile(request), session=session)
    allowed = set(request.selected_assets)
    allocations = []
    for item in recommendation.allocations:
        if item.percent == 0:
            continue
        allocations.append(
            {
                "asset": item.category,
                "label": ASSET_LABELS.get(item.category, "گزینه سرمایه‌گذاری"),
                "percent": item.percent,
                "amount_toman": item.amount_toman,
                "risk": RISK_LABELS.get(item.risk, "نامشخص"),
                "liquidity": LIQUIDITY_LABELS.get(item.liquidity, "نامشخص"),
                "reason": _reason(item.category, request.horizon, request.risk),
                "available": True,
                "selected_by_user": not allowed or item.category in allowed,
                "fund_candidates": [
                    {"name": fund.name_fa, "score": fund.score, "reason": "داده کافی و رتبه معتبر"}
                    for fund in item.instruments
                ],
            }
        )
    sources = list(session.scalars(select(DataSource)))
    fund_count = session.scalar(select(func.count(Fund.id))) or 0
    history_count = session.scalar(select(func.count(FundNavHistory.id))) or 0
    candidates = compare_assets(
        session, request.capital_toman, request.horizon, request.risk, request.horizon_days
    )
    freshness = "missing"
    if sources:
        freshness = "degraded" if any(source.status != "valid" for source in sources) else "fresh"
    return {
        "input": {
            "capital_toman": request.capital_toman,
            "horizon": request.horizon,
            "horizon_label": HORIZON_LABELS[request.horizon.value],
            "risk": request.risk,
            "risk_label": RISK_LABELS[request.risk.value],
            "goal": request.goal,
        },
        "allocation": allocations,
        "candidates": candidates,
        "decision_trace": _trace(request),
        "historical_context": {
            "available": history_count >= 2,
            "sample_count": history_count,
            "notice": "این بخش شواهد تاریخی است و پیش‌بینی آینده نیست.",
        },
        "data_freshness": {
            "status": freshness,
            "fund_count": fund_count,
            "latest_observation_at": max(
                (
                    source.last_valid_observation_at
                    for source in sources
                    if source.last_valid_observation_at
                ),
                default=None,
            ),
        },
        "warnings": recommendation.warnings,
        "notice": "این پیشنهاد قاعده‌محور است؛ سود آینده را تضمین نمی‌کند.",
    }


def _reason(asset: str, horizon: Horizon, risk: RiskTolerance) -> str:
    reasons = {
        "cash": "برای دسترسی سریع به بخشی از پول و مدیریت شرایط پیش‌بینی‌نشده.",
        "fixed_income": "برای کاهش نوسان کل سبد، به‌ویژه در افق کوتاه‌تر.",
        "gold": "برای تنوع و پوشش بخشی از ریسک تورم؛ همراه با امکان نوسان.",
        "equity_index": "برای رشد بلندمدت‌تر؛ با احتمال افت قابل توجه در کوتاه‌مدت.",
        "mixed_fund": "برای ترکیب کنترل‌شده‌تری از دارایی‌های کم‌ریسک و رشدی.",
        "short_term": "فقط برای بررسی پژوهشی پرریسک و نه سیگنال قطعی معامله.",
    }
    return reasons.get(
        asset, f"با توجه به افق {HORIZON_LABELS[horizon.value]} و ریسک {RISK_LABELS[risk.value]}."
    )


def _trace(request: SimpleDecisionRequest) -> list[str]:
    trace = [
        f"افق سرمایه‌گذاری شما {HORIZON_LABELS[request.horizon.value]} است.",
        f"ریسک‌پذیری انتخاب‌شده {RISK_LABELS[request.risk.value]} است.",
        "برای کنترل نوسان، بخشی از سرمایه به گزینه‌های باثبات‌تر اختصاص یافت.",
        "برای مقابله با تورم، تنوع بین چند نوع دارایی در نظر گرفته شد.",
        "فقط داده‌های موجود استفاده شده‌اند و نبود داده به‌عنوان صفر تفسیر نشده است.",
    ]
    if request.selected_assets:
        trace.append("گزینه‌های انتخابی شما در مقایسه لحاظ شدند؛ تنوع ضروری سبد حذف نشد.")
    return trace
