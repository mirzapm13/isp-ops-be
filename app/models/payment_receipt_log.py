from sqlalchemy import Column, Integer, String, Text, TIMESTAMP, UniqueConstraint
from sqlalchemy.sql import func

from app.models.base import Base


class PaymentReceiptLog(Base):
    __tablename__ = "payment_receipt_logs"

    id = Column(Integer, primary_key=True, index=True)
    id_pelanggan = Column(String(50), nullable=False, index=True)
    nama_pelanggan = Column(String(255), nullable=True)
    phone_number = Column(String(50), nullable=False)
    billing_period = Column(String(20), nullable=False, index=True)
    receipt_url = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="PENDING")
    qiscus_response = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    sent_at = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "id_pelanggan",
            "billing_period",
            name="uq_payment_receipt_log_pelanggan_period",
        ),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "id_pelanggan": self.id_pelanggan,
            "nama_pelanggan": self.nama_pelanggan,
            "phone_number": self.phone_number,
            "billing_period": self.billing_period,
            "receipt_url": self.receipt_url,
            "status": self.status,
            "qiscus_response": self.qiscus_response,
            "error_message": self.error_message,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
