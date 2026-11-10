"""Точка входа FastAPI.

Запуск:  uvicorn app.main:app --reload --port 8000
Документация: http://localhost:8000/docs
"""
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from app.api.routes.endpoints import router as api_router
from app.core.config import settings
from app.db.session import init_db
from app.services.analytics.metrics import sync_metrics
from app.workers.tasks import run_due_posts, sync_all_metrics

scheduler = AsyncIOScheduler(timezone="Europe/Moscow")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Инициализация БД и встроенного планировщика (работает без Celery/Redis)."""
    init_db()
    # Если доступен Redis — используем Celery Beat, иначе APScheduler
    scheduler.add_job(run_due_posts, "interval", hours=1, id="autopost")
    scheduler.add_job(sync_all_metrics, "interval", hours=1, id="metrics")
    try:
        scheduler.start()
    except Exception:  # окружение без event-loop-совместимого запуска — не критично
        pass
    yield
    try:
        scheduler.shutdown(wait=False)
    except Exception:
        pass


app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "AI-платформа для контент-маркетинга: планирование, генерация, "
        "мультиканальный автопостинг, аналитика и A/B-тесты.\n\n"
        "⚠️ Дисклеймер: публикация только в собственные аккаунты "
        "или с письменного разрешения клиента."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(api_router)


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/docs")


@app.get("/health")
def health():
    return {"status": "ok", "app": settings.APP_NAME, "posting_mode": settings.POSTING_MODE}
