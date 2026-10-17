"""ID-only hooks for n8n. Auth: x-entitle-secret header. No personal data crosses this API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import IngestionJob, Notification
from app.services import pulse

router = APIRouter(prefix="/api/internal", tags=["internal"])


def require_secret(x_entitle_secret: str = Header(default="")) -> None:
    if x_entitle_secret != get_settings().n8n_shared_secret:
        raise HTTPException(status_code=401, detail="unauthorized")


class IngestBody(BaseModel):
    url: str = ""
    program_id: str = ""
    notice_text: str = ""


@router.get("/health")
def health(_: None = Depends(require_secret)):
    return {"ok": True, "service": "entitle"}


@router.post("/check-sources")
def check_sources(db: Session = Depends(get_db), _: None = Depends(require_secret)):
    return pulse.check_sources(db, auto_ingest=True, trigger="n8n")


@router.post("/ingest")
def ingest(body: IngestBody, db: Session = Depends(get_db), _: None = Depends(require_secret)):
    if not (body.url.strip() or body.notice_text.strip()):
        raise HTTPException(status_code=400, detail="url_or_notice_text_required")
    if body.notice_text.strip() and not body.program_id:
        raise HTTPException(status_code=400, detail="program_id_required_with_notice_text")
    result = pulse.run_pipeline(
        db, url=body.url, notice_text=body.notice_text, program_id=body.program_id, trigger="n8n"
    )
    return {k: v for k, v in result.items() if k != "steps"} | {"steps": result.get("steps", [])}


@router.get("/queue")
def queue(db: Session = Depends(get_db), _: None = Depends(require_secret)):
    """What is waiting for a person. Approval itself only happens on the desk."""
    jobs = db.query(IngestionJob).filter(IngestionJob.status == "pending_review").all()
    held = db.query(Notification).filter(Notification.status.in_(["pending_review", "held"])).count()
    return {
        "ok": True,
        "drafts_waiting": [{"id": j.id, "program_id": j.program_id, "trigger": j.trigger} for j in jobs],
        "bad_news_held": held,
    }
