"""Сквозные API-тесты (FastAPI TestClient)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient

from app.main import app  # lifespan через TestClient with-контекст

client = TestClient(app)


def setup_module(module):
    """Явная инициализация БД (lifespan запускается только в with-контексте)."""
    from app.db.session import init_db
    init_db()


def _create_project():
    r = client.post("/api/projects", json={
        "name": "Тест-бренд", "niche": "тестовая ниша",
        "target_audience": "QA-инженеры", "tone_of_voice": "expert"})
    assert r.status_code == 200
    return r.json()["id"]


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_full_flow():
    pid = _create_project()

    # 1. Контент-план на месяц
    r = client.post("/api/plans/generate", json={
        "project_id": pid, "month": "2026-11",
        "channels": ["telegram", "vk", "instagram"], "posts_per_week": 3})
    assert r.status_code == 200
    plans = r.json()
    assert len(plans) >= 10
    # План учитывает праздники/тренды или хотя бы заполнен
    assert all(p["topic"] for p in plans)
    months = {p["month"] for p in plans}
    assert months == {"2026-11"}

    # 2. Генерация A/B контента
    plan_id = plans[0]["id"]
    r = client.post("/api/content/generate", json={"plan_id": plan_id, "variants": 2})
    assert r.status_code == 200
    variants = r.json()
    assert len(variants) == 2
    assert {v["variant_tag"] for v in variants} == {"A", "B"}

    # 3. Публикация в демо-режиме
    r = client.post("/api/publish", json={"content_id": variants[0]["id"]})
    assert r.status_code == 200
    pubs = r.json()
    assert pubs[0]["status"] == "success"
    assert pubs[0]["mode"] == "demo"

    # 4. Утверждение плана + автопостинг
    r = client.patch(f"/api/plans/{plan_id}/approve")
    assert r.status_code == 200
    r = client.post("/api/autopost/run-due")
    assert r.status_code == 200

    # 5. Синхронизация метрик и дашборд
    r = client.post("/api/analytics/sync-metrics")
    assert r.status_code == 200
    r = client.get("/api/analytics/dashboard")
    assert r.status_code == 200
    dash = r.json()
    assert len(dash) >= 1
    assert dash[0]["views"] > 0

    # 6. A/B тест
    r = client.post("/api/content/generate", json={"plan_id": plans[1]["id"], "variants": 2})
    a, b = r.json()[0], r.json()[1]
    for cid in (a["id"], b["id"]):
        client.post("/api/publish", json={"content_id": cid})
    client.post("/api/analytics/sync-metrics")
    r = client.post("/api/ab-tests", json={
        "project_id": pid, "name": "Тест", "content_a_id": a["id"],
        "content_b_id": b["id"], "metric": "engagement"})
    assert r.status_code == 200
    tid = r.json()["id"]
    r = client.post(f"/api/ab-tests/{tid}/evaluate")
    assert r.status_code == 200
    res = r.json()
    assert "A" in res["result_summary"] and "B" in res["result_summary"]


def test_brief_generation():
    pid = _create_project()
    r = client.post("/api/content/brief", json={
        "project_id": pid, "channel": "mailchimp",
        "content_type": "email", "topic": "Дайджест ноябрьских скидок"})
    assert r.status_code == 200
    assert len(r.json()["body"]) > 50


def test_invalid_month():
    pid = _create_project()
    r = client.post("/api/plans/generate", json={
        "project_id": pid, "month": "bad-month"})
    assert r.status_code == 422
