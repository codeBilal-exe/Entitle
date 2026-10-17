from sqlalchemy.orm import Session

from app.models import Event


def log_event(
    db: Session,
    *,
    stage: str,
    detail: str = "",
    case_id: str = "",
    status: str = "ok",
    actor: str = "system",
    human_decision: bool = False,
    commit: bool = True,
) -> Event:
    """actor is "ai", "human" or "system". Human decisions are what the desk audits."""
    if human_decision:
        actor = "human"
    event = Event(
        case_id=case_id,
        stage=stage,
        status=status,
        detail=detail,
        actor=actor,
        human_decision=human_decision or (actor == "human" and stage != "sign_in"),
    )
    db.add(event)
    if commit:
        db.commit()
    return event
