# Provider صندوق FIPIRAN

قرارداد معتبر فعلی `services-v1` است:

- `POST /services/fund/fundcompare/`
- `GET /services/chart/getfundchart?regno=...&showAll=true`

انتخاب قرارداد با `IRMA_FIPIRAN_CONTRACT` انجام می‌شود. مقدار `auto` فقط میان
قراردادهایی انتخاب می‌کند که Fixture و تست مستقل دارند؛ قرارداد ناشناخته خودکار فعال
نمی‌شود. مسیرها، Base URL و User-Agent قابل تنظیم‌اند.

Client یک Session و Connection Pool محدود دارد. فقط خطاهای 408، 425، 429 و 5xx با
Backoff، Jitter و رعایت `Retry-After` تکرار می‌شوند. HTML، Captcha، Block Page،
Content-Type غیر JSON و Schema ناسازگار شکست قرارداد محسوب می‌شوند.

Circuit Breaker پس از تعداد شکست تنظیم‌شده باز می‌شود، در Cooling Period درخواست
نمی‌فرستد و سپس فقط یک درخواست آزمایشی می‌پذیرد. Fixture هرگز fallback تولید نیست.

بررسی ۳۰ ژوئیه ۲۰۲۶ از محیط Agent برای دامنه‌های عمومی با پاسخ HTML 502 از Proxy و
`Connection refused` شکست خورد. این نتیجه محدودیت مسیر شبکه را نشان می‌دهد و تغییر
Endpoint یا نیاز Header را اثبات نمی‌کند.
