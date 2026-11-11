"""REST API платформы контент-маркетинга (FastAPI)."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.models import (
    ABTest, Channel, ChannelMetric, Content, ContentPlan, ContentType,
    PlanStatus, Project, Publication, SocialAccount,
)
from app.schemas.schemas import (
    ABTestCreate, ABTestOut, AccountCreate, AccountOut, ContentBrief,
    ContentGenerateRequest, ContentOut, ContentPlanOut, DashboardRow,
    MetricOut, PlanGenerateRequest, ProjectCreate, ProjectOut, PublishRequest,
    PublicationOut,
)
from app.services.ai.content_generator import generate_content
from app.services.ai.plan_generator import generate_content_plan, plan_generation_source
from app.services.analytics.metrics import (
    best_content, dashboard_summary, evaluate_ab_test, sync_metrics,
)
from app.services.posting.adapters import publish_content

router = APIRouter(prefix="/api")


# ---------------- Projects ----------------
@router.post("/projects", response_model=ProjectOut, tags=["projects"])
def create_project(data: ProjectCreate, db: Session = Depends(get_db)):
    p = Project(**data.model_dump())
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@router.get("/projects", response_model=list[ProjectOut], tags=["projects"])
def list_projects(db: Session = Depends(get_db)):
    return db.query(Project).all()


@router.get("/projects/{pid}", response_model=ProjectOut, tags=["projects"])
def get_project(pid: int, db: Session = Depends(get_db)):
    p = db.get(Project, pid)
    if not p:
        raise HTTPException(404, "Проект не найден")
    return p


# ---------------- Accounts ----------------
@router.post("/projects/{pid}/accounts", response_model=AccountOut, tags=["accounts"])
def connect_account(pid: int, data: AccountCreate, db: Session = Depends(get_db)):
    if not db.get(Project, pid):
        raise HTTPException(404, "Проект не найден")
    tok = data.token or ""
    masked = (tok[:4] + "…" + tok[-4:]) if len(tok) > 8 else "(демо-токен)"
    acc = SocialAccount(project_id=pid, channel=data.channel,
                        username=data.username, token_masked=masked)
    db.add(acc)
    db.commit()
    db.refresh(acc)
    return acc


@router.get("/projects/{pid}/accounts", response_model=list[AccountOut], tags=["accounts"])
def list_accounts(pid: int, db: Session = Depends(get_db)):
    return db.query(SocialAccount).filter_by(project_id=pid).all()


# ---------------- Контент-план ----------------
@router.post("/plans/generate", response_model=list[ContentPlanOut], tags=["planning"])
async def generate_plan(data: PlanGenerateRequest, db: Session = Depends(get_db)):
    """AI-контент-план на месяц с учётом праздников и трендов."""
    project = db.get(Project, data.project_id)
    if not project:
        raise HTTPException(404, "Проект не найден")
    try:
        y, m = map(int, data.month.split("-"))
        if not 1 <= m <= 12:
            raise ValueError
        date(y, m, 1)
    except (ValueError, TypeError):
        raise HTTPException(422, "Неверный формат месяца, ожидается YYYY-MM")
    plans = await generate_content_plan(db, project, data.month, data.channels,
                                        data.posts_per_week)
    return plans


@router.get("/plans", response_model=list[ContentPlanOut], tags=["planning"])
def list_plans(project_id: int | None = None, month: str | None = None,
               db: Session = Depends(get_db)):
    q = db.query(ContentPlan)
    if project_id:
        q = q.filter_by(project_id=project_id)
    if month:
        q = q.filter_by(month=month)
    return q.order_by(ContentPlan.plan_date).all()


@router.patch("/plans/{plan_id}/approve", response_model=ContentPlanOut, tags=["planning"])
def approve_plan(plan_id: int, db: Session = Depends(get_db)):
    plan = db.get(ContentPlan, plan_id)
    if not plan:
        raise HTTPException(404, "План не найден")
    plan.status = PlanStatus.approved
    db.commit()
    db.refresh(plan)
    return plan


@router.get("/plans/meta/source", tags=["planning"])
def plan_source():
    return {"generator": plan_generation_source()}


# ---------------- Генерация контента ----------------
@router.post("/content/generate", response_model=list[ContentOut], tags=["creation"])
async def create_content(data: ContentGenerateRequest, db: Session = Depends(get_db)):
    """Генерирует варианты A/B текста для элемента плана."""
    plan = db.get(ContentPlan, data.plan_id)
    if not plan:
        raise HTTPException(404, "План не найден")
    project = db.get(Project, plan.project_id)
    contents = await generate_content(db, plan, project, variants=data.variants,
                                      media_url=str(data.media_url) if data.media_url else None)
    return contents


@router.post("/content/brief", response_model=ContentOut, tags=["creation"])
async def content_from_brief(data: ContentBrief, db: Session = Depends(get_db)):
    """Быстрая генерация по брифу без контент-плана."""
    project = db.get(Project, data.project_id)
    if not project:
        raise HTTPException(404, "Проект не найден")
    plan = ContentPlan(
        project_id=project.id, plan_date=date.today(),
        month=date.today().strftime("%Y-%m"), content_type=data.content_type,
        channel=data.channel, topic=data.topic, headline=data.topic[:120],
        description=data.extra_instructions, status=PlanStatus.generated,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    contents = await generate_content(db, plan, project, variants=1,
                                      media_url=str(data.media_url) if data.media_url else None)
    return contents[0]


@router.get("/content", response_model=list[ContentOut], tags=["creation"])
def list_contents(plan_id: int | None = None, db: Session = Depends(get_db)):
    q = db.query(Content)
    if plan_id:
        q = q.filter_by(plan_id=plan_id)
    return q.order_by(Content.id.desc()).all()


# ---------------- Публикация / автопостинг ----------------
@router.post("/publish", response_model=list[PublicationOut], tags=["posting"])
async def publish(data: PublishRequest, db: Session = Depends(get_db)):
    content = db.get(Content, data.content_id)
    if not content:
        raise HTTPException(404, "Контент не найден")
    channels = data.channels or [content.plan.channel]
    pubs = await publish_content(db, content, channels)
    if all(p.status == "success" for p in pubs):
        content.plan.status = PlanStatus.published
    elif any(p.status == "error" for p in pubs):
        content.plan.status = PlanStatus.failed
    db.commit()
    return pubs


@router.post("/autopost/run-due", tags=["posting"])
async def run_due_posts(db: Session = Depends(get_db)):
    """Автопостинг: публикует утверждённый контент, у которого наступила дата."""
    due = db.query(ContentPlan).filter(
        ContentPlan.plan_date <= date.today(),
        ContentPlan.status == PlanStatus.approved,
    ).all()
    posted = []
    for plan in due:
        if not plan.contents:
            continue
        pubs = await publish_content(db, plan.contents[0], [plan.channel])
        plan.status = (PlanStatus.published if pubs and all(p.status == "success" for p in pubs)
                       else PlanStatus.failed)
        db.commit()
        posted.append({"plan_id": plan.id, "status": plan.status.value})
    return {"posted_plans": posted}


@router.get("/publications", response_model=list[PublicationOut], tags=["posting"])
def list_publications(limit: int = 50, db: Session = Depends(get_db)):
    return db.query(Publication).order_by(Publication.id.desc()).limit(limit).all()


# ---------------- Аналитика ----------------
@router.post("/analytics/sync-metrics", tags=["analytics"])
def sync_analytics(db: Session = Depends(get_db)):
    n = sync_metrics(db)
    return {"new_metric_rows": n}


@router.get("/analytics/dashboard", response_model=list[DashboardRow], tags=["analytics"])
def analytics_dashboard(project_id: int | None = None, db: Session = Depends(get_db)):
    return dashboard_summary(db, project_id)


@router.get("/analytics/top", tags=["analytics"])
def analytics_top(limit: int = 5, db: Session = Depends(get_db)):
    return best_content(db, limit)


@router.get("/analytics/metrics", response_model=list[MetricOut], tags=["analytics"])
def list_metrics(content_id: int | None = None, db: Session = Depends(get_db)):
    q = db.query(ChannelMetric)
    if content_id:
        q = q.filter_by(content_id=content_id)
    return q.all()


# ---------------- A/B тестирование ----------------
@router.post("/ab-tests", response_model=ABTestOut, tags=["ab-testing"])
def create_ab_test(data: ABTestCreate, db: Session = Depends(get_db)):
    a = db.get(Content, data.content_a_id)
    b = db.get(Content, data.content_b_id)
    if not a or not b:
        raise HTTPException(404, "Варианты контента не найдены")
    t = ABTest(**data.model_dump())
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


@router.get("/ab-tests", response_model=list[ABTestOut], tags=["ab-testing"])
def list_ab_tests(db: Session = Depends(get_db)):
    return db.query(ABTest).all()


@router.post("/ab-tests/{tid}/evaluate", response_model=ABTestOut, tags=["ab-testing"])
def evaluate_ab(tid: int, db: Session = Depends(get_db)):
    t = db.get(ABTest, tid)
    if not t:
        raise HTTPException(404, "Тест не найден")
    sync_metrics(db, [t.content_a_id, t.content_b_id])
    return evaluate_ab_test(db, t)
