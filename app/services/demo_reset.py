"""Reset demo runtime data while keeping the schema and re-seeding."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import (
    Application,
    DemoNotice,
    Event,
    IngestionJob,
    Notification,
    Program,
    ProgramVersion,
    Source,
    User,
)
from app.seed import INCLUSIVE_HIRING_NOTICE, seed_if_empty
from app.services import pulse
from app.services.timeline import log_event


def reset_demo(db: Session) -> dict[str, str]:
    db.query(Notification).delete()
    db.query(Application).delete()
    db.query(IngestionJob).delete()
    db.query(Event).delete()

    # Drop extra program versions; keep version 1 live.
    versions = db.query(ProgramVersion).order_by(ProgramVersion.id).all()
    keep_ids: set[int] = set()
    for program in db.query(Program).all():
        first = (
            db.query(ProgramVersion)
            .filter(ProgramVersion.program_id == program.id)
            .order_by(ProgramVersion.version.asc(), ProgramVersion.id.asc())
            .first()
        )
        if first:
            # Restore original age band for inclusive hiring
            if program.id == "demo_pk_work_01":
                import json

                rules = json.loads(first.rules_json)
                for condition in rules.get("conditions") or []:
                    if condition.get("id") == "c2":
                        condition["value"] = [18, 45]
                        condition["source_quote"] = "aged between 18 and 45 years"
                rules["version"] = 1
                first.rules_json = json.dumps(rules)
                first.version = 1
            program.current_version_id = first.id
            keep_ids.add(first.id)
    for version in versions:
        if version.id not in keep_ids:
            db.delete(version)

    notice = db.get(DemoNotice, "inclusive-hiring")
    if notice:
        notice.body = INCLUSIVE_HIRING_NOTICE

    # Clear source hashes so the next check establishes a clean baseline.
    for source in db.query(Source).all():
        source.last_hash = ""
        source.status = "ok"

    db.commit()

    # If somehow empty, seed.
    if not db.query(User).first():
        seed_if_empty(db)

    # Re-baseline hashes
    pulse.check_sources(db, auto_ingest=False)
    log_event(
        db,
        stage="demo_reset",
        detail="Demo runtime cleared and baseline restored",
        case_id="system",
        human_decision=True,
    )
    return {"ok": "true", "detail": "Demo reset complete"}
