"""Конфигурация платформы контент-маркетинга."""
from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Общие
    APP_NAME: str = "AI Content Marketing Platform"
    DEBUG: bool = True

    # База данных. PostgreSQL в продакшене, SQLite для разработки/демо.
    DATABASE_URL: str = "sqlite:///./data/content_platform.db"

    # OpenAI / LLM
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    # Если ключа нет — используется локальный rule-based генератор (демо-режим).
    AI_FALLBACK_LOCAL: bool = True

    # Celery / Redis
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"

    # Токены социальных сетей (только собственные аккаунты или с разрешения клиента!)
    TELEGRAM_BOT_TOKEN: str = ""
    VK_ACCESS_TOKEN: str = ""
    IG_ACCESS_TOKEN: str = ""
    WP_URL: str = ""
    WP_USER: str = ""
    WP_APP_PASSWORD: str = ""
    MAILCHIMP_API_KEY: str = ""
    MAILCHIMP_SERVER: str = ""  # напр. us21
    MAILCHIMP_AUDIENCE_ID: str = ""

    # Режим публикации: demo (имитация) | live (реальные API)
    POSTING_MODE: str = "demo"

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
