"""Internal Pulse API and fan-out routing through the public hooks."""

SECRET = {"x-rightpath-secret": "dev-shared-secret"}

TIGHTEN_NOTICE = (
    "Inclusive Hiring Programme — Official Notice (DEMO SAMPLE)\n\n"
    "This programme supports persons with disabilities aged between 18 and 35 years "
    "who have completed secondary education or higher. Applications are accepted by email. "
    "Required documents include an identity document and a disability certificate.\n\n"
    "This page is a controllable DEMO source for RightPath. It is not a government website."
)


def test_unauthorized_internal_rejected(api_client):
    response = api_client.get("/api/internal/health")
    assert response.status_code == 401


def test_check_ingest_approve_sends_amina_to_navigator(api_client):
    assert api_client.get("/api/internal/health", headers=SECRET).json()["ok"] is True

    api_client.post("/api/internal/check-sources?auto_ingest=false", headers=SECRET)

    api_client.post(
        "/login",
        data={"email": "curator@demo.rightpath", "password": "demo1234"},
        follow_redirects=False,
    )
    api_client.post(
        "/curator/demo-notice", data={"body": TIGHTEN_NOTICE}, follow_redirects=False
    )

    checked = api_client.post(
        "/api/internal/check-sources?auto_ingest=true", headers=SECRET
    ).json()
    changed = [s for s in checked["sources"] if s.get("changed")]
    assert changed, checked
    job_id = changed[0]["ingestion_job_id"]

    approved = api_client.post(
        "/api/internal/approve",
        headers=SECRET,
        json={"job_id": job_id, "reviewed_by": "test@rightpath"},
    ).json()
    assert approved["ok"] is True
    amina = next(r for r in approved["routed"] if r["display_name"] == "Amina Demo")
    assert amina["route"] == "navigator_review"


def test_direct_ingest_api_and_replay(api_client):
    ingested = api_client.post(
        "/api/internal/ingest",
        headers=SECRET,
        json={
            "program_id": "demo_pk_work_01",
            "notice_text": TIGHTEN_NOTICE,
            "prefer_llm": False,
        },
    ).json()
    assert ingested["ok"] is True
    replay = api_client.post("/api/internal/replay/tighten", headers=SECRET).json()
    assert replay["ok"] is True
    assert replay["mode"] == "REPLAY"
