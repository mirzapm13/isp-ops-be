import io
import json
import logging
import os
import tempfile
import threading
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import pandas as pd
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.adapters.whatsapp.qiscus_adapter import QiscusWhatsAppAdapter
from app.adapters.whatsapp.templates import TEMPLATES, get_all_templates
from app.config.database import engine
from app.models.wa_broadcast_log import WaBroadcastLog, WaBroadcastRun
from app.services.utils.whatsapp_formatter import (
    clean_value,
    find_matching_column,
    is_nominal_column,
    normalize_phone,
    resolve_preset_mapping,
)

logger = logging.getLogger(__name__)

# In-memory cache of uploaded spreadsheets (upload_id -> {filename, df, columns, created_at})
_UPLOAD_CACHE_LOCK = threading.Lock()
_UPLOAD_CACHE: Dict[str, Dict[str, Any]] = {}
MAX_CACHED_UPLOADS = 25

# Active run stop events (run_id -> threading.Event)
_ACTIVE_RUNS_LOCK = threading.Lock()
_ACTIVE_STOP_EVENTS: Dict[int, threading.Event] = {}


def _has_unnamed_headers(df: pd.DataFrame) -> bool:
    if df is None or df.empty:
        return True
    cols = [str(c).strip().lower() for c in df.columns]
    unnamed_count = sum(
        1 for c in cols if c.startswith("unnamed:") or not c or c == "nan"
    )
    return unnamed_count > len(cols) / 2


def parse_uploaded_spreadsheet(
    file_bytes: bytes, filename: str, header_row: int = 3
) -> tuple[pd.DataFrame, int]:
    """
    Parses spreadsheet with header starting at `header_row` (1-based, default 3 -> pandas header=2).
    If the file has fewer rows or `header=2` produces invalid/empty columns while `header=0` has valid headers,
    falls back or respects the requested header_row.
    Returns (df, effective_header_row_1_based).
    """
    header_idx = max(0, header_row - 1)
    lower_name = (filename or "").lower()

    if lower_name.endswith(".csv"):
        df = pd.read_csv(io.BytesIO(file_bytes), header=header_idx)
        if header_idx > 0 and (df.empty or _has_unnamed_headers(df)):
            df_row1 = pd.read_csv(io.BytesIO(file_bytes), header=0)
            if not _has_unnamed_headers(df_row1):
                return df_row1, 1
        return df, header_row

    suffix = ".xls" if lower_name.endswith(".xls") else ".xlsx"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name

    try:
        try:
            engine_name = "xlrd" if lower_name.endswith(".xls") else "openpyxl"
            df = pd.read_excel(tmp_path, engine=engine_name, header=header_idx)
            if header_idx > 0 and (df.empty or _has_unnamed_headers(df)):
                df_row1 = pd.read_excel(tmp_path, engine=engine_name, header=0)
                if not _has_unnamed_headers(df_row1):
                    return df_row1, 1
            return df, header_row
        except Exception:
            # Fallback for HTML-based .xls exports
            tables = pd.read_html(tmp_path, header=header_idx)
            if not tables:
                raise ValueError("No tables found in spreadsheet file")
            df = tables[0]
            if header_idx > 0 and (df.empty or _has_unnamed_headers(df)):
                tables_row1 = pd.read_html(tmp_path, header=0)
                if tables_row1 and not _has_unnamed_headers(tables_row1[0]):
                    return tables_row1[0], 1
            return df, header_row
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def store_uploaded_file(
    file_bytes: bytes, filename: str, header_row: int = 3
) -> Dict[str, Any]:
    df, effective_header_row = parse_uploaded_spreadsheet(
        file_bytes, filename, header_row=header_row
    )
    if df is None or df.empty:
        raise ValueError("The uploaded file contains no data rows.")

    df.columns = [str(c).strip() for c in df.columns]
    columns = list(df.columns)
    upload_id = str(uuid.uuid4())
    first_data_row = effective_header_row + 1

    with _UPLOAD_CACHE_LOCK:
        if len(_UPLOAD_CACHE) >= MAX_CACHED_UPLOADS:
            oldest_key = next(iter(_UPLOAD_CACHE))
            _UPLOAD_CACHE.pop(oldest_key, None)
        _UPLOAD_CACHE[upload_id] = {
            "upload_id": upload_id,
            "filename": filename,
            "df": df,
            "columns": columns,
            "header_row": effective_header_row,
            "first_data_row": first_data_row,
            "created_at": datetime.now(ZoneInfo("Asia/Jakarta")).isoformat(),
        }

    preset_mappings = {
        key: resolve_preset_mapping(preset, columns)
        for key, preset in TEMPLATES.items()
    }
    default_currency_columns = [c for c in columns if is_nominal_column(c)]

    return {
        "upload_id": upload_id,
        "filename": filename,
        "row_count": len(df),
        "header_row": effective_header_row,
        "first_data_row": first_data_row,
        "columns": columns,
        "default_currency_columns": default_currency_columns,
        "preset_mappings": preset_mappings,
    }


