from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import SessionLocal, get_db, init_db
from app.engine.approval_gate import ApprovalGate, ApplicationState
from app.engine.case_impact import CaseImpact
from app.engine.quote_gate import QuoteGate
from app.engine.rule_engine import RuleEngine, Status
from app.models import (
    Application,
    DemoNotice,
    Event,
    IngestionJob,
    Notification,
    Profile,
    Program,
    ProgramVersion,
    User,
)
from app.security import mount_session, verify_password
from app.seed import seed_if_empty
from app.services.questions import QuestionEngine
from app.services.timeline import log_event

settings = get_settings()
app = FastAPI(title="RightPath", version="0.1.0")
mount_session(app, settings.secret_key)

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

rule_engine = RuleEngine()
quote_gate = QuoteGate()
case_impact = CaseImpact(rule_engine)
question_engine = QuestionEngine(rule_engine)
approval_gate = ApprovalGate()


@app.on_event("startup")
def on_startup() -> None:
    Path("data").mkdir(exist_ok=True)
    init_db()
    db = SessionLocal()
    try:
        seed_if_empty(db)
    finally:
        db.close()


def current_user(request: Request, db: Session) -> User | None:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return db.get(User, user_id)


def require_user(request: Request, db: Session) -> User:
    user = current_user(request, db)
    if not user:
        raise RuntimeError("login_required")
    return user


def load_rules(db: Session, program: Program) -> dict[str, Any]:
    if not program.current_version_id:
        return {"conditions": []}
    version = db.get(ProgramVersion, program.current_version_id)
    if not version:
        return {"conditions": []}
    return json.loads(version.rules_json)


def all_live_rules(db: Session) -> list[dict[str, Any]]:
    programs = db.query(Program).filter(Program.status == "active").all()
    return [load_rules(db, p) for p in programs]


def profile_attrs(profile: Profile | None) -> dict[str, Any]:
    if not profile:
        return {}
    return json.loads(profile.attributes_json or "{}")


def base_ctx(request: Request, db: Session, **extra: Any) -> dict[str, Any]:
    user = current_user(request, db)
    return {
        "request": request,
        "user": user,
        "replay_mode": settings.replay_mode,
        **extra,
    }


@app.get("/", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db)):
    programs = db.query(Program).filter(Program.status == "active").all()
    return templates.TemplateResponse(
        "home.html",
        base_ctx(request, db, programs=programs),
    )


@app.get("/health")
def health():
    return {"status": "ok", "service": "rightpath-core"}


@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request, db: Session = Depends(get_db)):
    users = db.query(User).order_by(User.role, User.email).all()
    return templates.TemplateResponse(
        "login.html",
        base_ctx(request, db, users=users, error=None),
    )


@app.post("/login")
def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.password_hash):
        users = db.query(User).order_by(User.role, User.email).all()
        return templates.TemplateResponse(
            "login.html",
            base_ctx(request, db, users=users, error="Invalid email or password."),
            status_code=401,
        )
    request.session["user_id"] = user.id
    log_event(db, stage="login", detail=f"{user.email} signed in", case_id=str(user.id))
    return RedirectResponse("/", status_code=303)


@app.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)


