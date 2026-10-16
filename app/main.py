from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import quote

from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.api_internal import router as internal_router
from app.config import get_settings
from app.db import SessionLocal, get_db, init_db
from app.engine.approval_gate import ApprovalGate, ApplicationState
from app.engine.rule_engine import RuleEngine
from app.models import (
    Application,
    Event,
    IngestionJob,
    Notification,
    Profile,
    Program,
    Source,
    User,
)
from app.security import hash_password, mount_session, verify_password
from app.seed import ensure_catalogue, ensure_demo_accounts, ensure_demo_approved_rules, seed_if_empty
from app.services import pulse
from app.services.assistant import create_packet, reply_for
from app.services.explainer import short_reason
from app.services import plain
from app.services.manual_pack import build_manual_pack
from app.services.runtime import is_send_enabled, set_send_enabled
from app.services.scheduler import start_scheduler, stop_scheduler
from app.services.timeline import log_event

settings = get_settings()
app = FastAPI(title="RightPath", version="0.5.0")
mount_session(app, settings.secret_key)
app.include_router(internal_router)

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
templates.env.globals.update(
    attr_label=plain.attr_label,
    country_label=plain.country_label,
    describe_diff_lines=plain.describe_diff_lines,
    doc_label=plain.doc_label,
    domain_label=plain.domain_label,
    eligibility_label=plain.eligibility_label,
    kind_label=plain.kind_label,
    next_step_label=plain.next_step_label,
    notify_status_label=plain.notify_status_label,
    outcome_label=plain.outcome_label,
    payload_rows=plain.payload_rows,
    profile_rows=plain.profile_rows,
    rule_phrase=plain.rule_phrase,
    source_status_label=plain.source_status_label,
    stage_label=plain.stage_label,
    state_label=plain.state_label,
    status_shift=plain.status_shift,
)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

rule_engine = RuleEngine()
approval_gate = ApprovalGate()

STAFF_ROLES = {"admin", "staff"}


def render(request: Request, name: str, db: Session, status_code: int = 200, **extra: Any):
    return templates.TemplateResponse(
        request, name, base_ctx(request, db, **extra), status_code=status_code
    )


@app.on_event("startup")
def on_startup() -> None:
    Path("data").mkdir(exist_ok=True)
    init_db()
    db = SessionLocal()
    try:
        seed_if_empty(db)
        ensure_demo_accounts(db)
        ensure_catalogue(db)
        pulse.check_sources(db, auto_ingest=False)
        # After the watcher: restore demo quotes so a failed fetch cannot wipe eligibility.
        ensure_demo_approved_rules(db)
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


def is_staff(user: User | None) -> bool:
    return bool(user and user.role in STAFF_ROLES)


def is_admin(user: User | None) -> bool:
    return bool(user and user.role == "admin")


def redirect_login(next_path: str = "/") -> RedirectResponse:
    return RedirectResponse(f"/login?next={quote(next_path, safe='')}", status_code=303)


def safe_next(next_path: str) -> str:
    if next_path.startswith("/") and not next_path.startswith("//"):
        return next_path
    return "/"


def deny(request: Request, db: Session):
    return render(request, "forbidden.html", db, status_code=403)


def alert_visible(row: Notification) -> bool:
    """Bad news stays hidden until a person releases it."""
    if row.kind == "newly_not_eligible":
        return row.status == "approved"
    if row.kind in {"newly_eligible", "deadline_reminder"}:
        return row.status in {"queued", "approved"}
    return False


def unread_for(db: Session, user: User | None) -> int:
    if not user or user.role != "citizen":
        return 0
    rows = (
        db.query(Notification)
        .filter(Notification.user_id == user.id, Notification.read_at.is_(None))
        .all()
    )
    return sum(1 for row in rows if alert_visible(row))


def load_rules(db: Session, program: Program) -> dict[str, Any]:
    return pulse.load_rules(db, program)


def profile_attrs(profile: Profile | None) -> dict[str, Any]:
    return pulse.profile_attrs(profile)


def own_profile(db: Session, user: User) -> Profile | None:
    return db.query(Profile).filter(Profile.user_id == user.id).first()


