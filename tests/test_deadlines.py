"""Seam: deterministic deadline reminders."""

from datetime import date, timedelta
import json

from app.engine.approval_gate import ApplicationState
from app.models import Application, Program, ProgramVersion
from app.services.deadlines import run_deadline_reminders


def test_reminder_created_for_open_application_near_deadline(api_client):
    # api_client already started app + seeded DB via fixture
    from app.db import SessionLocal

    db = SessionLocal()
    try:
        program = db.get(Program, "demo_pk_work_01")
        assert program and program.current_version_id
        version = db.get(ProgramVersion, program.current_version_id)
        rules = json.loads(version.rules_json)
        rules["deadline"] = (date.today() + timedelta(days=5)).isoformat()
        version.rules_json = json.dumps(rules)
        db.add(
            Application(
                id="app-deadline-1",
                user_id=1,
                program_id="demo_pk_work_01",
                state=ApplicationState.READY.value,
                payload_json="{}",
                idempotency_key="deadline-test-1",
            )
        )
        db.commit()
        result = run_deadline_reminders(db, within_days=14)
        assert result["created"] >= 1
        # Idempotent
        again = run_deadline_reminders(db, within_days=14)
        assert again["created"] == 0
    finally:
        db.close()