def get_cached_upload(upload_id: str) -> Dict[str, Any]:
    with _UPLOAD_CACHE_LOCK:
        item = _UPLOAD_CACHE.get(upload_id)
    if not item:
        raise ValueError("Uploaded file session expired or not found. Please re-upload the file.")
    return item


def get_templates_and_config() -> Dict[str, Any]:
    qiscus = QiscusWhatsAppAdapter()
    return {
        "qiscus_configured": qiscus.is_configured(),
        "default_namespace": qiscus.namespace,
        "default_language_code": os.getenv("QISCUS_LANGUAGE_CODE", "id"),
        "templates": get_all_templates(),
    }


def preview_broadcast_payload(
    upload_id: str,
    excel_row: int,
    phone_column: str,
    template_name: str,
    language_code: str,
    body_columns: List[str],
    header_columns: List[str],
    buttons: List[Dict[str, Any]],
    currency_columns: List[str],
    namespace: Optional[str] = None,
) -> Dict[str, Any]:
    cached = get_cached_upload(upload_id)
    df: pd.DataFrame = cached["df"]
    first_data_row: int = cached.get("first_data_row", 4)
    max_excel_row = len(df) + first_data_row - 1
    if excel_row < first_data_row or excel_row > max_excel_row:
        excel_row = first_data_row

    row = df.iloc[int(excel_row) - first_data_row]
    raw_phone = row.get(phone_column, "") if phone_column in df.columns else ""
    normalized_phone = normalize_phone(raw_phone)

    qiscus = QiscusWhatsAppAdapter(namespace=namespace)
    resolved_namespace = qiscus.namespace.strip()

    payload = QiscusWhatsAppAdapter.build_template_payload(
        phone=normalized_phone,
        namespace=resolved_namespace,
        template_name=template_name.strip(),
        language_code=language_code.strip() or "id",
        body_columns=body_columns,
        header_columns=header_columns,
        button_configs=buttons,
        row=row,
        currency_columns=currency_columns,
    )

    return {
        "excel_row": excel_row,
        "raw_phone": clean_value(raw_phone),
        "normalized_phone": normalized_phone,
        "payload": payload,
    }


def is_any_broadcast_running() -> Optional[int]:
    with _ACTIVE_RUNS_LOCK:
        for run_id in list(_ACTIVE_STOP_EVENTS.keys()):
            return run_id
    return None


