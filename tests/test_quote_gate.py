"""Seam: QuoteGate.check — every source_quote must appear verbatim in the notice."""

from app.engine.quote_gate import QuoteGate


GATE = QuoteGate()

NOTICE = (
    "The Inclusive Hiring Programme is open to persons with disabilities "
    "aged between 18 and 45 years who have completed secondary education or higher."
)


def test_exact_quotes_pass():
    draft = {
        "conditions": [
            {"id": "c1", "source_quote": "persons with disabilities"},
            {"id": "c2", "source_quote": "aged between 18 and 45 years"},
        ]
    }
    result = GATE.check(NOTICE, draft)
    assert result.passed is True
    assert result.failed_ids == []
    assert all(item["ok"] for item in result.items)


def test_invented_quote_fails_red():
    draft = {
        "conditions": [
            {"id": "c1", "source_quote": "persons with disabilities"},
            {"id": "c2", "source_quote": "must own a private vehicle"},
        ]
    }
    result = GATE.check(NOTICE, draft)
    assert result.passed is False
    assert "c2" in result.failed_ids


def test_whitespace_mismatch_fails():
    draft = {
        "conditions": [
            {"id": "c1", "source_quote": "persons  with   disabilities"},
        ]
    }
    result = GATE.check(NOTICE, draft)
    assert result.passed is False
    assert "c1" in result.failed_ids


def test_empty_quote_fails():
    draft = {"conditions": [{"id": "c1", "source_quote": ""}]}
    result = GATE.check(NOTICE, draft)
    assert result.passed is False
    assert "c1" in result.failed_ids


def test_null_quote_fails():
    draft = {"conditions": [{"id": "c1", "source_quote": None}]}
    result = GATE.check(NOTICE, draft)
    assert result.passed is False
