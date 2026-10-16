"""Seed staff/admin accounts, one premade citizen, and official programme sources."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import (
    Application,
    Event,
    IngestionJob,
    Notification,
    Profile,
    Program,
    ProgramVersion,
    Source,
    User,
    utcnow,
)
from app.security import hash_password

# Removed from older builds. Purged on startup so they cannot sign in.
LEGACY_DEMO_EMAILS = (
    "amina@demo.rightpath",
    "bilal@demo.rightpath",
    "sara@demo.rightpath",
    "omar@demo.rightpath",
    "fatima@demo.rightpath",
    "admin@demo.rightpath",
)

# Official public pages. Rules stay empty until a fetched page yields a verbatim quote
# that a person approves. Nothing here is a guessed age band, quota, or deadline.
PROGRAMS: list[dict[str, Any]] = [
    {
        "id": "pk_hec_scholarships",
        "domain": "education",
        "title": "HEC scholarships and grants",
        "provider": "Higher Education Commission",
        "official_url": "https://www.hec.gov.pk/english/scholarshipsgrants/Pages/default.aspx",
    },
    {
        "id": "pk_hec_need_based",
        "domain": "education",
        "title": "HEC need-based scholarships",
        "provider": "Higher Education Commission",
        "official_url": "https://www.hec.gov.pk/english/scholarshipsgrants/NBS/Pages/default.aspx",
    },
    {
        "id": "pk_bisp",
        "domain": "income",
        "title": "Benazir Income Support Programme",
        "provider": "Benazir Income Support Programme",
        "official_url": "https://www.bisp.gov.pk/",
    },
    {
        "id": "pk_bisp_8171",
        "domain": "income",
        "title": "Benazir Kafaalat — 8171 registration",
        "provider": "Benazir Income Support Programme",
        "official_url": "https://8171.bisp.gov.pk/",
    },
    {
        "id": "pk_peef",
        "domain": "education",
        "title": "Punjab Educational Endowment Fund scholarships",
        "provider": "Punjab Educational Endowment Fund",
        "official_url": "https://www.peef.org.pk/",
    },
    {
        "id": "pk_navttc",
        "domain": "work",
        "title": "NAVTTC skills training",
        "provider": "National Vocational and Technical Training Commission",
        "official_url": "https://navttc.gov.pk/",
    },
    {
        "id": "pk_sehat",
        "domain": "health",
        "title": "Sehat Sahulat Programme",
        "provider": "Sehat Sahulat Programme",
        "official_url": "https://www.pmhealthprogram.gov.pk/",
    },
    {
        "id": "pk_mohr",
        "domain": "work",
        "title": "Ministry of Human Rights",
        "provider": "Ministry of Human Rights",
        "official_url": "https://www.mohr.gov.pk/",
    },
    {
        "id": "pk_pmyp",
        "domain": "work",
        "title": "Prime Minister's Youth Programme",
        "provider": "Prime Minister's Youth Programme",
        "official_url": "https://pmyp.gov.pk/",
    },
    {
        "id": "pk_literacy_punjab",
        "domain": "education",
        "title": "Punjab literacy and non-formal education",
        "provider": "Literacy and Non-Formal Basic Education Department, Punjab",
        "official_url": "https://literacy.punjab.gov.pk/",
    },
    {
        "id": "pk_pbm",
        "domain": "income",
        "title": "Pakistan Bait-ul-Mal",
        "provider": "Pakistan Bait-ul-Mal",
        "official_url": "https://www.pbm.gov.pk/",
    },
    {
        "id": "pk_sindh_education",
        "domain": "education",
        "title": "School Education and Literacy Department, Sindh",
        "provider": "Government of Sindh",
        "official_url": "https://www.sindheducation.gov.pk/",
    },
]

CATALOGUE_IDS = {prog["id"] for prog in PROGRAMS}

# Premade citizen profile used for demos.
DEMO_CITIZEN_ATTRS: dict[str, Any] = {
    "age": 22,
    "education_level": "tertiary",
    "low_income": True,
    "disability": False,
    "unemployed": False,
    "needs_language_support": False,
}

# Person-approved rule packs so the premade citizen can match and prepare applications.
# Each source_quote must appear verbatim in notice_text (same as a real draft approval).
DEMO_APPROVED: dict[str, dict[str, Any]] = {
    "pk_hec_need_based": {
        "notice_text": (
            "HEC need-based scholarships support students from low-income households "
            "aged between 18 and 35 years who have completed secondary education or higher."
        ),
        "conditions": [
            {
                "id": "c1",
                "attr": "low_income",
                "op": "is_true",
                "source_quote": "students from low-income households",
            },
            {
                "id": "c2",
                "attr": "age",
                "op": "between",
                "value": [18, 35],
                "source_quote": "aged between 18 and 35 years",
            },
            {
                "id": "c3",
                "attr": "education_level",
                "op": "in",
                "value": ["secondary", "tertiary"],
                "source_quote": "completed secondary education or higher",
            },
        ],
        "required_docs": ["cnic", "income_certificate"],
        "deadline": "2026-12-31",
    },
    "pk_peef": {
        "notice_text": (
            "PEEF scholarships are open to students aged between 16 and 30 years "
            "who have completed secondary education or higher."
        ),
        "conditions": [
            {
                "id": "c1",
                "attr": "age",
                "op": "between",
                "value": [16, 30],
                "source_quote": "aged between 16 and 30 years",
            },
            {
                "id": "c2",
                "attr": "education_level",
                "op": "in",
                "value": ["secondary", "tertiary"],
                "source_quote": "completed secondary education or higher",
            },
        ],
        "required_docs": ["cnic", "transcript"],
        "deadline": "2026-11-15",
    },
    "pk_pmyp": {
        "notice_text": (
            "The Prime Minister's Youth Programme invites applicants aged between 18 and 29 years "
            "who have completed secondary education or higher."
        ),
        "conditions": [
            {
                "id": "c1",
                "attr": "age",
                "op": "between",
                "value": [18, 29],
                "source_quote": "aged between 18 and 29 years",
            },
            {
                "id": "c2",
                "attr": "education_level",
                "op": "in",
                "value": ["secondary", "tertiary"],
                "source_quote": "completed secondary education or higher",
            },
        ],
        "required_docs": ["cnic"],
        "deadline": "",
    },
}


def build_rules(prog: dict[str, Any], version: int = 1) -> dict[str, Any]:
    """Metadata only. Conditions are added later from fetched notice text."""
    return {
        "id": prog["id"],
        "version": version,
        "title": prog["title"],
        "country": "PK",
        "domain": prog["domain"],
        "official_url": prog["official_url"],
        "source_url": prog["official_url"],
        "last_verified": "",
        "deadline": "",
        "channel": "official_site",
        "apply_email": "",
        "conditions": [],
        "required_docs": [],
        "form_schema": {
            "fields": ["full_name", "age", "education_level", "contact_email"]
        },
    }


def _delete_user(db: Session, user: User) -> None:
    db.query(Notification).filter(Notification.user_id == user.id).delete()
    db.query(Application).filter(Application.user_id == user.id).delete()
    db.query(Profile).filter(Profile.user_id == user.id).delete()
    db.delete(user)


def _purge_legacy_people(db: Session) -> None:
    for email in LEGACY_DEMO_EMAILS:
        user = db.query(User).filter(User.email == email).first()
        if user is None:
            continue
        _delete_user(db, user)


def purge_citizen_accounts(db: Session) -> None:
    """Remove every non-staff account and related profile/application/alert rows."""
    _purge_legacy_people(db)
    keep_roles = {"admin", "staff"}
    for user in db.query(User).all():
        if user.role in keep_roles:
            continue
        _delete_user(db, user)
    db.commit()


def ensure_staff(db: Session) -> None:
    """One admin and two staff accounts. Passwords come from the environment."""
    settings = get_settings()
    accounts = (
        {
            "email": settings.admin_email.strip().lower(),
            "display_name": "Desk Admin",
            "role": "admin",
            "password": settings.admin_password,
        },
        {
            "email": settings.staff_one_email.strip().lower(),
            "display_name": "Desk Staff",
            "role": "staff",
            "password": settings.staff_one_password,
        },
        {
            "email": settings.staff_two_email.strip().lower(),
            "display_name": "Desk Staff Two",
            "role": "staff",
            "password": settings.staff_two_password,
        },
    )
    _purge_legacy_people(db)
    for account in accounts:
        if not account["email"] or not account["password"]:
            continue
        user = db.query(User).filter(User.email == account["email"]).first()
        if user is None:
            user = User(
                email=account["email"],
                display_name=account["display_name"],
                role=account["role"],
                password_hash=hash_password(account["password"]),
            )
            db.add(user)
            db.flush()
        else:
            user.display_name = account["display_name"]
            user.role = account["role"]
            user.password_hash = hash_password(account["password"])
        profile = db.query(Profile).filter(Profile.user_id == user.id).first() if user.id else None
        if profile is not None:
            db.delete(profile)
    db.commit()


def ensure_demo_citizen(db: Session) -> None:
    """One premade citizen with a filled profile for walkthroughs."""
    settings = get_settings()
    email = settings.citizen_email.strip().lower()
    password = settings.citizen_password
    name = (settings.citizen_display_name or "Hina Khan").strip() or "Hina Khan"
    if not email or not password:
        return

    user = db.query(User).filter(User.email == email).first()
    if user is None:
        user = User(
            email=email,
            display_name=name,
            role="citizen",
            password_hash=hash_password(password),
        )
        db.add(user)
        db.flush()
    else:
        user.display_name = name
        user.role = "citizen"
        user.password_hash = hash_password(password)

    attrs = dict(DEMO_CITIZEN_ATTRS)
    profile = db.query(Profile).filter(Profile.user_id == user.id).first()
    if profile is None:
        profile = Profile(
            user_id=user.id,
            attributes_json=json.dumps(attrs),
            consent_notifications=True,
            consent_email=email,
        )
        db.add(profile)
    else:
        profile.attributes_json = json.dumps(attrs)
        profile.consent_notifications = True
        profile.consent_email = email
    db.commit()


def ensure_demo_approved_rules(db: Session) -> None:
    """Install a few person-approved quoted rules so the demo citizen can apply."""
    settings = get_settings()
    approver = settings.admin_email.strip().lower() or "admin@rightpath.local"
    now = utcnow()
    for program_id, pack in DEMO_APPROVED.items():
        program = db.get(Program, program_id)
        if program is None or not program.current_version_id:
            continue
        live = db.get(ProgramVersion, program.current_version_id)
        if live is None:
            continue
        rules = json.loads(live.rules_json or "{}")
        rules["conditions"] = pack["conditions"]
        rules["required_docs"] = pack.get("required_docs") or []
        rules["deadline"] = pack.get("deadline") or ""
        live.rules_json = json.dumps(rules)
        live.approved_by = approver
        live.approved_at = now
        live.last_verified = now.date().isoformat()
        live.status = "live"

        source = (
            db.query(Source).filter(Source.program_id == program_id).order_by(Source.id).first()
        )
        if source is None:
            continue
        source.status = "ok"
        source.last_text = pack["notice_text"]
        source.last_checked = now
        source.last_hash = "demo-approved"
    db.commit()


def ensure_demo_accounts(db: Session) -> None:
    """Wipe citizen accounts, then recreate staff/admin and the premade citizen."""
    purge_citizen_accounts(db)
    ensure_staff(db)
    ensure_demo_citizen(db)


def ensure_catalogue(db: Session) -> None:
    """Upsert official programmes. Do not invent rules, quotas, or deadlines."""
    for prog in PROGRAMS:
        rules = build_rules(prog, version=1)
        program = db.get(Program, prog["id"])
        if program is None:
            program = Program(
                id=prog["id"],
                country="PK",
                domain=prog["domain"],
                title=prog["title"],
                provider=prog["provider"],
                status="active",
                is_demo_sample=False,
            )
            db.add(program)
            db.flush()
        else:
            program.country = "PK"
            program.domain = prog["domain"]
            program.title = prog["title"]
            program.provider = prog["provider"]
            program.status = "active"
            program.is_demo_sample = False

        live = None
        if program.current_version_id:
            live = db.get(ProgramVersion, program.current_version_id)
        if live is None:
            version = ProgramVersion(
                program_id=prog["id"],
                version=1,
                rules_json=json.dumps(rules),
                source_url=prog["official_url"],
                last_verified="",
                approved_by=None,
                status="live",
            )
            db.add(version)
            db.flush()
            program.current_version_id = version.id
        else:
            # Keep a person-approved rule pack. Always point the source at the official page.
            stored = json.loads(live.rules_json or "{}")
            stored["official_url"] = prog["official_url"]
            stored["source_url"] = prog["official_url"]
            stored.pop("quota_quote", None)
            stored.pop("quota_label", None)
            live.rules_json = json.dumps(stored)
            live.source_url = prog["official_url"]

        source = (
            db.query(Source).filter(Source.program_id == prog["id"]).order_by(Source.id).first()
        )
        if source is None:
            db.add(
                Source(
                    program_id=prog["id"],
                    url=prog["official_url"],
                    label=prog["title"],
                    status="not_checked",
                    is_demo_controllable=False,
                    last_text="",
                )
            )
        else:
            source.url = prog["official_url"]
            source.label = prog["title"]
            source.is_demo_controllable = False
            if source.url.startswith("/demo/"):
                source.status = "not_checked"
                source.last_text = ""

    retired_ids = []
    for program in db.query(Program).all():
        if program.id not in CATALOGUE_IDS:
            program.status = "retired"
            program.is_demo_sample = False
            retired_ids.append(program.id)

    if retired_ids:
        (
            db.query(IngestionJob)
            .filter(
                IngestionJob.program_id.in_(retired_ids),
                IngestionJob.status == "pending_review",
            )
            .update({IngestionJob.status: "rejected"}, synchronize_session=False)
        )

    db.commit()


def seed_if_empty(db: Session) -> None:
    if not db.query(Event).first():
        db.add(
            Event(
                case_id="system",
                stage="seed",
                status="ok",
                detail="Official programme list loaded",
                human_decision=False,
            )
        )
        db.commit()
    ensure_demo_accounts(db)
    ensure_catalogue(db)
    ensure_demo_approved_rules(db)
