"""Deterministic eligibility evaluation. The LLM never calls this for decisions."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Status(str, Enum):
    ELIGIBLE = "eligible"
    LIKELY = "likely"
    NOT_ELIGIBLE = "not_eligible"


@dataclass
class EvaluationResult:
    status: Status
    condition_results: list[dict[str, Any]] = field(default_factory=list)
    failed_condition_ids: list[str] = field(default_factory=list)
    unknown_attributes: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)


class RuleEngine:
    """Evaluate a Rule Pack against a profile attribute map."""

    OPS = frozenset({"eq", "in", "gte", "lte", "between", "is_true", "any_of"})

    def evaluate(self, rules: dict[str, Any], profile: dict[str, Any]) -> EvaluationResult:
        conditions = rules.get("conditions") or []
        condition_results: list[dict[str, Any]] = []
        failed: list[str] = []
        unknown: list[str] = []
        reasons: list[str] = []

        for condition in conditions:
            outcome = self._eval_condition(condition, profile)
            entry = {
                "id": condition.get("id"),
                "attr": condition.get("attr"),
                "op": condition.get("op"),
                "source_quote": condition.get("source_quote", ""),
                "outcome": outcome,
            }
            condition_results.append(entry)

            if outcome is False:
                failed.append(condition["id"])
                quote = condition.get("source_quote") or ""
                attr = condition.get("attr") or "requirement"
                reasons.append(
                    f"Does not meet the {attr} rule"
                    + (f': "{quote}"' if quote else ".")
                )
            elif outcome is None:
                attr = condition.get("attr") or "unknown"
                if attr not in unknown:
                    unknown.append(attr)

        if failed:
            status = Status.NOT_ELIGIBLE
        elif unknown:
            status = Status.LIKELY
            reasons.append(
                "More information needed for: " + ", ".join(unknown)
            )
        else:
            status = Status.ELIGIBLE
            if conditions:
                reasons.append("All published conditions are met.")
            else:
                reasons.append("No conditions defined for this programme.")

        return EvaluationResult(
            status=status,
            condition_results=condition_results,
            failed_condition_ids=failed,
            unknown_attributes=unknown,
            reasons=reasons,
        )

    def _eval_condition(self, condition: dict[str, Any], profile: dict[str, Any]) -> bool | None:
        attr = condition.get("attr")
        op = condition.get("op")
        if attr is None or op is None:
            return None
        if op not in self.OPS:
            raise ValueError(f"Unsupported operator: {op}")

        if attr not in profile:
            return None

        value = profile[attr]
        if value is None:
            return None

        expected = condition.get("value")

        if op == "is_true":
            if isinstance(value, bool):
                return value is True
            return None
        if op == "eq":
            return value == expected
        if op == "in":
            if not isinstance(expected, (list, tuple, set)):
                return False
            return value in expected
        if op == "gte":
            return value >= expected
        if op == "lte":
            return value <= expected
        if op == "between":
            if not isinstance(expected, (list, tuple)) or len(expected) != 2:
                return False
            low, high = expected
            return low <= value <= high
        if op == "any_of":
            if not isinstance(expected, (list, tuple, set)):
                return False
            if not isinstance(value, (list, tuple, set)):
                return value in expected
            return any(item in expected for item in value)

        return None
