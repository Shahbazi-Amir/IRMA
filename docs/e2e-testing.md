# تست End-to-End

اجرای پایدار آفلاین:

```bash
python scripts/run_e2e.py
```

این دستور PostgreSQL، API و Streamlit را با Compose بالا می‌آورد، Migration را از
entrypoint اجرا می‌کند، Fixture صریحاً تستی را دو بار Import می‌کند، Idempotency،
`/ready`، `/metrics`، صندوق‌ها، Health رابط و Logها را می‌سنجد و در پایان Volume را
حذف می‌کند. گزارش‌ها در `artifacts/` ساخته و در CI آپلود می‌شوند. Fixture فقط وقتی
`IRMA_APP_ENV=e2e` است مجاز است و هیچ‌گاه داده زنده تلقی نمی‌شود.
