# اعتبارسنجی داده زنده

Workflow هفتگی یا دستی `Live FIPIRAN Validation` حداکثر سه تاریخچه صندوق را با فاصله
درخواست و Retry محدود دریافت می‌کند. اجرای دوم Idempotency را می‌سنجد و نتیجه واقعی
را به‌صورت Artifact نگه می‌دارد. شکست موقت منبع با وضعیت `source_unavailable` ثبت
می‌شود و Fixture جایگزین آن نمی‌شود. اجرای محلی:

```bash
IRMA_APP_ENV=e2e IRMA_FUND_PROVIDER=fipiran python scripts/live_data_validation.py
```
