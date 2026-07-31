# اعتبارسنجی داده زنده

Workflow هفتگی یا دستی `Live FIPIRAN Validation` حداکثر سه تاریخچه صندوق را با فاصله
درخواست و Retry محدود دریافت می‌کند. اجرای دوم Idempotency را می‌سنجد و نتیجه واقعی
را به‌صورت Artifact نگه می‌دارد. شکست موقت منبع با وضعیت `source_unavailable` ثبت
می‌شود و Fixture جایگزین آن نمی‌شود. اجرای محلی:

```bash
IRMA_APP_ENV=e2e IRMA_FUND_PROVIDER=fipiran python scripts/live_data_validation.py
```

برای Smoke کامل Bootstrap روی SQLite تازه:

```bash
IRMA_DATABASE_URL=sqlite:///./live-smoke.db \
IRMA_FUND_PROVIDER=fipiran \
IRMA_FUND_HISTORY_LIMIT=2 \
python scripts/bootstrap_data.py
```

سپس API و رابط را با فرمان‌های README اجرا کنید و `/health`، `/v1/funds`،
`/v1/data-sources/status` و صفحه «مقایسه صندوق‌ها» را بررسی کنید. Workflow
`Live FIPIRAN Validation` همین Bootstrap را هفتگی و با اجرای دستی انجام می‌دهد،
گزارش JSON را Artifact می‌کند و در شکست منبع هیچ Fixture جایگزین نمی‌کند.

Workflow ابتدا Diagnostics، سپس Refresh محدود، Analytics و Ranking را اجرا می‌کند و
Artifact شامل Contract، وضعیت Provider، تعداد صندوق/تاریخچه/واجدشرایط و ابزار واقعی
پیشنهادی می‌سازد. شکست منبع از شکست کد جداست. Issue ثابت
`Live fund data provider degraded` برای شکست ایجاد/به‌روزرسانی و پس از بازیابی بسته
می‌شود؛ برای هر شکست Issue تازه ساخته نمی‌شود.
