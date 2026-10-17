from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app import db as dbmod
from app.api_internal import router as internal_router
from app.auth import admin_user, check_admin, locked_out, mount_session, new_citizen
from app.config import get_settings
from app.db import get_db
from app.engine.approval_gate import ApplicationState, ApprovalGate
from app.models import Application, Event, IngestionJob, Notification, Profile, Program, Source, User
from app.seed import seed_catalogue
from app.services import matching, plain, pulse
from app.services.drafting import COUNTRY_NAMES, title_key
from app.services.scheduler import start_scheduler, stop_scheduler
from app.services.timeline import log_event

settings = get_settings()
app = FastAPI(title="Entitle", version="1.0.0")
mount_session(app)
app.include_router(internal_router)

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def source_icon_url(source_url: str) -> str:
    """Return the favicon path on a validated official HTTP(S) source."""
    try:
        parsed = urlsplit(source_url or "")
        host = parsed.hostname
        port = parsed.port
    except ValueError:
        return ""
    if parsed.scheme not in {"http", "https"} or not host:
        return ""
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    authority = host + (f":{port}" if port else "")
    return f"{parsed.scheme}://{authority}/favicon.ico"


templates.env.globals.update(
    ago=plain.ago,
    attr_label=plain.attr_label,
    country_name=plain.country_name,
    day=plain.day,
    domain_label=plain.domain_label,
    flag=plain.flag,
    rule_phrase=plain.rule_phrase,
    stage_label=plain.stage_label,
    status_word=plain.status_word,
    value_label=plain.value_label,
    source_icon_url=source_icon_url,
)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
approval_gate = ApprovalGate()


@app.get("/healthz", include_in_schema=False)
def healthz(db: Session = Depends(get_db)):
    """Container/readiness probe: confirm the app can reach its configured database."""
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse(status_code=503, content={"status": "unavailable", "dependency": "database"})
    return {"status": "ok"}


@app.on_event("startup")
def on_startup() -> None:
    if settings.base_url.startswith("https://") and (
        len(settings.secret_key.strip()) < 32
        or settings.secret_key.lower().startswith(("change-me", "dev-only"))
    ):
        raise RuntimeError("Set SECRET_KEY to a unique random value of at least 32 characters before deploying over HTTPS.")
    Path("data").mkdir(exist_ok=True)
    dbmod.init_db()
    session = dbmod.SessionLocal()
    try:
        seed_catalogue(session)
    finally:
        session.close()
    start_scheduler()


@app.on_event("shutdown")
def on_shutdown() -> None:
    stop_scheduler()


# ---------- helpers ----------

def _session_user(request: Request, db: Session, key: str, role: str) -> User | None:
    user_id = request.session.get(key)
    user = db.get(User, user_id) if isinstance(user_id, int) else None
    if user is None or user.role != role:
        request.session.pop(key, None)
        return None
    return user


def citizen_of(request: Request, db: Session) -> User | None:
    return _session_user(request, db, "citizen_id", "citizen")


def admin_of(request: Request, db: Session) -> User | None:
    return _session_user(request, db, "admin_id", "reviewer")


def flash(request: Request, text: str, kind: str = "ok") -> None:
    request.session["flash"] = {"text": text, "kind": kind}


def go(path: str) -> RedirectResponse:
    return RedirectResponse(path, status_code=303)


def render(request: Request, name: str, db: Session, status_code: int = 200, **extra: Any):
    context = {
        "request": request,
        "citizen": citizen_of(request, db),
        "admin": admin_of(request, db),
        "admin_ready": settings.admin_ready,
        "admin_error": request.session.pop("admin_error", None),
        "flash": request.session.pop("flash", None),
        **extra,
    }
    return templates.TemplateResponse(request, name, context, status_code=status_code)


def own_profile(db: Session, user: User) -> Profile | None:
    return db.query(Profile).filter(Profile.user_id == user.id).first()


def first_source(db: Session, program_id: str) -> Source | None:
    return db.query(Source).filter(Source.program_id == program_id).order_by(Source.id).first()


def alert_visible(row: Notification) -> bool:
    """Bad news stays hidden from the person until a reviewer releases it."""
    if row.kind == "newly_not_eligible":
        return row.status == "approved"
    return row.status in {"queued", "approved"}


