"""In-process watcher so Pulse still runs if n8n is down."""

from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.config import get_settings
from app.db import SessionLocal
from app.services.deadlines import run_deadline_reminders
from app.services.pulse import check_sources

logger = logging.getLogger("rightpath.scheduler")
_scheduler: BackgroundScheduler | None = None


def _watch_job() -> None:
    db = SessionLocal()
    try:
        result = check_sources(db, auto_ingest=True)
        changed = sum(1 for s in result.get("sources", []) if s.get("changed"))
        if changed:
            logger.info("watcher found %s changed source(s)", changed)
    except Exception:
        logger.exception("watcher job failed")
    finally:
        db.close()


def _deadline_job() -> None:
    db = SessionLocal()
    try:
        result = run_deadline_reminders(db)
        if result.get("created"):
            logger.info("deadline reminders created=%s", result["created"])
    except Exception:
        logger.exception("deadline job failed")
    finally:
        db.close()


def start_scheduler() -> None:
    global _scheduler
    settings = get_settings()
    if not settings.enable_scheduler:
        logger.info("scheduler disabled")
        return
    if _scheduler and _scheduler.running:
        return
    _scheduler = BackgroundScheduler(timezone="UTC")
    _scheduler.add_job(
        _watch_job,
        "interval",
        seconds=max(30, settings.watcher_interval_seconds),
        id="source_watcher",
        replace_existing=True,
    )
    _scheduler.add_job(
        _deadline_job,
        "interval",
        hours=1,
        id="deadline_guardian",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info(
        "source watcher every %ss; deadline guardian hourly",
        settings.watcher_interval_seconds,
    )


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
    _scheduler = None
