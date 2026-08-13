import ast
from pathlib import Path


def test_streamlit_app_parses_and_contains_required_pages() -> None:
    path = Path("apps/streamlit_app/app.py")
    text = path.read_text(encoding="utf-8")
    ast.parse(text)
    for page in ["سرمایه‌گذاری من", "بازار و تاریخچه", "پروفایل و روش تحلیل"]:
        assert page in text
    assert "direction:rtl" in text
    assert "۵۰۰" not in text  # numeric values remain machine-safe in source