def _worker_broadcast(
    run_id: int,
    stop_event: threading.Event,
    df: pd.DataFrame,
    first_data_row: int,
    phone_column: str,
    namespace: str,
    template_name: str,
    language_code: str,
    body_columns: List[str],
    header_columns: List[str],
    button_configs: List[Dict[str, Any]],
    currency_columns: List[str],
    delay_seconds: float,
    dry_run: bool,
):
    qiscus = QiscusWhatsAppAdapter(namespace=namespace)
    columns = [str(c) for c in df.columns]
    id_pelanggan_col = find_matching_column("ID Pelanggan", columns, default="")
    nama_pelanggan_col = find_matching_column("Nama Pelanggan", columns, default="")

    try:
        for idx, row in df.iterrows():
            if stop_event.is_set():
                with Session(engine) as session:
                    run = session.get(WaBroadcastRun, run_id)
                    if run:
                        run.status = "STOPPED"
                        run.stop_requested = True
                        run.message = "Stopped by user before the next message."
                        run.finished_at = datetime.now(ZoneInfo("Asia/Jakarta"))
                        session.commit()
                break

            excel_row = int(idx) + first_data_row

            raw_phone = row.get(phone_column, "") if phone_column in df.columns else ""
            phone = normalize_phone(raw_phone)
            id_pelanggan = (
                clean_value(row.get(id_pelanggan_col, ""))
                if id_pelanggan_col
                else None
            ) or None
            nama_pelanggan = (
                clean_value(row.get(nama_pelanggan_col, ""))
                if nama_pelanggan_col
                else None
            ) or None

            now_ts = datetime.now(ZoneInfo("Asia/Jakarta"))

            if not phone:
                with Session(engine) as session:
                    log_entry = WaBroadcastLog(
                        run_id=run_id,
                        excel_row=excel_row,
                        id_pelanggan=id_pelanggan,
                        nama_pelanggan=nama_pelanggan,
                        phone_number="",
                        status="SKIPPED",
                        http_status=None,
                        message_id="",
                        wa_id="",
                        qiscus_payload="",
                        qiscus_response="",
                        error_message="Empty/invalid phone number",
                        sent_at=None,
                    )
                    session.add(log_entry)
                    run = session.get(WaBroadcastRun, run_id)
                    if run:
                        run.processed += 1
                        run.failed += 1
                    session.commit()
                continue

            payload = QiscusWhatsAppAdapter.build_template_payload(
                phone=phone,
                namespace=namespace,
                template_name=template_name,
                language_code=language_code,
                body_columns=body_columns,
                header_columns=header_columns,
                button_configs=button_configs,
                row=row,
                currency_columns=currency_columns,
            )
            payload_json = json.dumps(payload, ensure_ascii=False)

            if dry_run:
                with Session(engine) as session:
                    log_entry = WaBroadcastLog(
                        run_id=run_id,
                        excel_row=excel_row,
                        id_pelanggan=id_pelanggan,
                        nama_pelanggan=nama_pelanggan,
                        phone_number=phone,
                        status="DRY_RUN",
                        http_status=None,
                        message_id="",
                        wa_id="",
                        qiscus_payload=payload_json,
                        qiscus_response=payload_json,
                        error_message="",
                        sent_at=now_ts,
                    )
                    session.add(log_entry)
                    run = session.get(WaBroadcastRun, run_id)
                    if run:
                        run.processed += 1
                        run.success += 1
                    session.commit()
            else:
                result = qiscus.send_template_message(payload)
                is_ok = bool(result.get("success"))
                http_status_val = result.get("http_status")
                http_status_int = (
                    int(http_status_val)
                    if isinstance(http_status_val, int)
                    else None
                )
                with Session(engine) as session:
                    log_entry = WaBroadcastLog(
                        run_id=run_id,
                        excel_row=excel_row,
                        id_pelanggan=id_pelanggan,
                        nama_pelanggan=nama_pelanggan,
                        phone_number=phone,
                        status="SUCCESS" if is_ok else "FAILED",
                        http_status=http_status_int,
                        message_id=result.get("message_id", ""),
                        wa_id=result.get("wa_id", ""),
                        qiscus_payload=payload_json,
                        qiscus_response=json.dumps(
                            result.get("response", {}), ensure_ascii=False
                        ),
                        error_message=result.get("error", ""),
                        sent_at=now_ts if is_ok else None,
                    )
                    session.add(log_entry)
                    run = session.get(WaBroadcastRun, run_id)
                    if run:
                        run.processed += 1
                        if is_ok:
                            run.success += 1
                        else:
                            run.failed += 1
                    session.commit()

            if delay_seconds > 0:
                stop_event.wait(delay_seconds)

            if stop_event.is_set():
                with Session(engine) as session:
                    run = session.get(WaBroadcastRun, run_id)
                    if run:
                        run.status = "STOPPED"
                        run.stop_requested = True
                        run.message = "Stop requested. No further messages will be sent."
                        run.finished_at = datetime.now(ZoneInfo("Asia/Jakarta"))
                        session.commit()
                break

        with Session(engine) as session:
            run = session.get(WaBroadcastRun, run_id)
            if run and run.status == "RUNNING":
                run.status = "COMPLETED"
                run.message = "Broadcast completed."
                run.finished_at = datetime.now(ZoneInfo("Asia/Jakarta"))
                session.commit()

    except Exception as exc:
        logger.exception(f"Worker error in WA broadcast run {run_id}: {exc}")
        with Session(engine) as session:
            run = session.get(WaBroadcastRun, run_id)
            if run:
                run.status = "FAILED"
                run.failed += 1
                run.message = f"Worker error: {exc}"
                run.finished_at = datetime.now(ZoneInfo("Asia/Jakarta"))
                session.commit()
    finally:
        with _ACTIVE_RUNS_LOCK:
            _ACTIVE_STOP_EVENTS.pop(run_id, None)


