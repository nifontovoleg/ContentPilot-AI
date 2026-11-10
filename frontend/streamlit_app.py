"""Streamlit UI — интерфейс контент-маркетолога.

Запуск:  streamlit run frontend/streamlit_app.py
UI общается с FastAPI backend (по умолчанию http://localhost:8000).
"""
import os

import pandas as pd
import requests
import streamlit as st

API = os.environ.get("API_BASE", "http://localhost:8000")


def api(method: str, path: str, json=None):
    try:
        r = requests.request(method, f"{API}{path}", json=json, timeout=60)
        if r.status_code >= 400:
            st.error(f"API {r.status_code}: {r.text[:300]}")
            return None
        return r.json()
    except requests.ConnectionError:
        st.error("Backend недоступен. Запустите: uvicorn app.main:app --port 8000")
        return None


st.set_page_config(page_title="AI Content Platform", page_icon="🤖", layout="wide")
st.title("🤖 AI-платформа для контент-маркетинга")

health = api("GET", "/health")
if health:
    st.caption(f"✅ Backend: {health['app']} · режим постинга: **{health['posting_mode']}**")

tab_projects, tab_plan, tab_create, tab_posting, tab_analytics, tab_ab = st.tabs(
    ["📁 Проекты", "🗓 Контент-план", "✍️ Создание контента",
     "🚀 Автопостинг", "📊 Аналитика", "🧪 A/B-тесты"]
)

# ---------------- Проекты ----------------
with tab_projects:
    st.subheader("Проекты (бренды)")
    with st.form("new_project"):
        name = st.text_input("Название бренда", "Кофейня «Бодрый день»")
        niche = st.text_input("Ниша", "спец-кофе и обжарка")
        audience = st.text_input("Целевая аудитория", "офисные работники 25–40 лет")
        tone = st.selectbox("Tone of voice", ["friendly", "expert", "playful", "premium"])
        submitted = st.form_submit_button("Создать проект")
        if submitted:
            p = api("POST", "/api/projects", json={
                "name": name, "niche": niche, "target_audience": audience, "tone_of_voice": tone})
            if p:
                st.success(f"Проект #{p['id']} создан")
    projects = api("GET", "/api/projects") or []
    if projects:
        st.dataframe(pd.DataFrame(projects)[["id", "name", "niche", "tone_of_voice"]], hide_index=True)

    st.subheader("Подключённые каналы")
    pid = st.number_input("ID проекта", min_value=1, value=projects[0]["id"] if projects else 1)
    with st.form("new_account"):
        c1, c2 = st.columns([1, 2])
        channel = c1.selectbox("Канал", ["telegram", "vk", "instagram", "wordpress", "mailchimp"])
        username = c2.text_input("Имя аккаунта / chat_id / audience_id", "@bodry_day")
        token = st.text_input("Токен доступа (хранится замаскированным)", type="password")
        add_acc = st.form_submit_button("Подключить")
        if add_acc:
            acc = api("POST", f"/api/projects/{int(pid)}/accounts",
                      json={"channel": channel, "username": username, "token": token})
            if acc:
                st.success("Аккаунт подключён (токен замаскирован)")
    accounts = api("GET", f"/api/projects/{int(pid)}/accounts") or []
    if accounts:
        st.dataframe(pd.DataFrame(accounts)[["id", "channel", "username", "token_masked", "is_active"]],
                     hide_index=True)

# ---------------- Контент-план ----------------
with tab_plan:
    st.subheader("🗓 AI-контент-план на месяц")
    with st.form("gen_plan"):
        pids = [p["id"] for p in projects]
        if pids:
            pid2 = st.selectbox("Проект", pids,
                                format_func=lambda i: next(p["name"] for p in projects if p["id"] == i))
        else:
            pid2 = st.number_input("ID проекта", value=1)
        month = st.text_input("Месяц (YYYY-MM)", "2026-11")
        channels = st.multiselect("Каналы", ["telegram", "vk", "instagram", "wordpress", "mailchimp"],
                                  default=["telegram", "vk", "instagram"])
        per_week = st.slider("Постов в неделю", 1, 5, 3)
        gen = st.form_submit_button("✨ Сгенерировать план через AI")
    if gen:
        res = api("POST", "/api/plans/generate", json={
            "project_id": int(pid2), "month": month,
            "channels": channels, "posts_per_week": per_week})
        if res:
            st.success(f"Сгенерировано элементов плана: {len(res)}")
    plans = api("GET", "/api/plans") or []
    if plans:
        df = pd.DataFrame(plans)
        show = df[["id", "plan_date", "channel", "content_type", "topic", "holiday", "trend", "status"]]
        st.dataframe(show, hide_index=True, use_container_width=True)
        st.caption("Элементы с заполненными полями holiday/trend привязаны к праздникам и трендам.")
        aid = st.selectbox("ID элемента плана для утверждения → автопостинга", df["id"].tolist())
        if st.button("✅ Утвердить элемент"):
            api("PATCH", f"/api/plans/{int(aid)}/approve")
            st.rerun()

