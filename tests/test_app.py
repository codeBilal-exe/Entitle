"""End-to-end checks of both views, the pipeline and every human stop."""

from __future__ import annotations

import json

from tests.conftest import admin_sign_in, answer, become, saved

NOTICE_PAGE = (
    "Youth Study Grant. Who can apply. You can apply if you are aged between 18 and 25 years "
    "and come from a low-income household. You must live in Pakistan. "
    "Applicants with a disability get extra help with travel."
)


def _db(client):
    import app.db as dbmod

    return dbmod.SessionLocal()


def _fake_page(monkeypatch, text=NOTICE_PAGE, title="Youth Study Grant | Gov"):
    from app.services import pulse

    monkeypatch.setattr(pulse, "fetch_page", lambda url: {"ok": True, "text": text, "title": title, "error": ""})


def _program(client, title):
    from app.models import Program

    db = _db(client)
    program = db.query(Program).filter(Program.title == title).one()
    db.close()
    return program


# ---------- the two views and admin sign-in ----------

def test_citizen_page_is_open_with_questions_and_no_google(client):
    page = client.get("/")
    assert page.status_code == 200
    assert "A few questions" in page.text
    assert "How old are you?" in page.text and "Which country do you live in?" in page.text
    assert "approved programmes ask this" in page.text or "approved programme ask this" in page.text
    assert "Google" not in page.text
    assert 'name="sentence"' not in page.text
    assert "Programmes Entitle can check right now" in page.text


def test_catalogue_is_real_verified_programmes(client):
    from app.models import Program
    from app.services.pulse import load_rules

    db = _db(client)
    programs = db.query(Program).all()
    assert len(programs) >= 5
    assert len({p.country for p in programs if p.country}) >= 3
    for program in programs:
        assert program.official_url.startswith("https://")
        assert load_rules(db, program)["conditions"], program.title
    db.close()


def test_admin_button_and_sign_in_opens_the_desk(client):
    assert "data-open-admin" in client.get("/").text
    response = admin_sign_in(client)
    assert response.status_code == 303 and response.headers["location"] == "/desk"
    desk = client.get("/desk")
    assert "Verification Desk" in desk.text and "Citizen view" in desk.text
    client.post("/admin/logout")
    assert client.get("/desk", follow_redirects=False).headers["location"] == "/#admin"


def test_wrong_admin_password_is_refused_then_locked(client):
    response = admin_sign_in(client, password="nope")
    assert response.headers["location"] == "/#admin"
    page = client.get("/")
    assert "do not match" in page.text and "data-autoopen" in page.text
    for _ in range(5):
        admin_sign_in(client, password="nope")
    admin_sign_in(client)  # right password, but locked for a minute
    assert "Too many wrong attempts" in client.get("/").text
    assert client.get("/desk", follow_redirects=False).status_code == 303


