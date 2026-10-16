"""Demo reset no longer rewrites programmes or people."""

from __future__ import annotations

from sqlalchemy.orm import Session


def reset_demo(db: Session) -> dict[str, str]:
    return {"ok": "false", "error": "demo_reset_removed"}
