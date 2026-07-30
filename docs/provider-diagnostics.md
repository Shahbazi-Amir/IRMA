# تشخیص Provider

```bash
python scripts/diagnose_fipiran.py --catalog
python scripts/diagnose_fipiran.py --history 11215
python scripts/diagnose_fipiran.py --catalog --output artifacts/fipiran-diagnostics
```

درخواست‌ها محدود، timeout و retry قابل تنظیم و User-Agent شفاف است. JSON و Markdown
شامل Status، Redirect، Content-Type، اندازه، زمان، Hash و نمونه ۵۰۰کاراکتری
Sanitized هستند. Cookie، Authorization، Token، CSRF و Secret ثبت نمی‌شوند.

این ابزار Captcha یا حفاظت دسترسی را دور نمی‌زند و برای کشف Endpoint خصوصی نیست.
