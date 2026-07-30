# راهنمای دیپلوی Docker

```bash
cp .env.example .env
# مقادیر placeholder، به‌ویژه رمز DB و IRMA_ADMIN_KEY را تغییر دهید.
docker compose up --build
```

API هنگام شروع `alembic upgrade head` را اجرا می‌کند. PostgreSQL در Host منتشر نمی‌شود و Volume دائمی دارد. API و Web به‌صورت non-root اجرا می‌شوند و Healthcheck دارند.

برای سرویس‌های عمومی دارای Docker، Repository را Clone، `.env` را تنظیم و Compose را اجرا کنید. Reverse proxy باید TLS، محدودیت درخواست و Hostnameهای واقعی را مدیریت کند. CORS را فقط روی Origin وب تنظیم کنید.

Worker اختیاری:

```bash
docker compose --profile scheduler up --build
```

قبل از ارتقا از Volume پایگاه داده Backup بگیرید و Migration را در Staging آزمایش کنید.

پیکربندی Staging از `.env.staging.example` شروع می‌شود و Secret واقعی باید در Secret
Store میزبان باشد. Fixture خاموش، CORS محدود و Debug غیرفعال بماند. برای Rollback از
Tag مبتنی بر SHA استفاده و پس از تعویض نسخه `/ready` بررسی شود. جزئیات GHCR و
Ephemeral Staging در `docs/staging-deployment.md` آمده است.
