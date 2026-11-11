"""Генерация контента (посты, статьи, email) через AI.

Режимы: OpenAI (при наличии ключа) или локальный rule-based шаблонизатор (демо).
Всегда создаёт минимум два варианта (A/B) для тестирования.
"""
import random

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.models import Content, ContentPlan, ContentType, PlanStatus, Project

CTA_BY_TYPE = {
    ContentType.post: "Ставьте 🔥, если полезно, и подписывайтесь — впереди много интересного!",
    ContentType.article: "Читайте другие материалы блога и подписывайтесь на обновления.",
    ContentType.email: "Ответьте на это письмо — мы читаем все сообщения 💌",
}

HOOKS_A = [
    "Знаете, что объединяет всех наших клиентов? {topic_l}",
    "Мы потратили месяц, чтобы разобраться: {topic_l}",
    "Коротко и по делу 👇 {topic_l}",
]
HOOKS_B = [
    "🔥 Главная тема недели: {topic_l}",
    "5 минут — и вы будете знать про «{topic_l}» всё.",
    "Спойлер: это изменит ваш подход. Тема: {topic_l}",
]


def _local_body(plan: ContentPlan, project: Project, variant: str) -> str:
    tone = project.tone_of_voice
    niche = project.niche or project.name
    hooks = HOOKS_A if variant == "A" else HOOKS_B
    hook = random.choice(hooks).format(topic_l=plan.topic.lower())
    bullets = [
        f"— Почему это важно для ниши «{niche}»;",
        f"— Что делать прямо сейчас (3 простых шага);",
        "— Какой результат получают наши клиенты;",
    ]
    body = (
        f"{hook}\n\n"
        f"{plan.description}\n\n"
        + "\n".join(bullets)
        + f"\n\n{CTA_BY_TYPE[plan.content_type]}"
    )
    if plan.hashtags:
        body += f"\n\n{plan.hashtags}"
    if tone and tone != "friendly":
        body = body.replace("👇", "→").replace("🔥", "•")  # грубая адаптация тона
    return body.strip()


async def _openai_body(plan: ContentPlan, project: Project, variant: str) -> str:
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    style = "сцепляющий, с эмодзи и CTA" if variant == "A" else \
        "экспертный, с цифрами и фактами, без эмодзи"
    prompt = (
        f"Напиши {plan.content_type.value} для канала «{plan.channel.value}».\n"
        f"Тема: {plan.topic}.\nКонтекст бренда: ниша «{project.niche}», "
        f"аудитория «{project.target_audience}», tone of voice «{project.tone_of_voice}».\n"
        f"Стиль варианта {variant}: {style}. Длина: до 1500 знаков (для статьи — до 4000).\n"
        f"Дополнительно: {plan.description}"
    )
    resp = await client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.8,
    )
    text = resp.choices[0].message.content.strip()
    if plan.hashtags and plan.channel.value in ("instagram", "vk", "telegram"):
        text += f"\n\n{plan.hashtags}"
    return text


async def generate_content(db: Session, plan: ContentPlan, project: Project,
                           variants: int = 2, media_url: str | None = None) -> list[Content]:
    """Создаёт варианты A/B текста для элемента плана и сохраняет в БД."""
    use_openai = bool(settings.OPENAI_API_KEY)
    created: list[Content] = []
    for v in range(max(1, min(variants, 2))):
        tag = "AB"[v]
        try:
            if use_openai:
                body = await _openai_body(plan, project, tag)
                model = f"openai:{settings.OPENAI_MODEL}"
            else:
                body = _local_body(plan, project, tag)
                model = "local-rule-based"
        except Exception:
            if not settings.AI_FALLBACK_LOCAL:
                raise
            body = _local_body(plan, project, tag)
            model = "local-rule-based (fallback)"

        metadata = {"channel": plan.channel.value, "type": plan.content_type.value}
        if media_url:
            metadata["media_url"] = media_url
        c = Content(plan_id=plan.id, title=plan.headline or plan.topic,
                    body=body, variant_tag=tag, model_used=model,
                    meta=metadata)
        db.add(c)
        created.append(c)

    plan.status = PlanStatus.generated
    db.commit()
    for c in created:
        db.refresh(c)
    return created