def checked_match(rules: dict[str, Any], source: Source | None, evaluation) -> str:
    """Do not call someone eligible when no quoted rule has been approved."""
    if source is not None and source.status == "unreachable":
        return "unreachable"
    if not (rules.get("conditions") or []):
        return "unchecked"
    return evaluation.status.value


def base_ctx(request: Request, db: Session, **extra: Any) -> dict[str, Any]:
    user = current_user(request, db)
    return {
        "request": request,
        "user": user,
        "is_staff": is_staff(user),
        "is_admin": is_admin(user),
        "unread_count": unread_for(db, user),
        "replay_mode": settings.replay_mode,
        **extra,
    }


def _optional_bool(raw: str) -> bool | None:
    if raw == "yes":
        return True
    if raw == "no":
        return False
    return None


@app.get("/health")
def health():
    return {"status": "ok", "service": "rightpath-core"}


@app.get("/", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user:
        return redirect_login("/")
    programs = (
        db.query(Program)
        .filter(Program.status == "active")
        .order_by(Program.domain, Program.title)
        .all()
    )
    if user.role == "citizen":
        profile = own_profile(db, user)
        attrs = profile_attrs(profile)
        rows = []
        for program in programs:
            rules = load_rules(db, program)
            source = (
                db.query(Source).filter(Source.program_id == program.id).order_by(Source.id).first()
            )
            evaluation = rule_engine.evaluate(rules, attrs)
            rows.append(
                {
                    "program": program,
                    "rules": rules,
                    "source": source,
                    "evaluation": evaluation,
                    "match": checked_match(rules, source, evaluation),
                    "why": short_reason(evaluation) if rules.get("conditions") else "",
                }
            )
        rank = {"eligible": 0, "likely": 1, "unchecked": 2, "unreachable": 3, "not_eligible": 4}
        rows.sort(key=lambda row: (rank.get(row["match"], 9), row["program"].title))
        eligible_count = sum(1 for row in rows if row["match"] == "eligible")
        return render(
            request,
            "home.html",
            db,
            program_rows=rows,
            has_profile=profile is not None,
            eligible_count=eligible_count,
            assistant=request.session.get("assistant"),
        )

    sources = (
        db.query(Source)
        .filter(Source.program_id.in_([p.id for p in programs]))
        .order_by(Source.label)
        .all()
    )
    return render(
        request,
        "home.html",
        db,
        sources=sources,
        titles={p.id: p.title for p in programs},
        job_count=db.query(IngestionJob)
        .filter(
            IngestionJob.status == "pending_review",
            IngestionJob.program_id.in_([p.id for p in programs]),
        )
        .count(),
        review_count=db.query(Notification)
        .filter(Notification.status.in_(["pending_review", "held"]))
        .count(),
        send_enabled=is_send_enabled(),
    )


@app.post("/assistant")
def assistant_ask(
    request: Request,
    sentence: str = Form(""),
    program_id: str = Form(""),
    db: Session = Depends(get_db),
):
    user = current_user(request, db)
    if not user:
        return redirect_login("/")
    if user.role != "citizen":
        return deny(request, db)

    if program_id.strip():
        program = db.get(Program, program_id.strip())
        if not program or program.status != "active":
            return HTMLResponse("Programme not found", status_code=404)
        attrs = profile_attrs(own_profile(db, user))
        rules = load_rules(db, program)
        source = (
            db.query(Source).filter(Source.program_id == program.id).order_by(Source.id).first()
        )
        evaluation = rule_engine.evaluate(rules, attrs)
        if checked_match(rules, source, evaluation) != "eligible":
            request.session["assistant"] = {
                "error": "That programme is not an approved match, so no packet was drafted.",
                "summary": "",
                "cards": [],
                "saved": [],
                "question": "",
                "used_model": False,
            }
            return RedirectResponse("/", status_code=303)
        application = create_packet(db, user, program, rules, attrs)
        log_event(
            db,
            stage="assistant_packet",
            detail=f"Drafted packet {application.id} for approval",
            case_id=application.id,
            human_decision=False,
        )
        db.commit()
        return RedirectResponse(f"/applications/{application.id}?drafted=1", status_code=303)

    result = reply_for(db, user, sentence)
    if result.get("program_id"):
        program = db.get(Program, result["program_id"])
        rules = load_rules(db, program) if program else {}
        if program is not None:
            application = create_packet(db, user, program, rules, result.get("attrs") or {})
            log_event(
                db,
                stage="assistant_packet",
                detail=f"Drafted packet {application.id} from a sentence",
                case_id=application.id,
                human_decision=False,
            )
            db.commit()
            request.session["assistant"] = {
                "error": None,
                "summary": result.get("summary") or "",
                "cards": result.get("cards") or [],
                "saved": result.get("saved") or [],
                "question": result.get("question") or "",
                "used_model": bool(result.get("used_model")),
            }
            return RedirectResponse(
                f"/applications/{application.id}?drafted=1", status_code=303
            )

    request.session["assistant"] = {
        "error": result.get("error"),
        "summary": result.get("summary") or "",
        "cards": result.get("cards") or [],
        "saved": result.get("saved") or [],
        "question": result.get("question") or "",
        "used_model": bool(result.get("used_model")),
    }
    if result.get("saved") or result.get("summary"):
        log_event(
            db,
            stage="assistant_reply",
            detail="Replied from approved rules",
            case_id=str(user.id),
            human_decision=False,
        )
        db.commit()
    return RedirectResponse("/", status_code=303)


@app.get("/programmes/{program_id}", response_class=HTMLResponse)
def programme_detail(program_id: str, request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user:
        return redirect_login(f"/programmes/{program_id}")
    program = db.get(Program, program_id)
    if not program or program.status != "active":
        return HTMLResponse("Programme not found", status_code=404)
    rules = load_rules(db, program)
    source = db.query(Source).filter(Source.program_id == program_id).order_by(Source.id).first()
    excerpt = ""
    if source and source.status == "ok" and source.last_text:
        excerpt = source.last_text[:700]
    quota = rules.get("quota_quote") or ""
    if not (source and quota and quota in (source.last_text or "")):
        quota = ""
    evaluation = None
    match = "unchecked"
    if user.role == "citizen":
        evaluation = rule_engine.evaluate(rules, profile_attrs(own_profile(db, user)))
        match = checked_match(rules, source, evaluation)
    return render(
        request,
        "programme.html",
        db,
        program=program,
        rules=rules,
        source=source,
        excerpt=excerpt,
        quota=quota,
        match=match,
    )


@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request, db: Session = Depends(get_db)):
    if current_user(request, db):
        return RedirectResponse("/", status_code=303)
    return render(
        request,
        "login.html",
        db,
        error=None,
        signup_error=None,
        deleted=bool(request.query_params.get("deleted")),
        next_path=request.query_params.get("next") or "/",
    )


@app.post("/login")
def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    next_path: str = Form("/"),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == email.strip().lower()).first()
    if not user or not verify_password(password, user.password_hash):
        return render(
            request,
            "login.html",
            db,
            status_code=401,
            error="That email or password is wrong.",
            signup_error=None,
            deleted=False,
            next_path=next_path or "/",
            login_email=email.strip(),
        )
    request.session["user_id"] = user.id
    log_event(db, stage="login", detail=f"{user.email} signed in", case_id=str(user.id))
    return RedirectResponse(safe_next(next_path), status_code=303)


