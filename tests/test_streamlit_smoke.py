import ast
from pathlib import Path


def test_streamlit_app_parses_and_contains_required_pages() -> None:
    path = Path("apps/streamlit_app/app.py")
    text = path.read_text(encoding="utf-8")
    ast.parse(text)
    for page in [
        "خانه",
        "پروفایل سرمایه‌گذار",
        "پیشنهاد سبد",
        "مقایسه صندوق‌ها",
        "سود مرکب",
        "تحلیل کوتاه‌مدت",
        "تحلیل بلندمدت",
        "وضعیت داده‌ها",
        "درباره و روش‌شناسی",
    ]:
        assert page in text
    assert "direction: rtl" in text
