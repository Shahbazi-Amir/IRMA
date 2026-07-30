# IRMA — Iranian Risk & Market Advisor

**سامانه هوشمند تحلیل بازار، ریسک و سرمایه‌گذاری ایران** یک برنامه پژوهشی فارسی برای ساخت پروفایل سرمایه‌گذار، محاسبات مالی، پیشنهاد سبد مبتنی بر قواعد، مقایسه داده‌محور صندوق‌ها و بک‌تست پژوهشی است.

> IRMA تضمین سود نمی‌دهد، جایگزین مشاوره مالی دارای مجوز نیست، سفارش واقعی ارسال نمی‌کند و داده مفقود را صفر یا داده جعلی تلقی نمی‌کند.

## قابلیت‌های نسخه ۱

- رابط فارسی و راست‌چین Streamlit برای موبایل و دسکتاپ
- FastAPI و OpenAPI
- پروفایل سرمایه‌گذار از حداقل ۱٬۰۰۰٬۰۰۰ تومان
- تخصیص درصدی و ریالی قابل‌توضیح با Ruleset نسخه‌بندی‌شده
- تبدیل ریال/تومان، بازده، CAGR، تورم، بازده واقعی، نوسان، افت، Sharpe و Sortino
- ماشین‌حساب سود مرکب با واریز ماهانه و ارزش واقعی
- مدل داده PostgreSQL با جایگزین SQLite و Migrationهای Alembic
- Provider خودکار FIPIRAN و Provider دستی CSV با ثبت منبع، زمان، کیفیت و هش
- زیرساخت چندبازاری با تاریخچه شاخص، بازار ETF، تورم رسمی و شرایط بانکی تأییدشده
- مقایسه کلاس‌های دارایی، ورود مرحله‌ای و تعادل مجدد قابل‌توضیح
- API صندوق‌ها، وضعیت داده‌ها، بازار، Refresh مدیریتی و بک‌تست
- بک‌تست long-only پژوهشی با هزینه، Slippage، فیلتر نقدشوندگی و اجرای دوره بعد
- Docker Compose برای API، Web و PostgreSQL

## اجرای Docker

```bash
cp .env.example .env
docker compose up --build
```

نشانی‌ها:

- Web: `http://localhost:8501`
- API: `http://localhost:8000`
- API Docs: `http://localhost:8000/docs`

PostgreSQL فقط داخل شبکه Docker در دسترس است.

