# اعتبارسنجی داده زنده

Workflow هفتگی یا دستی `Live FIPIRAN Validation` حداکثر سه تاریخچه صندوق را با فاصله
درخواست و Retry محدود دریافت می‌کند. اجرای دوم Idempotency را می‌سنجد و نتیجه واقعی
را به‌صورت Artifact نگه می‌دارد. شکست موقت منبع با وضعیت `source_unavailable` ثبت
می‌شود و Fixture جایگزین آن نمی‌شود. اجرای محلی:

```bash
IRMA_APP_ENV=e2e IRMA_FUND_PROVIDER=fipiran python scripts/live_data_validation.py
```

Workflow ابتدا Diagnostics، سپس Refresh محدود، Analytics و Ranking را اجرا می‌کند و
Artifact شامل Contract، وضعیت Provider، تعداد صندوق/تاریخچه/واجدشرایط و ابزار واقعی
پیشنهادی می‌سازد. شکست منبع از شکست کد جداست. Issue ثابت
`Live fund data provider degraded` برای شکست ایجاد/به‌روزرسانی و پس از بازیابی بسته
می‌شود؛ برای هر شکست Issue تازه ساخته نمی‌شود.
