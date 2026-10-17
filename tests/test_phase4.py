"""Phase 4 seams: gold-set, kill switch, manual pack, demo reset."""

from pathlib import Path

from app.services.goldset import run_gold_set
from app.services.manual_pack import build_manual_pack
from app.services.runtime import is_send_enabled, set_send_enabled


def test_gold_set_reports_perfect_deterministic_score():
    result = run_gold_set()
    assert result["correct"] == result["total"] == 4
    assert result["percent"] == 100
    assert "gold-set" in result["summary"]


def test_manual_pack_creates_zip(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = build_manual_pack(
        "app-test",
        {
            "program_id": "demo_pk_work_01",
            "to": "intake@example.org",
            "fields": {"full_name": "Hina Khan"},
            "attachments": ["id_document"],
        },
    )
    assert path.exists()
    assert path.suffix == ".zip"


def test_admin_can_turn_sending_off(api_client):
    set_send_enabled(True)
    assert is_send_enabled() is True

    api_client.post(
        "/login",
        data={"email": "admin@entitle.local", "password": "test-admin-pass", "next_path": "/"},
        follow_redirects=False,
    )
    page = api_client.get("/curator")
    assert page.status_code == 200
    assert "Sending" in page.text
    assert "Inclusive Hiring" not in page.text

    switched = api_client.post(
        "/curator/kill-switch", data={"enabled": "0"}, follow_redirects=False
    )
    assert switched.status_code == 303
    assert is_send_enabled() is False
    set_send_enabled(True)

    gold = api_client.get(
        "/api/internal/gold-set", headers={"x-entitle-secret": "dev-shared-secret"}
    ).json()
    assert gold["correct"] == 4
