# Backup و بازیابی PostgreSQL

```bash
IRMA_DATABASE_URL=postgresql://... python scripts/backup_database.py \
  --output-dir /secure/backups --retention-days 14
IRMA_RESTORE_DATABASE_URL=postgresql://.../irma_restore_test \
  python scripts/restore_database.py /secure/backups/irma-....dump
```

Backup با `pg_dump` در قالب فشرده custom ساخته می‌شود. URL و رمز از Environment
می‌آیند و Backup در Git نگهداری نمی‌شود. Restore فقط روی مقصد صریح انجام می‌شود و
مقصدی که نام `production` داشته باشد رد می‌شود. Restore باید ابتدا روی دیتابیس
آزمایشی اجرا و سپس با `alembic current` و Queryهای سلامت بررسی شود.