# ---------------- Создание контента ----------------
with tab_create:
    st.subheader("✍️ Генерация контента по элементу плана (A/B варианты)")
    plans_all = api("GET", "/api/plans") or []
    if plans_all:
        pdf = pd.DataFrame(plans_all)
        sel = st.selectbox(
            "Элемент плана", pdf["id"].tolist(),
            format_func=lambda i: f"#{i} · {pdf[pdf.id == i]['topic'].iloc[0][:70]}"
        )
        if st.button("🤖 Сгенерировать варианты A и B"):
            res = api("POST", "/api/content/generate", json={"plan_id": int(sel), "variants": 2})
            if res:
                for c in res:
                    with st.expander(f"Вариант {c['variant_tag']} · {c['model_used']}"):
                        st.markdown(f"**{c['title']}**\n\n{c['body']}")
    st.divider()
    st.subheader("Быстрая генерация по брифу")
    with st.form("brief"):
        bpid = st.number_input("ID проекта", min_value=1, value=1)
        bch = st.selectbox("Канал", ["telegram", "vk", "instagram", "wordpress", "mailchimp"])
        btype = st.selectbox("Тип", ["post", "article", "email"])
        btopic = st.text_input("Тема", "Как выбрать зерно для гейши")
        if st.form_submit_button("Сгенерировать"):
            res = api("POST", "/api/content/brief", json={
                "project_id": int(bpid), "channel": bch, "content_type": btype, "topic": btopic})
            if res:
                st.markdown(f"**{res['title']}**\n\n{res['body']}")

# ---------------- Автопостинг ----------------
with tab_posting:
    st.subheader("🚀 Публикации")
    contents = api("GET", "/api/content") or []
    if contents:
        cdf = pd.DataFrame(contents)
        cid = st.selectbox("Контент для публикации", cdf["id"].tolist(),
                           format_func=lambda i: f"#{i} [{cdf[cdf.id == i]['variant_tag'].iloc[0]}] "
                                                 f"{cdf[cdf.id == i]['title'].iloc[0][:60]}")
        multich = st.multiselect("Каналы (пусто = канал из плана)",
                                 ["telegram", "vk", "instagram", "wordpress", "mailchimp"])
        if st.button("📤 Опубликовать"):
            res = api("POST", "/api/publish",
                      json={"content_id": int(cid), "channels": multich or None})
            if res:
                st.dataframe(pd.DataFrame(res)[["channel", "status", "external_id", "mode"]],
                             hide_index=True)
    if st.button("⏰ Запустить автопостинг утверждённых записей со наступившей датой"):
        res = api("POST", "/api/autopost/run-due")
        st.info(f"Опубликовано планов: {len(res['posted_plans']) if res else 0}")
    pubs = api("GET", "/api/publications") or []
    if pubs:
        st.subheader("Журнал публикаций")
        st.dataframe(pd.DataFrame(pubs)[["id", "content_id", "channel", "status",
                                         "external_id", "published_at"]].head(20), hide_index=True)

# ---------------- Аналитика ----------------
with tab_analytics:
    st.subheader("📊 Аналитика эффективности")
    if st.button("🔄 Синхронизировать метрики со всех каналов"):
        api("POST", "/api/analytics/sync-metrics")
    dash = api("GET", "/api/analytics/dashboard") or []
    if dash:
        ddf = pd.DataFrame(dash)
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Всего просмотров", int(ddf["views"].sum()))
        m2.metric("Лайки", int(ddf["likes"].sum()))
        m3.metric("Комментарии", int(ddf["comments"].sum()))
        m4.metric("Шеры", int(ddf["shares"].sum()))
        st.bar_chart(ddf.set_index("channel")["views"])
        st.dataframe(ddf, hide_index=True)
        top = api("GET", "/api/analytics/top") or []
        if top:
            st.subheader("🏆 Топ по вовлечённости")
            st.dataframe(pd.DataFrame(top), hide_index=True)
    else:
        st.info("Нет данных. Сначала опубликуйте контент и синхронизируйте метрики.")

# ---------------- A/B тесты ----------------
with tab_ab:
    st.subheader("🧪 A/B-тестирование")
    contents = api("GET", "/api/content") or []
    if len(contents) >= 2:
        cdf = pd.DataFrame(contents)

        def fmt(i):
            row = cdf[cdf.id == i].iloc[0]
            return f"#{i} [{row['variant_tag']}] {row['title'][:50]}"

        ca = st.selectbox("Вариант A", cdf["id"].tolist(), format_func=fmt)
        cb = st.selectbox("Вариант B", cdf["id"].tolist(), index=min(1, len(cdf) - 1), format_func=fmt)
        metric = st.selectbox("Метрика", ["engagement", "ctr", "open_rate"])
        name = st.text_input("Название теста", "Hook эмодзи vs экспертный тон")
        if st.button("Создать тест"):
            t = api("POST", "/api/ab-tests", json={
                "project_id": 1, "name": name, "content_a_id": int(ca),
                "content_b_id": int(cb), "metric": metric})
            if t:
                st.success(f"Тест #{t['id']} создан")
    tests = api("GET", "/api/ab-tests") or []
    if tests:
        st.dataframe(pd.DataFrame(tests)[["id", "name", "metric", "status", "winner"]], hide_index=True)
        tid = st.selectbox("ID теста для расчёта победителя", [t["id"] for t in tests])
        if st.button("🏁 Подвести итоги"):
            r = api("POST", f"/api/ab-tests/{int(tid)}/evaluate")
            if r:
                st.json(r["result_summary"])
                if r["winner"]:
                    st.success(f"🏆 Победитель — вариант **{r['winner']}** "
                               f"(лифт B к A: {r['result_summary']['lift_B_vs_A']:.1%})")
                else:
                    st.warning("Выборки пока недостаточно — протестируйте ещё публикации.")
