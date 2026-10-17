"""In-process watcher, so pages are re-read even when n8n is not running."""

from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.config import get_settings

logger = logging.getLogger("entitle.scheduler")
_scheduler: BackgroundScheduler | None = None


def _watch_job() -> None:
    from app import db as dbmod
    from app.services.pulse import check_sources

    session = dbmod.SessionLocal()
    try:
        result = check_sources(session, auto_ingest=True, trigger="watcher")
        changed = sum(1 for s in result.get("sources", []) if s.get("changed"))
        if changed:
            logger.info("watcher drafted %s rule change(s)", changed)
    except Exception:
        logger.exception("watcher job failed")
    finally:
        session.close()


def start_scheduler() -> None:
    global _scheduler
    settings = get_settings()
    if not settings.enable_scheduler or (_scheduler and _scheduler.running):
        return
    _scheduler = BackgroundScheduler(timezone="UTC")
    _scheduler.add_job(
        _watch_job,
        "interval",
        seconds=max(300, settings.watcher_interval_seconds),
        id="source_watcher",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("watcher re-reads official pages every %ss", settings.watcher_interval_seconds)


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
    _scheduler = None