@app.post("/signup")
def signup(
    request: Request,
    display_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    name = display_name.strip()
    address = email.strip().lower()
    error = None
    if len(name) < 2:
        error = "Enter your name."
    elif "@" not in address or len(address) < 5:
        error = "Enter a real email address."
    elif len(password) < 8:
        error = "Use at least 8 characters for the password."
    elif db.query(User).filter(User.email == address).first():
        error = "That email is already in use. Sign in instead."
    if error:
        return render(
            request,
            "login.html",
            db,
            status_code=400,
            error=None,
            signup_error=error,
            deleted=False,
            next_path="/",
            signup_name=name,
            signup_email=address,
        )
    user = User(
        email=address,
        display_name=name,
        role="citizen",
        password_hash=hash_password(password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    request.session["user_id"] = user.id
    log_event(db, stage="signup", detail=f"{user.email} signed up", case_id=str(user.id))
    return RedirectResponse("/profile", status_code=303)


@app.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


def profile_completeness(attrs: dict[str, Any], has_profile: bool) -> int:
    score = 0
    if attrs.get("age") is not None:
        score += 25
    if attrs.get("education_level"):
        score += 25
    for key in ("disability", "low_income", "unemployed", "needs_language_support"):
        if key in attrs and attrs[key] is not None:
            score += 10
    if has_profile:
        score += 10
    return min(100, score)


@app.get("/profile", response_class=HTMLResponse)
def profile_form(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user:
        return redirect_login("/profile")
    if user.role != "citizen":
        return deny(request, db)
    profile = own_profile(db, user)
    attrs = profile_attrs(profile)
    has_profile = profile is not None
    return render(
        request,
        "profile.html",
        db,
        attrs=attrs,
        has_profile=has_profile,
        consent_notifications=bool(profile.consent_notifications) if profile else False,
        completeness=profile_completeness(attrs, has_profile),
    )


@app.get("/profiles/{user_id}", response_class=HTMLResponse)
def profile_by_id(user_id: int, request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user:
        return redirect_login(f"/profiles/{user_id}")
    owner = db.get(User, user_id)
    if owner is None:
        return HTMLResponse("Not found", status_code=404)
    if user.id != owner.id or user.role != "citizen":
        return deny(request, db)
    return RedirectResponse("/profile", status_code=303)


@app.post("/profile")
def profile_save(
    request: Request,
    age: str = Form(...),
    education_level: str = Form(...),
    disability: str = Form(""),
    low_income: str = Form(""),
    unemployed: str = Form(""),
    needs_language_support: str = Form(""),
    consent_notifications: str | None = Form(None),
    db: Session = Depends(get_db),
):
    user = current_user(request, db)
    if not user:
        return redirect_login("/profile")
    if user.role != "citizen":
        return deny(request, db)
    existing = own_profile(db, user)
    has_profile = existing is not None
    consent_on = consent_notifications == "1"
    draft_attrs: dict[str, Any] = {}
    if age.isdigit():
        draft_attrs["age"] = int(age)
    elif age.strip():
        # Keep a typed invalid age visible after validation fails.
        draft_attrs["age"] = age.strip()
    if education_level in {"primary", "secondary", "tertiary"}:
        draft_attrs["education_level"] = education_level
    for key, raw in (
        ("disability", disability),
        ("low_income", low_income),
        ("unemployed", unemployed),
        ("needs_language_support", needs_language_support),
    ):
        value = _optional_bool(raw)
        if value is not None:
            draft_attrs[key] = value
    if not age.isdigit() or not (0 <= int(age) <= 120):
        return render(
            request,
            "profile.html",
            db,
            status_code=400,
            attrs=draft_attrs,
            has_profile=has_profile,
            consent_notifications=consent_on,
            completeness=profile_completeness(draft_attrs, has_profile),
            error="Enter an age between 0 and 120.",
        )
    if education_level not in {"primary", "secondary", "tertiary"}:
        return render(
            request,
            "profile.html",
            db,
            status_code=400,
            attrs=draft_attrs,
            has_profile=has_profile,
            consent_notifications=consent_on,
            completeness=profile_completeness(draft_attrs, has_profile),
            error="Choose an education level.",
        )
    attrs = draft_attrs
    profile = existing
    if profile is None:
        profile = Profile(user_id=user.id, attributes_json=json.dumps(attrs))
        db.add(profile)
    else:
        profile.attributes_json = json.dumps(attrs)
    profile.consent_notifications = consent_on
    profile.consent_email = user.email if profile.consent_notifications else ""
    db.commit()
    return RedirectResponse("/", status_code=303)


@app.get("/wizard", response_class=HTMLResponse)
def wizard(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user:
        return redirect_login("/wizard")
    if user.role != "citizen":
        return deny(request, db)
    return RedirectResponse("/profile", status_code=303)


@app.get("/results", response_class=HTMLResponse)
def results(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user:
        return redirect_login("/results")
    return RedirectResponse("/", status_code=303)


@app.get("/timeline", response_class=HTMLResponse)
def timeline(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user:
        return redirect_login("/timeline")
    if not is_admin(user):
        return deny(request, db)
    events = db.query(Event).order_by(Event.at.desc()).limit(100).all()
    return render(request, "timeline.html", db, events=events)


@app.get("/privacy", response_class=HTMLResponse)
def privacy(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user:
        return redirect_login("/privacy")
    if user.role != "citizen":
        return deny(request, db)
    profile = own_profile(db, user)
    apps = db.query(Application).filter(Application.user_id == user.id).all()
    titles = {p.id: p.title for p in db.query(Program).all()}
    return render(
        request,
        "privacy.html",
        db,
        attrs=profile_attrs(profile),
        applications=apps,
        titles=titles,
    )


@app.post("/privacy/delete")
def privacy_delete(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if user.role != "citizen":
        return deny(request, db)
    case_id = str(user.id)
    db.query(Application).filter(Application.user_id == user.id).delete()
    db.query(Notification).filter(Notification.user_id == user.id).delete()
    profile = own_profile(db, user)
    if profile:
        db.delete(profile)
    log_event(
        db,
        stage="privacy_delete",
        detail="User deleted stored profile and applications",
        case_id=case_id,
        human_decision=True,
    )
    db.commit()
    request.session.clear()
    return RedirectResponse("/login?deleted=1", status_code=303)


@app.get("/curator", response_class=HTMLResponse)
def curator_home(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user:
        return redirect_login("/curator")
    if not is_staff(user):
        return deny(request, db)
    active = db.query(Program).filter(Program.status == "active").all()
    active_ids = {p.id for p in active}
    jobs = (
        db.query(IngestionJob)
        .filter(
            IngestionJob.status == "pending_review",
            IngestionJob.program_id.in_(active_ids),
        )
        .order_by(IngestionJob.created_at.desc())
        .all()
    )
    return render(
        request,
        "curator.html",
        db,
        jobs=jobs,
        sources=db.query(Source).filter(Source.program_id.in_(active_ids)).order_by(Source.label).all(),
        titles={p.id: p.title for p in active},
        send_enabled=is_send_enabled(),
    )


@app.post("/curator/check-now")
def curator_check_now(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user:
        return redirect_login("/curator")
    if not is_staff(user):
        return deny(request, db)
    result = pulse.check_sources(db, auto_ingest=True)
    changed = [s for s in result.get("sources", []) if s.get("changed")]
    if changed and changed[0].get("ingestion_job_id"):
        return RedirectResponse(f"/curator/jobs/{changed[0]['ingestion_job_id']}", status_code=303)
    return RedirectResponse("/curator?checked=1", status_code=303)


@app.post("/curator/sources/{source_id}")
def update_source(
    source_id: int,
    request: Request,
    url: str = Form(...),
    label: str = Form(""),
    db: Session = Depends(get_db),
):
    user = current_user(request, db)
    if not user:
        return redirect_login("/curator")
    if not is_admin(user):
        return deny(request, db)
    source = db.get(Source, source_id)
    cleaned = url.strip()
    if source and cleaned.startswith("https://"):
        source.url = cleaned
        if label.strip():
            source.label = label.strip()
        source.status = "not_checked"
        source.last_hash = ""
        source.last_text = ""
        log_event(
            db,
            stage="source_updated",
            detail=f"{user.email} set source {source.id} to {cleaned}",
            case_id=source.program_id,
            human_decision=True,
        )
        db.commit()
    return RedirectResponse("/curator", status_code=303)


@app.post("/curator/kill-switch")
def curator_kill_switch(
    request: Request,
    enabled: str = Form("1"),
    db: Session = Depends(get_db),
):
    user = current_user(request, db)
    if not user:
        return redirect_login("/curator")
    if not is_admin(user):
        return deny(request, db)
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
    if not user:
        return redirect_login(f"/curator/jobs/{job_id}")
    if not is_staff(user):
        return deny(request, db)
    job = db.get(IngestionJob, job_id)
    if not job:
        return HTMLResponse("Job not found", status_code=404)
    program = db.get(Program, job.program_id)
    return render(
        request,
        "curator_job.html",
        db,
        job=job,
        program=program,
        draft=json.loads(job.draft_json),
        quote_check=json.loads(job.quote_check_json),
        diff=json.loads(job.diff_json),
    )


@app.post("/curator/jobs/{job_id}/approve")
def approve_job(job_id: int, request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user:
        return redirect_login(f"/curator/jobs/{job_id}")
    if not is_staff(user):
        return deny(request, db)
    result = pulse.approve_and_fan_out(db, job_id, reviewed_by=user.email)
    if not result.get("ok"):
        if result.get("error") == "quote_gate_failed":
            return RedirectResponse(f"/curator/jobs/{job_id}?error=quote", status_code=303)
        return RedirectResponse("/curator", status_code=303)
    return RedirectResponse("/navigator", status_code=303)


@app.post("/curator/jobs/{job_id}/reject")
def reject_job(job_id: int, request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user:
        return redirect_login(f"/curator/jobs/{job_id}")
    if not is_staff(user):
        return deny(request, db)
    job = db.get(IngestionJob, job_id)
    if job and job.status == "pending_review":
        job.status = "rejected"
        job.reviewed_by = user.email
        log_event(
            db,
            stage="rule_rejected",
            detail=f"{user.email} rejected draft {job.id}",
            case_id=job.program_id,
            human_decision=True,
        )
        db.commit()
    return RedirectResponse("/curator", status_code=303)


@app.get("/navigator", response_class=HTMLResponse)
def navigator_queue(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user:
        return redirect_login("/navigator")
    if not is_staff(user):
        return deny(request, db)
    items = (
        db.query(Notification)
        .filter(Notification.status.in_(["pending_review", "held"]))
        .order_by(Notification.created_at.desc())
        .all()
    )
    titles = {p.id: p.title for p in db.query(Program).all()}
    parsed = []
    for item in items:
        detail = json.loads(item.detail_json or "{}")
        parsed.append(
            {
                "row": item,
                "detail": {
                    "display_name": detail.get("display_name") or "A person",
                    "before": detail.get("before"),
                    "after": detail.get("after"),
                    "meaning": detail.get("meaning") or "",
                    "quote": detail.get("quote") or "",
                },
            }
        )
    return render(request, "navigator.html", db, items=parsed, titles=titles)


@app.post("/navigator/{notification_id}/release")
def navigator_release(
    notification_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user = current_user(request, db)
    if not user:
        return redirect_login("/navigator")
    if not is_staff(user):
        return deny(request, db)
    item = db.get(Notification, notification_id)
    if item and item.status in {"pending_review", "held"}:
        item.status = "approved"
        item.reviewed_by = user.email
        detail = json.loads(item.detail_json or "{}")
        detail["released_by"] = user.email
        item.detail_json = json.dumps(detail)
        log_event(
            db,
            stage="navigator_release",
            detail=f"{user.email} released notification {item.id}",
            case_id=str(item.user_id),
            human_decision=True,
        )
        db.commit()
    return RedirectResponse("/navigator", status_code=303)


@app.post("/navigator/{notification_id}/hold")
def navigator_hold(
    notification_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user = current_user(request, db)
    if not user:
        return redirect_login("/navigator")
    if not is_staff(user):
        return deny(request, db)
    item = db.get(Notification, notification_id)
    if item and item.status == "pending_review":
        item.status = "held"
        item.reviewed_by = user.email
        log_event(
            db,
            stage="navigator_hold",
            detail=f"{user.email} held notification {item.id}",
            case_id=str(item.user_id),
            human_decision=True,
        )
        db.commit()
    return RedirectResponse("/navigator", status_code=303)


@app.get("/apply/{program_id}", response_class=HTMLResponse)
def apply_form(program_id: str, request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user:
        return redirect_login(f"/apply/{program_id}")
    if user.role != "citizen":
        return deny(request, db)
    program = db.get(Program, program_id)
    if not program or program.status != "active":
        return HTMLResponse("Programme not found", status_code=404)
    rules = load_rules(db, program)
    profile = own_profile(db, user)
    if profile is None:
        return RedirectResponse("/profile", status_code=303)
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
        return redirect_login(f"/apply/{program_id}")
    if user.role != "citizen":
        return deny(request, db)
    program = db.get(Program, program_id)
    if not program or program.status != "active":
        return HTMLResponse("Programme not found", status_code=404)
    rules = load_rules(db, program)
    destination = rules.get("official_url") or rules.get("apply_email") or ""
    payload = {
        "program_id": program_id,
        "to": destination,
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
        if existing.user_id != user.id:
            return deny(request, db)
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


def _own_application(request: Request, db: Session, application_id: str):
    user = current_user(request, db)
    if not user:
        return None, redirect_login(f"/applications/{application_id}")
    application = db.get(Application, application_id)
    if not application:
        return None, HTMLResponse("Not found", status_code=404)
    if application.user_id != user.id or user.role != "citizen":
        return None, deny(request, db)
    return application, None


@app.get("/applications/{application_id}", response_class=HTMLResponse)
def application_detail(
    application_id: str, request: Request, db: Session = Depends(get_db)
):
    application, blocked = _own_application(request, db, application_id)
    if blocked:
        return blocked
    payload = json.loads(application.payload_json)
    program = db.get(Program, application.program_id)
    pack_name = None
    pack_path = Path("data/manual_packs") / f"{application.id}.zip"
    if pack_path.exists():
        pack_name = pack_path.name
    smtp_ready = bool(settings.mail_host and settings.mail_user)
    return render(
        request,
        "application.html",
        db,
        application=application,
        program=program,
        payload=payload,
        pack_name=pack_name,
        send_enabled=is_send_enabled(),
        smtp_ready=smtp_ready,
    )


@app.post("/applications/{application_id}/approve")
def application_approve(
    application_id: str, request: Request, db: Session = Depends(get_db)
):
    application, blocked = _own_application(request, db, application_id)
    if blocked:
        return blocked
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
    application, blocked = _own_application(request, db, application_id)
    if blocked:
        return blocked
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
            detail=f"Sending is off — manual pack {pack.name}",
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

    application, blocked = _own_application(request, db, application_id)
    if blocked:
        return blocked
    path = Path("data/manual_packs") / f"{application_id}.zip"
    if not path.exists():
        return HTMLResponse("No manual pack for this application", status_code=404)
    return FileResponse(path, filename=path.name, media_type="application/zip")


def _alert_rows(db: Session, user: User) -> list[dict[str, Any]]:
    items = (
        db.query(Notification)
        .filter(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc())
        .all()
    )
    titles = {p.id: p.title for p in db.query(Program).all()}
    parsed = []
    for item in items:
        if not alert_visible(item):
            continue
        detail = json.loads(item.detail_json or "{}")
        parsed.append({"row": item, "detail": detail, "title": titles.get(item.program_id, "A programme")})
    return parsed


@app.get("/alerts", response_class=HTMLResponse)
@app.get("/notifications", response_class=HTMLResponse)
def my_alerts(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user:
        return redirect_login("/alerts")
    if user.role != "citizen":
        return deny(request, db)
    items = _alert_rows(db, user)
    gained = [item for item in items if item["row"].kind == "newly_eligible"]
    lost = [item for item in items if item["row"].kind == "newly_not_eligible"]
    deadlines = [item for item in items if item["row"].kind == "deadline_reminder"]

    def unread_count(rows: list) -> int:
        return sum(1 for item in rows if item["row"].read_at is None)

    return render(
        request,
        "notifications.html",
        db,
        gained=gained,
        lost=lost,
        deadlines=deadlines,
        gained_unread=unread_count(gained),
        lost_unread=unread_count(lost),
        deadline_unread=unread_count(deadlines),
    )


@app.get("/alerts/{notification_id}", response_class=HTMLResponse)
def alert_detail(notification_id: int, request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user:
        return redirect_login(f"/alerts/{notification_id}")
    item = db.get(Notification, notification_id)
    if not item:
        return HTMLResponse("Not found", status_code=404)
    if item.user_id != user.id or user.role != "citizen" or not alert_visible(item):
        return deny(request, db)
    if item.read_at is None:
        item.read_at = __import__("datetime").datetime.utcnow()
        db.commit()
    program = db.get(Program, item.program_id)
    return render(
        request,
        "alert.html",
        db,
        item=item,
        detail=json.loads(item.detail_json or "{}"),
        program=program,
    )
