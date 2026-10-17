"""Load the starting catalogue: real official pages whose rules were AI-drafted,
receipt-checked and approved by the Entitle team. No accounts are created here."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.engine.quote_gate import QuoteGate
from app.models import Program, ProgramVersion, Source
from app.services.timeline import log_event

CATALOGUE_PATH = Path(__file__).resolve().parent / "catalogue.json"
APPROVER = "Entitle team"


def _slug(url: str) -> str:
    import hashlib
    import re
    from urllib.parse import urlparse

    host = (urlparse(url).hostname or "page").replace("www.", "").split(".")[0]
    path = re.sub(r"[^a-z0-9]+", "-", urlparse(url).path.lower()).strip("-")[:30]
    return f"{host}-{path or 'home'}-{hashlib.sha256(url.encode()).hexdigest()[:4]}"


def load_catalogue() -> dict[str, Any]:
    return json.loads(CATALOGUE_PATH.read_text(encoding="utf-8"))


def seed_catalogue(db: Session) -> int:
    """Insert catalogue programmes that are missing. Never overwrites a reviewer's later approval."""
    data = load_catalogue()
    verified_on = datetime.fromisoformat(data["verified_on"])
    gate = QuoteGate()
    added = 0
    for item in data["programmes"]:
        program_id = _slug(item["url"])
        if db.get(Program, program_id) is not None:
            continue
        rules = {
            "id": program_id,
            "version": 1,
            "title": item["title"],
            "provider": item["provider"],
            "summary": item["summary"],
            "country": item["country"],
            "domain": item["domain"],
            "official_url": item["url"],
            "source_url": item["url"],
            "required_docs": item.get("required_docs") or [],
            "deadline": item.get("deadline") or "",
            "conditions": item["conditions"],
        }
        if not gate.check(item["page_text"], rules).passed:
            continue
        program = Program(
            id=program_id,
            country=item["country"],
            domain=item["domain"],
            title=item["title"],
            provider=item["provider"],
            summary=item["summary"],
            official_url=item["url"],
            status="active",
        )
        db.add(program)
        db.flush()
        version = ProgramVersion(
            program_id=program_id,
            version=1,
            rules_json=json.dumps(rules),
            source_url=item["url"],
            approved_by=APPROVER,
            approved_at=verified_on,
            status="live",
        )
        db.add(version)
        db.flush()
        program.current_version_id = version.id
        # No hash yet: the watcher's first read becomes the baseline instead of a false change.
        db.add(Source(program_id=program_id, url=item["url"], label=item["title"],
                      status="ok", last_text=item["page_text"], last_hash=""))
        added += 1
    db.commit()
    if added:
        log_event(db, stage="catalogue_loaded", detail=f"{added} verified programmes loaded", case_id="system")
    return added
