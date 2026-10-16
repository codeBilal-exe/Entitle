from __future__ import annotations

import smtplib
from email.message import EmailMessage
from typing import Any

from app.config import get_settings


def send_application_email(payload: dict[str, Any], recipient: str) -> None:
    settings = get_settings()
    if not settings.mail_host:
        raise RuntimeError("MAIL_HOST is not configured")

    fields = payload.get("fields") or {}
    msg = EmailMessage()
    msg["Subject"] = f"RightPath application packet — {payload.get('program_id')}"
    msg["From"] = settings.mail_from or settings.mail_user
    msg["To"] = recipient
    body_lines = [
        "This message was sent by RightPath after applicant consent.",
        "",
        f"Programme: {payload.get('program_id')}",
        "",
        "Fields:",
    ]
    for key, value in fields.items():
        body_lines.append(f"- {key}: {value}")
    body_lines.extend(
        [
            "",
            "Attachments listed (SAMPLE ONLY in demo):",
            *[f"- {name}" for name in (payload.get("attachments") or [])],
            "",
            "Information only — not legal or medical advice.",
        ]
    )
    msg.set_content("\n".join(body_lines))

    with smtplib.SMTP(settings.mail_host, settings.mail_port, timeout=30) as smtp:
        smtp.starttls()
        if settings.mail_user:
            smtp.login(settings.mail_user, settings.mail_pass)
        smtp.send_message(msg)
