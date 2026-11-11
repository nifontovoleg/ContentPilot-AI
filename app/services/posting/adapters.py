"""Мультиканальные адаптеры публикации.

Два режима (POSTING_MODE в .env):
- demo — имитация отправки без внешних API (для разработки и демонстрации);
- live — реальные вызовы API (Telegram Bot API, VK API, Instagram Graph API,
  WordPress REST API, Mailchimp API).

ВАЖНО (дисклеймер по персональным данным): публиковать можно только
в собственные аккаунты или с письменного разрешения клиента.
"""
import hashlib
from datetime import datetime

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.models import Channel, Content, Publication, SocialAccount


def _mask_token(token: str) -> str:
    if not token:
        return "(не задан)"
    return token[:4] + "…" + token[-4:]


def _safe_error(error: Exception) -> str:
    message = str(error)
    secrets = (
        settings.TELEGRAM_BOT_TOKEN, settings.VK_ACCESS_TOKEN,
        settings.IG_ACCESS_TOKEN, settings.WP_APP_PASSWORD,
        settings.MAILCHIMP_API_KEY,
    )
    for secret in secrets:
        if secret:
            message = message.replace(secret, "[REDACTED]")
    return f"{type(error).__name__}: {message[:500]}"


class BaseAdapter:
    channel: Channel

    def __init__(self, db: Session, project_id: int):
        self.db = db
        self.project_id = project_id

    def account(self) -> SocialAccount | None:
        return (
            self.db.query(SocialAccount)
            .filter(
                SocialAccount.project_id == self.project_id,
                SocialAccount.channel == self.channel,
                SocialAccount.is_active.is_(True),
            )
            .first()
        )

    def live_token(self) -> str:
        raise NotImplementedError

    def require_account(self) -> SocialAccount:
        account = self.account()
        if not account:
            raise ValueError(f"Не настроено назначение канала {self.channel.value}")
        return account

    def require_token(self) -> str:
        token = self.live_token()
        if not token:
            raise ValueError(f"Не задан токен для канала {self.channel.value}")
        return token

    async def publish_live(self, content: Content) -> dict:
        raise NotImplementedError

    async def publish(self, content: Content) -> Publication:
        """Точка входа: demo или live. Результат пишется в журнал публикаций."""
        mode = settings.POSTING_MODE
        pub = Publication(content_id=content.id, channel=self.channel, mode=mode,
                          payload_preview=content.body[:300])
        try:
            if mode == "live":
                res = await self.publish_live(content)
                pub.external_id = str(res.get("id", ""))
                pub.status = "success"
            else:
                # Демо-режим: имитируем успешную отправку
                fake_id = f"demo-{self.channel.value}-{hashlib.md5(content.body.encode()).hexdigest()[:8]}"
                pub.external_id = fake_id
                pub.status = "success"
            pub.published_at = datetime.utcnow()
        except Exception as e:  # noqa: BLE001
            pub.status = "error"
            pub.error = _safe_error(e)
        self.db.add(pub)
        self.db.commit()
        self.db.refresh(pub)
        return pub


class TelegramAdapter(BaseAdapter):
    channel = Channel.telegram

    def live_token(self) -> str:
        return settings.TELEGRAM_BOT_TOKEN

    async def publish_live(self, content: Content) -> dict:
        token = self.require_token()
        chat_id = self.require_account().username
        if not chat_id:
            raise ValueError("Для Telegram в поле username укажите chat_id или @username")
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(url, json={"chat_id": chat_id, "text": content.body})
            r.raise_for_status()
            data = r.json()
            if not data.get("ok"):
                raise RuntimeError(data.get("description", "Telegram API returned an error"))
            return {"id": data["result"]["message_id"]}


class VKAdapter(BaseAdapter):
    channel = Channel.vk

    def live_token(self) -> str:
        return settings.VK_ACCESS_TOKEN

    async def publish_live(self, content: Content) -> dict:
        token = self.require_token()
        community_id = self.require_account().username.lstrip("-")
        if not community_id.isdigit():
            raise ValueError("Для VK в поле username укажите числовой ID сообщества")
        url = "https://api.vk.com/method/wall.post"
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(url, data={
                "access_token": token, "v": "5.199",
                "owner_id": f"-{community_id}", "from_group": 1,
                "message": content.body,
            })
            r.raise_for_status()
            data = r.json()
            if "error" in data:
                raise RuntimeError(data["error_msg"])
            return {"id": data["response"]["post_id"]}


