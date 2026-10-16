"""Seed demo users, programmes, and the controllable DEMO notice."""

from __future__ import annotations

import json

from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.models import DemoNotice, Event, Profile, Program, ProgramVersion, Source, User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

DEMO_PASSWORD = "demo1234"

PROGRAMS = [
    {
        "id": "demo_pk_work_01",
        "country": "PK",
        "domain": "work",
        "title": "DEMO: Inclusive Hiring Programme (sample)",
        "provider": "Sample Public Body",
        "is_demo_sample": True,
        "source_url": "/demo/notices/inclusive-hiring",
        "last_verified": "2026-10-16",
        "deadline": "2026-12-01",
        "channel": "email",
        "apply_email": "intake@example.org",
        "required_docs": ["id_document", "disability_certificate"],
        "conditions": [
            {
                "id": "c1",
                "attr": "disability",
                "op": "is_true",
                "source_quote": "persons with disabilities",
            },
            {
                "id": "c2",
                "attr": "age",
                "op": "between",
                "value": [18, 45],
                "source_quote": "aged between 18 and 45 years",
            },
            {
                "id": "c3",
                "attr": "education_level",
                "op": "in",
                "value": ["secondary", "tertiary"],
                "source_quote": "completed secondary education or higher",
            },
        ],
    },
    {
        "id": "demo_pk_edu_01",
        "country": "PK",
        "domain": "education",
        "title": "DEMO: Skills Scholarship (sample)",
        "provider": "Sample Education Authority",
        "is_demo_sample": True,
        "source_url": "https://example.org/skills-scholarship",
        "last_verified": "2026-10-16",
        "deadline": "2026-11-15",
        "channel": "email",
        "apply_email": "scholarships@example.org",
        "required_docs": ["id_document", "education_certificate"],
        "conditions": [
            {
                "id": "c1",
                "attr": "age",
                "op": "between",
                "value": [16, 28],
                "source_quote": "applicants aged 16 to 28",
            },
            {
                "id": "c2",
                "attr": "education_level",
                "op": "in",
                "value": ["secondary"],
                "source_quote": "holding a secondary school certificate",
            },
        ],
    },
    {
        "id": "demo_pk_health_01",
        "country": "PK",
        "domain": "health",
        "title": "DEMO: Community Health Support (sample)",
        "provider": "Sample Health Directorate",
        "is_demo_sample": True,
        "source_url": "https://example.org/community-health",
        "last_verified": "2026-10-16",
        "deadline": "2026-12-31",
        "channel": "email",
        "apply_email": "health@example.org",
        "required_docs": ["id_document"],
        "conditions": [
            {
                "id": "c1",
                "attr": "low_income",
                "op": "is_true",
                "source_quote": "households on low income",
            },
            {
                "id": "c2",
                "attr": "age",
                "op": "gte",
                "value": 18,
                "source_quote": "adults aged 18 and over",
            },
        ],
    },
    {
        "id": "demo_pk_legal_01",
        "country": "PK",
        "domain": "legal",
        "title": "DEMO: Legal Aid Clinic Referral (sample)",
        "provider": "Sample Legal Aid Board",
        "is_demo_sample": True,
        "source_url": "https://example.org/legal-aid",
        "last_verified": "2026-10-16",
        "deadline": "2027-01-31",
        "channel": "email",
        "apply_email": "legalaid@example.org",
        "required_docs": ["id_document"],
        "conditions": [
            {
                "id": "c1",
                "attr": "low_income",
                "op": "is_true",
                "source_quote": "unable to afford private counsel",
            },
        ],
    },
    {
        "id": "demo_xx_lang_01",
        "country": "XX",
        "domain": "education",
        "title": "DEMO: Language Access Classes (sample)",
        "provider": "Sample Civic Centre",
        "is_demo_sample": True,
        "source_url": "https://example.org/language-access",
        "last_verified": "2026-10-16",
        "deadline": "2026-11-30",
        "channel": "email",
        "apply_email": "language@example.org",
        "required_docs": ["id_document"],
        "conditions": [
            {
                "id": "c1",
                "attr": "needs_language_support",
                "op": "is_true",
                "source_quote": "residents who need language support",
            },
            {
                "id": "c2",
                "attr": "age",
                "op": "gte",
                "value": 16,
                "source_quote": "aged 16 or older",
            },
        ],
    },
    {
        "id": "demo_xx_work_02",
        "country": "XX",
        "domain": "work",
        "title": "DEMO: Return-to-Work Grant (sample)",
        "provider": "Sample Labour Office",
        "is_demo_sample": True,
        "source_url": "https://example.org/return-to-work",
        "last_verified": "2026-10-16",
        "deadline": "2026-12-20",
        "channel": "email",
        "apply_email": "rtw@example.org",
        "required_docs": ["id_document", "education_certificate"],
        "conditions": [
            {
                "id": "c1",
                "attr": "unemployed",
                "op": "is_true",
                "source_quote": "currently unemployed",
            },
            {
                "id": "c2",
                "attr": "age",
                "op": "between",
                "value": [22, 55],
                "source_quote": "aged between 22 and 55 years",
            },
        ],
    },
]