## نصب محلی

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
cp .env.example .env
# برای توسعه ساده:
export IRMA_DATABASE_URL=sqlite:///./irma.db
alembic upgrade head
uvicorn irma.main:app --reload
```

رابط وب:

```bash
IRMA_API_BASE_URL=http://localhost:8000 streamlit run apps/streamlit_app/app.py
```

## ورود داده صندوق‌ها

IRMA هیچ رکورد نمونه را به‌عنوان داده واقعی ثبت نمی‌کند. برای FIPIRAN:

```env
IRMA_FUND_PROVIDER=fipiran
IRMA_FUND_HISTORY_LIMIT=25
```

یا فایل CSV معتبر را در `data/imports/funds.csv` قرار دهید. ستون‌های الزامی:

```text
name_fa,fund_type,source_identifier,observed_at
```

ستون‌های اختیاری:

```text
symbol,is_etf,inception_date,nav,market_price,volume,manager,market_maker,data_version
```

سپس با کلید مدیریتی تنظیم‌شده، Endpoint زیر را اجرا کنید:

```text
POST /v1/admin/data-refresh
Header: X-IRMA-Admin-Key
```

یا:

```bash
python scripts/refresh_data.py
```

## Migration

```bash
alembic upgrade head
alembic downgrade -1
```

## تست و کیفیت

```bash
ruff check .
ruff format --check .
mypy
pytest
python -m compileall src tests
python scripts/check_repo_safety.py
```

## سرویس‌ها و پورت‌ها

| سرویس | پورت | توضیح |
|---|---:|---|
| Streamlit | 8501 | رابط فارسی |
| FastAPI | 8000 | API و OpenAPI |
| PostgreSQL | داخلی | در Host منتشر نمی‌شود |

## متغیرهای محیطی مهم

- `IRMA_DATABASE_URL`: اتصال SQLAlchemy
- `IRMA_CORS_ORIGINS`: Originهای مجاز با کاما
- `IRMA_ADMIN_KEY`: محافظ Refresh مدیریتی؛ بدون مقدار Endpoint غیرفعال است
- `IRMA_FUND_CSV_PATH`: مسیر CSV صندوق‌ها
- `IRMA_FUND_PROVIDER`: یکی از `csv` یا `fipiran`
- `IRMA_FUND_HISTORY_LIMIT`: سقف تاریخچه صندوق‌ها در هر Refresh
- `IRMA_MARKET_INDEX_CSV_PATH`: فایل منبع‌دار شاخص‌های بازار
- `IRMA_INSTRUMENT_MARKET_CSV_PATH`: فایل OHLCV ابزارهای بازار
- `IRMA_INFLATION_CSV_PATH`: فایل رسمی تورم با سال پایه و تاریخ انتشار
- `IRMA_BANK_PRODUCT_CSV_PATH`: شرایط نسخه‌دار و تأییدشده محصولات بانکی
- `IRMA_REFRESH_ENABLED`: فعال‌سازی Worker زمان‌بندی‌شده
- `IRMA_REFRESH_INTERVAL_MINUTES`: فاصله Refresh
- `IRMA_API_BASE_URL`: نشانی API برای Streamlit

## صفحات رابط

خانه، پروفایل سرمایه‌گذار، پیشنهاد سبد، مقایسه صندوق‌ها، سود مرکب، تحلیل کوتاه‌مدت، تحلیل بلندمدت، وضعیت داده‌ها و درباره/روش‌شناسی.

## مستندات

- [معماری](docs/architecture.md)
- [منابع داده](docs/data-sources.md)
- [مدل پایگاه داده](docs/database-schema.md)
- [روش محاسبات مالی](docs/financial-methodology.md)
- [روش پیشنهاددهی](docs/recommendation-methodology.md)
- [رتبه‌بندی صندوق‌ها](docs/fund-ranking-methodology.md)
- [بک‌تست](docs/backtesting-methodology.md)
- [دیپلوی](docs/deployment.md)
- [امنیت](docs/security.md)
- [محدودیت‌ها](docs/limitations.md)
- [راهنمای فارسی](docs/user-guide-fa.md)
- [نقشه راه](docs/roadmap.md)

## محدودیت‌های فعلی

FIPIRAN Provider خودکار فعال صندوق‌هاست. شاخص، قیمت بازار ETF، تورم و محصولات بانکی
تا زمان تثبیت قرارداد رسمی API فقط از CSV منبع‌دار و اعتبارسنجی‌شده وارد می‌شوند.
رتبه‌بندی یا انتخاب ابزار بدون تاریخچه، تازگی، کیفیت و نگاشت قابل‌اعتماد متوقف می‌شود.
هیچ فایل نمونه‌ای همراه محصول به‌عنوان داده واقعی وارد نمی‌شود.

## اعتبارسنجی و Staging

```bash
python scripts/run_e2e.py
```

این دستور PostgreSQL، Migration، API و Streamlit را با Fixture صریحاً تستی و دو
Refresh برای اثبات Idempotency اجرا می‌کند. Fixture فقط در محیط `e2e` مجاز است.
Workflow جداگانه FIPIRAN محدود و زنده است و Fixture را جایگزین شکست منبع نمی‌کند.

پس از Merge، GitHub Actions در صورت مجازبودن Package Permission، Imageهای
`ghcr.io/shahbazi-amir/irma-api` و `ghcr.io/shahbazi-amir/irma-web` را با Tagهای
`latest`، `main` و `sha-<commit>` منتشر می‌کند. Credential استقرار خارجی موجود نیست؛
بنابراین فقط Ephemeral Staging در Actions آماده و اجرا می‌شود.
