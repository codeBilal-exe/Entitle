"""Turn stored fields into sentences a person can read."""

from __future__ import annotations

from typing import Any

ATTR_LABELS = {
    "disability": "Disability",
    "age": "Age",
    "education_level": "Education",
    "low_income": "Household income",
    "unemployed": "Employment",
    "needs_language_support": "Language support",
}

EDUCATION = {
    "primary": "Primary school",
    "secondary": "Secondary school",
    "tertiary": "University or college",
}

DOCS = {
    "id_document": "Identity document",
    "disability_certificate": "Disability certificate",
    "education_certificate": "Education certificate",
}

DOMAINS = {
    "work": "Work",
    "education": "Education",
    "health": "Health",
    "legal": "Legal aid",
    "income": "Income support",
}

COUNTRIES = {"PK": "Pakistan"}

STAGES = {
    "seed": "Programme list loaded",
    "login": "Signed in",
    "source_check": "Notice checked",
    "source_changed": "Notice text changed",
    "source_unreachable": "Notice could not be read",
    "ingest_draft": "Draft prepared",
    "rule_approved": "Rule change approved",
    "fanout_navigator": "Held for review",
    "fanout_notify": "Alert queued",
    "fanout_skip": "No alert needed",
    "navigator_release": "Alert released",
    "applicant_consent": "Packet approved",
    "send_ok": "Packet sent",
    "send_blocked": "Send blocked",
    "send_failed": "Send failed",
    "privacy_delete": "Stored data deleted",
    "kill_switch": "Sending switch changed",
    "deadline_reminder": "Deadline reminder",
    "signup": "Signed up",
    "rule_rejected": "Rule change rejected",
    "navigator_hold": "Alert held",
    "source_updated": "Source updated",
}

APP_STATES = {
    "ready": "Waiting for your approval",
    "approved": "Approved, not sent yet",
    "sent": "Sent",
    "failed": "Not sent",
}

NOTIFY_STATUS = {
    "pending_review": "Waiting for a person",
    "held": "Held by a person",
    "approved": "A person released this",
    "queued": "In your alerts",
    "rejected": "Rejected",
}

KINDS = {
    "newly_not_eligible": "You may no longer qualify",
    "newly_eligible": "You may now qualify",
    "deadline_reminder": "Deadline coming up",
}


def attr_label(attr: str | None) -> str:
    if not attr:
        return "Requirement"
    return ATTR_LABELS.get(attr, attr.replace("_", " ").capitalize())


def doc_label(doc: str) -> str:
    return DOCS.get(doc, doc.replace("_", " "))


def domain_label(domain: str | None) -> str:
    if not domain:
        return ""
    return DOMAINS.get(domain, domain.replace("_", " ").capitalize())


def country_label(code: str | None) -> str:
    if not code:
        return ""
    return COUNTRIES.get(code, code)


def education_label(value: Any) -> str:
    if value is None:
        return "Prefer not to say"
    return EDUCATION.get(str(value), str(value))


def value_label(attr: str, value: Any) -> str:
    if value is None:
        return "Prefer not to say"
    if attr == "education_level":
        return education_label(value)
    if isinstance(value, bool):
        if attr == "low_income":
            return "Low income" if value else "Not low income"
        if attr == "unemployed":
            return "Unemployed" if value else "In work"
        if attr == "disability":
            return "Yes" if value else "No"
        if attr == "needs_language_support":
            return "Needed" if value else "Not needed"
        return "Yes" if value else "No"
    return str(value)


def profile_rows(attrs: dict[str, Any] | None) -> list[dict[str, str]]:
    if not attrs:
        return []
    order = list(ATTR_LABELS)
    keys = [key for key in order if key in attrs] + [key for key in attrs if key not in order]
    return [
        {"key": key, "label": attr_label(key), "value": value_label(key, attrs[key])}
        for key in keys
    ]


def rule_phrase(condition: dict[str, Any] | None) -> str:
    if not condition:
        return "A published condition"
    attr = condition.get("attr")
    op = condition.get("op")
    value = condition.get("value")
    label = attr_label(attr if isinstance(attr, str) else None)
    if op == "is_true":
        if attr == "low_income":
            return "Household income is low"
        if attr == "unemployed":
            return "The person is unemployed"
        if attr == "disability":
            return "The person has a disability"
        if attr == "needs_language_support":
            return "Language support is needed"
        return f"{label} is required"
    if op == "between" and isinstance(value, (list, tuple)) and len(value) == 2:
        return f"{label} is {value[0]} to {value[1]}"
    if op == "gte":
        if attr == "age":
            return f"Age is {value} or older"
        return f"{label} is at least {value}"
    if op == "lte":
        if attr == "age":
            return f"Age is {value} or under"
        return f"{label} is at most {value}"
    if op == "in" and isinstance(value, (list, tuple)):
        pretty = ", ".join(education_label(item) if attr == "education_level" else str(item) for item in value)
        return f"{label} is {pretty}"
    if op == "eq":
        shown = education_label(value) if attr == "education_level" else value
        return f"{label} is {shown}"
    if op == "any_of" and isinstance(value, (list, tuple)):
        return f"{label} includes {', '.join(str(item) for item in value)}"
    return label


