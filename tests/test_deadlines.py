"""Seam: deterministic deadline reminders."""

from datetime import date, timedelta
import json

from app.engine.approval_gate import ApplicationState
from app.models import Application, Program, ProgramVersion, User
from app.services.deadlines import run_deadline_reminders


def test_reminder_created_for_open_application_near_deadline(api_client):
    api_client.post(
        "/signup",
        data={"display_name": "Hina Khan", "email": "hina@example.com", "password": "citizen-pass"},
        follow_redirects=False,
    )
    from app.db import SessionLocal

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "hina@example.com").one()
        program = db.get(Program, "pk_hec_scholarships")
        assert program and program.current_version_id
        version = db.get(ProgramVersion, program.current_version_id)
        rules = json.loads(version.rules_json)
        rules["deadline"] = (date.today() + timedelta(days=5)).isoformat()
        version.rules_json = json.dumps(rules)
        db.add(
            Application(
                id="app-deadline-1",
                user_id=user.id,
                program_id=program.id,
                state=ApplicationState.READY.value,
                payload_json="{}",
                idempotency_key="deadline-test-1",
            )
        )
        db.commit()
        result = run_deadline_reminders(db, within_days=14)
        assert result["created"] >= 1
        again = run_deadline_reminders(db, within_days=14)
        assert again["created"] == 0
    finally:
        db.close()

    alerts = api_client.get("/alerts")
    assert alerts.status_code == 200
    assert "Note the deadline" in alerts.text or "deadline" in alerts.text.lower()
    assert "Unread" in alerts.text or 'class="nav-count"' in alerts.text
