"""Seam: CaseImpact + FanOut.route."""

from app.engine.case_impact import CaseImpact
from app.engine.rule_engine import Status


IMPACT = CaseImpact()

OLD = {
    "deadline": "2026-12-01",
    "required_docs": ["id_document"],
    "conditions": [
        {"id": "c1", "attr": "disability", "op": "is_true", "source_quote": "persons with disabilities"},
        {"id": "c2", "attr": "age", "op": "between", "value": [18, 35], "source_quote": "aged 18 to 35"},
    ],
}

NEW = {
    "deadline": "2026-12-15",
    "required_docs": ["id_document", "disability_certificate"],
    "conditions": [
        {"id": "c1", "attr": "disability", "op": "is_true", "source_quote": "persons with disabilities"},
        {"id": "c2", "attr": "age", "op": "between", "value": [18, 45], "source_quote": "aged 18 to 45"},
    ],
}


def test_diff_detects_age_band_deadline_and_docs():
    diff = IMPACT.diff_conditions(OLD, NEW)
    assert len(diff["changed_conditions"]) == 1
    assert diff["changed_conditions"][0]["id"] == "c2"
    assert diff["deadline_changed"] is True
    assert diff["documents_added"] == ["disability_certificate"]


def test_amina_becomes_newly_eligible():
    # Age 40: outside old 18-35, inside new 18-45
    change = IMPACT.classify_case(
        "amina",
        OLD,
        NEW,
        {"disability": True, "age": 40},
    )
    assert change.before == Status.NOT_ELIGIBLE
    assert change.after == Status.ELIGIBLE
    assert change.kind == "newly_eligible"
    assert IMPACT.fan_out_route(change, consent_notifications=True) == "notify_applicant"


def test_rao_becomes_not_eligible_goes_to_navigator():
    tightened = {
        "conditions": [
            {"id": "c1", "attr": "disability", "op": "is_true", "source_quote": "pwd"},
            {"id": "c2", "attr": "age", "op": "between", "value": [18, 30], "source_quote": "18-30"},
        ]
    }
    change = IMPACT.classify_case(
        "rao",
        OLD,
        tightened,
        {"disability": True, "age": 34},
    )
    assert change.kind == "newly_not_eligible"
    assert IMPACT.fan_out_route(change, consent_notifications=True) == "navigator_review"


def test_good_news_without_consent_is_held():
    change = IMPACT.classify_case(
        "amina",
        OLD,
        NEW,
        {"disability": True, "age": 40},
    )
    assert IMPACT.fan_out_route(change, consent_notifications=False) == "hold_no_consent"
