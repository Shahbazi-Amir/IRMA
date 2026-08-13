"""Persian-first labels and safe presentation helpers shared by API and UI."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

PERSIAN_DIGITS = str.maketrans("0123456789,.%", "۰۱۲۳۴۵۶۷۸۹٬٫٪")

ASSET_LABELS = {
    "cash": "وجه نقد",
    "bank_deposit": "سپرده بانکی",
    "fixed_income": "صندوق درآمد ثابت",
    "fixed_income_fund": "صندوق درآمد ثابت",
    "gold": "طلا و صندوق طلا",
    "gold_fund": "صندوق طلا",
    "coin": "سکه",
    "fx": "ارز",
    "equity": "سهامی",
    "equity_fund": "صندوق سهامی",
    "equity_index": "صندوق شاخصی",
    "index_fund": "صندوق شاخصی",
    "mixed_fund": "صندوق مختلط",
    "market_index": "شاخص بورس",
    "housing": "مسکن",
    "short_term": "نوسان‌گیری پژوهشی",
}
RISK_LABELS = {
    "very_low": "بسیار کم",
    "low": "کم",
    "medium": "متوسط",
    "high": "زیاد",
    "very_high": "بسیار زیاد",
    "conservative": "کم",
    "moderate": "متوسط",
    "aggressive": "زیاد",
}
LIQUIDITY_LABELS = {
    "very_low": "بسیار کم",
    "low": "کم",
    "medium": "متوسط",
    "high": "زیاد",
    "very_high": "بسیار زیاد",
}
HORIZON_LABELS = {
    "days": "چند روز",
    "one_to_four_weeks": "یک هفته تا یک ماه",
    "one_to_three_months": "یک تا سه ماه",
    "three_to_six_months": "سه تا شش ماه",
    "six_to_twelve_months": "شش ماه تا یک سال",
    "one_to_three_years": "یک تا سه سال",
    "three_to_five_years": "سه تا پنج سال",
    "over_five_years": "پنج سال و بیشتر",
}


def persian_digits(value: object) -> str:
    return str(value).translate(PERSIAN_DIGITS)


def format_toman(value: Decimal | int | float | None) -> str:
    if value is None:
        return "داده موجود نیست"
    amount = Decimal(str(value)).quantize(Decimal("1"))
    return f"{persian_digits(f'{amount:,}')} تومان"


def human_toman(value: Decimal | int | float | None) -> str:
    if value is None:
        return "داده موجود نیست"
    amount = Decimal(str(value))
    if abs(amount) >= 1_000_000_000:
        return f"{persian_digits(f'{amount / Decimal(1_000_000_000):.1f}')} میلیارد تومان"
    if abs(amount) >= 1_000_000:
        return f"{persian_digits(f'{amount / Decimal(1_000_000):.1f}')} میلیون تومان"
    return format_toman(amount)


def format_percent(value: float | Decimal | None, *, ratio: bool = False) -> str:
    if value is None:
        return "داده کافی نیست"
    number = float(value) * 100 if ratio else float(value)
    return persian_digits(f"{number:.1f}%")


def format_date(value: date | datetime | None) -> str:
    if value is None:
        return "داده موجود نیست"
    day = value.date() if isinstance(value, datetime) else value
    return persian_digits(day.isoformat())


def rial_to_toman(value: Decimal | int | float) -> Decimal:
    """Convert explicitly; reject fractional rial values that cannot produce exact Toman."""
    rial = Decimal(str(value))
    if rial % 10:
        raise ValueError("Rial value must be divisible by 10 for exact Toman conversion")
    return rial / 10
