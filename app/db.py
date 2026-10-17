from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def _normalize(url: str) -> str:
    # Hosted Postgres hands out postgres:// URLs; SQLAlchemy wants the psycopg driver name.
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


def database_url() -> str:
    return _normalize(get_settings().database_url)


def _make_engine(url: str):
    if url.startswith("sqlite"):
        return create_engine(url, connect_args={"check_same_thread": False})
    # Neon's pooled endpoint runs PgBouncer in transaction mode, so psycopg must not
    # keep server-side prepared statements; computes also suspend when idle.
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_recycle=300,
        pool_size=5,
        max_overflow=5,
        connect_args={"prepare_threshold": None},
    )


def _engine():
    return _make_engine(database_url())


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

    direct = get_settings().database_url_unpooled
    if direct and not database_url().startswith("sqlite"):
        schema_engine = _make_engine(_normalize(direct))
        try:
            Base.metadata.create_all(bind=schema_engine)
        finally:
            schema_engine.dispose()
    else:
        Base.metadata.create_all(bind=engine)
