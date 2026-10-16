from sqlalchemy.orm import Session

from app.models import Event


def log_event(
    db: Session,
    *,
    stage: str,
    detail: str = "",
    case_id: str = "",
    status: str = "ok",
    human_decision: bool = False,
) -> Event:
    event = Event(
        case_id=case_id,
        stage=stage,
        status=status,
        detail=detail,
        human_decision=human_decision,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event
