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

    # Rebuild settings + engine bound to the test DB.
    from app.config import get_settings

    get_settings.cache_clear()

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
