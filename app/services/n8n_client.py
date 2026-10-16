"""Best-effort webhook calls to n8n. Failures are logged, never crash Core."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger("rightpath.n8n")


def notify(path: str, payload: dict[str, Any]) -> bool:
    settings = get_settings()
    base = (settings.n8n_base_url or "").rstrip("/")
    if not base:
        return False
    url = f"{base}/{path.lstrip('/')}"
    try:
        response = httpx.post(
            url,
            json=payload,
            headers={"x-rightpath-secret": settings.n8n_shared_secret},
            timeout=8.0,
        )
        response.raise_for_status()
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("n8n notify failed %s: %s", url, exc)
        return False


def notify_approve(job_id: int, reviewed_by: str) -> bool:
    # Matches n8n/w2_impact_fanout.json webhook path when deployed.
    return notify(
        "webhook/rightpath-approve",
        {"job_id": job_id, "reviewed_by": reviewed_by},
    )


def notify_send(application_id: str) -> bool:
    return notify(
        "webhook/rightpath-send",
        {"application_id": application_id},
    )