# Exported for demo reset.
INCLUSIVE_HIRING_NOTICE = (
    "Inclusive Hiring Programme — Official Notice (DEMO SAMPLE)\n\n"
    "This programme supports persons with disabilities aged between 18 and 45 years "
    "who have completed secondary education or higher. Applications are accepted by email. "
    "Required documents include an identity document and a disability certificate.\n\n"
    "This page is a controllable DEMO source for RightPath. It is not a government website."
)


def seed_if_empty(db: Session) -> None:
    if db.query(User).first():
        return

    users = [
        # Amina is 40: eligible at 18-45, loses eligibility if the notice tightens to 18-35.
        ("amina@demo.rightpath", "Amina Demo", "applicant", {"disability": True, "age": 40, "education_level": "tertiary", "low_income": True, "unemployed": False, "needs_language_support": False}),
        # Bilal is 28: stays eligible when the band tightens to 18-35 (control case).
        ("bilal@demo.rightpath", "Bilal Demo", "applicant", {"disability": True, "age": 28, "education_level": "secondary", "low_income": True, "unemployed": True, "needs_language_support": False}),
        # Mr Rao starts outside a tight band for the widen demo path (optional).
        ("rao@demo.rightpath", "Mr Rao Demo", "applicant", {"disability": True, "age": 34, "education_level": "secondary", "low_income": True, "unemployed": True, "needs_language_support": False}),
        ("nav@demo.rightpath", "Nadia Navigator", "navigator", {}),
        ("curator@demo.rightpath", "Carlos Curator", "curator", {}),
        ("admin@demo.rightpath", "Admin Demo", "admin", {}),
    ]

    password_hash = pwd_context.hash(DEMO_PASSWORD)
    for email, name, role, attrs in users:
        user = User(
            email=email,
            display_name=name,
            role=role,
            password_hash=password_hash,
        )
        db.add(user)
        db.flush()
        if role == "applicant":
            db.add(
                Profile(
                    user_id=user.id,
                    attributes_json=json.dumps(attrs),
                    consent_notifications=True,
                    consent_email=email,
                )
            )

    for prog in PROGRAMS:
        rules = {
            "id": prog["id"],
            "version": 1,
            "country": prog["country"],
            "domain": prog["domain"],
            "title": prog["title"],
            "provider": prog["provider"],
            "source_url": prog["source_url"],
            "last_verified": prog["last_verified"],
            "deadline": prog["deadline"],
            "channel": prog["channel"],
            "apply_email": prog["apply_email"],
            "conditions": prog["conditions"],
            "required_docs": prog["required_docs"],
            "form_schema": {
                "fields": ["full_name", "age", "education_level", "contact_email"]
            },
        }
        db.add(
            Program(
                id=prog["id"],
                country=prog["country"],
                domain=prog["domain"],
                title=prog["title"],
                provider=prog["provider"],
                status="active",
                is_demo_sample=prog["is_demo_sample"],
            )
        )
        db.flush()
        version = ProgramVersion(
            program_id=prog["id"],
            version=1,
            rules_json=json.dumps(rules),
            source_url=prog["source_url"],
            last_verified=prog["last_verified"],
            approved_by="seed",
            status="live",
        )
        db.add(version)
        db.flush()
        program = db.get(Program, prog["id"])
        assert program is not None
        program.current_version_id = version.id

        controllable = prog["id"] == "demo_pk_work_01"
        db.add(
            Source(
                program_id=prog["id"],
                url=prog["source_url"],
                label=prog["title"],
                status="ok",
                is_demo_controllable=controllable,
            )
        )

    db.add(
        DemoNotice(
            id="inclusive-hiring",
            title="Inclusive Hiring Programme — Official Notice (DEMO SAMPLE)",
            body=INCLUSIVE_HIRING_NOTICE,
        )
    )

    db.add(
        Event(
            case_id="system",
            stage="seed",
            status="ok",
            detail="Demo data loaded",
            human_decision=False,
        )
    )
    db.commit()
