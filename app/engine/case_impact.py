"""Diff rule versions and classify how a profile's status changes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.engine.rule_engine import RuleEngine, Status


@dataclass
class ImpactChange:
    case_id: str
    before: Status
    after: Status
    kind: str  # newly_eligible | newly_not_eligible | unchanged | other


class CaseImpact:
    def __init__(self, engine: RuleEngine | None = None) -> None:
        self.engine = engine or RuleEngine()

    def diff_conditions(
        self, old_rules: dict[str, Any], new_rules: dict[str, Any]
    ) -> dict[str, Any]:
        old_by_id = {c["id"]: c for c in (old_rules.get("conditions") or []) if "id" in c}
        new_by_id = {c["id"]: c for c in (new_rules.get("conditions") or []) if "id" in c}

        added = [new_by_id[i] for i in new_by_id.keys() - old_by_id.keys()]
        removed = [old_by_id[i] for i in old_by_id.keys() - new_by_id.keys()]
        changed = []
        for cid in old_by_id.keys() & new_by_id.keys():
            if old_by_id[cid] != new_by_id[cid]:
                changed.append({"id": cid, "before": old_by_id[cid], "after": new_by_id[cid]})

        deadline_changed = old_rules.get("deadline") != new_rules.get("deadline")
        docs_old = set(old_rules.get("required_docs") or [])
        docs_new = set(new_rules.get("required_docs") or [])

        return {
            "added_conditions": added,
            "removed_conditions": removed,
            "changed_conditions": changed,
            "deadline_changed": deadline_changed,
            "documents_added": sorted(docs_new - docs_old),
            "documents_removed": sorted(docs_old - docs_new),
        }

    def classify_case(
        self,
        case_id: str,
        old_rules: dict[str, Any],
        new_rules: dict[str, Any],
        profile: dict[str, Any],
    ) -> ImpactChange:
        before = self.engine.evaluate(old_rules, profile).status
        after = self.engine.evaluate(new_rules, profile).status
        if before != Status.ELIGIBLE and after == Status.ELIGIBLE:
            kind = "newly_eligible"
        elif before != Status.NOT_ELIGIBLE and after == Status.NOT_ELIGIBLE:
            kind = "newly_not_eligible"
        elif before == after:
            kind = "unchanged"
        else:
            kind = "other"
        return ImpactChange(case_id=case_id, before=before, after=after, kind=kind)

    def fan_out_route(self, change: ImpactChange, consent_notifications: bool) -> str:
        """Return routing target for a status change."""
        if change.kind == "newly_not_eligible":
            return "navigator_review"
        if change.kind == "newly_eligible":
            return "notify_applicant" if consent_notifications else "hold_no_consent"
        return "log_only"
