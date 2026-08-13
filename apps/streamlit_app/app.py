"""Beginner-first Persian RTL investment decision dashboard."""

from __future__ import annotations

import streamlit as st
from api_client import ApiUnavailable, get, post
from formatters import clean, friendly_date, percent, toman, toman_words

st.set_page_config(page_title="IRMA | تصمیم سرمایه‌گذاری", page_icon="🌱", layout="wide")
st.markdown(
    """
    <style>
    html,body,[data-testid="stAppViewContainer"],[data-testid="stSidebar"]{direction:rtl;text-align:right}
    [data-testid="stMarkdownContainer"], [data-testid="stAlert"], [data-testid="stForm"],
    [data-testid="stExpander"], [data-testid="stCaptionContainer"], [role="tablist"],
    [role="radiogroup"], label, p, h1, h2, h3 {direction:rtl;text-align:right}
    [data-baseweb="select"]>div, [data-baseweb="input"]>div {direction:rtl;text-align:right}
    [data-testid="stMetric"]{direction:rtl;text-align:right;overflow-wrap:anywhere}
    [data-testid="stMetricValue"]{font-size:1.25rem;line-height:1.6;white-space:normal}
    h1{font-size:1.8rem!important;line-height:1.6!important}h2{font-size:1.35rem!important;line-height:1.6!important}
    h3{font-size:1.1rem!important;line-height:1.65!important}p,span,label{line-height:1.8}
    button{min-height:2.8rem;white-space:normal!important}.block-container{max-width:1150px;padding-top:1.5rem}
    [data-testid="stHorizontalBlock"]{align-items:stretch}.irma-money{font-size:1rem;line-height:2;margin:.2rem 0 1rem}
    @media(max-width:700px){.block-container{padding:.75rem}.stColumn{min-width:100%!important}h1{font-size:1.45rem!important}h2{font-size:1.2rem!important}}
    </style>
    """,
    unsafe_allow_html=True,
)

NOTICE = "این تحلیل تضمین سود نیست؛ عملکرد گذشته آینده را تضمین نمی‌کند."
HORIZONS = {
    "یک هفته": ("days", 7),
    "یک ماه": ("one_to_four_weeks", 30),
    "سه ماه": ("one_to_three_months", 90),
    "شش ماه": ("three_to_six_months", 180),
    "یک سال": ("six_to_twelve_months", 365),
    "سه سال": ("one_to_three_years", 1095),
    "پنج سال": ("three_to_five_years", 1825),
}
RISKS = {"کم": "conservative", "متوسط": "moderate", "زیاد": "aggressive"}
ASSETS = {
    "صندوق درآمد ثابت": "fixed_income",
    "طلا و صندوق طلا": "gold",
    "صندوق شاخصی": "equity_index",
    "وجه نقد": "cash",
}
SOURCE_STATUS = {
    "fresh": "به‌روز",
    "valid": "معتبر",
    "stale": "قدیمی",
    "degraded": "ناقص",
    "missing": "ناموجود",
}


def gentle_error() -> None:
    st.warning(
        "دریافت داده جدید فعلاً موفق نبود. آخرین داده معتبر، در صورت وجود، همچنان قابل استفاده است."
    )


def market_strip() -> None:
    st.subheader("بازار در یک نگاه")
    try:
        inflation = get("/v1/economy/inflation", {"limit": 1})
        indices = get("/v1/market/indices", {"limit": 1})
        funds = get("/v1/funds", {"fund_type": "fixed_income"})
    except ApiUnavailable:
        gentle_error()
        return
    cards = [
        (
            "تورم",
            inflation["items"][0].get("annual_inflation") if inflation["items"] else None,
            "٪",
        ),
        ("شاخص بورس", indices["items"][0].get("close") if indices["items"] else None, "واحد"),
        ("درآمد ثابت", funds.get("count", 0) or None, "گزینه"),
        ("طلا و ارز", None, ""),
    ]
    for column, (label, value, unit) in zip(st.columns(4), cards, strict=True):
        column.metric(
            label, f"{clean(value)} {unit}" if value is not None else "داده معتبر موجود نیست"
        )


