"""Seed staff accounts and official programme sources. No citizen personas."""

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


def _purge_legacy_people(db: Session) -> None:
    for email in LEGACY_DEMO_EMAILS:
        user = db.query(User).filter(User.email == email).first()
        if user is None:
            continue
        db.query(Notification).filter(Notification.user_id == user.id).delete()
        db.query(Application).filter(Application.user_id == user.id).delete()
        db.query(Profile).filter(Profile.user_id == user.id).delete()
        db.delete(user)


def ensure_staff(db: Session) -> None:
    """One admin and two staff accounts. Passwords come from the environment."""
    settings = get_settings()
    accounts = (
        {
            "email": settings.admin_email.strip().lower(),
            "display_name": "Admin",
            "role": "admin",
            "password": settings.admin_password,
        },
        {
            "email": settings.staff_one_email.strip().lower(),
            "display_name": "Staff one",
            "role": "staff",
            "password": settings.staff_one_password,
        },
        {
            "email": settings.staff_two_email.strip().lower(),
            "display_name": "Staff two",
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
    ensure_staff(db)
    ensure_catalogue(db)
