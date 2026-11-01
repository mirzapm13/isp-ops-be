from sqlalchemy import (
    Boolean,
    Column,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    TIMESTAMP,
)
from sqlalchemy.sql import func

from app.models.base import Base


class WaBroadcastRun(Base):
    __tablename__ = "wa_broadcast_runs"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    template_name = Column(String(100), nullable=False)
    namespace = Column(String(150), nullable=False)
    language_code = Column(String(20), nullable=False, default="id")
    dry_run = Column(Boolean, nullable=False, default=False)
    delay_seconds = Column(Float, nullable=False, default=1.0)
    status = Column(String(30), nullable=False, default="RUNNING", index=True)
    stop_requested = Column(Boolean, nullable=False, default=False)
    total = Column(Integer, nullable=False, default=0)
    processed = Column(Integer, nullable=False, default=0)
    success = Column(Integer, nullable=False, default=0)
    failed = Column(Integer, nullable=False, default=0)
    message = Column(Text, nullable=True)
    created_by = Column(String(100), nullable=True)
    started_at = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at = Column(TIMESTAMP(timezone=True), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "filename": self.filename,
            "template_name": self.template_name,
            "namespace": self.namespace,
            "language_code": self.language_code,
            "dry_run": self.dry_run,
            "delay_seconds": self.delay_seconds,
            "status": self.status,
            "running": self.status == "RUNNING",
            "done": self.status in ("COMPLETED", "STOPPED", "FAILED"),
            "stop_requested": self.stop_requested,
            "total": self.total,
            "processed": self.processed,
            "success": self.success,
            "failed": self.failed,
            "message": self.message or "",
            "created_by": self.created_by,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
        }


class WaBroadcastLog(Base):
    __tablename__ = "wa_broadcast_logs"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(
        Integer,
        ForeignKey("wa_broadcast_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    excel_row = Column(Integer, nullable=False)
    id_pelanggan = Column(String(100), nullable=True, index=True)
    nama_pelanggan = Column(String(255), nullable=True)
    phone_number = Column(String(50), nullable=False, index=True)
    status = Column(String(30), nullable=False, default="PENDING", index=True)
    http_status = Column(Integer, nullable=True)
    message_id = Column(String(150), nullable=True)
    wa_id = Column(String(100), nullable=True)
    qiscus_payload = Column(Text, nullable=True)
    qiscus_response = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    sent_at = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    def to_dict(self):
        return {
            "id": self.id,
            "run_id": self.run_id,
            "excel_row": self.excel_row,
            "id_pelanggan": self.id_pelanggan or "",
            "nama_pelanggan": self.nama_pelanggan or "",
            "phone": self.phone_number or "",
            "phone_number": self.phone_number or "",
            "status": self.status,
            "http_status": self.http_status if self.http_status is not None else "",
            "message_id": self.message_id or "",
            "wa_id": self.wa_id or "",
            "payload": self.qiscus_payload or "",
            "response": self.qiscus_response or "",
            "error": self.error_message or "",
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
