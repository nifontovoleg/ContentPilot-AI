"""Слой доступа к базе данных (SQLAlchemy 2.0)."""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings

connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(settings.DATABASE_URL, connect_args=connect_args, future=True)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    """Разрешаем конкурентный доступ для SQLite (демо-режим)."""
    if settings.DATABASE_URL.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from app import models  # noqa: F401  — регистрация всех таблиц
    Base.metadata.create_all(bind=engine)
