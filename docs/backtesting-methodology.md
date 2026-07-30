# روش بک‌تست

ماژول `trading_engine` فقط پژوهشی و Paper Trading است. استراتژی‌های ساده: Moving Average، Momentum، Mean Reversion و Breakout.

سیگنال با داده‌های قبل از Bar اجرا ساخته و روی Bar بعدی اجرا می‌شود. فیلتر حجم، ارزش معاملات، Spread و Tradable بودن اعمال می‌شود. Fee، Slippage و نصف Spread در هزینه لحاظ می‌شوند.

خروجی شامل تعداد معامله، Win Rate، میانگین سود/زیان، Profit Factor، Expectancy، بازده، بازده سالانه، افت، Sharpe، زمان حضور و هزینه است.

Survivorship Bias، توقف نماد، صف و کیفیت داده باید در Dataset ورودی کنترل شوند؛ موتور به‌تنهایی این ریسک‌ها را حذف نمی‌کند.
