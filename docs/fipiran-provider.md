# Provider صندوق FIPIRAN

قرارداد معتبر فعلی `services-v1` است:

- `POST /services/fund/fundcompare/`
- `GET /services/chart/getfundchart?regno=...&showAll=true`

## Catalogue identity

The Catalogue's `regNo` is not a row identity. The validated full-catalogue key is
`(regNo, groupId)`, persisted as `fipiran:{regNo}:{groupId}`. `insCode` is retained at
the provider boundary but is nullable, and `smallSymbolName` is not unique. Exact
duplicate rows with the same composite identity are ignored; conflicting rows with
the same composite identity are rejected as a contract violation.

The full-catalogue audit found 21 duplicated `regNo` values: 14 had groups `(1, 2)`,
six had `(1, 2, 3)`, and one had `(1, 2, 3, 4)`. Every duplicated `regNo` included
group 1. `regNo` and symbol therefore fail uniqueness; `insCode` cannot be the primary
key because it is optional. `(regNo, groupId)` uniquely identified the audited rows;
the defensive `(regNo, groupId, insCode)` adds no identity value and would make null
handling part of the key.

The public History endpoint accepts only `regno`; no supported `groupId` or `insCode`
selector was found. IRMA therefore compares the newest History `cancelNav` and
`statisticalNav` with every Catalogue row sharing that `regNo`. History is written
only when exactly one row matches. Missing, mismatched, or ambiguous History is
reported in `history_errors` and never attached to another group.

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
