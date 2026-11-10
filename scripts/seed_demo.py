"""Скрипт заполнения демо-данными (полный сквозной сценарий).

Запуск:  python scripts/seed_demo.py
Создаёт проект, каналы, контент-план на месяц, A/B тексты, публикации,
метрики и завершённый A/B-тест — всё это видно в UI и API сразу после запуска.
"""
import asyncio
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal, init_db  # noqa: E402
from app.models.models import (  # noqa: E402
    ABTest, Channel, ContentPlan, ContentType, PlanStatus, Project, SocialAccount,
)
from app.services.ai.content_generator import generate_content  # noqa: E402
from app.services.ai.plan_generator import generate_content_plan  # noqa: E402
from app.services.analytics.metrics import evaluate_ab_test, sync_metrics  # noqa: E402
from app.services.posting.adapters import publish_content  # noqa: E402


async def main():
    init_db()
    db = SessionLocal()
    try:
        project = Project(
            name="Кофейня «Бодрый день»",
            niche="спец-кофе и обжарка",
            description="Локальная обжарочная кофейня с подпиской на зерно",
            tone_of_voice="friendly",
            target_audience="офисные работники 25–40 лет, любители кофе",
            website="https://bodryday.example.ru",
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        print(f"✅ Проект #{project.id}: {project.name}")

        for ch, uname in [
            (Channel.telegram, "@bodry_day_news"),
            (Channel.vk, "-192837465"),
            (Channel.instagram, "bodry.day"),
            (Channel.wordpress, "blog.bodryday.ru"),
            (Channel.mailchimp, "aud_bodry_subscribers"),
        ]:
            db.add(SocialAccount(project_id=project.id, channel=ch,
                                 username=uname, token_masked="demo…oken"))
        db.commit()
        print("✅ Подключено 5 каналов")

        month = date.today().strftime("%Y-%m")
        plans = await generate_content_plan(
            db, project, month,
            [Channel.telegram, Channel.vk, Channel.instagram], posts_per_week=3)
        print(f"✅ Контент-план на {month}: {len(plans)} элементов")

        # Генерируем A/B тексты для первых 4 записей плана
        ab_pairs = []
        for plan in plans[:4]:
            variants = await generate_content(db, plan, project, variants=2)
            ab_pairs.append((plan, variants))
            print(f"   ✍️ #{plan.id} «{plan.topic[:50]}…» → варианты A/B")

        # Публикуем вариант A каждого поста + один пост во все каналы
        published = 0
        for plan, variants in ab_pairs:
            await publish_content(db, variants[0], [plan.channel])
            published += 1
        multi = ab_pairs[0][1][0]
        await publish_content(db, multi, [Channel.telegram, Channel.vk, Channel.instagram])
        print(f"✅ Публикаций создано: {published + 3} (в т.ч. мультиканальная)")

        # Утверждаем одну будущую запись — она уйдёт через автопостинг
        future = db.query(ContentPlan).filter(
            ContentPlan.project_id == project.id,
            ContentPlan.status == PlanStatus.generated,
        ).order_by(ContentPlan.plan_date.desc()).first()
        if future:
            future.status = PlanStatus.approved
            db.commit()
            print(f"⏳ Запись #{future.id} утверждена для автопостинга")

        n = sync_metrics(db)
        print(f"📊 Метрик насинхронизировано: {n}")

        # Создаём и подводим итоги A/B теста
        a = ab_pairs[0][1][0]
        b = ab_pairs[0][1][1]
        # публикуем B, чтобы накопить метрики
        await publish_content(db, b, [ab_pairs[0][0].channel])
        sync_metrics(db)
        t = ABTest(project_id=project.id, name="Hook эмодзи vs экспертный тон",
                   hypothesis="Экспертный подаёт лучший CTR среди офисной аудитории",
                   content_a_id=a.id, content_b_id=b.id, metric="engagement")
        db.add(t)
        db.commit()
        db.refresh(t)
        t = evaluate_ab_test(db, t)
        print(f"🧪 A/B тест #{t.id}: статус={t.status}, победитель={t.winner or '—'}, "
              f"результат={t.result_summary}")

        print("\n🎉 Демо-данные готовы. Откройте http://localhost:8000/docs и Streamlit UI.")
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
