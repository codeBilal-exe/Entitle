from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.api_internal import router as internal_router
from app.config import get_settings
from app.db import SessionLocal, get_db, init_db
from app.engine.approval_gate import ApprovalGate, ApplicationState
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
from app.services import pulse
from app.services.demo_reset import reset_demo
from app.services.explainer import explain_result
from app.services.goldset import run_gold_set
from app.services.manual_pack import build_manual_pack
from app.services.questions import QuestionEngine
from app.services.runtime import is_send_enabled, set_send_enabled
from app.services.scheduler import start_scheduler, stop_scheduler
from app.services.timeline import log_event

settings = get_settings()
app = FastAPI(title="RightPath", version="0.3.0")
mount_session(app, settings.secret_key)
app.include_router(internal_router)

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

rule_engine = RuleEngine()
question_engine = QuestionEngine(rule_engine)
approval_gate = ApprovalGate()


def render(request: Request, name: str, db: Session, **extra: Any):
    return templates.TemplateResponse(request, name, base_ctx(request, db, **extra))


@app.on_event("startup")
def on_startup() -> None:
    Path("data").mkdir(exist_ok=True)
    init_db()
    db = SessionLocal()
    try:
        seed_if_empty(db)
        # Baseline hashes so the first watcher run does not false-trigger.
        pulse.check_sources(db, auto_ingest=False)
    finally:
        db.close()
    start_scheduler()


@app.on_event("shutdown")
def on_shutdown() -> None:
    stop_scheduler()


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
    return pulse.load_rules(db, program)


def all_live_rules(db: Session) -> list[dict[str, Any]]:
    programs = db.query(Program).filter(Program.status == "active").all()
    return [load_rules(db, p) for p in programs]


def profile_attrs(profile: Profile | None) -> dict[str, Any]:
    return pulse.profile_attrs(profile)


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
    return render(request, "home.html", db, programs=programs)


@app.get("/health")
def health():
    return {"status": "ok", "service": "rightpath-core"}


@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request, db: Session = Depends(get_db)):
    users = db.query(User).order_by(User.role, User.email).all()
    return render(request, "login.html", db, users=users, error=None)


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
            request,
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
    return render(request, "wizard.html", db, profile=attrs, question=question)


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
    for row in rows:
        row["explanation"] = explain_result(row["program"].title, row["evaluation"])
    return render(request, "results.html", db, rows=rows, profile=attrs, Status=Status)


@app.get("/timeline", response_class=HTMLResponse)
def timeline(request: Request, db: Session = Depends(get_db)):
    events = db.query(Event).order_by(Event.at.desc()).limit(100).all()
    return render(request, "timeline.html", db, events=events)


