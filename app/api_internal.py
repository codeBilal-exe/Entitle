"""ID-only hooks for n8n / automation. Auth: x-rightpath-secret header."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.engine.approval_gate import ApprovalGate, ApplicationState
from app.models import Application, DemoNotice
from app.services import pulse
from app.services.mailer import send_application_email
from app.services.timeline import log_event

router = APIRouter(prefix="/api/internal", tags=["internal"])
approval_gate = ApprovalGate()


def require_secret(x_rightpath_secret: str = Header(default="")) -> None:
    settings = get_settings()
    if x_rightpath_secret != settings.n8n_shared_secret:
        raise HTTPException(status_code=401, detail="unauthorized")


class IngestBody(BaseModel):
    program_id: str = "demo_pk_work_01"
    notice_text: str | None = None
    prefer_llm: bool = True


class ApproveBody(BaseModel):
    job_id: int
    reviewed_by: str = "n8n"


class SendBody(BaseModel):
    application_id: str


@router.get("/health")
def health(_: None = Depends(require_secret)):
    return {"ok": True, "service": "rightpath-core"}


@router.post("/check-sources")
def check_sources(
    auto_ingest: bool = True,
    db: Session = Depends(get_db),
    _: None = Depends(require_secret),
):
    return pulse.check_sources(db, auto_ingest=auto_ingest)


@router.post("/ingest")
def ingest(body: IngestBody, db: Session = Depends(get_db), _: None = Depends(require_secret)):
    text = body.notice_text
    if not text:
        notice = db.get(DemoNotice, "inclusive-hiring")
        text = notice.body if notice else ""
    job = pulse.create_ingest_job(
        db, body.program_id, text, prefer_llm=body.prefer_llm
    )
    return {"ok": True, "ingestion_job_id": job.id, "status": job.status}


@router.post("/approve")
def approve(body: ApproveBody, db: Session = Depends(get_db), _: None = Depends(require_secret)):
    return pulse.approve_and_fan_out(db, body.job_id, reviewed_by=body.reviewed_by)


@router.post("/send")
def send_packet(body: SendBody, db: Session = Depends(get_db), _: None = Depends(require_secret)):
    settings = get_settings()
    application = db.get(Application, body.application_id)
    if not application:
        raise HTTPException(status_code=404, detail="application_not_found")
    import json

    payload = json.loads(application.payload_json)
    decision = approval_gate.authorize_send(
        application_id=application.id,
        state=application.state,
        stored_hash=application.approval_hash,
        payload=payload,
    )
    if not decision.allowed:
        return {"ok": False, "reason": decision.reason}

    recipient = settings.demo_recipient or payload.get("to")
    sent_via = "log_only"
    if settings.mail_host and settings.mail_user:
        try:
            send_application_email(payload, recipient)
            sent_via = "smtp"
        except Exception as exc:  # noqa: BLE001
            application.state = ApplicationState.FAILED.value
            log_event(
                db,
                stage="send_failed",
                detail=str(exc),
                case_id=application.id,
                status="failed",
            )
            db.commit()
            return {"ok": False, "reason": "send_failed", "error": str(exc)}

    application.state = ApplicationState.SENT.value
    log_event(
        db,
        stage="send_ok",
        detail=f"Packet sent to {recipient} via {sent_via}",
        case_id=application.id,
    )
    db.commit()
    return {"ok": True, "sent_via": sent_via, "recipient": recipient}


@router.post("/replay/tighten")
def replay_tighten(db: Session = Depends(get_db), _: None = Depends(require_secret)):
    settings = get_settings()
    if not settings.replay_mode:
        # Still allow explicit REPLAY calls in demos, but label clearly.
        pass
    return pulse.run_replay_tighten(db)


@router.get("/pending-jobs")
def pending_jobs(db: Session = Depends(get_db), _: None = Depends(require_secret)):
    from app.models import IngestionJob

    jobs = (
        db.query(IngestionJob)
        .filter(IngestionJob.status == "pending_review")
        .order_by(IngestionJob.created_at.desc())
        .all()
    )
    return {
        "ok": True,
        "jobs": [
            {"id": j.id, "program_id": j.program_id, "status": j.status}
            for j in jobs
        ],
    }
