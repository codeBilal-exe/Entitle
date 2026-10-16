"""Ask the fewest useful questions. Sensitive attrs cost more."""

from __future__ import annotations

from typing import Any

from app.engine.rule_engine import RuleEngine, Status

SENSITIVE = frozenset({"disability", "low_income"})

ATTR_META = {
    "disability": {
        "label": "Do you identify as a person with a disability?",
        "type": "bool",
        "sensitive": True,
    },
    "age": {"label": "What is your age?", "type": "number", "sensitive": False},
    "education_level": {
        "label": "Highest education completed?",
        "type": "choice",
        "choices": ["primary", "secondary", "tertiary"],
        "sensitive": False,
    },
    "low_income": {
        "label": "Would you describe your household income as low?",
        "type": "bool",
        "sensitive": True,
    },
    "unemployed": {
        "label": "Are you currently unemployed?",
        "type": "bool",
        "sensitive": False,
    },
    "needs_language_support": {
        "label": "Do you need language support for public services?",
        "type": "bool",
        "sensitive": False,
    },
}


class QuestionEngine:
    def __init__(self, rule_engine: RuleEngine | None = None) -> None:
        self.rule_engine = rule_engine or RuleEngine()

    def next_question(
        self, programs_rules: list[dict[str, Any]], profile: dict[str, Any]
    ) -> dict[str, Any] | None:
        unanswered: set[str] = set()
        for rules in programs_rules:
            for condition in rules.get("conditions") or []:
                attr = condition.get("attr")
                if attr and attr not in profile:
                    unanswered.add(attr)

        if not unanswered:
            return None

        best_attr = None
        best_score = float("-inf")
        for attr in unanswered:
            impact = 0
            for rules in programs_rules:
                result = self.rule_engine.evaluate(rules, profile)
                if result.status == Status.LIKELY and attr in result.unknown_attributes:
                    impact += 1
                elif any(c.get("attr") == attr for c in (rules.get("conditions") or [])):
                    # Still unresolved programmes that depend on this attr
                    probe = dict(profile)
                    # Estimate impact by whether attr appears in unknowns if we leave it blank
                    if attr in [
                        c.get("attr")
                        for c in (rules.get("conditions") or [])
                        if c.get("attr") not in profile
                    ]:
                        impact += 1
            cost = 2 if attr in SENSITIVE else 0
            score = impact - cost
            if score > best_score:
                best_score = score
                best_attr = attr

        if best_attr is None:
            return None
        meta = ATTR_META.get(
            best_attr,
            {"label": best_attr.replace("_", " ").title(), "type": "text", "sensitive": False},
        )
        unlocks = sum(
            1
            for rules in programs_rules
            if any(c.get("attr") == best_attr for c in (rules.get("conditions") or []))
        )
        return {
            "attr": best_attr,
            "label": meta["label"],
            "type": meta.get("type", "text"),
            "choices": meta.get("choices"),
            "sensitive": bool(meta.get("sensitive")),
            "unlocks": unlocks,
        }
