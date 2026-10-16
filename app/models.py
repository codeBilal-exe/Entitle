from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.utcnow()


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(32), default="applicant")
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    profile: Mapped[Profile | None] = relationship(back_populates="user", uselist=False)


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    attributes_json: Mapped[str] = mapped_column(Text, default="{}")
    consent_notifications: Mapped[bool] = mapped_column(Boolean, default=False)
    consent_email: Mapped[str] = mapped_column(String(255), default="")

    user: Mapped[User] = relationship(back_populates="profile")


class Program(Base):
    __tablename__ = "programs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    country: Mapped[str] = mapped_column(String(8))
    domain: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(255))
    provider: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), default="active")
    is_demo_sample: Mapped[bool] = mapped_column(Boolean, default=True)
    current_version_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class ProgramVersion(Base):
    __tablename__ = "program_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    program_id: Mapped[str] = mapped_column(ForeignKey("programs.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    rules_json: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(String(512), default="")
    last_verified: Mapped[str] = mapped_column(String(32), default="")
    approved_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="live")


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    program_id: Mapped[str] = mapped_column(ForeignKey("programs.id"), index=True)
    url: Mapped[str] = mapped_column(String(512))
    label: Mapped[str] = mapped_column(String(255), default="")
    last_hash: Mapped[str] = mapped_column(String(64), default="")
    last_checked: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="not_checked")
    is_demo_controllable: Mapped[bool] = mapped_column(Boolean, default=False)
    last_text: Mapped[str] = mapped_column(Text, default="")


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources.id"), nullable=True)
    program_id: Mapped[str] = mapped_column(String(64), index=True)
    notice_text: Mapped[str] = mapped_column(Text, default="")
    draft_json: Mapped[str] = mapped_column(Text, default="{}")
    quote_check_json: Mapped[str] = mapped_column(Text, default="{}")
    diff_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(32), default="pending_review")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    reviewed_by: Mapped[str | None] = mapped_column(String(120), nullable=True)


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    program_id: Mapped[str] = mapped_column(ForeignKey("programs.id"), index=True)
    state: Mapped[str] = mapped_column(String(32), default="draft")
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    approval_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    program_id: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="pending_review")
    detail_json: Mapped[str] = mapped_column(Text, default="{}")
    reviewed_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[str] = mapped_column(String(64), index=True, default="")
    stage: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="ok")
    detail: Mapped[str] = mapped_column(Text, default="")
    human_decision: Mapped[bool] = mapped_column(Boolean, default=False)
    at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class DemoNotice(Base):
    """Controllable DEMO source body so the live rule-change can be shown on cue."""

    __tablename__ = "demo_notices"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
