"""Plain-language explanation. Deterministic first; optional Groq polish."""

from __future__ import annotations

from typing import Any

from app.engine.rule_engine import EvaluationResult, Status
from app.services.plain import attr_label


def short_reason(evaluation: EvaluationResult) -> str:
    if evaluation.status == Status.ELIGIBLE:
        return "Every published condition is met."
    if evaluation.status == Status.LIKELY:
        missing = [attr_label(attr) for attr in evaluation.unknown_attributes]
        if missing:
            return "Still needs: " + ", ".join(missing) + "."
        return "One more answer would settle this."
    quotes = [
        item.get("source_quote")
        for item in evaluation.condition_results
        if item.get("outcome") is False and item.get("source_quote")
    ]
    if not quotes:
        return "A published condition is not met."
    if len(quotes) == 1:
        return f"Does not meet “{quotes[0]}”."
    return f"Does not meet “{quotes[0]}” and {len(quotes) - 1} other condition(s)."


def explain_result(program_title: str, evaluation: EvaluationResult) -> str:
    if evaluation.status == Status.ELIGIBLE:
        return (
            f"You meet every published condition for {program_title}. "
            "Anything sent outside RightPath still needs your approval."
        )
    if evaluation.status == Status.LIKELY:
        missing = ", ".join(attr_label(attr) for attr in evaluation.unknown_attributes) or "another answer"
        return (
            f"You may qualify for {program_title}. RightPath still needs {missing}. "
            "No condition has failed yet."
        )
    return (
        f"You do not currently meet the published rules for {program_title}. "
        "The notice lines below show which conditions failed."
    )


def explain_from_dict(program_title: str, evaluation: dict[str, Any]) -> str:
    status = evaluation.get("status")
    result = EvaluationResult(
        status=Status(status) if status else Status.LIKELY,
        failed_condition_ids=evaluation.get("failed_condition_ids") or [],
        unknown_attributes=evaluation.get("unknown_attributes") or [],
        reasons=evaluation.get("reasons") or [],
    )
    return explain_result(program_title, result)
