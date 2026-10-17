"""The automation pipeline. Shared by the desk, the background watcher and n8n.

fetch page -> AI drafts rules -> receipt check -> impact preview -> a person decides
-> everyone is re-checked -> good news goes out, bad news waits for a person.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.config import get_settings
from app.engine.case_impact import CaseImpact
from app.engine.quote_gate import QuoteGate
from app.models import IngestionJob, Notification, Profile, Program, ProgramVersion, Source, User
from app.services import matching
from app.services.drafting import draft_rules
from app.services.plain import describe_diff_lines, rule_phrase
from app.services.timeline import log_event

quote_gate = QuoteGate()
case_impact = CaseImpact()


def content_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def load_rules(db: Session, program: Program) -> dict[str, Any]:
    if not program.current_version_id:
        return {"conditions": []}
    version = db.get(ProgramVersion, program.current_version_id)
    if not version:
        return {"conditions": []}
    return json.loads(version.rules_json)


def live_version(db: Session, program: Program) -> ProgramVersion | None:
    if not program.current_version_id:
        return None
    return db.get(ProgramVersion, program.current_version_id)


def profile_attrs(profile: Profile | None) -> dict[str, Any]:
    if not profile:
        return {}
    return json.loads(profile.attributes_json or "{}")


def html_to_text(raw: str) -> str:
    without_blocks = re.sub(r"(?is)<(script|style|noscript|svg|head)\b.*?>.*?</\1>", " ", raw or "")
    without_tags = re.sub(r"(?s)<[^>]+>", " ", without_blocks)
    text = html.unescape(without_tags)
    return re.sub(r"\s+", " ", text).strip()


def page_title(raw: str) -> str:
    match = re.search(r"(?is)<title[^>]*>(.*?)</title>", raw or "")
    if not match:
        return ""
    return re.sub(r"\s+", " ", html.unescape(match.group(1))).strip()[:200]


def fetch_page(url: str) -> dict[str, Any]:
    """Return {ok, text, title, error}. Never raises and never touches the database."""
    import httpx

    try:
        response = httpx.get(
            url,
            timeout=12.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; Entitle/1.0; public eligibility reader)",
                "Accept-Language": "en",
            },
        )
        response.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "text": "", "title": "", "error": _fetch_error(exc)}
    text = html_to_text(response.text)
    if len(text) < 80:
        return {"ok": False, "text": "", "title": "", "error": "The page had no readable text."}
    return {"ok": True, "text": text[:60000], "title": page_title(response.text), "error": ""}


def _fetch_error(exc: Exception) -> str:
    name = exc.__class__.__name__
    status = getattr(getattr(exc, "response", None), "status_code", None)
    if status:
        return f"The site answered with error {status}."
    if "Timeout" in name:
        return "The site took too long to answer."
    return "The site could not be reached."


class StepLog:
    def __init__(self) -> None:
        self.steps: list[dict[str, Any]] = []
        self._start = time.perf_counter()

    def add(self, key: str, label: str, actor: str, status: str, detail: str) -> None:
        now = time.perf_counter()
        self.steps.append(
            {
                "key": key,
                "label": label,
                "actor": actor,
                "status": status,
                "detail": detail,
                "ms": int((now - self._start) * 1000),
            }
        )
        self._start = now


def receipt_check(notice_text: str, draft: dict[str, Any]) -> dict[str, Any]:
    result = quote_gate.check(notice_text, draft)
    return {"passed": result.passed, "items": result.items, "failed_ids": result.failed_ids}


def people_with_profiles(db: Session) -> list[tuple[User, dict[str, Any], bool]]:
    rows = []
    for user in db.query(User).filter(User.role == "citizen").all():
        profile = db.query(Profile).filter(Profile.user_id == user.id).first()
        if profile is None:
            continue
        rows.append((user, profile_attrs(profile), bool(profile.consent_notifications)))
    return rows


def impact_preview(
    db: Session, country: str, old_rules: dict[str, Any], new_rules: dict[str, Any]
) -> dict[str, Any]:
    gained, lost = [], []
    people = people_with_profiles(db)
    for user, attrs, _ in people:
        before = matching.standing(country, old_rules, attrs)
        after = matching.standing(country, new_rules, attrs)
        kind = matching.change_kind(before, after)
        if kind == "newly_eligible":
            gained.append(user.display_name)
        elif kind == "newly_not_eligible":
            lost.append(user.display_name)
    return {"checked": len(people), "gained": gained, "lost": lost}


def run_pipeline(
    db: Session,
    *,
    url: str = "",
    notice_text: str = "",
    program_id: str = "",
    trigger: str = "reviewer",
    page: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run every automated step and leave the result waiting for a person.

    Returns {ok, job_id} or {ok: False, error, steps}.
    """
    log = StepLog()
    program = db.get(Program, program_id) if program_id else None
    live = load_rules(db, program) if program else {}
    url = url.strip() or (program.official_url if program else "")

    if notice_text.strip():
        text = re.sub(r"\s+", " ", notice_text).strip()
        title = ""
        log.add("fetch", "Read the pasted notice", "system", "ok", f"{len(text.split())} words")
    else:
        if page is None:
            page = fetch_page(url)
        if not page["ok"]:
            log.add("fetch", "Fetch the official page", "system", "fail", page["error"])
            log_event(db, stage="fetch_failed", detail=f"{url}: {page['error']}", case_id=program_id, status="error")
            return {"ok": False, "error": page["error"], "steps": log.steps}
        text, title = page["text"], page["title"]
        log.add("fetch", "Fetched the official page", "system", "ok", f"{len(text.split()):,} words read")

    draft, method = draft_rules(text, url=url, page_title=title, live_rules=live)
    if program:
        draft["id"] = program.id
    if program and notice_text.strip():
        # A pasted notice usually changes one rule. Rules it does not mention stay as approved,
        # and their receipts are still checked against the page they came from.
        source = db.get(Source, _source_id(db, program)) if _source_id(db, program) else None
        mentioned = {c["attr"] for c in draft["conditions"]}
        for condition in live.get("conditions") or []:
            if condition.get("attr") not in mentioned:
                carried = dict(condition, carried=True)
                carried["id"] = f"c{len(draft['conditions']) + 1}"
                draft["conditions"].append(carried)
        if source and source.last_text:
            text = text + "\n\n" + source.last_text
    count = len(draft["conditions"])
    aside = len(draft.get("unsupported") or [])
    if method == "ai":
        detail = f"{count} rule{'s' if count != 1 else ''} drafted"
        if aside:
            detail += f", {aside} set aside because Entitle cannot check them"
        log.add("draft", "AI drafted the eligibility rules", "ai", "ok" if count else "warn", detail)
    else:
        log.add(
            "draft", "Pattern reader drafted the rules", "system", "ok" if count else "warn",
            f"AI unavailable, {count} rule{'s' if count != 1 else ''} found by exact patterns",
        )

    check = receipt_check(text, draft)
    found = sum(1 for item in check["items"] if item["ok"])
    if not count:
        log.add("receipts", "Receipt check", "system", "fail", "No rule had a quote to check")
    elif check["passed"]:
        log.add("receipts", "Receipt check", "system", "ok", f"All {count} quotes found word for word on the page")
    else:
        log.add(
            "receipts", "Receipt check", "system", "fail",
            f"{count - found} of {count} quotes are not on the page and were blocked",
        )

    country = draft.get("country") or (program.country if program else "")
    preview = impact_preview(db, country, live, _verified_only(draft, check))
    log.add(
        "impact", "Previewed who this affects", "system", "ok",
        f"{preview['checked']} people checked: {len(preview['gained'])} would gain, {len(preview['lost'])} may lose",
    )
    log.add("review", "Waiting for a reviewer", "human", "pending", "Nothing goes live until a person approves")

    job = IngestionJob(
        kind="update" if program else "new",
        source_id=_source_id(db, program),
        program_id=program.id if program else "",
        source_url=url,
        trigger=trigger,
        notice_text=text,
        draft_json=json.dumps(draft),
        quote_check_json=json.dumps({**check, "method": method}),
        diff_json=json.dumps(case_impact.diff_conditions(live, draft)),
        steps_json=json.dumps(log.steps),
        impact_json=json.dumps(preview),
        status="pending_review",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    log_event(
        db,
        stage="ai_draft" if method == "ai" else "pattern_draft",
        detail=f"Drafted {count} rules for {draft.get('title')}; {found}/{count} receipts verified",
        case_id=f"job-{job.id}",
        actor="ai" if method == "ai" else "system",
        status="ok" if check["passed"] and count else "blocked",
    )
    return {"ok": True, "job_id": job.id}


def _source_id(db: Session, program: Program | None) -> int | None:
    if not program:
        return None
    source = db.query(Source).filter(Source.program_id == program.id).order_by(Source.id).first()
    return source.id if source else None


def _verified_only(draft: dict[str, Any], check: dict[str, Any]) -> dict[str, Any]:
    failed = set(check.get("failed_ids") or [])
    kept = dict(draft)
    kept["conditions"] = [c for c in draft.get("conditions") or [] if c.get("id") not in failed]
    return kept


def check_sources(db: Session, *, auto_ingest: bool = True, trigger: str = "watcher") -> dict[str, Any]:
    """Re-read every watched page. A real change becomes a draft that waits for a person."""
    sources = (
        db.query(Source)
        .join(Program, Program.id == Source.program_id)
        .filter(Program.status == "active")
        .order_by(Source.id)
        .all()
    )
    if not get_settings().fetch_remote or not sources:
        return {"ok": True, "sources": [], "skipped": True}

    with ThreadPoolExecutor(max_workers=6) as pool:
        pages = dict(zip([s.id for s in sources], pool.map(lambda s: fetch_page(s.url), sources)))

    results = []
    for source in sources:
        page = pages[source.id]
        source.last_checked = datetime.utcnow()
        entry: dict[str, Any] = {"source_id": source.id, "program_id": source.program_id, "changed": False}
        if not page["ok"]:
            source.status = "unreachable"
            entry["status"] = "unreachable"
            results.append(entry)
            continue
        digest = content_hash(page["text"])
        changed = bool(source.last_hash) and source.last_hash != digest
        source.status = "ok"
        source.last_text = page["text"]
        source.last_hash = digest
        entry["status"] = "ok"
        if changed and auto_ingest and not _pending_for(db, source.program_id):
            db.commit()
            result = run_pipeline(db, program_id=source.program_id, trigger=trigger, page=page)
            if result.get("ok"):
                job = db.get(IngestionJob, result["job_id"])
                program = db.get(Program, source.program_id)
                if _rules_same(load_rules(db, program), json.loads(job.draft_json or "{}")):
                    # The page moved but the rules did not. Nobody needs to review that.
                    job.status = "no_change"
                    job.reviewed_by = "receipt check"
                    entry["changed"] = False
                else:
                    entry["changed"] = True
                    entry["ingestion_job_id"] = job.id
        results.append(entry)
    db.commit()
    changed_count = sum(1 for r in results if r.get("changed"))
    unreachable = sum(1 for r in results if r.get("status") == "unreachable")
    log_event(
        db,
        stage="sources_checked",
        detail=f"{len(results)} pages read, {changed_count} rule changes found, {unreachable} unreachable",
        case_id="watcher",
    )
    return {"ok": True, "sources": results}


def _pending_for(db: Session, program_id: str) -> bool:
    return (
        db.query(IngestionJob)
        .filter(IngestionJob.program_id == program_id, IngestionJob.status == "pending_review")
        .first()
        is not None
    )


def _rule_set(rules: dict[str, Any]) -> set[str]:
    return {
        json.dumps([c.get("attr"), c.get("op"), c.get("value")], sort_keys=True)
        for c in rules.get("conditions") or []
    }


def _rules_same(live: dict[str, Any], draft: dict[str, Any]) -> bool:
    """Same checks, ignoring wording. A reworded page is not a rule change."""
    return _rule_set(live) == _rule_set(draft)


def _slug(title: str, url: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", (title or "programme").lower()).strip("-")[:40] or "programme"
    return f"{base}-{content_hash(url)[:6]}"


def approve(
    db: Session, job_id: int, *, reviewed_by: str, keep_ids: list[str] | None = None
) -> dict[str, Any]:
    """A person approves a draft. Only verified rules can go live.

    keep_ids is the reviewer's tick list. None means "every rule", which needs every receipt to pass.
    """
    job = db.get(IngestionJob, job_id)
    if not job or job.status != "pending_review":
        return {"ok": False, "error": "job_not_pending"}
    check = json.loads(job.quote_check_json or "{}")
    draft = json.loads(job.draft_json)
    if keep_ids is None:
        if not check.get("passed"):
            return {"ok": False, "error": "quote_gate_failed"}
    else:
        failed = set(check.get("failed_ids") or [])
        if failed & set(keep_ids):
            return {"ok": False, "error": "quote_gate_failed"}
        draft["conditions"] = [c for c in draft.get("conditions") or [] if c.get("id") in set(keep_ids)]
    draft.pop("unsupported", None)
    if not draft.get("conditions"):
        return {"ok": False, "error": "no_verified_rules"}
    # Re-run the receipt check on exactly what goes live.
    if not receipt_check(job.notice_text, draft)["passed"]:
        return {"ok": False, "error": "quote_gate_failed"}

    program = db.get(Program, job.program_id) if job.program_id else None
    old_rules: dict[str, Any] = {"conditions": []}
    if program is None:
        program_id = _slug(draft.get("title", ""), job.source_url)
        program = db.get(Program, program_id)
        if program is None:
            program = Program(
                id=program_id,
                country=draft.get("country") or "",
                domain=draft.get("domain") or "income",
                title=draft.get("title") or "Programme",
                provider=draft.get("provider") or "",
                summary=draft.get("summary") or "",
                official_url=job.source_url,
                status="active",
            )
            db.add(program)
            db.flush()
            db.add(Source(program_id=program.id, url=job.source_url, label=program.title,
                          status="ok", last_text=job.notice_text, last_hash=content_hash(job.notice_text)))
        else:
            old_rules = load_rules(db, program)
        job.program_id = program.id
    else:
        old_rules = load_rules(db, program)
        program.summary = draft.get("summary") or program.summary

    draft["id"] = program.id
    previous = live_version(db, program)
    draft["version"] = (previous.version + 1) if previous else 1
    version = ProgramVersion(
        program_id=program.id,
        version=draft["version"],
        rules_json=json.dumps(draft),
        source_url=job.source_url,
        approved_by=reviewed_by,
        approved_at=datetime.utcnow(),
        status="live",
    )
    db.add(version)
    db.flush()
    if previous:
        previous.status = "replaced"
    program.current_version_id = version.id
    job.status = "approved"
    job.reviewed_by = reviewed_by
    job.reviewed_at = datetime.utcnow()
    db.commit()
    log_event(
        db,
        stage="rule_approved",
        detail=f"{reviewed_by} approved {program.title} v{version.version} ({len(draft['conditions'])} verified rules)",
        case_id=program.id,
        human_decision=True,
    )

    outcome = fan_out(db, program, old_rules, draft, job)
    steps = json.loads(job.steps_json or "[]")
    for step in steps:
        if step["key"] == "review":
            step.update(status="ok", label="Approved by a reviewer", detail=reviewed_by)
    steps.append({"key": "recheck", "label": "Re-checked everyone", "actor": "system", "status": "ok",
                  "detail": f"{outcome['checked']} people re-checked against the new rules", "ms": 0})
    steps.append({"key": "alerts", "label": "Routed the alerts", "actor": "system", "status": "ok",
                  "detail": f"{outcome['notified']} told they may qualify, {outcome['held']} losses held for a person",
                  "ms": 0})
    job.steps_json = json.dumps(steps)
    db.commit()

    try:
        from app.services.n8n_client import notify_approve

        notify_approve(job.id, reviewed_by)
    except Exception:  # noqa: BLE001
        pass
    return {"ok": True, "job_id": job.id, "program_id": program.id, "version": version.version, **outcome}


def fan_out(
    db: Session, program: Program, old_rules: dict[str, Any], new_rules: dict[str, Any], job: IngestionJob
) -> dict[str, Any]:
    diff = case_impact.diff_conditions(old_rules, new_rules)
    changed_line = describe_diff_lines(diff)[0] if old_rules.get("conditions") else "Entitle started checking this programme."
    quote = _first_quote(new_rules, diff)
    checked = notified = held = 0
    for user, attrs, consent in people_with_profiles(db):
        checked += 1
        before = matching.standing(program.country, old_rules, attrs)
        after = matching.standing(program.country, new_rules, attrs)
        kind = matching.change_kind(before, after)
        if kind == "unchanged":
            continue
        detail = {
            "display_name": user.display_name,
            "before": before or "none",
            "after": after,
            "what_changed": changed_line,
            "quote": quote,
            "released_by": "",
        }
        if kind == "newly_not_eligible":
            detail["meaning"] = f"You may no longer qualify for {program.title}."
            db.add(Notification(user_id=user.id, program_id=program.id, job_id=job.id,
                                kind=kind, status="pending_review", detail_json=json.dumps(detail)))
            held += 1
        else:
            if not consent:
                continue
            detail["meaning"] = f"You may now qualify for {program.title}."
            db.add(Notification(user_id=user.id, program_id=program.id, job_id=job.id,
                                kind=kind, status="queued", detail_json=json.dumps(detail)))
            notified += 1
    db.commit()
    log_event(
        db,
        stage="fan_out",
        detail=f"{program.title}: {checked} re-checked, {notified} alerted, {held} held for a person",
        case_id=program.id,
    )
    return {"checked": checked, "notified": notified, "held": held}


def _first_quote(rules: dict[str, Any], diff: dict[str, Any]) -> str:
    for change in diff.get("changed_conditions") or []:
        quote = (change.get("after") or {}).get("source_quote") or ""
        if quote:
            return quote
    for condition in diff.get("added_conditions") or []:
        if condition.get("source_quote"):
            return condition["source_quote"]
    for condition in rules.get("conditions") or []:
        if condition.get("source_quote"):
            return condition["source_quote"]
    return ""


def reject(db: Session, job_id: int, *, reviewed_by: str) -> bool:
    job = db.get(IngestionJob, job_id)
    if not job or job.status != "pending_review":
        return False
    job.status = "rejected"
    job.reviewed_by = reviewed_by
    job.reviewed_at = datetime.utcnow()
    steps = json.loads(job.steps_json or "[]")
    for step in steps:
        if step["key"] == "review":
            step.update(status="fail", label="Rejected by a reviewer", detail=reviewed_by)
    job.steps_json = json.dumps(steps)
    db.commit()
    draft = json.loads(job.draft_json or "{}")
    log_event(db, stage="rule_rejected", detail=f"{reviewed_by} rejected the draft for {draft.get('title')}",
              case_id=f"job-{job.id}", human_decision=True)
    return True


def condition_line(condition: dict[str, Any]) -> str:
    return condition.get("plain") or rule_phrase(condition)
