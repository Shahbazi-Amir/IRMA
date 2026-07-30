# Observability

- Log تولید با JSON، زمان UTC و Request ID است.
- هر پاسخ `X-Request-ID` و `X-Response-Time-Ms` دارد.
- `/health` سلامت process، `/ready` اتصال دیتابیس و `/metrics` شمارنده‌های کم‌بعد را
  ارائه می‌کنند.
- Metrics شامل Refresh موفق/ناموفق، داده stale و ردشده و پیشنهاد دارای هشدار است.
- مقدار Admin Key، URL خصوصی دیتابیس یا محتوای پروفایل نباید Log شود.
