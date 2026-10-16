"""Official programme list: real URLs, no invented rules."""

from __future__ import annotations

import json

from app.seed import CATALOGUE_IDS, PROGRAMS, build_rules


def test_catalogue_has_at_least_ten_active_programmes(api_client):
    from app.db import SessionLocal
    from app.models import Program

    db = SessionLocal()
    try:
        active = db.query(Program).filter(Program.status == "active").all()
        ids = {p.id for p in active}
        assert ids == CATALOGUE_IDS
        assert len(active) >= 10
        assert all(not p.is_demo_sample for p in active)
        assert all("DEMO" not in p.title.upper() for p in active)
    finally:
        db.close()


def test_programmes_use_official_urls_and_no_invented_rules():
    for prog in PROGRAMS:
        rules = build_rules(prog)
        assert rules["official_url"].startswith("https://")
        assert rules["source_url"] == rules["official_url"]
        assert rules["conditions"] == []
        assert "quota_quote" not in rules
        assert not rules["deadline"]
        assert "/demo/" not in rules["source_url"]


def test_home_lists_real_programmes(api_client):
    api_client.post(
        "/login",
        data={"email": "admin@rightpath.local", "password": "test-admin-pass", "next_path": "/"},
        follow_redirects=False,
    )
    home = api_client.get("/")
    assert home.status_code == 200
    assert "Benazir Income Support Programme" in home.text or "sources watched" in home.text

    api_client.post("/logout", follow_redirects=False)
    api_client.post(
        "/signup",
        data={"display_name": "Hina Khan", "email": "hina@example.com", "password": "citizen-pass"},
        follow_redirects=False,
    )
    page = api_client.get("/")
    assert "HEC scholarships and grants" in page.text
    assert "Benazir Kafaalat" in page.text
    assert "Punjab literacy" in page.text
    assert "Demo sample" not in page.text
    assert "two percent" not in page.text.lower()

    detail = api_client.get("/programmes/pk_hec_scholarships")
    assert detail.status_code == 200
    assert "hec.gov.pk" in detail.text
    assert "No rule has been approved" in detail.text


def test_old_demo_notice_route_is_gone(api_client):
    api_client.post(
        "/signup",
        data={"display_name": "Hina Khan", "email": "hina@example.com", "password": "citizen-pass"},
        follow_redirects=False,
    )
    missing = api_client.get("/demo/notices/inclusive-hiring")
    assert missing.status_code == 404


def test_privacy_delete_clears_session(api_client):
    login = api_client.post(
        "/signup",
        data={"display_name": "Hina Khan", "email": "hina@example.com", "password": "citizen-pass"},
        follow_redirects=False,
    )
    assert login.status_code == 303
    api_client.post(
        "/profile",
        data={"age": "30", "education_level": "tertiary"},
        follow_redirects=False,
    )
    deleted = api_client.post("/privacy/delete", follow_redirects=False)
    assert deleted.status_code == 303
    assert deleted.headers["location"].startswith("/login")
    assert "deleted=1" in deleted.headers["location"]
    wizard = api_client.get("/wizard", follow_redirects=False)
    assert wizard.status_code == 303
    assert "/login" in wizard.headers["location"]


def test_ensure_catalogue_upserts_on_existing_db(api_client):
    from app.db import SessionLocal
    from app.models import Program, ProgramVersion
    from app.seed import ensure_catalogue

    db = SessionLocal()
    try:
        program = db.get(Program, "pk_hec_scholarships")
        assert program is not None
        version = db.get(ProgramVersion, program.current_version_id)
        rules = json.loads(version.rules_json)
        assert rules["official_url"].startswith("https://")
        ensure_catalogue(db)
        again = db.get(Program, "pk_hec_scholarships")
        assert again.status == "active"
    finally:
        db.close()