def quote_context(text: str, quote: str, width: int = 140) -> dict[str, str] | None:
    if not quote or quote not in (text or ""):
        return None
    start = text.index(quote)
    before = text[max(0, start - width):start]
    after = text[start + len(quote):start + len(quote) + width]
    return {"before": ("…" if start > width else "") + before, "quote": quote,
            "after": after + ("…" if start + len(quote) + width < len(text) else "")}


def require(request: Request, db: Session, role: str) -> tuple[User | None, RedirectResponse | HTMLResponse | None]:
    if role == "reviewer":
        user = admin_of(request, db)
        if user is None:
            flash(request, "Sign in as an admin to open the Verification Desk.", "warn")
            return None, go("/#admin")
        return user, None
    user = citizen_of(request, db)
    if user is None:
        flash(request, "Answer the questions first so Entitle knows who you are.", "warn")
        return None, go("/profile#questions")
    return user, None


# ---------- public ----------

@app.get("/health")
def health():
    return {"status": "ok", "service": "entitle"}


@app.get("/", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db)):
    return citizen_page(request, db, citizen_of(request, db), view="profile")


@app.get("/profile", response_class=HTMLResponse)
def profile_page(request: Request, db: Session = Depends(get_db)):
    return citizen_page(request, db, citizen_of(request, db), view="profile")


@app.get("/jobs", response_class=HTMLResponse)
def jobs_page(request: Request, db: Session = Depends(get_db)):
    user = citizen_of(request, db)
    if not user or not pulse.profile_attrs(own_profile(db, user)):
        flash(request, "Set up your profile to see your feed.", "warn")
        return go("/profile#questions")
    return citizen_page(request, db, user, view="jobs")


