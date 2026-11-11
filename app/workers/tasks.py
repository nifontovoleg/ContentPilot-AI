"""Celery-приложение для фоновых задач (автопостинг, сбор метрик).

Запуск воркера:
    celery -A app.workers.tasks worker --loglevel=info
Beat (планировщик):
    celery -A app.workers.tasks beat
Без Redis/Celery платформа работает во встроенном планировщике APScheduler.
"""
from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "content_platform",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    timezone="Europe/Moscow",
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    beat_schedule={
        "daily-plan-generation": {
            "task": "app.workers.tasks.generate_plans_for_all_projects",
            "schedule": 24 * 3600.0,
        },
        "hourly-autoposting": {
            "task": "app.workers.tasks.run_due_posts",
            "schedule": 3600.0,
        },
        "hourly-metrics-sync": {
            "task": "app.workers.tasks.sync_all_metrics",
            "schedule": 3600.0,
        },
    },
)


@celery_app.task(name="app.workers.tasks.generate_plans_for_all_projects")
def generate_plans_for_all_projects():
    from datetime import date

    from app.db.session import SessionLocal
    from app.models.models import Project, Channel
    from app.services.ai.plan_generator import generate_content_plan
    import asyncio

    db = SessionLocal()
    try:
        month = date.today().strftime("%Y-%m")
        channels = [Channel.telegram, Channel.vk, Channel.instagram]
        for p in db.query(Project).all():
            asyncio.run(generate_content_plan(db, p, month, channels))
        return {"status": "ok", "month": month}
    finally:
        db.close()


@celery_app.task(name="app.workers.tasks.publish_content")
def publish_content_task(content_id: int):
    import asyncio

    from app.db.session import SessionLocal
    from app.models.models import Content
    from app.services.posting.adapters import publish_content

    db = SessionLocal()
    try:
        c = db.get(Content, content_id)
        if not c:
            return {"error": "content not found"}
        pubs = asyncio.run(publish_content(db, c, [c.plan.channel]))
        return {"published": len(pubs)}
    finally:
        db.close()


@celery_app.task(name="app.workers.tasks.run_due_posts")
def run_due_posts():
    """Автопостинг: публикует контент из плана на сегодня."""
    from datetime import date

    from app.db.session import SessionLocal
    from app.models.models import ContentPlan, PlanStatus
    import asyncio

    db = SessionLocal()
    n = 0
    try:
        due = db.query(ContentPlan).filter(
            ContentPlan.plan_date <= date.today(),
            ContentPlan.status.in_([PlanStatus.approved, PlanStatus.generated]),
        ).all()
        for plan in due:
            if not plan.contents:
                continue
            from app.services.posting.adapters import publish_content
            best = plan.contents[0]
            pubs = asyncio.run(publish_content(db, best, [plan.channel]))
            plan.status = (PlanStatus.published if pubs and all(p.status == "success" for p in pubs)
                           else PlanStatus.failed)
            db.commit()
            n += int(plan.status == PlanStatus.published)
        return {"posted": n}
    finally:
        db.close()


@celery_app.task(name="app.workers.tasks.sync_all_metrics")
def sync_all_metrics():
    from app.db.session import SessionLocal
    from app.services.analytics.metrics import sync_metrics

    db = SessionLocal()
    try:
        return {"new_metrics": sync_metrics(db)}
    finally:
        db.close()
