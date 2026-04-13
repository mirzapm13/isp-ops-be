from datetime import datetime
from typing import Any

from sqlalchemy import String, cast, or_
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


def list_logs(
    db: Session,
    *,
    search: str | None = None,
    actor_type: str | None = None,
    actor_id: str | None = None,
    event_type: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    severity: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    page: int = 1,
    limit: int = 20,
) -> dict[str, Any]:
    query = db.query(Log)

    if search:
        term = f"%{search}%"
        query = query.filter(
            or_(
                Log.actor_type.ilike(term),
                Log.actor_id.ilike(term),
                Log.event_type.ilike(term),
                Log.entity_type.ilike(term),
                Log.entity_id.ilike(term),
                Log.message.ilike(term),
                cast(Log.payload, String).ilike(term),
            )
        )

    if actor_type:
        query = query.filter(Log.actor_type == actor_type)

    if actor_id:
        query = query.filter(Log.actor_id == actor_id)

    if event_type:
        query = query.filter(Log.event_type == event_type)

    if entity_type:
        query = query.filter(Log.entity_type == entity_type)

    if entity_id:
        query = query.filter(Log.entity_id == entity_id)

    if severity:
        query = query.filter(Log.severity == severity)

    if start_date:
        query = query.filter(Log.created_at >= start_date)

    if end_date:
        query = query.filter(Log.created_at <= end_date)

    total = query.count()
    logs = (
        query
        .order_by(Log.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    items = [
        {
            "id": log.id,
            "actor_type": log.actor_type,
            "actor_id": log.actor_id,
            "event_type": log.event_type,
            "entity_type": log.entity_type,
            "entity_id": log.entity_id,
            "message": log.message,
            "payload": log.payload,
            "severity": log.severity,
            "created_at": log.created_at.isoformat(),
        }
        for log in logs
    ]

    return {
        "items": items,
        "total": total,
        "page": page,
        "limit": limit,
    }
