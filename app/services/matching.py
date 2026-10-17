"""Decide where a person stands on one programme. Code decides; the model never does."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.engine.rule_engine import RuleEngine, Status

engine = RuleEngine()

# Ordered best first, so lists can sort by this rank.
RANK = {"eligible": 0, "likely": 1, "unchecked": 2, "not_eligible": 3, "elsewhere": 4}


@dataclass
class Match:
    status: str
    met: list[dict[str, Any]] = field(default_factory=list)
    unmet: list[dict[str, Any]] = field(default_factory=list)
    unknown: list[dict[str, Any]] = field(default_factory=list)


def _countries_allowed(rules: dict[str, Any]) -> set[str]:
    allowed: set[str] = set()
    for c in rules.get("conditions") or []:
        if c.get("attr") == "country":
            value = c.get("value")
            allowed.update(v.upper() for v in (value if isinstance(value, list) else [value]) if isinstance(v, str))
    return allowed


def match(program_country: str, rules: dict[str, Any], attrs: dict[str, Any]) -> Match:
    conditions = rules.get("conditions") or []
    if not conditions:
        return Match(status="unchecked")
    home = (attrs.get("country") or "").upper()
    if program_country and home and home != program_country.upper() and home not in _countries_allowed(rules):
        return Match(status="elsewhere")
    evaluation = engine.evaluate(rules, attrs)
    by_id = {c.get("id"): c for c in conditions}
    result = Match(status=evaluation.status.value)
    for item in evaluation.condition_results:
        condition = by_id.get(item["id"], {})
        row = {
            "id": item["id"],
            "attr": item["attr"],
            "plain": condition.get("plain") or "",
            "quote": item.get("source_quote") or "",
            "condition": condition,
        }
        if item["outcome"] is True:
            result.met.append(row)
        elif item["outcome"] is False:
            result.unmet.append(row)
        else:
            result.unknown.append(row)
    return result


def standing(program_country: str, rules: dict[str, Any] | None, attrs: dict[str, Any]) -> str | None:
    """Status used to compare before and after a rule change. None means no rules were live."""
    if not rules or not (rules.get("conditions") or []):
        return None
    status = match(program_country, rules, attrs).status
    return None if status == "elsewhere" else status


def change_kind(before: str | None, after: str | None) -> str:
    if after == Status.ELIGIBLE.value and before != Status.ELIGIBLE.value:
        return "newly_eligible"
    if before in {Status.ELIGIBLE.value, Status.LIKELY.value} and after == Status.NOT_ELIGIBLE.value:
        return "newly_not_eligible"
    return "unchanged"