@app.get("/privacy", response_class=HTMLResponse)
def privacy(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    profile = None
    apps = []
    if user:
        profile = db.query(Profile).filter(Profile.user_id == user.id).first()
        apps = db.query(Application).filter(Application.user_id == user.id).all()
    return render(request, "privacy.html", db, profile=profile, applications=apps)


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
    return render(request, "demo_notice.html", db, notice=notice)


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
    return render(
        request,
        "curator.html",
        db,
        jobs=jobs,
        notice=notice,
        goldset=run_gold_set(),
        send_enabled=is_send_enabled(),
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
    user = current_user(request, db)
    if not user or user.role not in {"curator", "admin"}:
        return RedirectResponse("/login", status_code=303)

    notice = db.get(DemoNotice, "inclusive-hiring")
    if not notice:
        return RedirectResponse("/curator", status_code=303)
    job = pulse.create_ingest_job(
        db, "demo_pk_work_01", notice.body, prefer_llm=True
    )
    return RedirectResponse(f"/curator/jobs/{job.id}", status_code=303)


@app.post("/curator/check-now")
def curator_check_now(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user or user.role not in {"curator", "admin"}:
        return RedirectResponse("/login", status_code=303)
    result = pulse.check_sources(db, auto_ingest=True)
    changed = [s for s in result.get("sources", []) if s.get("changed")]
    if changed and changed[0].get("ingestion_job_id"):
        return RedirectResponse(
            f"/curator/jobs/{changed[0]['ingestion_job_id']}", status_code=303
        )
    return RedirectResponse("/curator?checked=1", status_code=303)


@app.post("/curator/replay")
def curator_replay(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user or user.role not in {"curator", "admin"}:
        return RedirectResponse("/login", status_code=303)
    result = pulse.run_replay_tighten(db)
    job_id = result.get("ingestion_job_id")
    if job_id:
        return RedirectResponse(f"/curator/jobs/{job_id}", status_code=303)
    return RedirectResponse("/curator", status_code=303)


@app.post("/curator/reset-demo")
def curator_reset_demo(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user or user.role not in {"curator", "admin"}:
        return RedirectResponse("/login", status_code=303)
    reset_demo(db)
    return RedirectResponse("/curator?reset=1", status_code=303)


@app.post("/curator/kill-switch")
def curator_kill_switch(
    request: Request,
    enabled: str = Form("1"),
    db: Session = Depends(get_db),
):
    user = current_user(request, db)
    if not user or user.role not in {"curator", "admin"}:
        return RedirectResponse("/login", status_code=303)
    set_send_enabled(enabled == "1")
    log_event(
        db,
        stage="kill_switch",
        detail=f"send_enabled={enabled == '1'} by {user.email}",
        case_id="system",
        human_decision=True,
    )
    return RedirectResponse("/curator", status_code=303)


@app.get("/curator/jobs/{job_id}", response_class=HTMLResponse)
def curator_job(job_id: int, request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user or user.role not in {"curator", "admin"}:
        return RedirectResponse("/login", status_code=303)
    job = db.get(IngestionJob, job_id)
    if not job:
        return HTMLResponse("Job not found", status_code=404)
    return render(
        request,
        "curator_job.html",
        db,
        job=job,
        draft=json.loads(job.draft_json),
        quote_check=json.loads(job.quote_check_json),
        diff=json.loads(job.diff_json),
    )


@app.post("/curator/jobs/{job_id}/approve")
def approve_job(job_id: int, request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user or user.role not in {"curator", "admin"}:
        return RedirectResponse("/login", status_code=303)
    result = pulse.approve_and_fan_out(db, job_id, reviewed_by=user.email)
    if not result.get("ok"):
        if result.get("error") == "quote_gate_failed":
            return RedirectResponse(f"/curator/jobs/{job_id}?error=quote", status_code=303)
        return RedirectResponse("/curator", status_code=303)
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
    return render(request, "navigator.html", db, items=parsed)


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
    return render(
        request,
        "apply.html",
        db,
        program=program,
        rules=rules,
        profile=profile_attrs(profile),
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
    pack_name = None
    pack_path = Path("data/manual_packs") / f"{application.id}.zip"
    if pack_path.exists():
        pack_name = pack_path.name
    return render(
        request,
        "application.html",
        db,
        application=application,
        payload=payload,
        pack_name=pack_name,
        send_enabled=is_send_enabled(),
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

    if not is_send_enabled():
        pack = build_manual_pack(application.id, payload)
        application.state = ApplicationState.FAILED.value
        log_event(
            db,
            stage="send_blocked",
            detail=f"Kill switch on — manual pack {pack.name}",
            case_id=application_id,
            status="blocked",
            human_decision=True,
        )
        db.commit()
        return RedirectResponse(
            f"/applications/{application_id}?error=kill_switch&pack=1", status_code=303
        )

    recipient = settings.demo_recipient or payload.get("to")
    sent_via = "log_only"
    if settings.mail_host and settings.mail_user:
        try:
            from app.services.mailer import send_application_email

            send_application_email(payload, recipient)
            sent_via = "smtp"
        except Exception as exc:  # noqa: BLE001
            pack = build_manual_pack(application.id, payload)
            application.state = ApplicationState.FAILED.value
            log_event(
                db,
                stage="send_failed",
                detail=f"{exc} — manual pack {pack.name}",
                case_id=application_id,
                status="failed",
            )
            db.commit()
            return RedirectResponse(
                f"/applications/{application_id}?error=send_failed&pack=1",
                status_code=303,
            )

    application.state = ApplicationState.SENT.value
    log_event(
        db,
        stage="send_ok",
        detail=f"Packet sent to {recipient} via {sent_via}",
        case_id=application_id,
    )
    db.commit()
    try:
        from app.services.n8n_client import notify_send

        notify_send(application.id)
    except Exception:
        pass
    return RedirectResponse(f"/applications/{application_id}?sent=1", status_code=303)


@app.get("/applications/{application_id}/pack")
def download_manual_pack(
    application_id: str, request: Request, db: Session = Depends(get_db)
):
    from fastapi.responses import FileResponse

    user = current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    application = db.get(Application, application_id)
    if not application or application.user_id != user.id:
        return HTMLResponse("Not found", status_code=404)
    path = Path("data/manual_packs") / f"{application_id}.zip"
    if not path.exists():
        return HTMLResponse("No manual pack for this application", status_code=404)
    return FileResponse(path, filename=path.name, media_type="application/zip")


@app.get("/notifications", response_class=HTMLResponse)
def my_notifications(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    items = (
        db.query(Notification)
        .filter(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc())
        .all()
    )
    parsed = [{"row": i, "detail": json.loads(i.detail_json or "{}")} for i in items]
    return render(request, "notifications.html", db, items=parsed)
