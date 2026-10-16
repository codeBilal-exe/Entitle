"""Draft Rule Pack updates from notice text. Deterministic first; LLM optional."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from typing import Any

from app.config import get_settings
from app.services.groq_pool import get_groq_pool


AGE_BAND_RE = re.compile(
    r"aged between\s+(\d+)\s+and\s+(\d+)\s+years",
    re.IGNORECASE,
)


def draft_from_notice_deterministic(
    live_rules: dict[str, Any], notice_text: str
) -> dict[str, Any]:
    """Update an existing condition only when the new phrase is in the notice."""
    draft = deepcopy(live_rules)
    draft["version"] = int(live_rules.get("version", 1)) + 1

    match = AGE_BAND_RE.search(notice_text or "")
    if match:
        low, high = int(match.group(1)), int(match.group(2))
        quote = f"aged between {low} and {high} years"
        for condition in draft.get("conditions") or []:
            if condition.get("id") == "c2" or condition.get("attr") == "age":
                if condition.get("op") == "between":
                    condition["value"] = [low, high]
                    condition["source_quote"] = quote

    if "persons with disabilities" in (notice_text or "").lower():
        for condition in draft.get("conditions") or []:
            if condition.get("attr") == "disability":
                condition["source_quote"] = "persons with disabilities"

    return draft


def draft_from_notice_llm(
    live_rules: dict[str, Any], notice_text: str
) -> dict[str, Any] | None:
    """Ask Groq to draft an updated Rule Pack. Returns None if unavailable/fails."""
    settings = get_settings()
    pool = get_groq_pool()
    if len(pool) == 0:
        return None

    system = (
        "You update eligibility Rule Packs from official notice text. "
        "Return ONLY valid JSON for the full Rule Pack. "
        "Copy eligibility phrases into source_quote exactly as they appear in the notice. "
        "Never invent facts. If a detail is missing, keep the previous value. "
        "Allowed ops: eq, in, gte, lte, between, is_true, any_of."
    )
    user = (
        "Current Rule Pack JSON:\n"
        f"{json.dumps(live_rules, indent=2)}\n\n"
        "Notice text:\n"
        f"{notice_text}\n\n"
        "Return the updated Rule Pack JSON only."
    )
    content = pool.complete(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        model=settings.llm_model,
        temperature=0,
        response_format={"type": "json_object"},
        timeout=45.0,
    )
    if not content:
        return None
    try:
        draft = json.loads(content)
    except json.JSONDecodeError:
        return None
    if "conditions" not in draft:
        return None
    draft["version"] = int(live_rules.get("version", 1)) + 1
    draft.setdefault("id", live_rules.get("id"))
    return draft


def draft_rule_pack(
    live_rules: dict[str, Any], notice_text: str, *, prefer_llm: bool = True
) -> tuple[dict[str, Any], str]:
    """Return (draft, method) where method is 'llm' or 'deterministic'."""
    if prefer_llm:
        llm_draft = draft_from_notice_llm(live_rules, notice_text)
        if llm_draft is not None:
            return llm_draft, "llm"
    return draft_from_notice_deterministic(live_rules, notice_text), "deterministic"
