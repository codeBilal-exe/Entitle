"""Seam: ApprovalGate.send — state and payload hash guards."""

from app.engine.approval_gate import ApprovalGate, ApplicationState


GATE = ApprovalGate()
PAYLOAD = {
    "program_id": "demo_xx_work_01",
    "to": "intake@example.org",
    "fields": {"full_name": "Hina Khan", "age": 40},
    "attachments": ["disability_certificate.pdf"],
}


def test_approve_stores_stable_hash():
    state, digest = GATE.approve(ApplicationState.READY.value, PAYLOAD)
    assert state == ApplicationState.APPROVED.value
    assert digest == GATE.payload_hash(PAYLOAD)
    assert digest == GATE.payload_hash(dict(PAYLOAD))  # order-independent via sort_keys


def test_send_rejected_if_not_approved():
    decision = GATE.authorize_send(
        application_id="app-1",
        state=ApplicationState.READY.value,
        stored_hash=GATE.payload_hash(PAYLOAD),
        payload=PAYLOAD,
    )
    assert decision.allowed is False
    assert decision.reason == "not_approved"


def test_send_rejected_if_payload_changed():
    _, digest = GATE.approve(ApplicationState.READY.value, PAYLOAD)
    tampered = dict(PAYLOAD)
    tampered["fields"] = {"full_name": "Hina Khan", "age": 41}
    decision = GATE.authorize_send(
        application_id="app-1",
        state=ApplicationState.APPROVED.value,
        stored_hash=digest,
        payload=tampered,
    )
    assert decision.allowed is False
    assert decision.reason == "hash_mismatch"


def test_send_allowed_when_approved_and_hash_matches():
    _, digest = GATE.approve(ApplicationState.READY.value, PAYLOAD)
    decision = GATE.authorize_send(
        application_id="app-1",
        state=ApplicationState.APPROVED.value,
        stored_hash=digest,
        payload=PAYLOAD,
    )
    assert decision.allowed is True


def test_double_send_is_idempotent_reject():
    _, digest = GATE.approve(ApplicationState.READY.value, PAYLOAD)
    decision = GATE.authorize_send(
        application_id="app-1",
        state=ApplicationState.SENT.value,
        stored_hash=digest,
        payload=PAYLOAD,
        already_sent_ids={"app-1"},
    )
    assert decision.allowed is False
    assert decision.reason == "already_sent"
