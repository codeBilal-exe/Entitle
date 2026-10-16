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
            "fields": {"full_name": "Amina Demo"},
            "attachments": ["id_document"],
        },
    )
    assert path.exists()
    assert path.suffix == ".zip"


def test_kill_switch_and_reset(api_client):
    set_send_enabled(True)
    assert is_send_enabled() is True
    set_send_enabled(False)
    assert is_send_enabled() is False
    set_send_enabled(True)

    api_client.post(
        "/login",
        data={"email": "curator@demo.rightpath", "password": "demo1234"},
        follow_redirects=False,
    )
    page = api_client.get("/curator")
    assert page.status_code == 200
    assert "Gold-set accuracy" in page.text
    assert "4/4" in page.text or "100%" in page.text

    reset = api_client.post("/curator/reset-demo", follow_redirects=False)
    assert reset.status_code == 303

    gold = api_client.get(
        "/api/internal/gold-set", headers={"x-rightpath-secret": "dev-shared-secret"}
    ).json()
    assert gold["correct"] == 4
