"""Генерация контент-плана через AI.

Два режима:
1. OpenAI (если задан OPENAI_API_KEY) — план генерируется LLM.
2. Локальный rule-based генератор (демо) — без внешних вызовов,
   учитывает праздники, сезонные события и тренды.
"""
import calendar
import json
from datetime import date

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.models import ContentPlan, ContentType, PlanStatus, Project, Channel
from app.services.ai import holidays as hol

WEEKDAY_NAMES = {1: "Пн", 2: "Вт", 3: "Ср", 4: "Чт", 5: "Пт"}

TOPIC_TEMPLATES = {
    ContentType.post: [
        "Экспертный совет: как {niche} помогает экономить время",
        "Закулисье: как устроен наш продукт изнутри",
        "Подборка: 5 ошибок в теме «{niche}»",
        "Кейс клиента: результат в цифрах",
        "Интерактив: опрос аудитории по теме «{niche}»",
        "Мем недели по мотивам «{niche}»",
        "Чек-лист: готовность к {event}",
        "Тренд-разбор: {trend} и как это применить в «{niche}»",
        "Анонс: что нового у нас на этой неделе",
        "Туториал: {niche} за 3 шага",
    ],
    ContentType.article: [
        "Гайд: полный обзор «{niche}» на {year} год",
        "SEO-статья: как выбрать подрядчика в нише «{niche}»",
        "Аналитика: тренды «{niche}» перед {event}",
        "Longread: путь клиента в нише «{niche}»",
    ],
    ContentType.email: [
        "Рассылка: дайджест новостей за месяц",
        "Промо-письмо: спецпредложение к {event}",
        "Письмо вовлечения: возврат спящих подписчиков",
        "Экспертная рассылка: 3 инсайта про «{niche}»",
    ],
}

HASHTAG_SETS = {
    Channel.telegram: "#новости #бизнес #{slug}",
    Channel.vk: "#{slug} #вкбизнес #рекомендации",
    Channel.instagram: "#{slug} #reels #маркетинг #бизнес #мотивация",
    Channel.wordpress: "#{slug} #seo #блог",
    Channel.mailchimp: "",
}


def _month_dates(month: str) -> list[date]:
    y, m = map(int, month.split("-"))
    last = calendar.monthrange(y, m)[1]
    return [date(y, m, d) for d in range(1, last + 1)]


def _pick_days(dates: list[date], per_week: int) -> list[date]:
    """Распределяем посты по будням (Пн/Ср/Пт и т.п.)."""
    chosen: list[date] = []
    week_used: dict[int, int] = {}
    for d in dates:
        if d.weekday() >= 5:  # сб, вс — отдыхаем
            continue
        iso_week = d.isocalendar()[1]
        used = week_used.get(iso_week, 0)
        if used < per_week:
            chosen.append(d)
            week_used[iso_week] = used + 1
    return chosen


def _local_generate_plan(project: Project, month: str, channels: list[Channel],
                        posts_per_week: int) -> list[dict]:
    y, m = map(int, month.split("-"))
    days = _pick_days(_month_dates(month), posts_per_week)
    niche = project.niche or project.name
    slug = "".join(c for c in niche.lower().replace(" ", "_") if c.isalnum() or c == "_")[:20]

    items: list[dict] = []
    # В каждый месяц обязательно включаем email-рассылку и SEO-статью (2-й и 4-й вторник)
    tuesdays = [d for d in days if d.weekday() == 1]
    forced: dict[date, tuple[Channel, ContentType]] = {}
    if len(tuesdays) >= 2:
        forced[tuesdays[0]] = (Channel.wordpress, ContentType.article)
        forced[tuesdays[1]] = (Channel.mailchimp, ContentType.email)

    for i, d in enumerate(days):
        if d in forced:
            channel = forced[d][0]
        else:
            channel = channels[i % len(channels)]
        holiday = hol.get_holiday(d)
        event = holiday or hol.get_month_event(m, i)
        trend = hol.get_trend_for_date(d, seed=i)

        if channel == Channel.wordpress:
            ctype = ContentType.article
        elif channel == Channel.mailchimp:
            ctype = ContentType.email
        else:
            ctype = ContentType.post

        templates = TOPIC_TEMPLATES[ctype]
        topic = templates[i % len(templates)].format(
            niche=niche, event=event or "сезоном", trend=trend, year=y,
        )
        if holiday:
            topic = f"Поздравительный контент к «{holiday}»: {topic}"

        items.append({
            "plan_date": d,
            "content_type": ctype,
            "channel": channel,
            "topic": topic,
            "headline": topic[:120],
            "description": (
                f"Формат: {ctype.value}. Привязка: "
                f"{('праздник — ' + holiday) if holiday else ('событие — ' + event if event else 'тренд — ' + trend)}."
            ),
            "hashtags": HASHTAG_SETS[channel].format(slug=slug),
            "holiday": holiday,
            "trend": "" if holiday else trend,
        })
    return items


