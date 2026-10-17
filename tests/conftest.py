"""Each test gets a fresh app on its own SQLite file, with no network and no AI key."""

from __future__ import annotations

import importlib
import itertools
from pathlib import Path

import pytest

_counter = itertools.count()


@pytest.fixture()
def client(monkeypatch, tmp_path: Path):
    db_file = tmp_path / f"test_{next(_counter)}.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file.as_posix()}")
    monkeypatch.setenv("ENABLE_SCHEDULER", "false")
    monkeypatch.setenv("FETCH_REMOTE", "false")
    monkeypatch.setenv("N8N_SHARED_SECRET", "test-secret")
    monkeypatch.setenv("N8N_BASE_URL", "")
    monkeypatch.setenv("GROQ_API_KEY", "")
    monkeypatch.setenv("GROQ_API_KEYS", "")
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "test-pass")
    monkeypatch.setenv("ADMIN_NAME", "Rev")
    monkeypatch.setenv("BASE_URL", "http://testserver")

    from app.config import get_settings
    from app.services.groq_pool import reset_groq_pool

    get_settings.cache_clear()
    reset_groq_pool()
    from app import auth

    auth._failures.clear()

    import app.db as dbmod
    from sqlalchemy.orm import sessionmaker

    dbmod.engine = dbmod._engine()
    dbmod.SessionLocal = sessionmaker(bind=dbmod.engine, autoflush=False, autocommit=False)
    import app.main as mainmod

    importlib.reload(mainmod)

    from fastapi.testclient import TestClient

    with TestClient(mainmod.app) as test_client:
        test_client.app_module = mainmod
        yield test_client
    dbmod.engine.dispose()
    get_settings.cache_clear()
    reset_groq_pool()


def become(client, cookies: dict | None = None) -> None:
    """Switch the browser: a fresh visitor, or someone whose cookies were saved earlier."""
    client.cookies.clear()
    for key, value in (cookies or {}).items():
        client.cookies.set(key, value)


def saved(client) -> dict:
    return dict(client.cookies.items())


def admin_sign_in(client, password: str = "test-pass"):
    return client.post("/admin/login", data={"username": "admin", "password": password}, follow_redirects=False)


def answer(client, name: str = "Sara Ahmed", **overrides):
    form = {"name": name, "age": "22", "education_level": "tertiary", "country": "PK", "low_income": "yes",
            "student": "yes", "consent": "1"}
    form.update(overrides)
    return client.post("/me/details", data=form, follow_redirects=False)
