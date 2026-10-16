"""Seam: RuleEngine.evaluate — eligibility is decided only by code."""

from app.engine.rule_engine import RuleEngine, Status


ENGINE = RuleEngine()

SAMPLE_RULES = {
    "id": "demo_xx_work_01",
    "version": 1,
    "title": "DEMO: Inclusive Hiring Programme",
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


def test_all_true_conditions_are_eligible():
    profile = {"disability": True, "age": 30, "education_level": "tertiary"}
    result = ENGINE.evaluate(SAMPLE_RULES, profile)
    assert result.status == Status.ELIGIBLE
    assert result.failed_condition_ids == []
    assert all(c["outcome"] is True for c in result.condition_results)


def test_one_false_condition_is_not_eligible_and_names_the_rule():
    profile = {"disability": True, "age": 50, "education_level": "tertiary"}
    result = ENGINE.evaluate(SAMPLE_RULES, profile)
    assert result.status == Status.NOT_ELIGIBLE
    assert "c2" in result.failed_condition_ids
    assert any(
        c["id"] == "c2" and "18 and 45" in c["source_quote"]
        for c in result.condition_results
    )


def test_unknown_answers_yield_likely_and_name_missing_attrs():
    profile = {"disability": True, "age": 30}
    result = ENGINE.evaluate(SAMPLE_RULES, profile)
    assert result.status == Status.LIKELY
    assert "education_level" in result.unknown_attributes
    assert result.failed_condition_ids == []


def test_false_beats_unknown():
    profile = {"disability": False, "age": 30}
    result = ENGINE.evaluate(SAMPLE_RULES, profile)
    assert result.status == Status.NOT_ELIGIBLE
    assert "c1" in result.failed_condition_ids


def test_eq_and_gte_ops():
    rules = {
        "conditions": [
            {"id": "a", "attr": "country", "op": "eq", "value": "PK", "source_quote": "Pakistan"},
            {"id": "b", "attr": "income", "op": "gte", "value": 0, "source_quote": "any income"},
            {"id": "c", "attr": "income", "op": "lte", "value": 50000, "source_quote": "below threshold"},
        ]
    }
    ok = ENGINE.evaluate(rules, {"country": "PK", "income": 12000})
    assert ok.status == Status.ELIGIBLE
    bad = ENGINE.evaluate(rules, {"country": "IN", "income": 12000})
    assert bad.status == Status.NOT_ELIGIBLE


def test_any_of_op():
    rules = {
        "conditions": [
            {
                "id": "a",
                "attr": "languages",
                "op": "any_of",
                "value": ["en", "ur"],
                "source_quote": "English or Urdu",
            }
        ]
    }
    assert ENGINE.evaluate(rules, {"languages": ["fr", "ur"]}).status == Status.ELIGIBLE
    assert ENGINE.evaluate(rules, {"languages": ["fr"]}).status == Status.NOT_ELIGIBLE


def test_prefer_not_to_say_counts_as_unknown_not_false():
    profile = {"disability": None, "age": 30, "education_level": "secondary"}
    result = ENGINE.evaluate(SAMPLE_RULES, profile)
    assert result.status == Status.LIKELY
    assert "disability" in result.unknown_attributes


def test_empty_conditions_are_eligible():
    result = ENGINE.evaluate({"conditions": []}, {})
    assert result.status == Status.ELIGIBLE


def test_boundary_ages_inclusive():
    for age in (18, 45):
        result = ENGINE.evaluate(
            SAMPLE_RULES,
            {"disability": True, "age": age, "education_level": "secondary"},
        )
        assert result.status == Status.ELIGIBLE, age


def test_reasons_include_plain_language_and_quote():
    result = ENGINE.evaluate(
        SAMPLE_RULES,
        {"disability": True, "age": 60, "education_level": "tertiary"},
    )
    assert result.status == Status.NOT_ELIGIBLE
    assert result.reasons
    assert any("age" in r.lower() or "45" in r for r in result.reasons)