def describe_diff_lines(diff: dict[str, Any] | None) -> list[str]:
    if not diff:
        return ["Nothing in the rules changed."]
    lines: list[str] = []
    for change in diff.get("changed_conditions") or []:
        before = change.get("before") or {}
        after = change.get("after") or {}
        lines.append(f"{rule_phrase(before)}. After this draft: {rule_phrase(after)}.")
    for added in diff.get("added_conditions") or []:
        lines.append(f"Added condition: {rule_phrase(added)}.")
    for removed in diff.get("removed_conditions") or []:
        lines.append(f"Removed condition: {rule_phrase(removed)}.")
    if diff.get("deadline_changed"):
        lines.append("The deadline changed.")
    for doc in diff.get("documents_added") or []:
        lines.append(f"Document added to the checklist: {doc_label(doc)}.")
    for doc in diff.get("documents_removed") or []:
        lines.append(f"Document removed from the checklist: {doc_label(doc)}.")
    if not lines:
        return ["Nothing in the rules changed."]
    return lines


def payload_rows(payload: dict[str, Any] | None) -> list[dict[str, str]]:
    if not payload:
        return []
    fields = payload.get("fields") or {}
    rows: list[dict[str, str]] = []
    if payload.get("to"):
        rows.append({"label": "Send to", "value": str(payload["to"])})
    labels = (
        ("full_name", "Full name"),
        ("contact_email", "Email"),
        ("age", "Age"),
        ("education_level", "Education"),
    )
    for key, label in labels:
        if key not in fields:
            continue
        value = fields[key]
        if key == "education_level":
            value = education_label(value)
        rows.append({"label": label, "value": str(value)})
    docs = payload.get("attachments") or []
    if docs:
        rows.append(
            {"label": "Sample documents", "value": ", ".join(doc_label(doc) for doc in docs)}
        )
    return rows


def stage_label(stage: str | None) -> str:
    if not stage:
        return "Event"
    return STAGES.get(stage, stage.replace("_", " ").capitalize())


def state_label(state: str | None) -> str:
    if not state:
        return "Unknown"
    return APP_STATES.get(state, state.replace("_", " ").capitalize())


def notify_status_label(status: str | None) -> str:
    if not status:
        return ""
    return NOTIFY_STATUS.get(status, status.replace("_", " "))


def kind_label(kind: str | None) -> str:
    if not kind:
        return "Update"
    return KINDS.get(kind, kind.replace("_", " ").capitalize())


def eligibility_label(status: str | None) -> str:
    return {
        "eligible": "Eligible",
        "likely": "Needs an answer",
        "not_eligible": "Not eligible",
    }.get(status or "", status or "")


def outcome_label(outcome: Any) -> str:
    if outcome is True:
        return "Met"
    if outcome is False:
        return "Not met"
    return "Not answered"


def source_status_label(status: str | None) -> str:
    return {
        "ok": "Read",
        "unreachable": "Unreachable",
        "not_checked": "Not read yet",
        "changed": "Changed",
    }.get(status or "", (status or "Unknown").replace("_", " "))


def status_shift(before: str | None, after: str | None) -> str:
    return f"{eligibility_label(before)} before. {eligibility_label(after)} after this change."


def next_step_label(step: str | None) -> str:
    return {
        "review": "Review the programme",
        "apply": "Prepare an application",
        "deadline": "Note the deadline",
    }.get(step or "", "Review the programme")


def alert_copy(
    kind: str,
    program_title: str,
    *,
    diff_lines: list[str] | None = None,
    quote: str = "",
    days_left: int | None = None,
    deadline: str = "",
) -> dict[str, str]:
    """Sentences for one alert. Quotes are passed in; this does not invent them."""
    title = program_title or "this programme"
    changed = ""
    if diff_lines:
        changed = diff_lines[0]
    if kind == "newly_eligible":
        return {
            "what_changed": changed or f"The rules for {title} changed.",
            "meaning": f"You may now qualify for {title}.",
            "quote": quote,
            "next_step": "apply",
        }
    if kind == "newly_not_eligible":
        return {
            "what_changed": changed or f"The rules for {title} changed.",
            "meaning": f"You may no longer qualify for {title}.",
            "quote": quote,
            "next_step": "review",
        }
    if kind == "deadline_reminder":
        when = deadline or "the date on file"
        left = f"{days_left} days left. " if days_left is not None else ""
        return {
            "what_changed": f"{left}The deadline on file is {when}.",
            "meaning": f"Your application for {title} is still open. Note the deadline.",
            "quote": quote,
            "next_step": "deadline",
        }
    return {
        "what_changed": changed or f"Something changed for {title}.",
        "meaning": f"Read the notice for {title}.",
        "quote": quote,
        "next_step": "review",
    }