def render_decision(data: dict[str, object]) -> None:
    st.success("پیشنهاد متناسب با اطلاعات شما آماده شد")
    st.caption(data["notice"])
    st.subheader("بهترین گزینه‌ها برای شرایط شما")
    available = [item for item in data["candidates"] if item["numeric_scenario_allowed"]]
    if available:
        st.success(f"گزینه مناسب‌تر بر پایه داده موجود: {available[0]['label']}")
    else:
        st.info(
            "فعلاً داده کافی برای رتبه‌بندی عددی دارایی‌ها وجود ندارد؛ هیچ بازدهی حدس زده نشده است."
        )
    for item in data["candidates"]:
        with st.container(border=True):
            st.markdown(f"### {item['label']}")
            cols = st.columns(3)
            cols[0].metric("تناسب با شرایط شما", item["suitability"])
            cols[1].metric("ریسک", item["risk"])
            cols[2].metric("نقدشوندگی", item["liquidity"])
            if not item["numeric_scenario_allowed"]:
                st.info(item["withheld_reason"])
                st.caption(item["method"])
                continue
            scenario = item["scenario"]["median"]
            st.write("**سناریوی میانه در پنجره‌های تاریخی مشابه**")
            values = st.columns(3)
            values[0].metric("اصل سرمایه", toman(scenario["principal_toman"]))
            change_label = "سود تاریخی" if scenario["profit_loss_toman"] >= 0 else "زیان تاریخی"
            values[1].metric(change_label, toman(abs(scenario["profit_loss_toman"])))
            values[2].metric("مبلغ نهایی تاریخی", toman(scenario["final_value_toman"]))
            st.caption(
                f"تعداد پنجره‌ها: {clean(item['scenario']['sample_count'])} | "
                f"آخرین مشاهده: {friendly_date(item['latest_observation_at'])}"
            )
            st.caption("این اعداد شواهد تاریخی‌اند و پیش‌بینی یا تضمین آینده نیستند.")
            if item["fund_candidates"]:
                st.write(
                    "گزینه‌های دارای داده: " + "، ".join(x["name"] for x in item["fund_candidates"])
                )
    st.subheader("مقایسه نتیجه")
    st.dataframe(
        [
            {
                "گزینه": item["label"],
                "ریسک": item["risk"],
                "تناسب": item["suitability"],
                "سناریوی میانه": (
                    toman(item["scenario"]["median"]["final_value_toman"])
                    if item["scenario"]
                    else "داده کافی نیست"
                ),
                "وضعیت داده": "معتبر" if item["numeric_scenario_allowed"] else "ناکافی",
            }
            for item in data["candidates"]
        ],
        hide_index=True,
        width="stretch",
    )
    st.subheader("تخصیص پیشنهادی ثانویه")
    for item in data["allocation"]:
        if not item["available"]:
            continue
        with st.container(border=True):
            cols = st.columns([2, 1, 2])
            cols[0].markdown(f"### {item['label']}")
            cols[1].metric("سهم از سبد", percent(item["percent"]))
            cols[2].metric("مبلغ تخصیص‌یافته", toman(item["amount_toman"]))
            st.write(item["reason"])
            st.caption(f"ریسک: {item['risk']} | نقدشوندگی: {item['liquidity']}")
            if item["fund_candidates"]:
                st.write(
                    "گزینه‌های قابل بررسی: "
                    + "، ".join(fund["name"] for fund in item["fund_candidates"])
                )
    st.subheader("چرا این پیشنهاد؟")
    for step in data["decision_trace"]:
        st.write(f"• {step}")
    history = data["historical_context"]
    with st.expander("عملکرد تاریخی و سناریوی ضعیف"):
        if history["available"]:
            st.write(f"تعداد مشاهدات ذخیره‌شده: {clean(history['sample_count'])}")
        else:
            st.info("برای محاسبه سناریوی تاریخی هنوز داده کافی وجود ندارد.")
        st.caption(history["notice"])
    freshness = data["data_freshness"]
    label = {"fresh": "به‌روز", "degraded": "ناقص یا قدیمی", "missing": "هنوز دریافت نشده"}
    st.caption(
        f"وضعیت داده: {label.get(freshness['status'], 'نامشخص')} | "
        f"آخرین مشاهده: {friendly_date(freshness['latest_observation_at'])}"
    )