class InstagramAdapter(BaseAdapter):
    channel = Channel.instagram

    def live_token(self) -> str:
        return settings.IG_ACCESS_TOKEN

    async def publish_live(self, content: Content) -> dict:
        # Instagram Graph API: сначала media container, потом publish.
        token = self.require_token()
        ig_user = self.require_account().username
        if not ig_user:
            raise ValueError("Для Instagram в поле username укажите ID профессионального аккаунта")
        media_url = (content.meta or {}).get("media_url")
        if not media_url:
            raise ValueError("Для Instagram требуется публичный URL изображения в content.meta.media_url")
        base = "https://graph.facebook.com/v21.0"
        async with httpx.AsyncClient(timeout=20) as client:
            r1 = await client.post(f"{base}/{ig_user}/media", data={
                "image_url": media_url, "caption": content.body[:2200], "access_token": token,
            })
            r1.raise_for_status()
            creation_id = r1.json()["id"]
            r2 = await client.post(f"{base}/{ig_user}/media_publish", data={
                "creation_id": creation_id, "access_token": token,
            })
            r2.raise_for_status()
            return {"id": r2.json()["id"]}


class WordPressAdapter(BaseAdapter):
    channel = Channel.wordpress

    def live_token(self) -> str:
        return settings.WP_APP_PASSWORD

    async def publish_live(self, content: Content) -> dict:
        self.require_token()
        self.require_account()
        if not settings.WP_URL or not settings.WP_USER:
            raise ValueError("Для WordPress задайте WP_URL и WP_USER")
        url = f"{settings.WP_URL.rstrip('/')}/wp-json/wp/v2/posts"
        html = "<p>" + content.body.replace("\n\n", "</p><p>") + "</p>"
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                url, json={"title": content.title, "content": html, "status": "publish"},
                auth=(settings.WP_USER, settings.WP_APP_PASSWORD),
            )
            r.raise_for_status()
            return {"id": r.json()["id"]}


class MailchimpAdapter(BaseAdapter):
    channel = Channel.mailchimp

    def live_token(self) -> str:
        return settings.MAILCHIMP_API_KEY

    async def publish_live(self, content: Content) -> dict:
        self.require_token()
        self.require_account()
        if (not settings.MAILCHIMP_SERVER or not settings.MAILCHIMP_AUDIENCE_ID
                or not settings.MAILCHIMP_REPLY_TO):
            raise ValueError("Для Mailchimp задайте MAILCHIMP_SERVER, MAILCHIMP_AUDIENCE_ID и MAILCHIMP_REPLY_TO")
        base = f"https://{settings.MAILCHIMP_SERVER}.api.mailchimp.com/3.0"
        headers = {"Authorization": f"Bearer {settings.MAILCHIMP_API_KEY}"}
        body_html = "<p>" + content.body.replace("\n\n", "</p><p>") + "</p>"
        async with httpx.AsyncClient(timeout=30) as client:
            r1 = await client.post(f"{base}/campaigns", headers=headers, json={
                "type": "regular",
                "recipients": {"list_id": settings.MAILCHIMP_AUDIENCE_ID},
                "settings": {"subject_line": content.title, "from_name": "AI Platform",
                             "reply_to": settings.MAILCHIMP_REPLY_TO},
            })
            r1.raise_for_status()
            cid = r1.json()["id"]
            r2 = await client.put(f"{base}/campaigns/{cid}/content", headers=headers,
                                  json={"html": body_html})
            r2.raise_for_status()
            r3 = await client.post(f"{base}/campaigns/{cid}/actions/send", headers=headers)
            r3.raise_for_status()
            return {"id": cid}


ADAPTERS: dict[Channel, type[BaseAdapter]] = {
    Channel.telegram: TelegramAdapter,
    Channel.vk: VKAdapter,
    Channel.instagram: InstagramAdapter,
    Channel.wordpress: WordPressAdapter,
    Channel.mailchimp: MailchimpAdapter,
}


async def publish_content(db: Session, content: Content, channels: list[Channel]) -> list[Publication]:
    """Публикует контент в список каналов, возвращает записи журнала."""
    results = []
    for ch in channels:
        adapter_cls = ADAPTERS.get(ch)
        if not adapter_cls:
            continue
        adapter = adapter_cls(db, content.plan.project_id)
        results.append(await adapter.publish(content))
    return results