def test_admin_sign_in_is_off_without_a_password(client, monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("ADMIN_PASSWORD", "")
    get_settings.cache_clear()
    client.app_module.settings = get_settings()
    response = admin_sign_in(client, password="")
    assert response.headers["location"] == "/#admin"
    assert "switched off" in client.get("/").text


def test_desk_actions_need_the_admin(client):
    for path in ("/desk/run", "/desk/check-now", "/desk/jobs/1/approve", "/desk/news/1/release"):
        response = client.post(path, data={"url": "https://example.org/x"}, follow_redirects=False)
        assert response.status_code == 303 and response.headers["location"] == "/#admin", path


# ---------- citizen ----------

def test_answers_create_a_saved_record_and_show_receipts(client):
    from app.models import Profile, User

    response = answer(client)
    assert response.status_code == 303 and response.headers["location"] == "/#matches"
    page = client.get("/").text
    assert "Hi, Sara" in page and "You may be owed" in page
    assert "HEC Need-Based Scholarships" in page and "Approved by Entitle team" in page
    db = _db(client)
    user = db.query(User).filter(User.role == "citizen").one()
    profile = db.query(Profile).filter(Profile.user_id == user.id).one()
    assert user.display_name == "Sara Ahmed"
    assert json.loads(profile.attributes_json) == {"age": 22, "education_level": "tertiary", "country": "PK",
                                                   "low_income": True, "student": True}
    db.close()


def test_updating_answers_keeps_the_same_record(client):
    from app.models import User

    answer(client)
    answer(client, name="Sara A.", age="23")
    db = _db(client)
    users = db.query(User).filter(User.role == "citizen").all()
    assert len(users) == 1 and users[0].display_name == "Sara A."
    db.close()


def test_first_answers_need_a_name_and_a_valid_age(client):
    assert answer(client, name="").headers["location"] == "/#questions"
    assert "first name" in client.get("/").text
    answer(client, age="500")
    assert "Age must be a number between 5 and 120" in client.get("/").text
    answer(client, name="Sam", age="", education_level="", country="", low_income="", student="")
    assert "Answer at least one question" in client.get("/").text


def test_citizen_actions_without_answers_go_to_the_questions(client):
    response = client.post("/me/apply/anything", follow_redirects=False)
    assert response.headers["location"] == "/#questions"


def test_packet_needs_eligibility_and_the_applicants_approval(client):
    from app.models import Application

    answer(client)
    hec = _program(client, "HEC Need-Based Scholarships")
    snap = _program(client, "SNAP food benefits")
    client.post(f"/me/apply/{snap.id}")  # lives in Pakistan, so the US programme is not a match
    client.post(f"/me/apply/{hec.id}")
    db = _db(client)
    apps = db.query(Application).all()
    assert [a.program_id for a in apps] == [hec.id]
    assert apps[0].state == "ready"
    assert "email" not in json.loads(apps[0].payload_json)["fields"]
    db.close()
    client.post(f"/me/applications/{apps[0].id}/approve")
    db = _db(client)
    approved = db.get(Application, apps[0].id)
    assert approved.state == "approved" and approved.approval_hash
    db.close()


def test_one_citizen_cannot_touch_anothers_packet(client):
    from app.models import Application

    answer(client, name="Ana")
    hec = _program(client, "HEC Need-Based Scholarships")
    client.post(f"/me/apply/{hec.id}")
    db = _db(client)
    app_id = db.query(Application).one().id
    db.close()
    become(client)
    answer(client, name="Bilal")
    assert client.post(f"/me/applications/{app_id}/approve").status_code == 403
    assert client.post(f"/me/applications/{app_id}/withdraw").status_code == 403


def test_delete_removes_everything(client):
    from app.models import Profile, User

    answer(client)
    client.post("/me/delete")
    db = _db(client)
    assert db.query(User).filter(User.role == "citizen").count() == 0 and db.query(Profile).count() == 0
    db.close()
    assert "A few questions" in client.get("/").text


# ---------- desk pipeline and human stops ----------

def test_pipeline_from_url_to_approval_and_alerts(client, monkeypatch):
    from app.models import IngestionJob, Notification, Program

    answer(client)
    sara = saved(client)
    become(client)
    admin_sign_in(client)
    _fake_page(monkeypatch)

    response = client.post("/desk/run", data={"url": "https://youth.gov.pk/grant"}, follow_redirects=False)
    assert response.status_code == 303 and "job=" in response.headers["location"]
    db = _db(client)
    job = db.query(IngestionJob).one()
    steps = [s["key"] for s in json.loads(job.steps_json)]
    assert steps == ["fetch", "draft", "receipts", "impact", "review"]
    draft = json.loads(job.draft_json)
    assert sorted(c["attr"] for c in draft["conditions"]) == ["age", "low_income"]
    assert json.loads(job.quote_check_json)["passed"] is True
    keep = [c["id"] for c in draft["conditions"]]
    db.close()

    desk = client.get(f"/desk?job={job.id}")
    assert "Found word for word on the page" in desk.text
    assert "1 would be told they may qualify" in desk.text

    client.post(f"/desk/jobs/{job.id}/approve", data={"keep": keep})
    db = _db(client)
    job = db.get(IngestionJob, job.id)
    assert job.status == "approved" and job.reviewed_by == "Rev"
    assert db.get(Program, job.program_id).country == "PK"
    assert [(a.kind, a.status) for a in db.query(Notification).all()] == [("newly_eligible", "queued")]
    db.close()

    become(client, sara)
    assert "You may now qualify for" in client.get("/").text


def test_made_up_quote_is_blocked_and_cannot_be_ticked_live(client, monkeypatch):
    from app.models import IngestionJob, Program
    from app.services.pulse import load_rules

    admin_sign_in(client)
    _fake_page(monkeypatch)
    invented = {
        "title": "Youth Study Grant", "country": "PK", "domain": "education",
        "conditions": [
            {"attr": "age", "op": "between", "value": [18, 25], "source_quote": "aged between 18 and 25 years"},
            {"attr": "student", "op": "is_true", "source_quote": "must be enrolled full time at a university"},
        ],
    }
    monkeypatch.setattr("app.services.drafting._model_json", lambda user: invented)
    monkeypatch.setattr("app.services.drafting.get_groq_pool", lambda: [1])
    client.post("/desk/run", data={"url": "https://youth.gov.pk/grant"})
    db = _db(client)
    job = db.query(IngestionJob).one()
    check = json.loads(job.quote_check_json)
    assert check["passed"] is False and check["failed_ids"] == ["c2"]
    db.close()

    assert "Not on the page. Blocked" in client.get("/desk").text
    client.post(f"/desk/jobs/{job.id}/approve", data={"keep": ["c1", "c2"]})
    db = _db(client)
    assert db.get(IngestionJob, job.id).status == "pending_review"
    db.close()
    client.post(f"/desk/jobs/{job.id}/approve", data={"keep": ["c1"]})
    db = _db(client)
    approved = db.get(IngestionJob, job.id)
    assert approved.status == "approved"
    rules = load_rules(db, db.get(Program, approved.program_id))
    assert [c["attr"] for c in rules["conditions"]] == ["age"]
    db.close()


def test_a_loss_is_held_until_a_reviewer_releases_it(client):
    from app.models import IngestionJob, Notification

    answer(client)
    sara = saved(client)
    become(client)
    admin_sign_in(client)
    admin = saved(client)
    hec = _program(client, "HEC Need-Based Scholarships")
    client.post("/desk/run", data={
        "program_id": hec.id,
        "notice_text": "Need based scholarships are for students aged between 16 and 20 years from financially needy families.",
    })
    db = _db(client)
    job = db.query(IngestionJob).one()
    draft = json.loads(job.draft_json)
    db.close()
    assert any(c["attr"] == "age" for c in draft["conditions"])
    client.post(f"/desk/jobs/{job.id}/approve", data={"keep": [c["id"] for c in draft["conditions"]]})
    db = _db(client)
    held = db.query(Notification).one()
    assert held.kind == "newly_not_eligible" and held.status == "pending_review"
    db.close()

    become(client, sara)
    assert "You may no longer qualify" not in client.get("/").text

    become(client, admin)
    assert "may lose" in client.get("/desk").text
    client.post(f"/desk/news/{held.id}/release")
    become(client, sara)
    page = client.get("/")
    assert "You may no longer qualify" in page.text and "checked this before it reached you" in page.text


def test_unreachable_page_stops_with_a_clear_message(client, monkeypatch):
    from app.services import pulse

    admin_sign_in(client)
    monkeypatch.setattr(pulse, "fetch_page", lambda url: {"ok": False, "text": "", "title": "", "error": "The site could not be reached."})
    page = client.post("/desk/run", data={"url": "https://down.gov.pk/x"})
    assert "The pipeline stopped: The site could not be reached." in page.text


def test_bad_url_is_refused(client):
    admin_sign_in(client)
    page = client.post("/desk/run", data={"url": "not a link"})
    assert "starting with https://" in page.text


def test_internal_api_needs_the_secret_and_cannot_approve(client):
    assert client.get("/api/internal/queue").status_code == 401
    ok = client.get("/api/internal/queue", headers={"x-entitle-secret": "test-secret"})
    assert ok.status_code == 200 and ok.json()["ok"] is True
    assert client.post("/api/internal/approve", headers={"x-entitle-secret": "test-secret"}).status_code in {404, 405}


def test_desk_warns_when_a_new_draft_looks_like_a_live_programme(client, monkeypatch):
    admin_sign_in(client)
    _fake_page(monkeypatch, title="SNAP food benefits - Overview | USDA")
    page = client.post("/desk/run", data={"url": "https://www.fns.usda.gov/snap/another-page"})
    assert "which is already live" in page.text
