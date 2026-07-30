# معماری IRMA

```text
Streamlit Web App
        ↓ HTTP/JSON
FastAPI Backend
        ↓
Application Services
        ↓
Domain / Analytics / Trading Engine
        ↓
Provider Adapters + SQLAlchemy
        ↓
PostgreSQL (SQLite for tests)
```

منطق مالی داخل UI قرار ندارد. Domain شامل توابع Pure است. Providerها فقط داده منبع‌دار تولید می‌کنند. Serviceها Persistence و Domain را هماهنگ می‌کنند. API مرز اعتبارسنجی و دسترسی مدیریتی است.

بک‌تست از داده آینده استفاده نمی‌کند: سیگنال هر روز فقط از داده‌های روزهای قبل ساخته و در نخستین Bar بعدی قابل‌معامله اجرا می‌شود.

Providerهای NAV صندوق، بازار ابزار، شاخص، تورم و بانک مستقل‌اند. اتصال صندوق به ابزار در
`fund_instrument_mappings` و Service Layer انجام می‌شود؛ Match مبهم وارد انتخاب ابزار نمی‌شود.
Analytics سری زمانی ورودی‌های دارای frequency و معنای روشن (NAV، قیمت یا CPI) می‌گیرد و
مقادیر مفقود را forward-fill نمی‌کند.
