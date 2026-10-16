"""Source watching, ingest jobs, approve + fan-out. Shared by UI, cron, and n8n."""

from __future__ import annotations

import hashlib
import html
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.config import get_settings
from app.engine.case_impact import CaseImpact
from app.engine.quote_gate import QuoteGate
from app.models import (
    IngestionJob,
    Notification,
    Profile,
    Program,
    ProgramVersion,
    Source,
    User,
)
from app.services.ingest import draft_rule_pack
from app.services.plain import alert_copy, describe_diff_lines
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


def profile_attrs(profile: Profile | None) -> dict[str, Any]:
    if not profile:
        return {}
    return json.loads(profile.attributes_json or "{}")


def html_to_text(raw: str) -> str:
    """Visible text from a fetched page. Tags and scripts are dropped."""
    without_blocks = re.sub(r"(?is)<(script|style|noscript).*?>.*?</\1>", " ", raw or "")
    without_tags = re.sub(r"(?s)<[^>]+>", " ", without_blocks)
    text = html.unescape(without_tags)
    return re.sub(r"\s+", " ", text).strip()


def _download(url: str) -> tuple[str, str]:
    """Return (status, text). status is ok or unreachable. Does not touch the database."""
    import httpx

    try:
        response = httpx.get(
            url,
            timeout=8.0,
            follow_redirects=True,
            headers={"User-Agent": "RightPath/0.5 (public notice watcher)"},
        )
        response.raise_for_status()
        text = html_to_text(response.text)
        if not text:
            return "unreachable", ""
        return "ok", text[:50000]
    except Exception:
        return "unreachable", ""


def check_sources(db: Session, *, auto_ingest: bool = True) -> dict[str, Any]:
    """Re-read official pages. A text change becomes a draft that waits for a person."""
    sources = db.query(Source).order_by(Source.id).all()
    settings = get_settings()
    downloaded: dict[int, tuple[str, str]] = {}
    if settings.fetch_remote and sources:
        targets = [(source.id, source.url) for source in sources]
        with ThreadPoolExecutor(max_workers=6) as pool:
            pairs = list(pool.map(lambda item: (item[0], _download(item[1])), targets))
        downloaded = {source_id: payload for source_id, payload in pairs}

    results = []
    for source in sources:
        if not settings.fetch_remote:
            results.append(
                {
                    "source_id": source.id,
                    "program_id": source.program_id,
                    "hash": source.last_hash,
                    "changed": False,
                    "first_seen": not source.last_hash,
                    "status": source.status or "not_checked",
                    "skipped": True,
                }
            )
            continue

        status, text = downloaded.get(source.id, ("unreachable", ""))
        source.last_checked = datetime.utcnow()
        if status != "ok" or not text:
            source.status = "unreachable"
            source.last_text = ""
            log_event(
                db,
                stage="source_unreachable",
                detail=f"source {source.id} could not be read",
                case_id=source.program_id,
                status="error",
            )
            results.append(
                {
                    "source_id": source.id,
                    "program_id": source.program_id,
                    "hash": source.last_hash,
                    "changed": False,
                    "first_seen": False,
                    "status": "unreachable",
                }
            )
            continue

        digest = content_hash(text)
        changed = bool(source.last_hash) and source.last_hash != digest
        first_seen = not source.last_hash
        previous = source.last_hash
        source.status = "ok"
        source.last_text = text
        source.last_hash = digest
        entry: dict[str, Any] = {
            "source_id": source.id,
            "program_id": source.program_id,
            "hash": digest,
            "changed": changed,
            "first_seen": first_seen,
            "status": source.status,
        }
        if changed and auto_ingest:
            job = create_ingest_job(db, source.program_id, text, source_id=source.id)
            entry["ingestion_job_id"] = job.id
            log_event(
                db,
                stage="source_changed",
                detail=f"source {source.id} hash {str(previous)[:8]}→{digest[:8]}",
                case_id=source.program_id,
            )
        else:
            log_event(
                db,
                stage="source_check",
                detail=f"source {source.id} hash={digest[:12]} changed={changed}",
                case_id=source.program_id,
            )
        results.append(entry)
    db.commit()
    return {"ok": True, "sources": results}


