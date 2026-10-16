"""Server-side role and ownership checks."""

from __future__ import annotations

import json

from app.models import Application, Notification


def _signup(client, email, name="Hina Khan"):
    return client.post(
        "/signup",
        data={"display_name": name, "email": email, "password": "citizen-pass"},
        follow_redirects=False,
    )


def test_second_citizen_cannot_open_the_first(api_client):
    _signup(api_client, "hina@example.com", "Hina Khan")
    api_client.post(
        "/profile",
        data={"age": "21", "education_level": "secondary", "consent_notifications": "1"},
        follow_redirects=False,
    )
    api_client.post(
        "/apply/pk_hec_scholarships",
        data={
            "full_name": "Hina Khan",
            "contact_email": "hina@example.com",
            "age": 21,
            "education_level": "secondary",
        },
        follow_redirects=False,
    )

    from app.db import SessionLocal
    from app.models import User

    db = SessionLocal()
    try:
        owner = db.query(User).filter(User.email == "hina@example.com").one()
        application = db.query(Application).filter(Application.user_id == owner.id).one()
        alert = Notification(
            user_id=owner.id,
            program_id="pk_hec_scholarships",
            kind="newly_eligible",
            status="queued",
            detail_json=json.dumps(
                {
                    "what_changed": "The rules changed.",
                    "meaning": "You may now qualify for HEC scholarships and grants.",
                    "quote": "",
                    "next_step": "apply",
                    "released_by": "",
                }
            ),
        )
        db.add(alert)
        db.commit()
        db.refresh(alert)
        owner_id = owner.id
        application_id = application.id
        alert_id = alert.id
    finally:
        db.close()

    api_client.post("/logout", follow_redirects=False)
    _signup(api_client, "omar@example.com", "Omar Ali")

    assert api_client.get(f"/profiles/{owner_id}").status_code == 403
    assert api_client.get(f"/applications/{application_id}").status_code == 403
    assert api_client.get(f"/alerts/{alert_id}").status_code == 403
    alerts = api_client.get("/alerts")
    assert alerts.status_code == 200
    assert "Hina Khan" not in alerts.text
    assert "You may now qualify" not in alerts.text or "None yet" in alerts.text


def test_citizen_cannot_open_staff_tools(api_client):
    _signup(api_client, "hina@example.com")
    assert api_client.get("/curator").status_code == 403
    assert api_client.get("/navigator").status_code == 403
    assert api_client.get("/timeline").status_code == 403
    blocked = api_client.post("/curator/check-now", follow_redirects=False)
    assert blocked.status_code == 403


def test_staff_cannot_toggle_sending_or_open_a_profile(api_client):
    from app.db import SessionLocal
    from app.models import User

    _signup(api_client, "hina@example.com")
    api_client.post(
        "/profile",
        data={"age": "21", "education_level": "secondary"},
        follow_redirects=False,
    )
    db = SessionLocal()
    try:
        owner_id = db.query(User).filter(User.email == "hina@example.com").one().id
    finally:
        db.close()

    api_client.post("/logout", follow_redirects=False)
    api_client.post(
        "/login",
        data={
            "email": "staff.one@rightpath.local",
            "password": "test-staff-1",
            "next_path": "/",
        },
        follow_redirects=False,
    )
    assert api_client.get(f"/profiles/{owner_id}").status_code == 403
    assert api_client.post("/curator/kill-switch", data={"enabled": "0"}).status_code == 403
    assert api_client.get("/alerts").status_code == 403


def test_admin_cannot_open_a_citizen_profile(api_client):
    from app.db import SessionLocal
    from app.models import User

    _signup(api_client, "hina@example.com")
    db = SessionLocal()
    try:
        owner_id = db.query(User).filter(User.email == "hina@example.com").one().id
    finally:
        db.close()
    api_client.post("/logout", follow_redirects=False)
    api_client.post(
        "/login",
        data={"email": "admin@rightpath.local", "password": "test-admin-pass", "next_path": "/"},
        follow_redirects=False,
    )
    assert api_client.get(f"/profiles/{owner_id}").status_code == 403
    assert api_client.get("/profile").status_code == 403
