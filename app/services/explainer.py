"""Plain-language explanation. Deterministic first; optional Groq polish."""

from __future__ import annotations

from typing import Any

from app.engine.rule_engine import EvaluationResult, Status


def explain_result(program_title: str, evaluation: EvaluationResult) -> str:
    if evaluation.status == Status.ELIGIBLE:
        return (
            f"Based on the published rules for {program_title}, you meet every listed "
            "condition. A human still approves anything sent outside RightPath."
        )
    if evaluation.status == Status.LIKELY:
        missing = ", ".join(evaluation.unknown_attributes) or "a few answers"
        return (
            f"You may qualify for {program_title}, but RightPath still needs: {missing}. "
            "No condition has failed yet."
        )
    failed = evaluation.failed_condition_ids or ["a published condition"]
    return (
        f"You do not currently meet the rules for {program_title} "
        f"(failed: {', '.join(failed)}). The source quotes below show why."
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
