"""Internal hooks still draft, quote-check, and hold a loss for a person."""

import json

SECRET = {"x-entitle-secret": "dev-shared-secret"}

NOTICE = (
    "This programme supports persons with disabilities aged between 18 and 35 years "
    "who have completed secondary education or higher."
)


def test_unauthorized_internal_rejected(api_client):
    response = api_client.get("/api/internal/health")
    assert response.status_code == 401


def test_text_change_holds_a_loss_for_staff(api_client):
    api_client.post(
        "/signup",
        data={"display_name": "Hina Khan", "email": "hina@example.com", "password": "citizen-pass"},
        follow_redirects=False,
    )
    api_client.post(
        "/profile",
        data={
            "age": "40",
            "education_level": "tertiary",
            "disability": "yes",
            "consent_notifications": "1",
        },
        follow_redirects=False,
    )

    from app.db import SessionLocal
    from app.models import Program, ProgramVersion

    db = SessionLocal()
    try:
        program = db.get(Program, "pk_hec_scholarships")
        version = db.get(ProgramVersion, program.current_version_id)
        rules = json.loads(version.rules_json)
        rules["conditions"] = [
            {
                "id": "c1",
                "attr": "disability",
                "op": "is_true",
                "source_quote": "persons with disabilities",
            },
            {
                "id": "c2",
                "attr": "age",
                "op": "between",
                "value": [18, 45],
                "source_quote": "aged between 18 and 45 years",
            },
            {
                "id": "c3",
                "attr": "education_level",
                "op": "in",
                "value": ["secondary", "tertiary"],
                "source_quote": "completed secondary education or higher",
            },
        ]
        version.rules_json = json.dumps(rules)
        db.commit()
    finally:
        db.close()

    ingested = api_client.post(
        "/api/internal/ingest",
        headers=SECRET,
        json={"program_id": "pk_hec_scholarships", "notice_text": NOTICE, "prefer_llm": False},
    ).json()
    assert ingested["ok"] is True

    approved = api_client.post(
        "/api/internal/approve",
        headers=SECRET,
        json={"job_id": ingested["ingestion_job_id"], "reviewed_by": "staff.one@entitle.local"},
    ).json()
    assert approved["ok"] is True
    hina = next(row for row in approved["routed"] if row["display_name"] == "Hina Khan")
    assert hina["route"] == "navigator_review"
    assert "may no longer qualify" in hina["meaning"]

    api_client.post("/logout", follow_redirects=False)
    api_client.post(
        "/login",
        data={"email": "hina@example.com", "password": "citizen-pass", "next_path": "/alerts"},
        follow_redirects=False,
    )
    alerts = api_client.get("/alerts")
    assert "None yet. A loss stays with staff" in alerts.text
    assert "may no longer qualify for" not in alerts.text


def test_replay_endpoint_does_not_restore_a_demo_notice(api_client):
    replay = api_client.post("/api/internal/replay/tighten", headers=SECRET).json()
    assert replay["ok"] is False
    assert replay["error"] == "demo_replay_removed"