def start_broadcast_job(
    upload_id: str,
    phone_column: str,
    template_name: str,
    language_code: str,
    body_columns: List[str],
    header_columns: List[str],
    buttons: List[Dict[str, Any]],
    currency_columns: List[str],
    delay_seconds: float,
    dry_run: bool,
    namespace: Optional[str] = None,
    created_by: Optional[str] = None,
) -> Dict[str, Any]:
    active_run_id = is_any_broadcast_running()
    if active_run_id is not None:
        raise ValueError(
            f"A broadcast job (#{active_run_id}) is already running. Please wait or stop it first."
        )

    qiscus = QiscusWhatsAppAdapter(namespace=namespace)
    resolved_namespace = qiscus.namespace.strip()
    if not dry_run and not qiscus.is_configured():
        raise ValueError(
            "Missing Qiscus credentials (QISCUS_APP_ID, QISCUS_SECRET_KEY, QISCUS_CHANNEL_ID, QISCUS_WABA_NAMESPACE) in server .env"
        )

    cached = get_cached_upload(upload_id)
    df: pd.DataFrame = cached["df"].copy()
    filename: str = cached["filename"]
    first_data_row: int = cached.get("first_data_row", 4)

    with Session(engine) as session:
        run = WaBroadcastRun(
            filename=filename,
            template_name=template_name.strip(),
            namespace=resolved_namespace,
            language_code=language_code.strip() or "id",
            dry_run=dry_run,
            delay_seconds=float(delay_seconds),
            status="RUNNING",
            stop_requested=False,
            total=len(df),
            processed=0,
            success=0,
            failed=0,
            message="Broadcast running",
            created_by=created_by,
        )
        session.add(run)
        session.commit()
        session.refresh(run)
        run_dict = run.to_dict()
        run_id = run.id

    stop_event = threading.Event()
    with _ACTIVE_RUNS_LOCK:
        _ACTIVE_STOP_EVENTS[run_id] = stop_event

    thread = threading.Thread(
        target=_worker_broadcast,
        kwargs={
            "run_id": run_id,
            "stop_event": stop_event,
            "df": df,
            "first_data_row": first_data_row,
            "phone_column": phone_column,
            "namespace": resolved_namespace,
            "template_name": template_name.strip(),
            "language_code": language_code.strip() or "id",
            "body_columns": body_columns,
            "header_columns": header_columns,
            "button_configs": buttons,
            "currency_columns": currency_columns,
            "delay_seconds": float(delay_seconds),
            "dry_run": dry_run,
        },
        daemon=True,
        name=f"qiscus-broadcast-worker-{run_id}",
    )
    thread.start()

    return run_dict


def stop_broadcast_job(run_id: int) -> Dict[str, Any]:
    with _ACTIVE_RUNS_LOCK:
        stop_event = _ACTIVE_STOP_EVENTS.get(run_id)
    if stop_event:
        stop_event.set()

    with Session(engine) as session:
        run = session.get(WaBroadcastRun, run_id)
        if not run:
            raise ValueError(f"Broadcast run #{run_id} not found")
        if run.status == "RUNNING":
            run.stop_requested = True
            run.message = (
                "Stop requested. The current HTTP request, if any, will finish."
            )
            if not stop_event:
                run.status = "STOPPED"
                run.finished_at = datetime.now(ZoneInfo("Asia/Jakarta"))
            session.commit()
            session.refresh(run)
        return run.to_dict()


def get_broadcast_run_detail(run_id: int) -> Dict[str, Any]:
    with Session(engine) as session:
        run = session.get(WaBroadcastRun, run_id)
        if not run:
            raise ValueError(f"Broadcast run #{run_id} not found")
        logs = session.scalars(
            select(WaBroadcastLog)
            .where(WaBroadcastLog.run_id == run_id)
            .order_by(WaBroadcastLog.excel_row.asc(), WaBroadcastLog.id.asc())
        ).all()
        data = run.to_dict()
        data["results"] = [log.to_dict() for log in logs]
        return data


def list_broadcast_runs(page: int = 1, limit: int = 20) -> Dict[str, Any]:
    offset = (page - 1) * limit
    with Session(engine) as session:
        total = (
            session.scalar(select(func.count()).select_from(WaBroadcastRun))
            or 0
        )
        runs = session.scalars(
            select(WaBroadcastRun)
            .order_by(desc(WaBroadcastRun.id))
            .offset(offset)
            .limit(limit)
        ).all()
        return {
            "items": [r.to_dict() for r in runs],
            "total": total,
            "page": page,
            "limit": limit,
        }


def export_broadcast_run_csv(run_id: int) -> str:
    detail = get_broadcast_run_detail(run_id)
    results = detail.get("results", [])
    rows_for_csv = [
        {
            "excel_row": r["excel_row"],
            "id_pelanggan": r["id_pelanggan"],
            "nama_pelanggan": r["nama_pelanggan"],
            "phone": r["phone"],
            "status": r["status"],
            "http_status": r["http_status"],
            "message_id": r["message_id"],
            "wa_id": r["wa_id"],
            "error": r["error"],
            "response": r["response"],
            "sent_at": r["sent_at"] or "",
        }
        for r in results
    ]
    df = pd.DataFrame(rows_for_csv)
    return df.to_csv(index=False)
