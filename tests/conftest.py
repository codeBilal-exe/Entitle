"""Isolate API tests from the developer's running uvicorn database."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

TEST_DB = Path("data/test_rightpath.db")


@pytest.fixture()
def api_client(monkeypatch):
    """Fresh app + SQLite file per test (safe while uvicorn uses rightpath.db)."""
    TEST_DB.parent.mkdir(exist_ok=True)
    if TEST_DB.exists():
        try:
            TEST_DB.unlink()
        except PermissionError:
            pass

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{TEST_DB.as_posix()}")
    monkeypatch.setenv("ENABLE_SCHEDULER", "false")
    monkeypatch.setenv("N8N_SHARED_SECRET", "dev-shared-secret")
    monkeypatch.setenv("FETCH_REMOTE", "false")
    monkeypatch.setenv("ADMIN_EMAIL", "admin@rightpath.local")
    monkeypatch.setenv("ADMIN_PASSWORD", "test-admin-pass")
    monkeypatch.setenv("STAFF_ONE_EMAIL", "staff.one@rightpath.local")
    monkeypatch.setenv("STAFF_ONE_PASSWORD", "test-staff-1")
    monkeypatch.setenv("STAFF_TWO_EMAIL", "staff.two@rightpath.local")
    monkeypatch.setenv("STAFF_TWO_PASSWORD", "test-staff-2")
    monkeypatch.setenv("CITIZEN_EMAIL", "citizen@rightpath.local")
    monkeypatch.setenv("CITIZEN_PASSWORD", "test-citizen")
    monkeypatch.setenv("CITIZEN_DISPLAY_NAME", "Hina Khan")
    monkeypatch.setenv("GROQ_API_KEY", "")
    monkeypatch.setenv("GROQ_API_KEYS", "")

    # Rebuild settings + engine bound to the test DB.
    from app.config import get_settings
    from app.services.groq_pool import reset_groq_pool

    get_settings.cache_clear()
    reset_groq_pool()

    import app.db as dbmod
    from app.db import Base
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    connect_args = {"check_same_thread": False}
    dbmod.engine = create_engine(
        f"sqlite:///{TEST_DB.as_posix()}", connect_args=connect_args
    )
    dbmod.SessionLocal = sessionmaker(
        bind=dbmod.engine, autoflush=False, autocommit=False
    )
    # Models must be imported so metadata includes every table before create_all.
    import app.models  # noqa: F401

    Base.metadata.drop_all(bind=dbmod.engine)
    Base.metadata.create_all(bind=dbmod.engine)

    # Re-import app after engine swap so startup uses SessionLocal above.
    import importlib
    import app.main as mainmod

    importlib.reload(mainmod)

    from fastapi.testclient import TestClient

    with TestClient(mainmod.app) as client:
        yield client

    get_settings.cache_clear()
    reset_groq_pool()
