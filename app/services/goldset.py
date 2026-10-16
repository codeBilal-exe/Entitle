"""Honest gold-set accuracy for the curator desk and submission PDF."""

from __future__ import annotations

from typing import Any

from app.engine.quote_gate import QuoteGate
from app.services.ingest import draft_from_notice_deterministic

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

CASES = [
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
        "name": "band_22_40",
        "notice": (
            "Open to persons with disabilities aged between 22 and 40 years "
            "with completed secondary education or higher."
        ),
        "expect_age": [22, 40],
    },
    {
        "name": "band_18_30",
        "notice": (
            "persons with disabilities aged between 18 and 30 years "
            "completed secondary education or higher."
        ),
        "expect_age": [18, 30],
    },
]


def run_gold_set() -> dict[str, Any]:
    results = []
    correct = 0
    for case in CASES:
        draft = draft_from_notice_deterministic(LIVE, case["notice"])
        age = next(c for c in draft["conditions"] if c["id"] == "c2")
        age_ok = age["value"] == case["expect_age"]
        quote_ok = GATE.check(case["notice"], draft).passed
        ok = age_ok and quote_ok
        if ok:
            correct += 1
        results.append(
            {
                "name": case["name"],
                "age_ok": age_ok,
                "quote_ok": quote_ok,
                "ok": ok,
                "got_age": age["value"],
                "expect_age": case["expect_age"],
            }
        )
    total = len(CASES)
    return {
        "correct": correct,
        "total": total,
        "percent": round(100 * correct / total) if total else 0,
        "method": "deterministic",
        "cases": results,
        "summary": f"{correct} of {total} gold-set conditions correct before curator edits",
    }
