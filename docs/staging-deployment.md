# استقرار Staging

در این فاز Credential سرویس خارجی داخل مخزن وجود ندارد؛ بنابراین Staging خارجی
انجام‌شده ادعا نمی‌شود. Workflow `Publish and Ephemeral Staging` پس از Merge، Imageها
را با `GITHUB_TOKEN` در GHCR منتشر و Compose ایزوله را با PostgreSQL، Migration، API
و Web اجرا می‌کند.

برای Staging خارجی، یک میزبان Docker-compatible، DNS/HTTPS و Secretهای
`IRMA_DATABASE_URL`، `IRMA_DB_PASSWORD`، `IRMA_ADMIN_KEY` و `IRMA_CORS_ORIGINS`
لازم است. `.env.staging.example` مبناست. Fixture باید خاموش باشد. Migration پیش از
تعویض ترافیک اجرا، `/ready` بررسی و نسخه قبلی Image برای Rollback حفظ شود.

Imageها:

```text
ghcr.io/shahbazi-amir/irma-api:{main,latest,sha-<commit>}
ghcr.io/shahbazi-amir/irma-web:{main,latest,sha-<commit>}
```
