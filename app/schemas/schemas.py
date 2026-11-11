"""Pydantic-схемы API."""
from datetime import date, datetime
from typing import Optional, Any

from pydantic import BaseModel, ConfigDict, HttpUrl

from app.models.models import Channel, ContentType, PlanStatus


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Project ---
class ProjectCreate(BaseModel):
    name: str
    niche: str = ""
    description: str = ""
    tone_of_voice: str = "friendly"
    target_audience: str = ""
    website: str = ""


class ProjectOut(ORMModel):
    id: int
    name: str
    niche: str
    description: str
    tone_of_voice: str
    target_audience: str
    website: str


# --- SocialAccount ---
class AccountCreate(BaseModel):
    channel: Channel
    username: str = ""
    token: str = ""  # не сохраняется в открытом виде


class AccountOut(ORMModel):
    id: int
    project_id: int
    channel: Channel
    username: str
    token_masked: str
    is_active: bool


# --- ContentPlan ---
class PlanGenerateRequest(BaseModel):
    project_id: int
    month: str  # "YYYY-MM"
    channels: list[Channel] = [Channel.telegram, Channel.vk, Channel.instagram]
    posts_per_week: int = 3


class ContentPlanOut(ORMModel):
    id: int
    project_id: int
    plan_date: date
    month: str
    content_type: ContentType
    channel: Channel
    topic: str
    headline: str
    description: str
    hashtags: str
    holiday: str
    trend: str
    status: PlanStatus


# --- Content ---
class ContentGenerateRequest(BaseModel):
    plan_id: int
    variants: int = 2  # A/B
    media_url: HttpUrl | None = None  # required for Instagram live feed posts


class ContentOut(ORMModel):
    id: int
    plan_id: int
    title: str
    body: str
    variant_tag: str
    model_used: str


class ContentBrief(BaseModel):
    """Ручной бриф на генерацию без плана."""
    project_id: int
    channel: Channel
    content_type: ContentType
    topic: str
    extra_instructions: str = ""
    media_url: HttpUrl | None = None


# --- Publication ---
class PublishRequest(BaseModel):
    content_id: int
    channels: list[Channel] | None = None  # None => канал из плана


class PublicationOut(ORMModel):
    id: int
    content_id: int
    channel: Channel
    external_id: str
    status: str
    error: str
    payload_preview: str
    mode: str
    published_at: Optional[datetime] = None


# --- Metrics ---
class MetricOut(ORMModel):
    id: int
    content_id: int
    channel: Channel
    views: int
    likes: int
    comments: int
    shares: int
    clicks: int
    reach: int
    open_rate: float
    ctr: float


class DashboardRow(BaseModel):
    channel: str
    posts: int
    views: int
    likes: int
    comments: int
    shares: int
    engagement_rate: float


# --- A/B test ---
class ABTestCreate(BaseModel):
    project_id: int
    name: str
    hypothesis: str = ""
    content_a_id: int
    content_b_id: int
    metric: str = "engagement"


class ABTestOut(ORMModel):
    id: int
    project_id: int
    name: str
    hypothesis: str
    content_a_id: int
    content_b_id: int
    metric: str
    status: str
    winner: str
    result_summary: dict[Any, Any]
