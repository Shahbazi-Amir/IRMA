"""Persian RTL Streamlit interface for IRMA."""

from __future__ import annotations

import os
from typing import Any

import httpx
import streamlit as st

API_BASE = os.getenv("IRMA_API_BASE_URL", "http://localhost:8000").rstrip("/")
TIMEOUT = 15.0

st.set_page_config(page_title="IRMA", page_icon="📊", layout="wide")
st.markdown(
    """
    <style>
    html, body, [class*="css"] { direction: rtl; text-align: right; }
    .stMetric, .stAlert, .stDataFrame { direction: rtl; }
    div[data-testid="stSidebar"] { direction: rtl; }
    </style>
    """,
    unsafe_allow_html=True,
)

WARNING = (
    "این سامانه تضمین سود نمی‌دهد و جایگزین مشاوره مالی دارای مجوز نیست. "
    "عملکرد گذشته تضمین آینده نیست و داده‌ها ممکن است ناقص یا با تأخیر باشند."
)


def get_json(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    with httpx.Client(timeout=TIMEOUT) as client:
        response = client.get(f"{API_BASE}{path}", params=params)
        response.raise_for_status()
        return response.json()


def post_json(
    path: str,
    payload: dict[str, Any],
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    with httpx.Client(timeout=TIMEOUT) as client:
        response = client.post(f"{API_BASE}{path}", json=payload, headers=headers)
        response.raise_for_status()
        return response.json()


def money(value: float | int | str) -> str:
    return f"{float(value):,.0f} تومان"


def api_error(exc: Exception) -> None:
    st.error(f"ارتباط با API ناموفق بود: {exc}")


def page_home() -> None:
    st.title("IRMA — تحلیل بازار، ریسک و سرمایه‌گذاری ایران")
    st.info(WARNING)
    st.write(
        "IRMA یک ابزار پژوهشی برای ثبت پروفایل سرمایه‌گذار، محاسبات مالی و ارائه "
        "پیشنهاد آزمایشی مبتنی بر قواعد است."
    )
    try:
        info = get_json("/v1/info")
        status = get_json("/v1/data-sources/status")
        st.metric("نسخه", info["version"])
        st.caption(f"آخرین بررسی وضعیت داده: {status['checked_at']}")
        if not status["database_sources"]:
            st.warning(
                "داده‌ای وارد نشده است. برای آماده‌سازی داده واقعی اجرا کنید: "
                "`IRMA_FUND_PROVIDER=fipiran python scripts/bootstrap_data.py`"
            )
    except Exception as exc:
        api_error(exc)


def page_market_dashboard() -> None:
    st.title("داشبورد چندبازاری")
    try:
        indices = get_json("/v1/market/indices", {"limit": 10})
        inflation = get_json("/v1/economy/inflation", {"limit": 1})
        banks = get_json("/v1/bank-products", {"limit": 10})
        cols = st.columns(3)
        cols[0].metric("رکورد شاخص", indices["count"])
        cols[1].metric("رکورد تورم رسمی", inflation["count"])
        cols[2].metric("محصول بانکی معتبر", banks["count"])
        if indices["items"]:
            st.subheader("شاخص‌های بازار")
            st.dataframe(indices["items"], use_container_width=True, hide_index=True)
        else:
            st.warning("داده معتبر شاخص موجود نیست؛ مقدار حدسی نمایش داده نمی‌شود.")
        if inflation["items"]:
            st.subheader("تورم رسمی")
            st.dataframe(inflation["items"], use_container_width=True, hide_index=True)
        if banks["items"]:
            st.subheader("شرایط فعلی و تأییدشده بانکی")
            st.dataframe(banks["items"], use_container_width=True, hide_index=True)
            st.caption("نرخ فعلی تضمین بازده آینده نیست و تاریخ اعتبار باید بررسی شود.")
    except Exception as exc:
        api_error(exc)


def page_asset_classes() -> None:
    st.title("مقایسه کلاس‌های دارایی")
    try:
        payload = get_json("/v1/asset-classes/comparison")
        st.dataframe(payload["items"], use_container_width=True, hide_index=True)
        st.caption(payload["notice"])
        st.info(
            "مقدار null یعنی داده کافی موجود نیست؛ نرخ تاریخی، شرط فعلی، فرض سناریو و "
            "پیشنهاد قاعده‌محور مفاهیم جداگانه‌اند."
        )
    except Exception as exc:
        api_error(exc)


def profile_form() -> dict[str, Any] | None:
    with st.form("investor-profile"):
        capital = st.number_input(
            "کل سرمایه (تومان)", min_value=1_000_000, value=50_000_000, step=500_000
        )
        monthly = st.number_input("سرمایه‌گذاری ماهانه (تومان)", min_value=0, value=0, step=100_000)
        horizon_labels = {
            "چندروزه": "days",
            "یک تا چهار هفته": "one_to_four_weeks",
            "یک تا سه ماه": "one_to_three_months",
            "سه تا شش ماه": "three_to_six_months",
            "شش ماه تا یک سال": "six_to_twelve_months",
            "یک تا سه سال": "one_to_three_years",
            "سه تا پنج سال": "three_to_five_years",
            "بیشتر از پنج سال": "over_five_years",
        }
        horizon_label = st.selectbox("افق زمانی", list(horizon_labels))
        risk_labels = {"محافظه‌کار": "conservative", "متوسط": "moderate", "ریسک‌پذیر": "aggressive"}
        risk_label = st.selectbox("ریسک‌پذیری", list(risk_labels), index=1)
        max_drawdown = st.slider("حداکثر افت قابل‌تحمل", 0, 60, 20) / 100
        liquidity_labels = {"کم": "low", "متوسط": "medium", "زیاد": "high"}
        liquidity_label = st.selectbox("نیاز به نقدشوندگی", list(liquidity_labels), index=1)
        needs_income = st.checkbox("نیاز به درآمد ماهانه")
        experience_labels = {
            "بدون تجربه": "none",
            "مبتدی": "beginner",
            "متوسط": "intermediate",
            "حرفه‌ای": "advanced",
        }
        experience_label = st.selectbox("تجربه سرمایه‌گذاری", list(experience_labels), index=1)
        trading_label = st.selectbox("تجربه معامله‌گری", list(experience_labels))
        style_labels = {"غیرفعال": "passive", "متعادل": "balanced", "فعال": "active"}
        style_label = st.selectbox("سبک سرمایه‌گذاری", list(style_labels), index=1)
        wants_trading = st.checkbox("تمایل به نوسان‌گیری پژوهشی")
        max_trading = st.slider("حداکثر درصد بخش کوتاه‌مدت", 0, 20, 5, disabled=not wants_trading)
        emergency = st.checkbox("صندوق اضطراری دارم")
        goal = st.text_input("هدف سرمایه‌گذاری", value="رشد سرمایه")
        submitted = st.form_submit_button("ساخت پیشنهاد")
    if not submitted:
        return None
    return {
        "capital_toman": capital,
        "monthly_contribution_toman": monthly,
        "horizon": horizon_labels[horizon_label],
        "risk_tolerance": risk_labels[risk_label],
        "max_drawdown_tolerance": max_drawdown,
        "needs_monthly_income": needs_income,
        "liquidity_need": liquidity_labels[liquidity_label],
        "experience": experience_labels[experience_label],
        "trading_experience": experience_labels[trading_label],
        "investment_style": style_labels[style_label],
        "wants_trading": wants_trading,
        "max_trading_percent": max_trading if wants_trading else 0,
        "has_emergency_fund": emergency,
        "goal": goal,
        "current_assets": [],
    }


def page_profile() -> None:
    st.title("پروفایل سرمایه‌گذار")
    payload = profile_form()
    if payload:
        try:
            st.session_state["recommendation"] = post_json("/v1/recommendations", payload)
            st.success("پروفایل تحلیل شد. صفحه «پیشنهاد سبد» را باز کنید.")
        except Exception as exc:
            api_error(exc)


def page_recommendation() -> None:
    st.title("پیشنهاد سبد")
    result = st.session_state.get("recommendation")
    if not result:
        st.warning("ابتدا فرم پروفایل سرمایه‌گذار را تکمیل کنید.")
        return
    st.info(result["disclaimer"])
    rows = []
    for item in result["allocations"]:
        rows.append(
            {
                "دسته": item["category"],
                "درصد": item["percent"],
                "مبلغ": money(item["amount_toman"]),
                "ریسک": item["risk"],
                "نقدشوندگی": item["liquidity"],
                "نگهداری": item["suggested_holding"],
                "روش ورود": item["entry_method"],
                "دلیل": item["reason"],
                "ابزارهای واجد شرایط": "، ".join(
                    suggestion["name_fa"] for suggestion in item.get("instruments", [])
                )
                or "به‌دلیل نبود داده کافی، ابزار مشخص پیشنهاد نشد",
            }
        )
    st.dataframe(rows, use_container_width=True, hide_index=True)
    st.bar_chart({row["دسته"]: row["درصد"] for row in rows})
    st.subheader("قواعد اعمال‌شده")
    for rule in result["applied_rules"]:
        st.write(f"• {rule}")
    st.caption(f"زمان پیشنهادی بازبینی: {result['review_at']}")
    for data in result["data_used"]:
        st.caption(f"منبع: {data['source']} | کیفیت: {data['quality']} | {data['note']}")
    with st.expander("برنامه بازبینی و تعادل مجدد"):
        st.write("بازبینی عادی هر سه ماه و هشدار انحراف در ۵ واحد درصد.")
        st.caption("اصلاح با واریز جدید بر فروش غیرضروری اولویت دارد.")


def page_funds() -> None:
    st.title("مقایسه صندوق‌ها")
    tabs = st.tabs(["درآمد ثابت", "سهامی", "طلا", "شاخصی", "مختلط", "اهرمی"])
    types = ["fixed_income", "equity", "gold", "index", "mixed", "leveraged"]
    for tab, fund_type in zip(tabs, types, strict=True):
        with tab:
            query = st.text_input("جست‌وجو", key=f"search-{fund_type}")
            try:
                payload = get_json("/v1/funds", {"fund_type": fund_type, "query": query or None})
                if payload["items"]:
                    labels = {
                        "live": "🟢 زنده",
                        "official_file": "🔵 فایل رسمی",
                        "fallback_live": "🟡 منبع جایگزین",
                        "last_known_good": "🟠 آخرین داده معتبر",
                        "stale": "🟠 قدیمی",
                        "unavailable": "⚪ ناموجود",
                    }
                    for item in payload["items"]:
                        item["وضعیت منبع"] = labels.get(
                            item.get("source_status"), item.get("source_status")
                        )
                    st.dataframe(payload["items"], use_container_width=True, hide_index=True)
                    ranking = get_json("/v1/funds/rankings", {"fund_type": fund_type})
                    if ranking["items"]:
                        st.subheader("رتبه‌بندی داده‌محور")
                        st.dataframe(ranking["items"], use_container_width=True, hide_index=True)
                        st.caption(
                            f"نسخه روش: {ranking['ranking_version']} | "
                            f"داده واجد شرایط: {ranking['eligible_count']}"
                        )
                    else:
                        st.warning("تاریخچه معتبر و تازه برای رتبه‌بندی کافی نیست.")
                else:
                    st.warning(
                        "داده کافی موجود نیست و داده جعلی نمایش داده نمی‌شود. "
                        "فرمان آماده‌سازی: "
                        "`IRMA_FUND_PROVIDER=fipiran python scripts/bootstrap_data.py`"
                    )
                st.caption(payload["data_notice"])
            except Exception as exc:
                api_error(exc)
    st.subheader("صندوق‌های طلا: NAV در برابر قیمت بازار")
    try:
        gold = get_json("/v1/market/gold-funds")
        if gold["items"]:
            st.dataframe(gold["items"], use_container_width=True, hide_index=True)
        else:
            st.warning("داده بازار و نگاشت تأییدشده صندوق طلا موجود نیست.")
    except Exception as exc:
        api_error(exc)


def page_compound() -> None:
    st.title("ماشین‌حساب سود مرکب")
    st.info("نرخ واردشده فقط فرض محاسباتی است و بازده تضمینی نیست.")
    with st.form("compound"):
        principal = st.number_input("سرمایه اولیه", min_value=0, value=10_000_000, step=100_000)
        monthly = st.number_input("واریز ماهانه", min_value=0, value=1_000_000, step=100_000)
        rate = st.number_input("نرخ سالانه فرضی (درصد)", value=25.0, step=1.0) / 100
        inflation = st.number_input("تورم فرضی سالانه (درصد)", value=35.0, step=1.0) / 100
        months = st.slider("مدت (ماه)", 1, 360, 60)
        compounding = st.selectbox("دوره مرکب‌شدن", ["monthly", "annual"])
        submitted = st.form_submit_button("محاسبه")
    if submitted:
        try:
            result = post_json(
                "/v1/compound-interest",
                {
                    "principal_toman": principal,
                    "monthly_contribution_toman": monthly,
                    "annual_rate": rate,
                    "annual_inflation": inflation,
                    "months": months,
                    "compounding": compounding,
                },
            )
            cols = st.columns(4)
            cols[0].metric("ارزش نهایی اسمی", money(result["final_nominal_toman"]))
            cols[1].metric("ارزش واقعی", money(result["final_real_toman"]))
            cols[2].metric("مجموع واریز", money(result["total_contributions_toman"]))
            cols[3].metric("سود اسمی", money(result["nominal_profit_toman"]))
            st.line_chart(
                {
                    "اسمی": [item["nominal"] for item in result["timeline"]],
                    "واقعی": [item["real"] for item in result["timeline"]],
                }
            )
        except Exception as exc:
            api_error(exc)


def page_short_term() -> None:
    st.title("تحلیل کوتاه‌مدت پژوهشی")
    st.warning("این بخش فقط بک‌تست و Paper Trading است و سیگنال قطعی خرید یا فروش تولید نمی‌کند.")
    st.write(
        "برای اجرای بک‌تست، داده معتبر روزانه شامل تاریخ، قیمت پایانی، حجم، ارزش معاملات و قابلیت معامله لازم است."
    )
    st.write("استراتژی‌ها: میانگین متحرک، مومنتوم، بازگشت به میانگین و شکست محدوده.")
    st.info("در نسخه فعلی داده بازار داخلی به‌صورت خودکار متصل نیست؛ API بک‌تست ورودی صریح می‌پذیرد.")


def page_long_term() -> None:
    st.title("تحلیل بلندمدت")
    st.write("معیارها شامل CAGR، بازده واقعی، بیشترین افت، زمان بازیابی، ثبات و کیفیت داده است.")
    try:
        payload = get_json("/v1/funds", {})
        if not payload["items"]:
            st.warning("داده تاریخی کافی برای رتبه‌بندی بلندمدت موجود نیست.")
        else:
            st.dataframe(payload["items"], use_container_width=True)
    except Exception as exc:
        api_error(exc)


def page_data_status() -> None:
    st.title("وضعیت داده‌ها")
    try:
        payload = get_json("/v1/data-sources/status")
        st.subheader("منابع ثبت‌شده")
        if payload["database_sources"]:
            st.dataframe(payload["database_sources"], use_container_width=True, hide_index=True)
        else:
            st.warning(
                "هنوز داده معتبر وارد نشده است. اجرا کنید: "
                "`IRMA_FUND_PROVIDER=fipiran python scripts/bootstrap_data.py`"
            )
        st.subheader("Adapterهای در انتظار اتصال")
        st.dataframe(payload["unavailable_adapters"], use_container_width=True, hide_index=True)
    except Exception as exc:
        api_error(exc)
        return
    with st.expander("به‌روزرسانی مدیریتی"):
        admin_key = st.text_input("کلید مدیر", type="password")
        if st.button("اجرای Refresh داده صندوق‌ها"):
            try:
                result = post_json(
                    "/v1/admin/data-refresh",
                    {},
                    headers={"X-IRMA-Admin-Key": admin_key},
                )
                st.success(result)
            except Exception as exc:
                api_error(exc)


def page_about() -> None:
    st.title("درباره و روش‌شناسی")
    st.markdown(
        """
        - پیشنهاد سبد با قواعد نسخه‌بندی‌شده و قابل‌آزمایش ساخته می‌شود.
        - داده مفقود صفر تلقی نمی‌شود و نبود داده صریح نمایش داده می‌شود.
        - بازده اسمی، واقعی، تاریخی و سناریویی از یکدیگر جدا هستند.
        - بخش کوتاه‌مدت فقط پژوهشی است و به کارگزاری متصل نمی‌شود.
        - پیش از تصمیم نهایی باید اطلاعات از منبع رسمی بررسی شود.
        """
    )


PAGES = {
    "خانه": page_home,
    "داشبورد بازار": page_market_dashboard,
    "مقایسه کلاس‌های دارایی": page_asset_classes,
    "پروفایل سرمایه‌گذار": page_profile,
    "پیشنهاد سبد": page_recommendation,
    "مقایسه صندوق‌ها": page_funds,
    "سود مرکب": page_compound,
    "تحلیل کوتاه‌مدت": page_short_term,
    "تحلیل بلندمدت": page_long_term,
    "وضعیت داده‌ها": page_data_status,
    "درباره و روش‌شناسی": page_about,
}

selected = st.sidebar.radio("صفحه", list(PAGES))
PAGES[selected]()
st.sidebar.caption(WARNING)
