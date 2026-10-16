from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def _engine():
    settings = get_settings()
    connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
    return create_engine(settings.database_url, connect_args=connect_args)


engine = _engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_columns()


def _ensure_columns() -> None:
    """Add columns that create_all will not alter onto an existing SQLite file."""
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        if "sources" in tables:
            names = {col["name"] for col in inspector.get_columns("sources")}
            if "last_text" not in names:
                conn.execute(text("ALTER TABLE sources ADD COLUMN last_text TEXT DEFAULT ''"))
        if "notifications" in tables:
            names = {col["name"] for col in inspector.get_columns("notifications")}
            if "read_at" not in names:
                conn.execute(text("ALTER TABLE notifications ADD COLUMN read_at DATETIME"))
