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
