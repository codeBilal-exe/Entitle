"""Source watching, ingest jobs, approve + fan-out. Shared by UI, cron, and n8n."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.engine.case_impact import CaseImpact
from app.engine.quote_gate import QuoteGate
from app.models import (
    DemoNotice,
    IngestionJob,
    Notification,
    Profile,
    Program,
    ProgramVersion,
    Source,
    User,
)
from app.services.ingest import draft_rule_pack
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


def fetch_source_text(db: Session, source: Source) -> str:
    if source.is_demo_controllable or source.url.startswith("/demo/notices/"):
        notice_id = source.url.rstrip("/").split("/")[-1]
        notice = db.get(DemoNotice, notice_id)
        return notice.body if notice else ""
    # External URLs: best-effort fetch for real watchers.
    try:
        import httpx

        response = httpx.get(source.url, timeout=20.0, follow_redirects=True)
        response.raise_for_status()
        return response.text
    except Exception as exc:  # noqa: BLE001
        source.status = "unreachable"
        log_event(
            db,
            stage="source_unreachable",
            detail=f"{source.id}: {exc}",
            case_id=source.program_id,
            status="error",
        )
        return ""


def check_sources(db: Session, *, auto_ingest: bool = True) -> dict[str, Any]:
    """Compare content hashes. Optionally create ingest jobs for changed sources."""
    results = []
    sources = db.query(Source).all()
    for source in sources:
        text = fetch_source_text(db, source)
        digest = content_hash(text)
        changed = bool(source.last_hash) and source.last_hash != digest
        first_seen = not source.last_hash
        source.last_checked = datetime.utcnow()
        if text:
            source.status = "ok"
        previous = source.last_hash
        source.last_hash = digest
        entry: dict[str, Any] = {
            "source_id": source.id,
            "program_id": source.program_id,
            "hash": digest,
            "changed": changed,
            "first_seen": first_seen,
            "status": source.status,
        }
        job = None
        if changed and auto_ingest and text:
            job = create_ingest_job(db, source.program_id, text, source_id=source.id)
            entry["ingestion_job_id"] = job.id
            log_event(
                db,
                stage="source_changed",
                detail=f"source {source.id} hash {previous[:8]}→{digest[:8]}",
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
    applicants = db.query(User).filter(User.role == "applicant").all()
    for applicant in applicants:
        profile = db.query(Profile).filter(Profile.user_id == applicant.id).first()
        attrs = profile_attrs(profile)
        change = case_impact.classify_case(str(applicant.id), old_rules, draft, attrs)
        consent = bool(profile and profile.consent_notifications)
        route = case_impact.fan_out_route(change, consent)
        detail = {
            "before": change.before.value,
            "after": change.after.value,
            "display_name": applicant.display_name,
            "kind": change.kind,
            "route": route,
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
                detail=f"{applicant.display_name} may no longer qualify — held for navigator",
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
                detail=f"{applicant.display_name} newly eligible — notification queued",
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


def run_replay_tighten(db: Session) -> dict[str, Any]:
    """Labeled REPLAY helper: tighten DEMO notice to 18-35 and ingest."""
    notice = db.get(DemoNotice, "inclusive-hiring")
    if not notice:
        return {"ok": False, "error": "demo_notice_missing"}
    notice.body = (
        "Inclusive Hiring Programme — Official Notice (DEMO SAMPLE)\n\n"
        "This programme supports persons with disabilities aged between 18 and 35 years "
        "who have completed secondary education or higher. Applications are accepted by email. "
        "Required documents include an identity document and a disability certificate.\n\n"
        "This page is a controllable DEMO source for RightPath. It is not a government website.\n"
        "REPLAY: scripted tighten for offline demos."
    )
    db.commit()
    log_event(
        db,
        stage="replay",
        detail="REPLAY tighten applied to DEMO notice",
        case_id="inclusive-hiring",
    )
    job = create_ingest_job(
        db, "demo_pk_work_01", notice.body, prefer_llm=False
    )
    return {"ok": True, "mode": "REPLAY", "ingestion_job_id": job.id}
