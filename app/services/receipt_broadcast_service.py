import json
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Dict, Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.database import engine
from app.models.payment_receipt_log import PaymentReceiptLog
from app.adapters.billing.receipt_excel_reader import (
    download_receipt_excel,
    parse_receipt_excel,
)
from app.adapters.whatsapp.qiscus_adapter import QiscusWhatsAppAdapter

logger = logging.getLogger(__name__)


def process_receipt_broadcast(
    data_account: str = "23213",
    tglskg: Optional[str] = None,
    url: Optional[str] = None,
    dry_run: bool = False,
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    now_jakarta = datetime.now(ZoneInfo("Asia/Jakarta"))

    if not tglskg:
        # Default to first day of current month YYYY-MM-01
        tglskg = now_jakarta.strftime("%Y-%m-01")

    # Extract billing period YYYY-MM from tglskg
    billing_period = tglskg[:7]

    # Step 1: Download & parse Excel
    try:
        excel_path = download_receipt_excel(
            data_account=data_account, tglskg=tglskg, url=url
        )
        records = parse_receipt_excel(excel_path)
        if limit and limit > 0:
            records = records[:limit]
    except Exception as e:
        logger.error(f"Failed to fetch or parse Excel: {e}")
        return {
            "status": "FAILED",
            "message": f"Failed to download or parse Excel file: {str(e)}",
            "billing_period": billing_period,
            "timestamp": now_jakarta.isoformat(),
        }

    if not records:
        return {
            "status": "NO_DATA",
            "message": "No valid customer payment records found in Excel",
            "billing_period": billing_period,
            "total_found": 0,
            "timestamp": now_jakarta.isoformat(),
        }

    qiscus = QiscusWhatsAppAdapter()
    summary = {
        "total_found": len(records),
        "processed": 0,
        "skipped": 0,
        "failed": 0,
        "items": [],
    }

    with Session(engine) as session:
        # Step 2: Query all existing logs for this billing period
        existing_logs = session.scalars(
            select(PaymentReceiptLog).where(
                PaymentReceiptLog.billing_period == billing_period,
            )
        ).all()

        log_map = {log.id_pelanggan: log for log in existing_logs}

        # Step 3: Process each customer
        for rec in records:
            id_pelanggan = rec["id_pelanggan"]
            existing_log = log_map.get(id_pelanggan)

            # Idempotency check: Skip if already sent successfully
            if existing_log and existing_log.status == "SENT":
                summary["skipped"] += 1
                # summary["items"].append({
                #     "id_pelanggan": id_pelanggan,
                #     "nama_pelanggan": rec["nama_pelanggan"],
                #     "status": "SKIPPED",
                #     "reason": "Already sent for this period",
                # })
                continue

            if dry_run:
                summary["processed"] += 1
                summary["items"].append({
                    "id_pelanggan": id_pelanggan,
                    "nama_pelanggan": rec["nama_pelanggan"],
                    "status": "DRY_RUN",
                    "message": "Would send WhatsApp receipt",
                })
                continue

            # Step 4: Send WhatsApp message via Qiscus
            res = qiscus.send_receipt_template(
                to_phone=rec["phone_number"],
                customer_name=rec["nama_pelanggan"],
                address=rec["alamat"],
                amount=rec["nominal_pembayaran"],
                package_name=rec["nama_langganan"],
                package_desc=rec["keterangan_langganan"],
                month=rec["bulan"],
                receipt_url=rec["bukti_link"],
            )

            is_success = res.get("success", False)
            sent_timestamp = datetime.now(ZoneInfo("Asia/Jakarta"))

            # Update existing failed log row on retry, or create new log entry
            if existing_log:
                existing_log.status = "SENT" if is_success else "FAILED"
                existing_log.qiscus_response = json.dumps(res.get("data", {}))
                existing_log.error_message = (
                    json.dumps(res.get("error", "")) if not is_success else None
                )
                existing_log.sent_at = sent_timestamp if is_success else None
            else:
                log_entry = PaymentReceiptLog(
                    id_pelanggan=id_pelanggan,
                    nama_pelanggan=rec["nama_pelanggan"],
                    phone_number=rec["phone_number"],
                    billing_period=billing_period,
                    receipt_url=rec["bukti_link"],
                    status="SENT" if is_success else "FAILED",
                    qiscus_response=json.dumps(res.get("data", {})),
                    error_message=(
                        json.dumps(res.get("error", "")) if not is_success else None
                    ),
                    sent_at=sent_timestamp if is_success else None,
                )
                session.add(log_entry)
                log_map[id_pelanggan] = log_entry

            session.commit()

            if is_success:
                summary["processed"] += 1
                summary["items"].append({
                    "id_pelanggan": id_pelanggan,
                    "nama_pelanggan": rec["nama_pelanggan"],
                    "status": "SENT",
                })
            else:
                summary["failed"] += 1
                summary["items"].append({
                    "id_pelanggan": id_pelanggan,
                    "nama_pelanggan": rec["nama_pelanggan"],
                    "status": "FAILED",
                    "error": res.get("error"),
                })

    return {
        "status": "SUCCESS" if summary["failed"] == 0 else "PARTIAL",
        "message": f"Processed {summary['processed']} receipts, skipped {summary['skipped']}, failed {summary['failed']}",
        "billing_period": billing_period,
        "summary": summary,
        "timestamp": now_jakarta.isoformat(),
    }
