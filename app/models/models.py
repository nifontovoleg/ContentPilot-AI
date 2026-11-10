"""ORM-модели платформы."""
import enum
from datetime import datetime, date

from sqlalchemy import (
    String, Text, Integer, Float, Boolean, DateTime, Date, Enum, ForeignKey, JSON,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Channel(str, enum.Enum):
    telegram = "telegram"
    vk = "vk"
    instagram = "instagram"
    wordpress = "wordpress"
    mailchimp = "mailchimp"


class ContentType(str, enum.Enum):
    post = "post"            # пост для соцсетей
    article = "article"      # статья для блога
    email = "email"          # email-рассылка


class PlanStatus(str, enum.Enum):
    draft = "draft"
    approved = "approved"
    generated = "generated"
    published = "published"
    failed = "failed"
    scheduled = "scheduled"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class Project(Base, TimestampMixin):
    """Клиентский проект (бренд). Персональные данные — только со своего аккаунта
    или с письменного разрешения клиента."""
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    niche: Mapped[str] = mapped_column(String(200), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    tone_of_voice: Mapped[str] = mapped_column(String(100), default="friendly")
    target_audience: Mapped[str] = mapped_column(Text, default="")
    website: Mapped[str] = mapped_column(String(300), default="")

    plans: Mapped[list["ContentPlan"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    accounts: Mapped[list["SocialAccount"]] = relationship(back_populates="project", cascade="all, delete-orphan")


class SocialAccount(Base, TimestampMixin):
    """Подключённый аккаунт канала. Токены хранятся в зашифрованном виде
    (в демо — заглушка)."""
    __tablename__ = "social_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    channel: Mapped[Channel] = mapped_column(Enum(Channel))
    username: Mapped[str] = mapped_column(String(200), default="")
    token_masked: Mapped[str] = mapped_column(String(100), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    project: Mapped["Project"] = relationship(back_populates="accounts")


class ContentPlan(Base, TimestampMixin):
    """Элемент AI-контент-плана на месяц."""
    __tablename__ = "content_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    plan_date: Mapped[date] = mapped_column(Date)
    month: Mapped[str] = mapped_column(String(7), index=True)  # "2026-11"
    content_type: Mapped[ContentType] = mapped_column(Enum(ContentType))
    channel: Mapped[Channel] = mapped_column(Enum(Channel))
    topic: Mapped[str] = mapped_column(String(500))
    headline: Mapped[str] = mapped_column(String(500), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    hashtags: Mapped[str] = mapped_column(String(1000), default="")
    holiday: Mapped[str] = mapped_column(String(200), default="")  # привязка к празднику
    trend: Mapped[str] = mapped_column(String(200), default="")    # привязка к тренду
    status: Mapped[PlanStatus] = mapped_column(Enum(PlanStatus), default=PlanStatus.draft)

    project: Mapped["Project"] = relationship(back_populates="plans")
    contents: Mapped[list["Content"]] = relationship(back_populates="plan", cascade="all, delete-orphan")


class Content(Base, TimestampMixin):
    """Сгенерированный контент (текст поста/статьи/письма)."""
    __tablename__ = "contents"

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("content_plans.id"))
    title: Mapped[str] = mapped_column(String(500), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    variant_tag: Mapped[str] = mapped_column(String(10), default="A")  # A/B вариант
    model_used: Mapped[str] = mapped_column(String(100), default="local-rule-based")
    meta: Mapped[dict] = mapped_column(JSON, default=dict)

    plan: Mapped["ContentPlan"] = relationship(back_populates="contents")
    publications: Mapped[list["Publication"]] = relationship(back_populates="content", cascade="all, delete-orphan")
    metrics: Mapped[list["ChannelMetric"]] = relationship(back_populates="content", cascade="all, delete-orphan")


class Publication(Base, TimestampMixin):
    """Журнал публикаций/отправок по каналам."""
    __tablename__ = "publications"

    id: Mapped[int] = mapped_column(primary_key=True)
    content_id: Mapped[int] = mapped_column(ForeignKey("contents.id"))
    channel: Mapped[Channel] = mapped_column(Enum(Channel))
    external_id: Mapped[str] = mapped_column(String(200), default="")
    status: Mapped[str] = mapped_column(String(30), default="pending")  # pending/success/error
    error: Mapped[str] = mapped_column(Text, default="")
    payload_preview: Mapped[str] = mapped_column(Text, default="")
    mode: Mapped[str] = mapped_column(String(10), default="demo")
    published_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    content: Mapped["Content"] = relationship(back_populates="publications")


class ChannelMetric(Base, TimestampMixin):
    """Метрики эффективности опубликованного контента."""
    __tablename__ = "channel_metrics"

    id: Mapped[int] = mapped_column(primary_key=True)
    content_id: Mapped[int] = mapped_column(ForeignKey("contents.id"))
    channel: Mapped[Channel] = mapped_column(Enum(Channel))
    views: Mapped[int] = mapped_column(Integer, default=0)
    likes: Mapped[int] = mapped_column(Integer, default=0)
    comments: Mapped[int] = mapped_column(Integer, default=0)
    shares: Mapped[int] = mapped_column(Integer, default=0)
    clicks: Mapped[int] = mapped_column(Integer, default=0)
    reach: Mapped[int] = mapped_column(Integer, default=0)
    open_rate: Mapped[float] = mapped_column(Float, default=0.0)     # для email
    ctr: Mapped[float] = mapped_column(Float, default=0.0)           # для email

    content: Mapped["Content"] = relationship(back_populates="metrics")


class ABTest(Base, TimestampMixin):
    """A/B-тест двух вариантов контента."""
    __tablename__ = "ab_tests"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    name: Mapped[str] = mapped_column(String(300))
    hypothesis: Mapped[str] = mapped_column(Text, default="")
    content_a_id: Mapped[int] = mapped_column(ForeignKey("contents.id"))
    content_b_id: Mapped[int] = mapped_column(ForeignKey("contents.id"))
    metric: Mapped[str] = mapped_column(String(50), default="engagement")  # engagement/ctr/open_rate
    status: Mapped[str] = mapped_column(String(30), default="running")     # running/completed
    winner: Mapped[str] = mapped_column(String(10), default="")            # A / B / ""
    result_summary: Mapped[dict] = mapped_column(JSON, default=dict)
