"""Съёмка скриншотов и скринкаста Streamlit UI через Playwright.

Запуск (при работающих backend и streamlit):
    python scripts/make_screenshots.py
Результат: docs/screenshots/*.png, docs/screencast/*.png, docs/screencast.webm
"""
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://localhost:8501"
OUT = Path(__file__).resolve().parents[1] / "docs"
SHOTS = OUT / "screenshots"
CAST = OUT / "screencast"
SHOTS.mkdir(parents=True, exist_ok=True)
CAST.mkdir(parents=True, exist_ok=True)


def wait_streamlit(page, timeout=40):
    page.wait_for_load_state("networkidle", timeout=timeout * 1000)
    time.sleep(2.5)


def main():
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
        page.screenshot(path=SHOTS / "03_content_generation.png", full_page=True)

        page.get_by_role("tab", name="Автопостинг").click()
        wait_streamlit(page, 20)
        page.screenshot(path=SHOTS / "04_autoposting.png", full_page=True)

        page.get_by_role("tab", name="Аналитика").click()
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
            cont = v.locator(f"div[data-testid='stTextInput']:has(> div > label:text-is('{label}'))").first
            cont.locator("input").click()
            cont.locator("input").fill(value)

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

        ctx.close()
        browser.close()

        # Переименовываем видео в понятное имя
        vids = sorted(CAST.glob("**/webm/video.webm")) or sorted(CAST.rglob("*.webm"))
        if vids:
            vids[0].rename(OUT / "screencast.webm")
            print("🎬 Скринкаст:", OUT / "screencast.webm")
    print("📸 Готово. См. docs/screenshots и docs/screencast")


if __name__ == "__main__":
    main()