def _client_key(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    return forwarded.split(",")[0].strip() or (request.client.host if request.client else "unknown")


@app.post("/admin/login")
def admin_login(request: Request, username: str = Form(""), password: str = Form(""),
                db: Session = Depends(get_db)):
    if not settings.admin_ready:
        request.session["admin_error"] = "Admin sign-in is not set up on this server. Add ADMIN_PASSWORD to the environment."
        return go("/#admin")
    key = _client_key(request)
    if locked_out(key):
        request.session["admin_error"] = "Too many wrong attempts. Wait a minute, then try again."
        return go("/#admin")
    if not check_admin(username, password, key):
        request.session["admin_error"] = "That username and password do not match."
        return go("/#admin")
    user = admin_user(db)
    request.session["admin_id"] = user.id
    log_event(db, stage="sign_in", detail=f"{user.display_name} opened the Verification Desk", case_id=str(user.id),
              actor="human")
    return go("/desk")


@app.post("/admin/logout")
def admin_logout(request: Request):
    request.session.pop("admin_id", None)
    flash(request, "Signed out of the Verification Desk.")
    return go("/")


# ---------- citizen view ----------

YES_NO = [("yes", "Yes"), ("no", "No"), ("", "Skip")]
QUESTIONS: list[dict[str, Any]] = [
    {"key": "age", "kind": "number", "ask": "How old are you?",
     "why": "Many programmes have an age range."},
    {"key": "country", "kind": "select", "ask": "Which country do you live in?",
     "why": "Programmes only cover people who live in their country."},
    {"key": "education_level", "kind": "choice", "ask": "What level of education are you in, or did you finish?",
     "why": "Scholarships and grants are set for one level.",
     "options": [("primary", "Primary school"), ("secondary", "Secondary school"),
                 ("tertiary", "University or college"), ("", "Skip")]},
    {"key": "student", "kind": "choice", "ask": "Are you studying right now?",
     "why": "Student grants need current enrolment.", "options": YES_NO},
    {"key": "low_income", "kind": "choice", "ask": "Is your household income low for where you live?",
     "why": "Need-based support checks household income.", "options": YES_NO},
    {"key": "unemployed", "kind": "choice", "ask": "Are you out of work and looking for a job?",
     "why": "Jobseeker support needs this.", "options": YES_NO},
    {"key": "disability", "kind": "choice", "ask": "Do you have a disability or long-term health condition?",
     "why": "Some support is only for disabled people or their carers.", "options": YES_NO},
]


def _choice_value(attrs: dict[str, Any], key: str) -> str:
    value = attrs.get(key)
    if value is True:
        return "yes"
    if value is False:
        return "no"
    return "" if value is None else str(value)


def citizen_page(request: Request, db: Session, user: User | None, view: str = "profile"):
    profile = own_profile(db, user) if user else None
    attrs = pulse.profile_attrs(profile)
    groups: dict[str, list[dict[str, Any]]] = {k: [] for k in ("eligible", "likely", "not_eligible", "elsewhere", "unchecked")}
    usage: dict[str, int] = {}
    programs = db.query(Program).filter(Program.status == "active").order_by(Program.title).all()
    for program in programs:
        rules = pulse.load_rules(db, program)
        if not rules.get("conditions"):
            continue
        for attr in {c.get("attr") for c in rules["conditions"]}:
            usage[attr] = usage.get(attr, 0) + 1
        result = matching.match(program.country, rules, attrs) if attrs else matching.Match(status="unchecked")
        groups.setdefault(result.status, []).append({
            "program": program,
            "rules": rules,
            "match": result,
            "version": pulse.live_version(db, program),
        })

    app_rows: list[dict[str, Any]] = []
    applied: dict[str, Application] = {}
    alerts: list[dict[str, Any]] = []
    if user:
        titles = {p.id: p for p in programs}
        applications = (
            db.query(Application).filter(Application.user_id == user.id).order_by(Application.created_at.desc()).all()
        )
        app_rows = [
            {"row": a, "payload": json.loads(a.payload_json or "{}"), "program": titles.get(a.program_id)}
            for a in applications
        ]
        applied = {a.program_id: a for a in applications}
        alerts = [
            {"row": n, "detail": json.loads(n.detail_json or "{}"), "program": titles.get(n.program_id)}
            for n in db.query(Notification).filter(Notification.user_id == user.id)
            .order_by(Notification.created_at.desc()).all()
            if alert_visible(n)
        ]

    questions = []
    for q in QUESTIONS:
        questions.append({**q, "used_by": usage.get(q["key"], 0), "value": _choice_value(attrs, q["key"])})
    return render(
        request, "job_feed.html" if view == "jobs" else "citizen.html", db,
        view=view,
        profile=profile,
        attrs=attrs,
        rows=plain.profile_rows(attrs),
        groups=groups,
        applications=app_rows,
        applied=applied,
        alerts=alerts,
        unread=sum(1 for a in alerts if a["row"].read_at is None),
        questions=questions,
        programme_count=len(programs),
        country_count=len({p.country for p in programs if p.country}),
        countries=sorted(COUNTRY_NAMES, key=plain.country_name),
        email_ready=settings.email_ready,
    )


def save_attrs(db: Session, user: User, attrs: dict[str, Any]) -> Profile:
    profile = own_profile(db, user)
    if profile is None:
        profile = Profile(user_id=user.id, consent_notifications=True)
        db.add(profile)
    profile.attributes_json = json.dumps(attrs)
    profile.updated_at = datetime.utcnow()
    db.commit()
    return profile


def _tri(raw: str) -> bool | None:
    return {"yes": True, "no": False}.get(raw)


@app.post("/me/details")
def me_details(
    request: Request,
    name: str = Form(""),
    age: str = Form(""),
    education_level: str = Form(""),
    country: str = Form(""),
    low_income: str = Form(""),
    student: str = Form(""),
    unemployed: str = Form(""),
    disability: str = Form(""),
    consent: str = Form(""),
    notification_email: str = Form(""),
    db: Session = Depends(get_db),
):
    user = citizen_of(request, db)
    target = "/profile#answers" if user else "/profile#questions"
    name = re.sub(r"\s+", " ", name).strip()
    if user is None and not name:
        flash(request, "Tell us your first name so your packets carry it.", "error")
        return go(target)
    attrs: dict[str, Any] = {}
    if age.strip():
        if not age.strip().isdigit() or not 5 <= int(age) <= 120:
            flash(request, "Age must be a number between 5 and 120.", "error")
            return go(target)
        attrs["age"] = int(age)
    if education_level in plain.EDUCATION:
        attrs["education_level"] = education_level
    if country in COUNTRY_NAMES:
        attrs["country"] = country
    for key, raw in (("low_income", low_income), ("student", student),
                     ("unemployed", unemployed), ("disability", disability)):
        value = _tri(raw)
        if value is not None:
            attrs[key] = value
    if not attrs:
        flash(request, "Answer at least one question so Entitle can check the rules for you.", "warn")
        return go(target)
    notification_email = notification_email.strip().lower()
    if consent == "1" and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", notification_email):
        flash(request, "Enter a valid email address to receive Entitle updates, or choose No.", "error")
        return go(target)
    first_time = user is None
    if user is None:
        user = new_citizen(db, name)
        request.session["citizen_id"] = user.id
    elif name:
        user.display_name = name[:120]
    profile = save_attrs(db, user, attrs)
    profile.consent_notifications = consent == "1"
    profile.notification_email = notification_email if consent == "1" else ""
    db.commit()
    log_event(db, stage="profile_saved", detail=f"{len(attrs)} answers saved", case_id=str(user.id))
    flash(request, "Your answers are saved. Here is what you may be owed." if first_time
          else "Your answers are updated and your matches re-checked.")
    return go("/jobs")


@app.post("/me/apply/{program_id}")
def me_apply(program_id: str, request: Request, db: Session = Depends(get_db)):
    user, blocked = require(request, db, "citizen")
    if blocked:
        return blocked
    program = db.get(Program, program_id)
    if not program or program.status != "active":
        flash(request, "That programme is no longer listed.", "error")
        return go("/jobs")
    attrs = pulse.profile_attrs(own_profile(db, user))
    rules = pulse.load_rules(db, program)
    if matching.match(program.country, rules, attrs).status != "eligible":
        flash(request, "You can only prepare a packet for a programme you qualify for.", "warn")
        return go("/jobs")
    key = f"{user.id}:{program.id}"
    if db.query(Application).filter(Application.idempotency_key == key).first() is None:
        payload = {
            "program_id": program.id,
            "programme": program.title,
            "official_url": program.official_url,
            "fields": {
                "full_name": user.display_name,
                **{plain.attr_label(k): plain.value_label(k, v) for k, v in attrs.items()},
            },
            "documents": rules.get("required_docs") or [],
            "rules_version": rules.get("version"),
        }
        db.add(Application(id=f"app-{user.id}-{program.id}"[:64], user_id=user.id, program_id=program.id,
                           state=ApplicationState.READY.value, payload_json=json.dumps(payload),
                           idempotency_key=key))
        db.commit()
    flash(request, f"Your packet for {program.title} is ready. Check it, then approve it.")
    return go("/profile#packets")


def _own_application(request: Request, db: Session, application_id: str):
    user, blocked = require(request, db, "citizen")
    if blocked:
        return None, None, blocked
    application = db.get(Application, application_id)
    if not application or application.user_id != user.id:
        return None, None, render(request, "forbidden.html", db, status_code=403)
    return user, application, None


@app.post("/me/applications/{application_id}/approve")
def me_approve(application_id: str, request: Request, db: Session = Depends(get_db)):
    user, application, blocked = _own_application(request, db, application_id)
    if blocked:
        return blocked
    if application.state == ApplicationState.READY.value:
        state, digest = approval_gate.approve(application.state, json.loads(application.payload_json))
        application.state = state
        application.approval_hash = digest
        application.updated_at = datetime.utcnow()
        db.commit()
        log_event(db, stage="packet_approved", detail=f"{user.display_name} approved their packet",
                  case_id=application.id, human_decision=True)
        flash(request, "Approved. Open the official page to submit it in your own name.")
    return go("/profile#packets")


@app.post("/me/applications/{application_id}/withdraw")
def me_withdraw(application_id: str, request: Request, db: Session = Depends(get_db)):
    user, application, blocked = _own_application(request, db, application_id)
    if blocked:
        return blocked
    db.delete(application)
    db.commit()
    flash(request, "Packet removed.", "delete")
    return go("/profile#packets")


@app.post("/me/alerts/read")
def me_alerts_read(request: Request, db: Session = Depends(get_db)):
    user, blocked = require(request, db, "citizen")
    if blocked:
        return blocked
    now = datetime.utcnow()
    for row in db.query(Notification).filter(Notification.user_id == user.id, Notification.read_at.is_(None)):
        if alert_visible(row):
            row.read_at = now
    db.commit()
    return go("/profile#alerts")


@app.post("/me/delete")
def me_delete(request: Request, db: Session = Depends(get_db)):
    user, blocked = require(request, db, "citizen")
    if blocked:
        return blocked
    db.query(Notification).filter(Notification.user_id == user.id).delete()
    db.query(Application).filter(Application.user_id == user.id).delete()
    db.query(Profile).filter(Profile.user_id == user.id).delete()
    log_event(db, stage="data_deleted", detail="A person deleted their answers and data", case_id=str(user.id),
              human_decision=True, commit=False)
    db.delete(user)
    db.commit()
    request.session.pop("citizen_id", None)
    flash(request, "Your Entitle data was deleted.", "delete")
    return go("/")


# ---------- verification desk ----------

def job_view(db: Session, job: IngestionJob) -> dict[str, Any]:
    draft = json.loads(job.draft_json or "{}")
    check = json.loads(job.quote_check_json or "{}")
    ok_by_id = {item["id"]: item["ok"] for item in check.get("items") or []}
    rules = []
    for condition in draft.get("conditions") or []:
        rules.append({
            "c": condition,
            "ok": ok_by_id.get(condition.get("id"), False),
            "context": quote_context(job.notice_text, condition.get("source_quote") or ""),
        })
    program = db.get(Program, job.program_id) if job.program_id else None
    impact = json.loads(job.impact_json or "{}")
    if job.status == "pending_review":
        live = pulse.load_rules(db, program) if program else {}
        verified = {**draft, "conditions": [r["c"] for r in rules if r["ok"]]}
        impact = pulse.impact_preview(db, draft.get("country") or (program.country if program else ""), live, verified)
    lookalike = None
    if job.kind == "new" and job.status == "pending_review":
        key = title_key(draft.get("title") or "")
        for existing in db.query(Program).filter(Program.status == "active").all():
            other = title_key(existing.title)
            if key and other and (key == other or key in other or other in key):
                lookalike = existing
                break
    return {
        "lookalike": lookalike,
        "job": job,
        "draft": draft,
        "rules": rules,
        "verified": sum(1 for r in rules if r["ok"]),
        "blocked": sum(1 for r in rules if not r["ok"]),
        "method": check.get("method", "ai"),
        "steps": json.loads(job.steps_json or "[]"),
        "program": program,
        "impact": impact,
        "diff": plain.describe_diff_lines(json.loads(job.diff_json or "{}")) if program else [],
    }


@app.get("/desk", response_class=HTMLResponse)
def desk(request: Request, job: int | None = None, db: Session = Depends(get_db)):
    user, blocked = require(request, db, "reviewer")
    if blocked:
        return blocked
    pending = (
        db.query(IngestionJob).filter(IngestionJob.status == "pending_review")
        .order_by(IngestionJob.created_at.desc()).all()
    )
    decided = (
        db.query(IngestionJob).filter(IngestionJob.status.in_(["approved", "rejected"]))
        .order_by(IngestionJob.reviewed_at.desc()).limit(6).all()
    )
    focus = db.get(IngestionJob, job) if job else None
    if focus is None:
        focus = db.query(IngestionJob).filter(IngestionJob.status != "no_change") \
            .order_by(IngestionJob.created_at.desc()).first()

    programs = db.query(Program).filter(Program.status == "active").order_by(Program.title).all()
    held = []
    for n in db.query(Notification).filter(Notification.status.in_(["pending_review", "held"])) \
            .order_by(Notification.created_at.desc()).all():
        held.append({"row": n, "detail": json.loads(n.detail_json or "{}"), "program": db.get(Program, n.program_id)})

    all_jobs = db.query(IngestionJob).all()
    blocked_quotes = sum(len(json.loads(j.quote_check_json or "{}").get("failed_ids") or []) for j in all_jobs)
    sources = (
        db.query(Source).join(Program, Program.id == Source.program_id)
        .filter(Program.status == "active").order_by(Source.label).all()
    )
    return render(
        request, "desk.html", db,
        focus=job_view(db, focus) if focus else None,
        pending=[job_view(db, j) for j in pending],
        decided=[job_view(db, j) for j in decided],
        held=held,
        programs=programs,
        sources=sources,
        program_titles={p.id: p.title for p in programs},
        events=db.query(Event).order_by(Event.at.desc(), Event.id.desc()).limit(40).all(),
        config_minutes=max(5, settings.watcher_interval_seconds // 60),
        stats={
            "live": len(programs),
            "people": db.query(Profile).count(),
            "pending": len(pending),
            "blocked": blocked_quotes,
            "human": db.query(Event).filter(Event.human_decision.is_(True)).count(),
        },
    )


@app.post("/desk/run")
def desk_run(request: Request, url: str = Form(""), notice_text: str = Form(""), program_id: str = Form(""),
             db: Session = Depends(get_db)):
    user, blocked = require(request, db, "reviewer")
    if blocked:
        return blocked
    url = url.strip()
    if notice_text.strip():
        if not program_id or not db.get(Program, program_id):
            flash(request, "Choose which programme the pasted notice belongs to.", "error")
            return go("/desk#run")
        result = pulse.run_pipeline(db, notice_text=notice_text, program_id=program_id, trigger="reviewer")
    else:
        if not re.match(r"^https?://[^\s/]+\.[^\s]+$", url):
            flash(request, "Paste the full address of an official page, starting with https://", "error")
            return go("/desk#run")
        existing = db.query(Program).filter(Program.official_url == url, Program.status == "active").first()
        result = pulse.run_pipeline(db, url=url, program_id=existing.id if existing else "", trigger="reviewer")
    if not result.get("ok"):
        flash(request, f"The pipeline stopped: {result.get('error')}", "error")
        return go("/desk#run")
    return go(f"/desk?job={result['job_id']}#job-{result['job_id']}")


@app.post("/desk/jobs/{job_id}/approve")
async def desk_approve(job_id: int, request: Request, db: Session = Depends(get_db)):
    user, blocked = require(request, db, "reviewer")
    if blocked:
        return blocked
    form = await request.form()
    keep = [str(v) for v in form.getlist("keep")]
    if not keep:
        flash(request, "Tick at least one verified rule to approve.", "warn")
        return go(f"/desk?job={job_id}#job-{job_id}")
    result = pulse.approve(db, job_id, reviewed_by=user.display_name or user.email, keep_ids=keep)
    if not result.get("ok"):
        messages = {
            "quote_gate_failed": "A ticked rule has no verified receipt, so it cannot go live.",
            "no_verified_rules": "Tick at least one verified rule to approve.",
            "job_not_pending": "This draft was already decided.",
        }
        flash(request, messages.get(result.get("error"), "This draft could not be approved."), "error")
        return go(f"/desk?job={job_id}#job-{job_id}")
    flash(request, f"Live. {result['checked']} people re-checked: {result['notified']} told they may qualify, "
                   f"{result['held']} losses held for you below.")
    return go(f"/desk?job={job_id}#job-{job_id}")


@app.post("/desk/jobs/{job_id}/reject")
def desk_reject(job_id: int, request: Request, db: Session = Depends(get_db)):
    user, blocked = require(request, db, "reviewer")
    if blocked:
        return blocked
    if pulse.reject(db, job_id, reviewed_by=user.display_name or user.email):
        flash(request, "Draft rejected. Nothing changed for anyone.")
    return go(f"/desk?job={job_id}#job-{job_id}")


@app.post("/desk/news/{notification_id}/{action}")
def desk_news(notification_id: int, action: str, request: Request, db: Session = Depends(get_db)):
    user, blocked = require(request, db, "reviewer")
    if blocked:
        return blocked
    item = db.get(Notification, notification_id)
    if item and item.status in {"pending_review", "held"} and action in {"release", "hold"}:
        detail = json.loads(item.detail_json or "{}")
        who = user.display_name or user.email
        if action == "release":
            item.status = "approved"
            detail["released_by"] = who
            item.detail_json = json.dumps(detail)
            flash(request, f"Released to {detail.get('display_name', 'the person')} with the quote and a next step.")
        else:
            item.status = "held"
            flash(request, "Kept on hold. The person sees nothing yet.")
        item.reviewed_by = who
        db.commit()
        if action == "release":
            from app.services.email_updates import send_notification_email

            send_notification_email(db, item)
        log_event(db, stage="news_released" if action == "release" else "news_held",
                  detail=f"{who}: {detail.get('display_name')} - {detail.get('meaning', '')}",
                  case_id=str(item.user_id), human_decision=True)
    return go("/desk#news")


@app.post("/desk/check-now")
def desk_check_now(request: Request, db: Session = Depends(get_db)):
    user, blocked = require(request, db, "reviewer")
    if blocked:
        return blocked
    result = pulse.check_sources(db, auto_ingest=True, trigger="reviewer")
    rows = result.get("sources") or []
    changed = [r for r in rows if r.get("changed")]
    unreachable = sum(1 for r in rows if r.get("status") == "unreachable")
    if result.get("skipped"):
        flash(request, "Page fetching is switched off on this server.", "warn")
    elif changed:
        flash(request, f"{len(rows)} pages read. {len(changed)} rule change found and drafted for you.")
        return go(f"/desk?job={changed[0]['ingestion_job_id']}#job-{changed[0]['ingestion_job_id']}")
    else:
        flash(request, f"{len(rows)} pages read. No rule changes. {unreachable} could not be reached.")
    return go("/desk#pages")