def investment_page() -> None:
    st.title("سرمایه‌گذاری شما")
    st.write("سه پاسخ کوتاه بدهید تا گزینه‌ها را متناسب با شرایط شما مقایسه کنیم.")
    market_strip()
    with st.form("simple-decision"):
        capital = st.number_input(
            "سرمایه قابل سرمایه‌گذاری (تومان)",
            min_value=1_000_000,
            max_value=1_000_000_000_000_000,
            value=500_000_000,
            step=10_000_000,
        )
        st.markdown(
            f'<div class="irma-money"><strong>{toman(capital)}</strong><br>{toman_words(capital)}</div>',
            unsafe_allow_html=True,
        )
        horizon_label = st.selectbox("برای چه مدتی؟", list(HORIZONS), index=2)
        risk_label = st.radio(
            "چه مقدار ریسک می‌پذیرید؟",
            list(RISKS),
            index=1,
            horizontal=True,
            help="کم: حفظ اصل سرمایه مهم‌تر است؛ متوسط: نوسان محدود پذیرفته می‌شود؛ زیاد: افت قابل توجه ممکن است.",
        )
        with st.expander("تنظیمات بیشتر"):
            monthly = st.number_input("سرمایه‌گذاری ماهانه", min_value=0, value=0, step=1_000_000)
            goal = st.selectbox("هدف", ["رشد سرمایه", "حفظ ارزش پول", "درآمد کم‌ریسک", "خرید خانه"])
            selected_asset_labels = st.multiselect(
                "این گزینه‌ها را بررسی کن",
                list(ASSETS),
                placeholder="پیش‌فرض: همه گزینه‌های قابل تحلیل",
            )
        submitted = st.form_submit_button("بررسی بهترین گزینه‌ها", width="stretch")
    if submitted:
        try:
            st.session_state["decision"] = post(
                "/v2/investment-decision",
                {
                    "capital_toman": capital,
                    "horizon": HORIZONS[horizon_label][0],
                    "horizon_days": HORIZONS[horizon_label][1],
                    "risk": RISKS[risk_label],
                    "monthly_contribution_toman": monthly,
                    "goal": goal,
                    "selected_assets": [ASSETS[label] for label in selected_asset_labels],
                },
            )
        except ApiUnavailable:
            gentle_error()
    if decision := st.session_state.get("decision"):
        render_decision(decision)
    with st.expander("ابزارهای بیشتر: محاسبه سود مرکب"):
        st.caption("نرخ این ابزار فرض کاربر است؛ بازده تاریخی یا پیش‌بینی نیست.")


def market_page() -> None:
    st.title("بازار و تاریخچه")
    current, history, funds_tab = st.tabs(["آخرین وضعیت", "رفتار تاریخی", "صندوق‌ها"])
    with current:
        market_strip()
        st.info("هر کارت فقط در صورت وجود داده معتبر نمایش داده می‌شود؛ مقدار مفقود صفر نیست.")
    with history:
        st.subheader("روند ارزش دارایی")
        st.info("پس از ورود سری تاریخی معتبر، بازه‌های ۱، ۳، ۵، ۱۰ سال و کل تاریخچه فعال می‌شوند.")
        st.toggle("نمایش بازده واقعی پس از تورم", disabled=True)
    with funds_tab:
        try:
            payload = get("/v1/funds")
            if not payload["items"]:
                st.info("هنوز داده معتبر صندوق‌ها دریافت نشده است.")
            for fund in payload["items"][:10]:
                with st.container(border=True):
                    st.write(f"**{fund['name_fa']}**")
                    st.caption(
                        f"آخرین NAV: {toman(fund['latest_nav'])} | وضعیت داده: "
                        f"{SOURCE_STATUS.get(fund['source_status'], 'نامشخص')}"
                    )
        except ApiUnavailable:
            gentle_error()


def profile_page() -> None:
    st.title("پروفایل و روش تحلیل")
    profile, method, data = st.tabs(["پروفایل ریسک", "روش تحلیل", "وضعیت داده"])
    with profile:
        st.write("پروفایل پایه با سه ورودی ساخته می‌شود؛ جزئیات پیشرفته اختیاری است.")
        st.warning("نوسان‌گیری حالتی جدا و پرریسک است و فقط با داده روزانه کافی فعال می‌شود.")
    with method:
        for text in [
            "افق و تحمل ریسک بررسی می‌شود.",
            "فقط داده معتبر وارد مقایسه می‌شود.",
            "بازده تاریخی از پیش‌بینی آینده جدا است.",
            "دلیل هر وزن ثبت می‌شود.",
        ]:
            st.write(f"• {text}")
    with data:
        try:
            status = get("/v1/data-sources/status")
            if not status["database_sources"]:
                st.info("هنوز داده معتبر وارد نشده است؛ بخش‌های مستقل همچنان کار می‌کنند.")
            for source in status["database_sources"]:
                st.write(f"**{source['name']}** — {source['status']}")
                st.caption(f"آخرین داده: {friendly_date(source['last_valid_observation_at'])}")
        except ApiUnavailable:
            gentle_error()


PAGES = {
    "سرمایه‌گذاری من": investment_page,
    "بازار و تاریخچه": market_page,
    "پروفایل و روش تحلیل": profile_page,
}
selected = st.sidebar.radio("بخش اصلی", list(PAGES))
PAGES[selected]()
st.sidebar.caption(NOTICE)
