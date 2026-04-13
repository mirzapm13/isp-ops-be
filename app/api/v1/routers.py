from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.security.auth import get_current_user, get_db
from app.services.log_service import list_logs
from app.services.router_service import list_routers

router = APIRouter(
    prefix="/routers",
    tags=["Routers"],
    dependencies=[Depends(get_current_user)]
)

@router.get("")
def get_routers():
    return list_routers()


@router.get("/logs")
def get_router_logs(
    search: str | None = Query(default=None),
    actor_type: str | None = Query(default=None),
    actor_id: str | None = Query(default=None),
    event_type: str | None = Query(default=None),
    entity_type: str | None = Query(default=None),
    entity_id: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return list_logs(
        db,
        search=search,
        actor_type=actor_type,
        actor_id=actor_id,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        severity=severity,
        start_date=start_date,
        end_date=end_date,
        page=page,
        limit=limit,
    )
