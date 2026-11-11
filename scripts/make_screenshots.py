"""Съёмка скриншотов и скринкаста Streamlit UI через Playwright.

Запуск (при работающих backend и streamlit):
    python scripts/make_screenshots.py
Результат: docs/screenshots/*.png, docs/screencast/*.png, docs/screencast.webm
"""
import time
from datetime import date
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright

BASE = "http://localhost:8501"
API = "http://localhost:8000"
DEMO_IMAGE_URL = "https://placehold.co/1080x1080.jpg"
OUT = Path(__file__).resolve().parents[1] / "docs"
SHOTS = OUT / "screenshots"
CAST = OUT / "screencast"
SHOTS.mkdir(parents=True, exist_ok=True)
CAST.mkdir(parents=True, exist_ok=True)


def wait_streamlit(page, timeout=40):
    page.wait_for_load_state("networkidle", timeout=timeout * 1000)
    time.sleep(2.5)


def seed_demo_workflow():
    """Populate a demo project so screenshots show actual feature output."""
    health = requests.get(f"{API}/health", timeout=15)
    health.raise_for_status()
    if health.json().get("posting_mode") != "demo":
        raise RuntimeError("Съёмка создаёт демо-записи; задайте POSTING_MODE=demo")

    project = requests.post(f"{API}/api/projects", json={
        "name": "ContentPilot — демо для скриншотов",
        "niche": "контент-маркетинг",
        "target_audience": "маркетологи и контент-менеджеры",
        "tone_of_voice": "expert",
    }, timeout=30)
    project.raise_for_status()
    project_id = project.json()["id"]

    plans = requests.post(f"{API}/api/plans/generate", json={
        "project_id": project_id,
        "month": date.today().strftime("%Y-%m"),
        "channels": ["instagram"],
        "posts_per_week": 1,
    }, timeout=60)
    plans.raise_for_status()
    instagram_plan = next((p for p in plans.json() if p["channel"] == "instagram"), None)
    if not instagram_plan:
        raise RuntimeError("Не удалось создать Instagram-план для демо-съёмки")

    content = requests.post(f"{API}/api/content/generate", json={
        "plan_id": instagram_plan["id"],
        "variants": 2,
        "media_url": DEMO_IMAGE_URL,
    }, timeout=60)
    content.raise_for_status()
    variants = content.json()
    if len(variants) != 2:
        raise RuntimeError("Для демо-съёмки ожидались варианты A и B")

    for item in variants:
        response = requests.post(f"{API}/api/publish", json={"content_id": item["id"]}, timeout=60)
        response.raise_for_status()
    requests.post(f"{API}/api/analytics/sync-metrics", timeout=60).raise_for_status()
    test = requests.post(f"{API}/api/ab-tests", json={
        "project_id": project_id,
        "name": "Демо: сравнение вариантов A/B",
        "hypothesis": "Вариант B повысит вовлечённость.",
        "content_a_id": variants[0]["id"],
        "content_b_id": variants[1]["id"],
        "metric": "engagement",
    }, timeout=30)
    test.raise_for_status()
    requests.post(f"{API}/api/ab-tests/{test.json()['id']}/evaluate", timeout=60).raise_for_status()


