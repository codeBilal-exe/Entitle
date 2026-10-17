"""Sessions, the anonymous citizen record, and the admin sign-in for the Verification Desk."""

from __future__ import annotations

import hmac
import secrets
import threading
import time
from datetime import datetime

from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from app.config import get_settings
from app.models import User

MAX_FAILURES = 5
LOCKOUT_SECONDS = 60
_failures: dict[str, list[float]] = {}
_lock = threading.Lock()


def mount_session(app) -> None:
    settings = get_settings()
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        session_cookie="entitle_session",
        same_site="lax",
        https_only=settings.base_url.startswith("https://"),
        max_age=60 * 60 * 24 * 180,
    )


def new_citizen(db: Session, name: str) -> User:
    user = User(
        email=f"citizen-{secrets.token_hex(10)}@entitle.local",
        display_name=name.strip()[:120] or "Friend",
        role="citizen",
        last_login_at=datetime.utcnow(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def locked_out(client_key: str) -> bool:
    now = time.monotonic()
    with _lock:
        recent = [t for t in _failures.get(client_key, []) if now - t < LOCKOUT_SECONDS]
        _failures[client_key] = recent
        return len(recent) >= MAX_FAILURES


def check_admin(username: str, password: str, client_key: str) -> bool:
    settings = get_settings()
    if not settings.admin_ready:
        return False
    user_ok = hmac.compare_digest(username.strip().encode(), settings.admin_username.strip().encode())
    pass_ok = hmac.compare_digest(password.encode(), settings.admin_password.encode())
    if user_ok and pass_ok:
        with _lock:
            _failures.pop(client_key, None)
        return True
    with _lock:
        _failures.setdefault(client_key, []).append(time.monotonic())
    return False


def admin_user(db: Session) -> User:
    settings = get_settings()
    key = f"admin-{settings.admin_username.strip().lower()}@entitle.local"
    user = db.query(User).filter(User.email == key).first()
    if user is None:
        user = User(email=key, display_name="", role="reviewer")
        db.add(user)
    user.display_name = settings.admin_name.strip()[:120] or "Entitle reviewer"
    user.role = "reviewer"
    user.last_login_at = datetime.utcnow()
    db.commit()
    db.refresh(user)
    return user