async def _openai_generate_plan(project: Project, month: str, channels: list[Channel],
                                posts_per_week: int) -> list[dict]:
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    prompt = (
        f"Ты — контент-стратег. Составь контент-план на {month} для проекта: "
        f"ниша «{project.niche}», аудитория «{project.target_audience}», "
        f"tone of voice «{project.tone_of_voice}». Каналы: {', '.join(c.value for c in channels)}. "
        f"Частота: {posts_per_week} постов в неделю (только будни). "
        f"Учти праздники РФ и тренды. Верни JSON-массив объектов "
        f"[{{\"date\":\"YYYY-MM-DD\",\"channel\":\"...\",\"type\":\"post|article|email\","
        f"\"topic\":\"...\",\"headline\":\"...\",\"description\":\"...\",\"hashtags\":\"...\"]}}."
    )
    resp = await client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0.7,
    )
    data = json.loads(resp.choices[0].message.content)
    raw = data.get("plan") or data.get("items") or next(iter(data.values()))
    out = []
    ch_map = {c.value: c for c in Channel}
    for it in raw:
        out.append({
            "plan_date": date.fromisoformat(it["date"]),
            "content_type": ContentType(it.get("type", "post")),
            "channel": ch_map.get(it.get("channel", "telegram"), Channel.telegram),
            "topic": it["topic"],
            "headline": it.get("headline", it["topic"][:120]),
            "description": it.get("description", ""),
            "hashtags": it.get("hashtags", ""),
            "holiday": it.get("holiday", ""),
            "trend": it.get("trend", ""),
        })
    return out


async def generate_content_plan(db: Session, project: Project, month: str,
                                channels: list[Channel], posts_per_week: int = 3) -> list[ContentPlan]:
    """Генерирует план и сохраняет в БД (старый черновик за месяц заменяется)."""
    use_openai = bool(settings.OPENAI_API_KEY)
    try:
        items = await _openai_generate_plan(project, month, channels, posts_per_week) \
            if use_openai else _local_generate_plan(project, month, channels, posts_per_week)
        source = f"openai:{settings.OPENAI_MODEL}" if use_openai else "local-rule-based"
    except Exception:
        if not settings.AI_FALLBACK_LOCAL:
            raise
        # Устойчивость: при сбое API падаем на локальный генератор
        items = _local_generate_plan(project, month, channels, posts_per_week)
        source = "local-rule-based (fallback)"

    db.query(ContentPlan).filter(
        ContentPlan.project_id == project.id,
        ContentPlan.month == month,
        ContentPlan.status.in_([PlanStatus.draft, PlanStatus.generated]),
    ).delete()

    plans = []
    for it in items:
        p = ContentPlan(
            project_id=project.id, month=month, status=PlanStatus.generated,
            **it,
        )
        p.meta_source = source  # type: ignore[attr-defined]
        db.add(p)
        plans.append(p)
    db.commit()
    for p in plans:
        db.refresh(p)
    return plans


def plan_generation_source() -> str:
    """Для отображения в UI: какой генератор будет использован сейчас."""
    return f"openai:{settings.OPENAI_MODEL}" if settings.OPENAI_API_KEY else "local-rule-based (демо)"
