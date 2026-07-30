# امنیت

- `.env`، Token، Cookie، Credential و داده مالی خصوصی Commit نمی‌شوند.
- Endpoint Refresh بدون `IRMA_ADMIN_KEY` غیرفعال و با Header محافظت می‌شود؛ این محافظ حداقلی است.
- PostgreSQL روی Host Port ندارد.
- Containerها non-root هستند.
- CORS محدود و قابل‌تنظیم است.
- ورودی CSV اعتبارسنجی و هش می‌شود، اما فایل باید از منبع مورداعتماد تهیه شود.
- برای Production به Secret Manager، TLS، Authentication واقعی، Rate Limit و Audit Log مرکزی نیاز است.