@app.get("/wizard", response_class=HTMLResponse)
def wizard(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    profile = db.query(Profile).filter(Profile.user_id == user.id).first()
    attrs = profile_attrs(profile)
    question = question_engine.next_question(all_live_rules(db), attrs)
    return templates.TemplateResponse(
        "wizard.html",
        base_ctx(request, db, profile=attrs, question=question),
    )


@app.post("/wizard")
def wizard_answer(
    request: Request,
    attr: str = Form(...),
    value: str = Form(""),
    prefer_not: str | None = Form(None),
    db: Session = Depends(get_db),
):
    user = current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    profile = db.query(Profile).filter(Profile.user_id == user.id).first()
    if not profile:
        profile = Profile(user_id=user.id, attributes_json="{}")
        db.add(profile)
        db.flush()
    attrs = profile_attrs(profile)
    if prefer_not:
        attrs[attr] = None
    elif value == "":
        return RedirectResponse("/wizard", status_code=303)
    else:
        if value.lower() in {"true", "yes", "1"}:
            attrs[attr] = True
        elif value.lower() in {"false", "no", "0"}:
            attrs[attr] = False
        elif value.isdigit():
            attrs[attr] = int(value)
        else:
            attrs[attr] = value
    profile.attributes_json = json.dumps(attrs)
    db.commit()
    return RedirectResponse("/wizard", status_code=303)


@app.get("/results", response_class=HTMLResponse)
def results(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    profile = db.query(Profile).filter(Profile.user_id == user.id).first()
    attrs = profile_attrs(profile)
    rows = []
    for program in db.query(Program).filter(Program.status == "active").all():
        rules = load_rules(db, program)
        evaluation = rule_engine.evaluate(rules, attrs)
        rows.append({"program": program, "rules": rules, "evaluation": evaluation})
    rows.sort(key=lambda r: {"eligible": 0, "likely": 1, "not_eligible": 2}[r["evaluation"].status.value])
    return templates.TemplateResponse(
        "results.html",
        base_ctx(request, db, rows=rows, profile=attrs, Status=Status),
    )


@app.get("/timeline", response_class=HTMLResponse)
def timeline(request: Request, db: Session = Depends(get_db)):
    events = db.query(Event).order_by(Event.at.desc()).limit(100).all()
    return templates.TemplateResponse(
        "timeline.html",
        base_ctx(request, db, events=events),
    )


@app.get("/privacy", response_class=HTMLResponse)
def privacy(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    profile = None
    apps = []
    if user:
        profile = db.query(Profile).filter(Profile.user_id == user.id).first()
        apps = db.query(Application).filter(Application.user_id == user.id).all()
    return templates.TemplateResponse(
        "privacy.html",
        base_ctx(request, db, profile=profile, applications=apps),
    )


@app.post("/privacy/delete")
def privacy_delete(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    db.query(Application).filter(Application.user_id == user.id).delete()
    db.query(Notification).filter(Notification.user_id == user.id).delete()
    profile = db.query(Profile).filter(Profile.user_id == user.id).first()
    if profile:
        profile.attributes_json = "{}"
        profile.consent_notifications = False
        profile.consent_email = ""
    log_event(
        db,
        stage="privacy_delete",
        detail="User deleted stored profile and applications",
        case_id=str(user.id),
        human_decision=True,
    )
    db.commit()
    return RedirectResponse("/privacy?deleted=1", status_code=303)


@app.get("/demo/notices/{notice_id}", response_class=HTMLResponse)
def demo_notice(notice_id: str, request: Request, db: Session = Depends(get_db)):
    notice = db.get(DemoNotice, notice_id)
    if not notice:
        return HTMLResponse("Notice not found", status_code=404)
    return templates.TemplateResponse(
        "demo_notice.html",
        base_ctx(request, db, notice=notice),
    )


@app.get("/curator", response_class=HTMLResponse)
def curator_home(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user or user.role not in {"curator", "admin"}:
        return RedirectResponse("/login", status_code=303)
    jobs = (
        db.query(IngestionJob)
        .filter(IngestionJob.status == "pending_review")
        .order_by(IngestionJob.created_at.desc())
        .all()
    )
    notice = db.get(DemoNotice, "inclusive-hiring")
    return templates.TemplateResponse(
        "curator.html",
        base_ctx(request, db, jobs=jobs, notice=notice),
    )


@app.post("/curator/demo-notice")
def update_demo_notice(
    request: Request,
    body: str = Form(...),
    db: Session = Depends(get_db),
):
    user = current_user(request, db)
    if not user or user.role not in {"curator", "admin"}:
        return RedirectResponse("/login", status_code=303)
    notice = db.get(DemoNotice, "inclusive-hiring")
    if notice:
        notice.body = body
        db.commit()
        log_event(
            db,
            stage="demo_notice_edit",
            detail="DEMO source notice updated",
            case_id="inclusive-hiring",
            human_decision=True,
        )
    return RedirectResponse("/curator", status_code=303)


@app.post("/curator/ingest-demo")
def ingest_demo(request: Request, db: Session = Depends(get_db)):
    """Deterministic demo ingest (no LLM required for the hero path)."""
    user = current_user(request, db)
    if not user or user.role not in {"curator", "admin"}:
        return RedirectResponse("/login", status_code=303)

    notice = db.get(DemoNotice, "inclusive-hiring")
    program = db.get(Program, "demo_pk_work_01")
    if not notice or not program:
        return RedirectResponse("/curator", status_code=303)

    live = load_rules(db, program)
    # Draft widens age band 18-35 -> 18-45 using quotes from the notice text.
    # Curator edits the notice first in the demo so QuoteGate passes.
    draft = json.loads(json.dumps(live))
    draft["version"] = int(live.get("version", 1)) + 1
    # Infer age band from the controllable DEMO notice text so the live demo
    # can widen (good news) or tighten (navigator review) on cue.
    for condition in draft.get("conditions") or []:
        if condition.get("id") != "c2":
            continue
        if "aged between 18 and 35 years" in notice.body:
            condition["value"] = [18, 35]
            condition["source_quote"] = "aged between 18 and 35 years"
        elif "aged between 18 and 45 years" in notice.body:
            condition["value"] = [18, 45]
            condition["source_quote"] = "aged between 18 and 45 years"

    quote_result = quote_gate.check(notice.body, draft)
    diff = case_impact.diff_conditions(live, draft)
    job = IngestionJob(
        program_id=program.id,
        notice_text=notice.body,
        draft_json=json.dumps(draft),
        quote_check_json=json.dumps(
            {
                "passed": quote_result.passed,
                "items": quote_result.items,
                "failed_ids": quote_result.failed_ids,
            }
        ),
        diff_json=json.dumps(diff),
        status="pending_review",
    )
    db.add(job)
    db.commit()
    log_event(
        db,
        stage="ingest_draft",
        detail=f"Draft v{draft['version']} for {program.id}; quote_gate={quote_result.passed}",
        case_id=program.id,
    )
    return RedirectResponse(f"/curator/jobs/{job.id}", status_code=303)


@app.get("/curator/jobs/{job_id}", response_class=HTMLResponse)
def curator_job(job_id: int, request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user or user.role not in {"curator", "admin"}:
        return RedirectResponse("/login", status_code=303)
    job = db.get(IngestionJob, job_id)
    if not job:
        return HTMLResponse("Job not found", status_code=404)
    return templates.TemplateResponse(
        "curator_job.html",
        base_ctx(
            request,
            db,
            job=job,
            draft=json.loads(job.draft_json),
            quote_check=json.loads(job.quote_check_json),
            diff=json.loads(job.diff_json),
        ),
    )


@app.post("/curator/jobs/{job_id}/approve")
def approve_job(job_id: int, request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user or user.role not in {"curator", "admin"}:
        return RedirectResponse("/login", status_code=303)
    job = db.get(IngestionJob, job_id)
    if not job or job.status != "pending_review":
        return RedirectResponse("/curator", status_code=303)

    quote_check = json.loads(job.quote_check_json)
    if not quote_check.get("passed"):
        return RedirectResponse(f"/curator/jobs/{job_id}?error=quote", status_code=303)

    program = db.get(Program, job.program_id)
    if not program:
        return RedirectResponse("/curator", status_code=303)

    old_rules = load_rules(db, program)
    draft = json.loads(job.draft_json)
    version = ProgramVersion(
        program_id=program.id,
        version=int(draft.get("version", 1)),
        rules_json=json.dumps(draft),
        source_url=draft.get("source_url", ""),
        last_verified=draft.get("last_verified", ""),
        approved_by=user.email,
        status="live",
    )
    db.add(version)
    db.flush()
    program.current_version_id = version.id
    job.status = "approved"
    job.reviewed_by = user.email

    log_event(
        db,
        stage="rule_approved",
        detail=f"{user.email} approved {program.id} v{version.version}",
        case_id=program.id,
        human_decision=True,
    )

    # Fan-out over applicant profiles
    applicants = db.query(User).filter(User.role == "applicant").all()
    for applicant in applicants:
        profile = db.query(Profile).filter(Profile.user_id == applicant.id).first()
        attrs = profile_attrs(profile)
        change = case_impact.classify_case(
            str(applicant.id), old_rules, draft, attrs
        )
        consent = bool(profile and profile.consent_notifications)
        route = case_impact.fan_out_route(change, consent)
        if route == "navigator_review":
            db.add(
                Notification(
                    user_id=applicant.id,
                    program_id=program.id,
                    kind="newly_not_eligible",
                    status="pending_review",
                    detail_json=json.dumps(
                        {
                            "before": change.before.value,
                            "after": change.after.value,
                            "display_name": applicant.display_name,
                        }
                    ),
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
                    detail_json=json.dumps(
                        {
                            "before": change.before.value,
                            "after": change.after.value,
                            "display_name": applicant.display_name,
                        }
                    ),
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

    db.commit()
    return RedirectResponse("/navigator", status_code=303)


@app.get("/navigator", response_class=HTMLResponse)
def navigator_queue(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user or user.role not in {"navigator", "admin", "curator"}:
        return RedirectResponse("/login", status_code=303)
    items = (
        db.query(Notification)
        .filter(Notification.status == "pending_review")
        .order_by(Notification.created_at.desc())
        .all()
    )
    parsed = []
    for item in items:
        parsed.append({"row": item, "detail": json.loads(item.detail_json or "{}")})
    return templates.TemplateResponse(
        "navigator.html",
        base_ctx(request, db, items=parsed),
    )


@app.post("/navigator/{notification_id}/release")
def navigator_release(
    notification_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user = current_user(request, db)
    if not user or user.role not in {"navigator", "admin", "curator"}:
        return RedirectResponse("/login", status_code=303)
    item = db.get(Notification, notification_id)
    if item:
        item.status = "approved"
        item.reviewed_by = user.email
        log_event(
            db,
            stage="navigator_release",
            detail=f"{user.email} released notification {item.id}",
            case_id=str(item.user_id),
            human_decision=True,
        )
        db.commit()
    return RedirectResponse("/navigator", status_code=303)


@app.get("/apply/{program_id}", response_class=HTMLResponse)
def apply_form(program_id: str, request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    program = db.get(Program, program_id)
    if not program:
        return HTMLResponse("Programme not found", status_code=404)
    rules = load_rules(db, program)
    profile = db.query(Profile).filter(Profile.user_id == user.id).first()
    return templates.TemplateResponse(
        "apply.html",
        base_ctx(
            request,
            db,
            program=program,
            rules=rules,
            profile=profile_attrs(profile),
        ),
    )


@app.post("/apply/{program_id}")
def apply_submit(
    program_id: str,
    request: Request,
    full_name: str = Form(...),
    contact_email: str = Form(...),
    age: int = Form(...),
    education_level: str = Form(...),
    db: Session = Depends(get_db),
):
    user = current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    program = db.get(Program, program_id)
    if not program:
        return HTMLResponse("Programme not found", status_code=404)
    rules = load_rules(db, program)
    payload = {
        "program_id": program_id,
        "to": rules.get("apply_email", "intake@example.org"),
        "fields": {
            "full_name": full_name,
            "contact_email": contact_email,
            "age": age,
            "education_level": education_level,
        },
        "attachments": rules.get("required_docs") or [],
    }
    idem = f"{user.id}:{program_id}"
    existing = db.query(Application).filter(Application.idempotency_key == idem).first()
    if existing:
        return RedirectResponse(f"/applications/{existing.id}", status_code=303)

    app_id = f"app-{user.id}-{program_id}"
    application = Application(
        id=app_id,
        user_id=user.id,
        program_id=program_id,
        state=ApplicationState.READY.value,
        payload_json=json.dumps(payload),
        idempotency_key=idem,
    )
    db.add(application)
    db.commit()
    return RedirectResponse(f"/applications/{app_id}", status_code=303)


@app.get("/applications/{application_id}", response_class=HTMLResponse)
def application_detail(
    application_id: str, request: Request, db: Session = Depends(get_db)
):
    user = current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    application = db.get(Application, application_id)
    if not application or application.user_id != user.id:
        return HTMLResponse("Not found", status_code=404)
    payload = json.loads(application.payload_json)
    return templates.TemplateResponse(
        "application.html",
        base_ctx(request, db, application=application, payload=payload),
    )


@app.post("/applications/{application_id}/approve")
def application_approve(
    application_id: str, request: Request, db: Session = Depends(get_db)
):
    user = current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    application = db.get(Application, application_id)
    if not application or application.user_id != user.id:
        return HTMLResponse("Not found", status_code=404)
    payload = json.loads(application.payload_json)
    state, digest = approval_gate.approve(application.state, payload)
    application.state = state
    application.approval_hash = digest
    log_event(
        db,
        stage="applicant_consent",
        detail=f"Applicant approved packet {application_id}",
        case_id=application_id,
        human_decision=True,
    )
    db.commit()
    return RedirectResponse(f"/applications/{application_id}", status_code=303)


@app.post("/applications/{application_id}/send")
def application_send(
    application_id: str, request: Request, db: Session = Depends(get_db)
):
    user = current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    application = db.get(Application, application_id)
    if not application or application.user_id != user.id:
        return HTMLResponse("Not found", status_code=404)
    payload = json.loads(application.payload_json)
    decision = approval_gate.authorize_send(
        application_id=application.id,
        state=application.state,
        stored_hash=application.approval_hash,
        payload=payload,
    )
    if not decision.allowed:
        log_event(
            db,
            stage="send_blocked",
            detail=decision.reason,
            case_id=application_id,
            status="blocked",
        )
        return RedirectResponse(
            f"/applications/{application_id}?error={decision.reason}", status_code=303
        )

    # Local/dev: mark sent and log. Real SMTP wired when MAIL_* is configured.
    recipient = settings.demo_recipient or payload.get("to")
    sent_via = "log_only"
    if settings.mail_host and settings.mail_user:
        try:
            from app.services.mailer import send_application_email

            send_application_email(payload, recipient)
            sent_via = "smtp"
        except Exception as exc:  # noqa: BLE001 — surface failure on timeline
            application.state = ApplicationState.FAILED.value
            log_event(
                db,
                stage="send_failed",
                detail=str(exc),
                case_id=application_id,
                status="failed",
            )
            db.commit()
            return RedirectResponse(
                f"/applications/{application_id}?error=send_failed", status_code=303
            )

    application.state = ApplicationState.SENT.value
    log_event(
        db,
        stage="send_ok",
        detail=f"Packet sent to {recipient} via {sent_via}",
        case_id=application_id,
    )
    db.commit()
    return RedirectResponse(f"/applications/{application_id}?sent=1", status_code=303)


# --- Internal / n8n hooks (IDs only) ---


@app.get("/api/internal/health")
def internal_health(request: Request):
    secret = request.headers.get("x-rightpath-secret", "")
    if secret != settings.n8n_shared_secret:
        return {"ok": False, "error": "unauthorized"}
    return {"ok": True}


@app.post("/api/internal/check-sources")
def internal_check_sources(request: Request, db: Session = Depends(get_db)):
    secret = request.headers.get("x-rightpath-secret", "")
    if secret != settings.n8n_shared_secret:
        return {"ok": False, "error": "unauthorized"}
    notice = db.get(DemoNotice, "inclusive-hiring")
    import hashlib

    body = notice.body if notice else ""
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    log_event(
        db,
        stage="source_check",
        detail=f"hash={digest[:12]}",
        case_id="inclusive-hiring",
    )
    return {"ok": True, "sources": [{"id": "inclusive-hiring", "hash": digest}]}