def main():
    seed_demo_workflow()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        # --- Скриншоты (статичные) ---
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(BASE)
        wait_streamlit(page)
        page.get_by_role("tab", name="Проекты").click()
        wait_streamlit(page, 20)
        page.screenshot(path=SHOTS / "01_projects.png", full_page=True)

        page.get_by_role("tab", name="Контент-план").click()
        wait_streamlit(page, 20)
        page.screenshot(path=SHOTS / "02_content_plan.png", full_page=True)

        page.get_by_role("tab", name="Создание контента").click()
        wait_streamlit(page, 20)
        page.get_by_role("textbox", name="Публичный HTTPS URL изображения для Instagram",
                         exact=True).fill(DEMO_IMAGE_URL)
        page.get_by_role("button", name="Сгенерировать варианты A и B").click()
        wait_streamlit(page, 30)
        page.screenshot(path=SHOTS / "03_content_generation.png", full_page=True)

        page.get_by_role("tab", name="Автопостинг").click()
        wait_streamlit(page, 20)
        page.get_by_role("button", name="Опубликовать").click()
        wait_streamlit(page, 20)
        page.screenshot(path=SHOTS / "04_autoposting.png", full_page=True)

        page.get_by_role("tab", name="Аналитика").click()
        wait_streamlit(page, 20)
        page.get_by_role("button", name="Синхронизировать метрики со всех каналов").click()
        wait_streamlit(page, 20)
        page.screenshot(path=SHOTS / "05_analytics.png", full_page=True)

        page.get_by_role("tab", name="A/B-тесты").click()
        wait_streamlit(page, 20)
        page.screenshot(path=SHOTS / "06_ab_tests.png", full_page=True)

        api = browser.new_page(viewport={"width": 1440, "height": 900})
        api.goto("http://localhost:8000/docs")
        api.wait_for_load_state("networkidle")
        api.screenshot(path=SHOTS / "07_fastapi_docs.png", full_page=False)

        # --- Скринкаст: полный пользовательский сценарий ---
        ctx = browser.new_context(
            viewport={"width": 1440, "height": 900},
            record_video_dir=str(CAST), record_video_size={"width": 1440, "height": 900},
        )
        v = ctx.new_page()
        v.goto(BASE)
        wait_streamlit(v, 40)

        # 1. Новый проект (в Streamlit label — отдельный элемент, поэтому кликаем по контейнеру)
        v.get_by_role("tab", name="Проекты").click()
        wait_streamlit(v, 20)

        def st_fill(label: str, value: str):
            v.get_by_role("textbox", name=label, exact=True).fill(value)

        st_fill("Название бренда", "Фитнес-студия «Пульс»")
        st_fill("Ниша", "фитнес и здоровый образ жизни")
        st_fill("Целевая аудитория", "женщины и мужчины 20–45 лет")
        v.get_by_role("button", name="Создать проект", exact=True).click()
        wait_streamlit(v, 25)
        v.screenshot(path=CAST / "step1_project_created.png", full_page=True)

        # 2. Генерация контент-плана
        v.get_by_role("tab", name="Контент-план").click()
        wait_streamlit(v, 20)
        v.get_by_role("button", name="Сгенерировать план через AI").click()
        wait_streamlit(v, 30)
        v.screenshot(path=CAST / "step2_plan_generated.png", full_page=True)

        # 3. Генерация A/B текстов
        v.get_by_role("tab", name="Создание контента").click()
        wait_streamlit(v, 20)
        image_input = v.get_by_role("textbox", name="Публичный HTTPS URL изображения для Instagram",
                                    exact=True)
        if image_input.count():
            image_input.fill(DEMO_IMAGE_URL)
        v.get_by_role("button", name="Сгенерировать варианты A и B").click()
        wait_streamlit(v, 30)
        v.screenshot(path=CAST / "step3_ab_variants.png", full_page=True)

        # 4. Публикация
        v.get_by_role("tab", name="Автопостинг").click()
        wait_streamlit(v, 20)
        v.get_by_role("button", name="Опубликовать").click()
        wait_streamlit(v, 30)
        v.screenshot(path=CAST / "step4_published.png", full_page=True)

        # 5. Аналитика
        v.get_by_role("tab", name="Аналитика").click()
        wait_streamlit(v, 20)
        v.get_by_role("button", name="Синхронизировать метрики со всех каналов").click()
        wait_streamlit(v, 30)
        v.screenshot(path=CAST / "step5_analytics.png", full_page=True)

        # 6. A/B тест
        v.get_by_role("tab", name="A/B-тесты").click()
        wait_streamlit(v, 20)
        v.get_by_role("button", name="Создать тест").click()
        wait_streamlit(v, 25)
        v.get_by_role("button", name="Подвести итоги").click()
        wait_streamlit(v, 30)
        v.screenshot(path=CAST / "step6_ab_result.png", full_page=True)

        video = v.video
        ctx.close()
        browser.close()

        if video is None:
            raise RuntimeError("Playwright не создал запись скринкаста")
        video_path = Path(video.path())
        video_path.replace(OUT / "screencast.webm")
        print("Screencast:", OUT / "screencast.webm")
    print("Done. See docs/screenshots and docs/screencast")


if __name__ == "__main__":
    main()
