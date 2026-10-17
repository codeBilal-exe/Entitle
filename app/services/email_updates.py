"""Deliver approved Entitle profile alerts over the configured SMTP transport."""

from __future__ import annotations

import html
import logging
import smtplib
from datetime import datetime
from email.message import EmailMessage
from email.utils import formataddr

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Notification, Profile, Program, User

logger = logging.getLogger("entitle.email")


def send_notification_email(db: Session, notification: Notification) -> bool:
    """Send once when enabled and consented; retain an in-app alert on any failure."""
    settings = get_settings()
    if notification.email_sent_at or not settings.email_ready:
        return False
    if notification.kind == "newly_not_eligible" and notification.status != "approved":
        return False

    profile = db.query(Profile).filter(Profile.user_id == notification.user_id).first()
    if not profile or not profile.consent_notifications or not profile.notification_email:
        return False
    user = db.get(User, notification.user_id)
    program = db.get(Program, notification.program_id)
    if not user or not program:
        return False

    import json

    detail = json.loads(notification.detail_json or "{}")
    opportunity = notification.kind != "newly_not_eligible"
    subject = (f"Entitle update: You may qualify for {program.title}"
               if opportunity else f"Entitle update: A rule changed for {program.title}")
    app_url = settings.base_url.rstrip("/") + ("/jobs" if opportunity else "/profile#alerts")
    quote = detail.get("quote") or ""
    meaning = detail.get("meaning") or f"There is an update about {program.title}."
    changed = detail.get("what_changed") or "The official programme rules were updated."
    next_step = ("Open your Job feed to review the opportunity and its official source."
                 if opportunity else "Review the alert and official source before deciding what to do next.")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = formataddr((settings.smtp_from_name, settings.smtp_from_email))
    message["To"] = profile.notification_email
    lines = [f"Hi {user.display_name or 'there'},", "", meaning, "", changed]
    if quote:
        lines.extend(["", f'From the official page: “{quote}”'])
    lines.extend(["", next_step, app_url])
    if program.official_url:
        lines.extend(["", f"Official source: {program.official_url}"])
    lines.extend(["", "You can change email updates in your Entitle profile."])
    message.set_content("\n".join(lines))

    safe = html.escape
    quote_html = f"<blockquote>{safe(quote)}</blockquote>" if quote else ""
    source_html = (f'<p><a href="{safe(program.official_url, quote=True)}">Read the official source</a></p>'
                   if program.official_url else "")
    message.add_alternative(
        "<!doctype html><html><body style=\"font-family:Arial,sans-serif;color:#153330;line-height:1.6\">"
        f"<p>Hi {safe(user.display_name or 'there')},</p><h2>{safe(meaning)}</h2>"
        f"<p>{safe(changed)}</p>{quote_html}<p>{safe(next_step)}</p>"
        f'<p><a href="{safe(app_url, quote=True)}">Open Entitle</a></p>{source_html}'
        "<p>You can change email updates in your Entitle profile.</p></body></html>",
        subtype="html",
    )

    try:
        if settings.smtp_port == 465:
            with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=12) as smtp:
                _smtp_login(smtp, settings.smtp_username, settings.smtp_password)
                smtp.send_message(message)
        else:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=12) as smtp:
                smtp.ehlo()
                if settings.smtp_use_tls:
                    smtp.starttls()
                    smtp.ehlo()
                _smtp_login(smtp, settings.smtp_username, settings.smtp_password)
                smtp.send_message(message)
    except Exception as exc:  # mail must never interrupt profile or review workflows
        notification.email_error = str(exc)[:500]
        db.commit()
        logger.warning("could not email notification %s: %s", notification.id, exc)
        return False

    notification.email_sent_at = datetime.utcnow()
    notification.email_error = ""
    db.commit()
    logger.info("emailed notification %s to the saved profile address", notification.id)
    return True


def _smtp_login(smtp: smtplib.SMTP, username: str, password: str) -> None:
    if username:
        smtp.login(username, password)
