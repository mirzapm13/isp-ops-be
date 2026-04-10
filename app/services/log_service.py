from typing import Any

from sqlalchemy.orm import Session

from app.models.log import Log


def log_event(
    db: Session,
    *,
    actor_type: str | None = None,
    actor_id: str | None = None,
    event_type: str,
    entity_type: str,
    entity_id: str | None = None,
    message: str | None = None,
    payload: dict[str, Any] | None = None,
    severity: str = "INFO",
) -> Log:
    """
    Persist one audit/event log entry to `logs` table.

    Mirrors the helper pattern from the screenshot, adapted for
    synchronous SQLAlchemy sessions used in this codebase.
    """
    log = Log(
        actor_type=actor_type,
        actor_id=actor_id,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        message=message,
        payload=payload,
        severity=severity,
    )

    db.add(log)
    db.commit()
    db.refresh(log)

    return log
