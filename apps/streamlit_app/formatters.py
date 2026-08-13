"""Persian presentation helpers."""

from datetime import date, datetime
from decimal import Decimal

DIGITS = str.maketrans("0123456789,.%", "۰۱۲۳۴۵۶۷۸۹٬٫٪")


def fa(value: object) -> str:
    return str(value).translate(DIGITS)


def toman(value: int | float | Decimal | None) -> str:
    if value is None:
        return "داده موجود نیست"
    return f"{fa(f'{Decimal(str(value)).quantize(Decimal(1)):,}')} تومان"


def human_toman(value: int | float | Decimal | None) -> str:
    if value is None:
        return "داده موجود نیست"
    amount = Decimal(str(value))
    if amount >= 1_000_000_000:
        return f"{fa(f'{amount / Decimal(1_000_000_000):.1f}')} میلیارد تومان"
    if amount >= 1_000_000:
        return f"{fa(f'{amount / Decimal(1_000_000):.1f}')} میلیون تومان"
    return toman(amount)


def percent(value: float | Decimal | None, *, ratio: bool = False) -> str:
    if value is None:
        return "داده کافی نیست"
    number = float(value) * 100 if ratio else float(value)
    return fa(f"{number:.1f}%")


def friendly_date(value: str | date | datetime | None) -> str:
    return "داده موجود نیست" if value is None else fa(str(value)[:10])


def clean(value: object | None) -> str:
    return "داده موجود نیست" if value is None else fa(value)
