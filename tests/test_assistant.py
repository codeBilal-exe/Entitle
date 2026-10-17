"""Citizen assistant: Groq may read the sentence. The rule engine decides."""

from app.services.assistant import (
    extract_deterministic,
    pick_card,
    summary_is_grounded,
    _corroborated,
)


SENTENCE = (
    "I am 22 years old, at university in Punjab, and my household income is low."
)


def _login(client, email, password):
    return client.post(
        "/login",
        data={"email": email, "password": password, "next_path": "/"},
        follow_redirects=False,
    )


def test_deterministic_extract_reads_age_study_income_and_province():
    found = extract_deterministic(SENTENCE)
    assert found["age"] == 22
    assert found["education_level"] == "tertiary"
    assert found["low_income"] is True
    assert found["province"] == "Punjab"


def test_model_cannot_invent_a_field_the_sentence_does_not_support():
    found = _corroborated(
        SENTENCE,
        {"age": 99, "disability": True, "education_level": "primary", "low_income": True},
    )
    assert "disability" not in found
    assert "age" not in found or found["age"] == 22
    assert found.get("education_level") != "primary"
    assert found["low_income"] is True


def test_summary_keeps_quoted_facts_and_drops_an_invented_programme():
    cards = [
        {
            "title": "HEC need-based scholarships",
            "quote": "aged between 18 and 35 years",
            "deadline": "2026-12-31",
            "document": "CNIC",
            "next_step": "Prepare the packet.",
        }
    ]
    titles = ["HEC need-based scholarships", "Pakistan Bait-ul-Mal"]
    good = "HEC need-based scholarships matches you. The notice says aged between 18 and 35 years."
    assert summary_is_grounded(good, cards, SENTENCE, titles)
    invented = "You also qualify for Pakistan Bait-ul-Mal with a quota of 500."
    assert not summary_is_grounded(invented, cards, SENTENCE, titles)


def test_packet_is_prepared_only_for_the_named_eligible_programme():
    cards = [
        {"title": "HEC need-based scholarships", "status": "eligible", "program_id": "pk_hec_need_based"},
        {"title": "PEEF scholarships", "status": "eligible", "program_id": "pk_peef"},
    ]
    chosen = pick_card("HEC need-based", cards)
    assert chosen["program_id"] == "pk_hec_need_based"
    assert pick_card("", cards) is None


def test_sentence_saves_profile_and_shows_the_approved_quote(api_client, monkeypatch):
    def fake(system, user):
        if "short reply" in system:
            return {
                "summary": (
                    "HEC need-based scholarships matches you. "
                    "The notice says aged between 18 and 35 years."
                )
            }
        return {
            "age": 99,
            "disability": True,
            "wants_packet": True,
            "program_hint": "Pakistan Bait-ul-Mal",
        }

    monkeypatch.setattr("app.services.assistant._groq_json", fake)
    _login(api_client, "citizen@entitle.local", "test-citizen")
    sent = api_client.post(
        "/assistant",
        data={"sentence": SENTENCE},
        follow_redirects=False,
    )
    assert sent.status_code == 303
    assert sent.headers["location"] == "/"

    home = api_client.get("/")
    assert home.status_code == 200
    assert "HEC need-based scholarships" in home.text
    assert "aged between 18 and 35 years" in home.text
    assert "CNIC" in home.text
    assert "2026-12-31" in home.text
    assert "Groq wrote this summary" in home.text
    assert "Pakistan Bait-ul-Mal" not in home.text.split("Tell ENTITLE your situation")[-1].split("Programmes")[0]

    from app.db import SessionLocal
    from app.models import Profile, User

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "citizen@entitle.local").one()
        profile = db.query(Profile).filter(Profile.user_id == user.id).one()
        import json

        attrs = json.loads(profile.attributes_json)
        assert attrs["age"] == 22
        assert attrs["education_level"] == "tertiary"
        assert attrs["low_income"] is True
        assert "disability" not in attrs or attrs["disability"] is False
    finally:
        db.close()


def test_prepare_sentence_drafts_a_packet_that_is_not_sent(api_client, monkeypatch):
    monkeypatch.setattr("app.services.assistant._groq_json", lambda system, user: None)
    _login(api_client, "citizen@entitle.local", "test-citizen")
    sent = api_client.post(
        "/assistant",
        data={
            "sentence": (
                "I am 22 years old, at university, from a low-income household. "
                "Prepare the HEC need-based packet."
            )
        },
        follow_redirects=False,
    )
    assert sent.status_code == 303
    location = sent.headers["location"]
    assert location.startswith("/applications/")
    assert "drafted=1" in location

    page = api_client.get(location)
    assert page.status_code == 200
    assert "I approve this exact packet" in page.text
    assert "Waiting for your approval" in page.text
    assert "It is not sent until you approve it." in page.text
    assert "Send now" not in page.text

    from app.db import SessionLocal
    from app.models import Application, User

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "citizen@entitle.local").one()
        application = (
            db.query(Application).filter(Application.user_id == user.id).one()
        )
        assert application.state == "ready"
        assert application.state != "sent"
    finally:
        db.close()


def test_staff_cannot_use_the_citizen_assistant(api_client):
    _login(api_client, "staff.one@entitle.local", "test-staff-1")
    sent = api_client.post(
        "/assistant",
        data={"sentence": SENTENCE},
        follow_redirects=False,
    )
    assert sent.status_code == 403
