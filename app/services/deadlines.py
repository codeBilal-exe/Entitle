"""Deterministic deadline reminders — no AI agent required."""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.models import Application, Notification, Program, ProgramVersion, User
from app.services.timeline import log_event


def _deadline_for(db: Session, program_id: str) -> date | None:
    program = db.get(Program, program_id)
    if not program or not program.current_version_id:
        return None
    version = db.get(ProgramVersion, program.current_version_id)
    if not version:
        return None
    rules: dict[str, Any] = json.loads(version.rules_json)
    raw = rules.get("deadline")
    if not raw:
        return None
    try:
        return date.fromisoformat(str(raw)[:10])
    except ValueError:
        return None


def run_deadline_reminders(db: Session, *, within_days: int = 14) -> dict[str, Any]:
    today = date.today()
    created = 0
    scanned = 0
    apps = (
        db.query(Application)
        .filter(Application.state.in_(["draft", "ready", "approved"]))
        .all()
    )
    for application in apps:
        scanned += 1
        deadline = _deadline_for(db, application.program_id)
        if not deadline:
            continue
        days_left = (deadline - today).days
        if days_left < 0 or days_left > within_days:
            continue
        # Avoid duplicate open reminders for the same application.
        existing = (
            db.query(Notification)
            .filter(
                Notification.user_id == application.user_id,
                Notification.program_id == application.program_id,
                Notification.kind == "deadline_reminder",
                Notification.status.in_(["queued", "pending_review"]),
            )
            .first()
        )
        if existing:
            continue
        user = db.get(User, application.user_id)
        db.add(
            Notification(
                user_id=application.user_id,
                program_id=application.program_id,
                kind="deadline_reminder",
                status="queued",
                detail_json=json.dumps(
                    {
                        "application_id": application.id,
                        "deadline": deadline.isoformat(),
                        "days_left": days_left,
                        "display_name": user.display_name if user else "",
                        "before": "open",
                        "after": "reminder",
                    }
                ),
            )
        )
        log_event(
            db,
            stage="deadline_reminder",
            detail=f"{application.id} due in {days_left} day(s)",
            case_id=application.id,
        )
        created += 1
    db.commit()
    return {"ok": True, "scanned": scanned, "created": created, "as_of": today.isoformat()}
