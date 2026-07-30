# امنیت

- `.env`، Token، Cookie، Credential و داده مالی خصوصی Commit نمی‌شوند.
- Endpoint Refresh بدون `IRMA_ADMIN_KEY` غیرفعال و با Header محافظت می‌شود؛ این محافظ حداقلی است.
- کلید مدیر با مقایسه constant-time بررسی و هرگز Log نمی‌شود.
- PostgreSQL روی Host Port ندارد.
- Containerها non-root هستند.
- CORS محدود و قابل‌تنظیم است.
- ورودی CSV اعتبارسنجی و هش می‌شود، اما فایل باید از منبع مورداعتماد تهیه شود.
- برای Production به Secret Manager، TLS، Authentication واقعی، Rate Limit و Audit Log مرکزی نیاز است.
- ADR آینده: احراز هویت OIDC، session کوتاه‌عمر، نقش `admin` و Audit مرکزی؛ این فاز
  حساب کاربری ناقص ایجاد نمی‌کند.
