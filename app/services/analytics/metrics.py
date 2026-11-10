"""Сбор и агрегация метрик по каналам + A/B-тестирование.

В demo-режиме метрики симулируются детерминированным генератором на основе
текста поста (чтобы демо было воспроизводимым). В live-режиме сюда подключаются
реальные API: Telegram (getMessagesViews нет для каналов -> используется аналитика
через ботов), VK stats, Instagram insights, Mailchimp reports.
"""
import hashlib
import random
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.models import (
    ABTest, Channel, ChannelMetric, Content, Publication, PlanStatus,
)


def _seed(text: str) -> int:
    return int(hashlib.md5(text.encode()).hexdigest()[:8], 16)


def simulate_metrics(content: Content, channel: Channel) -> ChannelMetric:
    """Детерминированная симуляция метрик для демо-режима."""
    rng = random.Random(_seed(content.body + channel.value))
    base_views = {"telegram": 3200, "vk": 5400, "instagram": 7800,
                  "wordpress": 900, "mailchimp": 2600}[channel.value]
    views = int(base_views * rng.uniform(0.5, 2.2))
    likes = int(views * rng.uniform(0.02, 0.09))
    comments = int(likes * rng.uniform(0.05, 0.25))
    shares = int(likes * rng.uniform(0.03, 0.15))
    clicks = int(views * rng.uniform(0.01, 0.06))
    reach = int(views * rng.uniform(1.1, 1.8))
    m = ChannelMetric(
        content_id=content.id, channel=channel,
        views=views, likes=likes, comments=comments, shares=shares,
        clicks=clicks, reach=reach,
        open_rate=round(rng.uniform(0.18, 0.45), 3) if channel == Channel.mailchimp else 0.0,
        ctr=round(rng.uniform(0.01, 0.08), 3) if channel == Channel.mailchimp else 0.0,
    )
    return m


def sync_metrics(db: Session, content_ids: list[int] | None = None) -> int:
    """Собирает метрики по опубликованному контенту (демо-симуляция)."""
    q = db.query(Content).join(Publication, Publication.content_id == Content.id)
    if content_ids:
        q = q.filter(Content.id.in_(content_ids))
    contents = q.distinct().all()
    n = 0
    for c in contents:
        channels = {p.channel for p in c.publications if p.status == "success"}
        for ch in channels:
            exists = db.query(ChannelMetric).filter_by(content_id=c.id, channel=ch).first()
            if not exists:
                db.add(simulate_metrics(c, ch))
                n += 1
    db.commit()
    return n


def engagement(m: ChannelMetric) -> float:
    total = m.likes + m.comments + m.shares
    return round(total / max(m.views, 1), 4)


def dashboard_summary(db: Session, project_id: int | None = None) -> list[dict]:
    """Агрегированная аналитика по каналам."""
    q = (
        db.query(
            ChannelMetric.channel,
            func.count(ChannelMetric.id),
            func.sum(ChannelMetric.views),
            func.sum(ChannelMetric.likes),
            func.sum(ChannelMetric.comments),
            func.sum(ChannelMetric.shares),
            func.sum(ChannelMetric.clicks),
            func.sum(ChannelMetric.reach),
        )
        .join(Content, Content.id == ChannelMetric.content_id)
    )
    if project_id:
        from app.models.models import ContentPlan
        q = q.join(ContentPlan, ContentPlan.id == Content.plan_id).filter(
            ContentPlan.project_id == project_id
        )
    rows = q.group_by(ChannelMetric.channel).all()
    out = []
    for ch, posts, views, likes, comments, shares, clicks, reach in rows:
        views = views or 0
        er = round(((likes or 0) + (comments or 0) + (shares or 0)) / max(views, 1), 4)
        out.append({
            "channel": ch.value if hasattr(ch, "value") else str(ch),
            "posts": posts, "views": views, "likes": likes or 0,
            "comments": comments or 0, "shares": shares or 0,
            "clicks": clicks or 0, "reach": reach or 0,
            "engagement_rate": er,
        })
    return sorted(out, key=lambda r: r["views"], reverse=True)


def best_content(db: Session, limit: int = 5) -> list[dict]:
    """Топ контента по вовлечённости."""
    metrics = db.query(ChannelMetric).all()
    by_content: dict[int, dict] = {}
    for m in metrics:
        d = by_content.setdefault(m.content_id, {"views": 0, "eng": 0})
        d["views"] += m.views
        d["eng"] += (m.likes + m.comments + m.shares)
    ranked = sorted(by_content.items(), key=lambda kv: kv[1]["eng"] / max(kv[1]["views"], 1), reverse=True)
    out = []
    for cid, agg in ranked[:limit]:
        c = db.get(Content, cid)
        if c:
            out.append({
                "content_id": cid, "title": c.title, "variant": c.variant_tag,
                "views": agg["views"],
                "engagement_rate": round(agg["eng"] / max(agg["views"], 1), 4),
            })
    return out


# ---------------- A/B тестирование ----------------

def metric_value(db: Session, content_id: int, metric: str) -> tuple[float, int]:
    """Значение метрики, агрегированное по всем публикациям варианта."""
    ms = db.query(ChannelMetric).filter_by(content_id=content_id).all()
    if not ms:
        return 0.0, 0
    sample = sum(m.views for m in ms)
    if metric == "ctr":
        vals = [m.ctr for m in ms if m.ctr > 0] or [m.clicks / max(m.views, 1) for m in ms]
        return round(sum(vals) / len(vals), 4), sample
    if metric == "open_rate":
        vals = [m.open_rate for m in ms if m.open_rate > 0]
        return (round(sum(vals) / len(vals), 4), sample) if vals else (0.0, sample)
    # engagement по умолчанию
    eng = sum(m.likes + m.comments + m.shares for m in ms)
    return round(eng / max(sample, 1), 4), sample


def evaluate_ab_test(db: Session, test: ABTest) -> ABTest:
    """Считывает накопленные метрики и определяет победителя."""
    va, sa = metric_value(db, test.content_a_id, test.metric)
    vb, sb = metric_value(db, test.content_b_id, test.metric)
    lift = round((vb - va) / va, 3) if va > 0 else 0.0
    winner = ""
    if sa >= 100 and sb >= 100:  # минимальная выборка для «статистической значимости» в демо
        winner = "B" if vb > va else ("A" if va > vb else "")
        test.status = "completed"
    test.result_summary = {
        "A": {"metric": test.metric, "value": va, "sample": sa},
        "B": {"metric": test.metric, "value": vb, "sample": sb},
        "lift_B_vs_A": lift,
        "evaluated_at": datetime.utcnow().isoformat(),
    }
    test.winner = winner
    db.commit()
    db.refresh(test)
    return test
