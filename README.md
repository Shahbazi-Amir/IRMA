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

اتصال خودکار پایدار به منابع رسمی ایران در این نسخه فعال نیست. تا زمان بررسی حقوقی، فنی و پایداری Endpointها، داده صندوق‌ها از CSV دارای منشأ وارد می‌شود. رتبه‌بندی صندوق بدون تاریخچه کافی نمایش داده نمی‌شود. املاک و ارز Interface و قالب ورود آینده دارند، اما تحلیل کامل آن‌ها انجام نشده است.