def create_ingest_job(
    db: Session,
    program_id: str,
    notice_text: str,
    *,
    source_id: int | None = None,
    prefer_llm: bool = True,
) -> IngestionJob:
    program = db.get(Program, program_id)
    if not program:
        raise ValueError(f"unknown program {program_id}")
    live = load_rules(db, program)
    draft, method = draft_rule_pack(live, notice_text, prefer_llm=prefer_llm)
    quote_result = quote_gate.check(notice_text, draft)
    diff = case_impact.diff_conditions(live, draft)
    job = IngestionJob(
        source_id=source_id,
        program_id=program.id,
        notice_text=notice_text,
        draft_json=json.dumps(draft),
        quote_check_json=json.dumps(
            {
                "passed": quote_result.passed,
                "items": quote_result.items,
                "failed_ids": quote_result.failed_ids,
                "method": method,
            }
        ),
        diff_json=json.dumps(diff),
        status="pending_review",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    log_event(
        db,
        stage="ingest_draft",
        detail=f"Draft v{draft.get('version')} for {program.id} via {method}; quote_gate={quote_result.passed}",
        case_id=program.id,
    )
    return job


def approve_and_fan_out(
    db: Session, job_id: int, *, reviewed_by: str
) -> dict[str, Any]:
    job = db.get(IngestionJob, job_id)
    if not job or job.status != "pending_review":
        return {"ok": False, "error": "job_not_pending"}

    quote_check = json.loads(job.quote_check_json)
    if not quote_check.get("passed"):
        return {"ok": False, "error": "quote_gate_failed"}

    program = db.get(Program, job.program_id)
    if not program:
        return {"ok": False, "error": "program_missing"}

    old_rules = load_rules(db, program)
    draft = json.loads(job.draft_json)
    version = ProgramVersion(
        program_id=program.id,
        version=int(draft.get("version", 1)),
        rules_json=json.dumps(draft),
        source_url=draft.get("source_url", ""),
        last_verified=draft.get("last_verified", ""),
        approved_by=reviewed_by,
        approved_at=datetime.utcnow(),
        status="live",
    )
    db.add(version)
    db.flush()
    program.current_version_id = version.id
    job.status = "approved"
    job.reviewed_by = reviewed_by

    log_event(
        db,
        stage="rule_approved",
        detail=f"{reviewed_by} approved {program.id} v{version.version}",
        case_id=program.id,
        human_decision=True,
    )

    routed = []
    diff = json.loads(job.diff_json or "{}")
    quote = _quote_from(draft, diff)
    changed_line = describe_diff_lines(diff)[0]
    citizens = db.query(User).filter(User.role == "citizen").all()
    for applicant in citizens:
        profile = db.query(Profile).filter(Profile.user_id == applicant.id).first()
        if profile is None:
            log_event(
                db,
                stage="fanout_skip",
                detail=f"{applicant.display_name}: no profile",
                case_id=str(applicant.id),
            )
            continue
        attrs = profile_attrs(profile)
        change = case_impact.classify_case(str(applicant.id), old_rules, draft, attrs)
        consent = bool(profile.consent_notifications)
        route = case_impact.fan_out_route(change, consent)
        copy = alert_copy(
            change.kind,
            program.title,
            diff_lines=[changed_line],
            quote=quote,
        )
        detail = {
            "before": change.before.value,
            "after": change.after.value,
            "display_name": applicant.display_name,
            "kind": change.kind,
            "route": route,
            "what_changed": copy["what_changed"],
            "meaning": copy["meaning"],
            "quote": copy["quote"],
            "next_step": copy["next_step"],
            "released_by": "",
        }
        if route == "navigator_review":
            db.add(
                Notification(
                    user_id=applicant.id,
                    program_id=program.id,
                    kind="newly_not_eligible",
                    status="pending_review",
                    detail_json=json.dumps(detail),
                )
            )
            log_event(
                db,
                stage="fanout_navigator",
                detail=f"{applicant.display_name} may no longer qualify — held for a person",
                case_id=str(applicant.id),
                human_decision=True,
            )
        elif route == "notify_applicant":
            db.add(
                Notification(
                    user_id=applicant.id,
                    program_id=program.id,
                    kind="newly_eligible",
                    status="queued",
                    detail_json=json.dumps(detail),
                )
            )
            log_event(
                db,
                stage="fanout_notify",
                detail=f"{applicant.display_name} may now qualify — alert queued",
                case_id=str(applicant.id),
            )
        else:
            log_event(
                db,
                stage="fanout_skip",
                detail=f"{applicant.display_name}: {change.kind}/{route}",
                case_id=str(applicant.id),
            )
        routed.append({"user_id": applicant.id, **detail})

    db.commit()

    try:
        from app.services.n8n_client import notify_approve

        notify_approve(job.id, reviewed_by)
    except Exception:
        pass

    return {
        "ok": True,
        "job_id": job.id,
        "program_id": program.id,
        "version": version.version,
        "routed": routed,
    }


def _quote_from(rules: dict[str, Any], diff: dict[str, Any]) -> str:
    for change in diff.get("changed_conditions") or []:
        after = change.get("after") or {}
        quote = after.get("source_quote") or ""
        if quote:
            return quote
    for condition in rules.get("conditions") or []:
        quote = condition.get("source_quote") or ""
        if quote:
            return quote
    return ""


def run_replay_tighten(db: Session) -> dict[str, Any]:
    """The controllable demo notice is gone. Rule changes come from fetched pages."""
    return {"ok": False, "error": "demo_replay_removed"}
