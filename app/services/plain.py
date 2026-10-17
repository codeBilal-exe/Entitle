"""Turn stored fields into words a person can read."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.services.drafting import COUNTRY_NAMES

ATTR_LABELS = {
    "age": "Age",
    "education_level": "Education",
    "low_income": "Low income",
    "disability": "Disability",
    "unemployed": "Out of work",
    "student": "Student",
    "country": "Lives in",
}
EDUCATION = {"primary": "Primary school", "secondary": "Secondary school", "tertiary": "University or college"}
DOMAINS = {"education": "Education", "income": "Income support", "health": "Health", "work": "Work",
           "housing": "Housing"}
STAGES = {
    "catalogue_loaded": "Catalogue loaded",
    "sign_in": "Signed in",
    "profile_saved": "Profile saved",
    "ai_draft": "AI drafted rules",
    "pattern_draft": "Rules drafted by pattern",
    "fetch_failed": "Page could not be read",
    "rule_approved": "Rules approved",
    "rule_rejected": "Draft rejected",
    "fan_out": "Everyone re-checked",
    "news_released": "Bad news released",
    "news_held": "Bad news kept on hold",
    "sources_checked": "Watched pages re-read",
    "packet_approved": "Applicant approved a packet",
    "data_deleted": "Account deleted",
}


def attr_label(attr: str | None) -> str:
    return ATTR_LABELS.get(attr or "", (attr or "Requirement").replace("_", " ").capitalize())


def country_name(code: str | None) -> str:
    return COUNTRY_NAMES.get((code or "").upper(), code or "")


def flag(code: str | None) -> str:
    """Country code badge text. Flag emoji do not render on Windows, so codes are used."""
    return (code or "").upper() or "ANY"


def domain_label(domain: str | None) -> str:
    return DOMAINS.get(domain or "", (domain or "").capitalize())


def value_label(attr: str, value: Any) -> str:
    if value is None:
        return "Not given"
    if attr == "education_level":
        return EDUCATION.get(str(value), str(value))
    if attr == "country":
        return country_name(str(value))
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return str(value)


def rule_phrase(condition: dict[str, Any] | None) -> str:
    if not condition:
        return "A published condition"
    attr, op, value = condition.get("attr"), condition.get("op"), condition.get("value")
    if op == "is_true":
        return {
            "low_income": "Household income is low",
            "disability": "Has a disability",
            "unemployed": "Is out of work",
            "student": "Is a student",
        }.get(attr or "", f"{attr_label(attr)} is required")
    if attr == "age":
        if op == "between" and isinstance(value, list):
            return f"Aged {value[0]} to {value[1]}"
        if op == "gte":
            return f"Aged {value} or over"
        if op == "lte":
            return f"Aged {value} or under"
    if attr == "education_level":
        values = value if isinstance(value, list) else [value]
        return "Education: " + " or ".join(EDUCATION.get(str(v), str(v)) for v in values)
    if attr == "country":
        values = value if isinstance(value, list) else [value]
        return "Lives in " + " or ".join(country_name(str(v)) for v in values)
    return f"{attr_label(attr)} {op} {value}"


def describe_diff_lines(diff: dict[str, Any] | None) -> list[str]:
    lines: list[str] = []
    for change in (diff or {}).get("changed_conditions") or []:
        lines.append(f"{rule_phrase(change.get('before'))} is now: {rule_phrase(change.get('after'))}.")
    for added in (diff or {}).get("added_conditions") or []:
        lines.append(f"New rule: {rule_phrase(added)}.")
    for removed in (diff or {}).get("removed_conditions") or []:
        lines.append(f"Rule removed: {rule_phrase(removed)}.")
    return lines or ["The rules were re-confirmed with no change."]


def stage_label(stage: str | None) -> str:
    return STAGES.get(stage or "", (stage or "Event").replace("_", " ").capitalize())


def ago(moment: datetime | None) -> str:
    if not moment:
        return "never"
    seconds = int((datetime.utcnow() - moment).total_seconds())
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{seconds // 60} min ago"
    if seconds < 86400:
        return f"{seconds // 3600} h ago"
    return moment.strftime("%d %b %Y")


def day(moment: datetime | None) -> str:
    return moment.strftime("%d %b %Y") if moment else ""


def status_word(status: str | None) -> str:
    return {
        "eligible": "Qualifies",
        "likely": "One answer away",
        "not_eligible": "Does not qualify",
        "none": "Not listed",
        "unchecked": "Not checked",
    }.get(status or "", status or "")


def profile_rows(attrs: dict[str, Any] | None) -> list[dict[str, str]]:
    rows = []
    for key in ATTR_LABELS:
        if key in (attrs or {}):
            rows.append({"key": key, "label": attr_label(key), "value": value_label(key, attrs[key])})
    return rows
