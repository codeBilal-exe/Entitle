"""Seam: deterministic draft_from_notice + QuoteGate on gold notices."""

from app.engine.quote_gate import QuoteGate
from app.services.ingest import draft_from_notice_deterministic, draft_rule_pack


GATE = QuoteGate()

LIVE = {
    "id": "demo_pk_work_01",
    "version": 1,
    "conditions": [
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
    ],
}

GOLD = [
    {
        "name": "tighten_to_35",
        "notice": (
            "This programme supports persons with disabilities "
            "aged between 18 and 35 years who have completed secondary education or higher."
        ),
        "expect_age": [18, 35],
    },
    {
        "name": "widen_to_45",
        "notice": (
            "This programme supports persons with disabilities "
            "aged between 18 and 45 years who have completed secondary education or higher."
        ),
        "expect_age": [18, 45],
    },
    {
        "name": "keep_band_22_40",
        "notice": (
            "Open to persons with disabilities aged between 22 and 40 years "
            "with completed secondary education or higher."
        ),
        "expect_age": [22, 40],
    },
    {
        "name": "invented_extra_ignored_by_deterministic",
        "notice": (
            "persons with disabilities aged between 18 and 30 years "
            "completed secondary education or higher. Must own a yacht."
        ),
        "expect_age": [18, 30],
    },
]


def test_gold_set_deterministic_quotes_pass_and_age_updates():
    correct = 0
    total = 0
    for case in GOLD:
        draft = draft_from_notice_deterministic(LIVE, case["notice"])
        age = next(c for c in draft["conditions"] if c["id"] == "c2")
        total += 1
        if age["value"] == case["expect_age"]:
            correct += 1
        result = GATE.check(case["notice"], draft)
        assert result.passed, case["name"]
    # Honest gold-set score for the PDF/demo
    assert correct == total
    assert total == 4


def test_draft_rule_pack_falls_back_without_api_key(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "")
    from app.config import get_settings

    get_settings.cache_clear()
    draft, method = draft_rule_pack(LIVE, GOLD[0]["notice"], prefer_llm=True)
    assert method == "deterministic"
    assert next(c for c in draft["conditions"] if c["id"] == "c2")["value"] == [18, 35]
    get_settings.cache_clear()
