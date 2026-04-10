from sqlalchemy import String,text, TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from datetime import datetime

from app.models.base import Base

class Log(Base):
    __tablename__ = "logs"

    id: Mapped[int] = mapped_column(primary_key=True)

    actor_type: Mapped[str] = mapped_column(String(50))
    actor_id: Mapped[str] = mapped_column(String(50))
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(100))

    message: Mapped[str | None] = mapped_column(String(255))

    payload: Mapped[dict | None] = mapped_column(JSONB)

    severity: Mapped[str] = mapped_column(
        String(20),
        server_default=text("'INFO'")
    )

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        server_default=func.now(),
        nullable=False
    )