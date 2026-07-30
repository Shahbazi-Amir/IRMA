# Backfill تاریخچه صندوق

```bash
python scripts/backfill_fund_history.py --limit 10
python scripts/backfill_fund_history.py --fund-type fixed_income --limit 10
python scripts/backfill_fund_history.py --resume RUN_ID
python scripts/backfill_fund_history.py --from-date 2026-01-01
```

Backfill از صندوق‌های فعال دارای شناسه پایدار شروع می‌کند، تاریخ موجود را دوباره
نمی‌نویسد و پس از هر صندوق Commit می‌کند. Checkpoint، آخرین تاریخ، وضعیت و نوع خطا
ذخیره می‌شوند؛ شکست یک صندوق مانع ادامه بقیه نیست. Concurrency عمداً یک است تا فشار
روی منبع پایین بماند.
