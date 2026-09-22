import os
import tempfile
import requests
import re
import math
from typing import Any
from decimal import Decimal, InvalidOperation
from app.adapters.billing.column_normalize import normalize_column_name
from app.adapters.billing.gsheet_reader import read_google_sheet
from app.config.database import engine
from app.models.billing import BillingCustomer
from sqlalchemy import text, types, or_
import pandas as pd
from datetime import date, timedelta
from app.config.database import SessionLocal
import numpy as np
from app.adapters.billing.excel_reader import read_billing_excel

from app.services.pppoe_service import isolir_user_all_routers

def get_billing_customers_paginated(
    *,
    search: str | None = None,
    page: int = 1,
    limit: int = 20,
) -> dict[str, Any]:
    """
    Retrieve paginated billing customers with optional search filtering by
    id_pelanggan, ip_secret, nama_pelanggan, or tlp.
    """
    db = SessionLocal()
    try:
        query = db.query(BillingCustomer)

        if search and search.strip():
            term = f"%{search.strip()}%"
            query = query.filter(
                or_(
                    BillingCustomer.id_pelanggan.ilike(term),
                    BillingCustomer.ip_secret.ilike(term),
                    BillingCustomer.nama_pelanggan.ilike(term),
                    BillingCustomer.tlp.ilike(term),
                )
            )

        total = query.count()
        total_pages = math.ceil(total / limit) if total > 0 else 0

        customers = (
            query
            .order_by(BillingCustomer.id.asc())
            .offset((page - 1) * limit)
            .limit(limit)
            .all()
        )

        return {
            "data": [r.to_dict() for r in customers],
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "total_pages": total_pages,
            }
        }
    finally:
        db.close()


def get_all_billing():
    """
    Retrieve all billing entries from all routers.
    Returns a list of billing entries.
    """
    db = SessionLocal()
    try:
        return db.query(BillingCustomer).all()
    except Exception as e:
        raise e
    finally:
        db.close()


def get_billing_by_ip_secret(ip_secret: str) -> list[BillingCustomer]:
    """
    Get all billing customer rows matching ip_secret.
    Duplicates are allowed.
    """
    db = SessionLocal()
    try:
        return (
            db.query(BillingCustomer)
            .filter(BillingCustomer.ip_secret == ip_secret)
            .all()
        )
    finally:
        db.close()

def import_billing_data(file_path: str, filename: str):
    """
    Import billing data from an Excel file.
    Returns a list of billing records as dictionaries.
    """
    
    df = read_billing_excel(file_path)

    # Normalize column names
    df.columns = [normalize_column_name(c) for c in df.columns]
    df = df.replace({np.nan: None})
    
    # Example mapping — adjust to your real columns
    records = []
    for _, row in df.iterrows():
        records.append({
        "id_pelanggan": row.get("id_pelanggan"),
        "ip_secret": row.get("ip_secret"),
        "tlp": row.get("tlp"),
        "alamat": row.get("alamat"),

        "nama_pelanggan": row.get("nama_pelanggan"),
        "nama_langganan": row.get("nama_langganan"),
        "harga": parse_harga(row.get("harga")),

        "status_langganan": row.get("status_langganan"),
        "jatuh_tempo": parse_excel_date(row.get("jatuh_tempo")),

        "nama_router": row.get("nama_router"),
        "id_olt": row.get("id_olt"),
        "id_odp": row.get("id_odp"),

        "source_file": filename
        # imported_at handled by DB default
        })

    return records


def insert_billing_records(records: list[dict]) -> None:
    """
    FULL REPLACE import:
    - Delete all existing billing records
    - Insert all records from the new Excel file
    """

    if not records:
        return

    with engine.begin() as conn:
        # 1. Remove all existing billing data
        BillingCustomer.metadata.create_all(engine)
        conn.execute(text("TRUNCATE TABLE billing_customers RESTART IDENTITY"))

        # 2. Bulk insert new records
        conn.execute(
            BillingCustomer.__table__.insert(),
            records
        )

def parse_harga(value):
    """
    Convert harga like 'Rp. 150,000' into Decimal(150000)
    """
    if value is None:
        return None

    # Convert to string and normalize
    s = str(value).strip()

    if not s:
        return None

    # Remove currency symbols and spaces
    s = s.lower()
    s = s.replace("rp", "")
    s = s.replace(" ", "")

    # Remove thousand separators (.,)
    s = re.sub(r"[.,]", "", s)

    try:
        return Decimal(s)
    except InvalidOperation:
        return None

def parse_excel_date(value):
    """
    Convert Excel date / string / pandas timestamp into Python date.
    """
    if value is None or pd.isna(value):
        return None

    # Case 1: pandas Timestamp
    if isinstance(value, pd.Timestamp):
        return value.date()

    # Case 2: already a date
    if isinstance(value, date):
        return value

    # Case 3: Excel serial number
    if isinstance(value, (int, float)):
        # Excel date starts at 1899-12-30
        return date(1899, 12, 30) + timedelta(days=int(value))

    # Case 4: string date
    try:
        return pd.to_datetime(value).date()
    except Exception:
        return None

def bulk_isolir_from_file(file_bytes: bytes):
    df = read_billing_excel(file_bytes)
    df = df.head(10)

    # Filter GPON,XPON,TPLINK,Static,null
    mask = (
        df["IP Address / Secret"].astype(str).str.contains(r"[A-Za-z]") &
        df["IP Address / Secret"].astype(str).str.contains(r"\d") &
        df["Catatan"].isna()
    )

    # Filter GPON,XPON,TPLINK,Static,null
    isolir_df = df[mask]
    
    # Insert GPON,XPON,TPLINK,Static,null
    unisolir_df = df[~mask]
    
    # isolir_df = isolir_df.replace({np.nan: None}).to_dict(orient="records")
    unisolir_df = unisolir_df.replace({np.nan: None}).to_dict(orient="records")
    
    # return {
    #     "isolir": {
    #         "data": isolir_df,
    #         "count" : len(isolir_df)
    #         },
    #     "no-isolir": {
    #         "data":unisolir_df,
    #         "count": len(unisolir_df)
    #         }
    # }

    usernames = isolir_df['IP Address / Secret'].values.tolist()

    summary = {
        "total_input": len(usernames),
        "processed": [],
        "unisolir" : unisolir_df,
        "report" : []
    }

    for username in usernames:
        result = isolir_user_all_routers(username)

        summary["processed"].append(result)
        
        summary["report"].append({
        "username": username,
        "disconnected": (",").join(result["disconnected"]),
        "status": result["status"],
        "errors": result["errors"],
        "found_secret":  (",").join(result["found_on"]),
    })
        
    excel_file = 'isolir_report.xlsx'
    
    # unisolir_xl = unisolir_df.to_excel()
    isolir_report = pd.DataFrame(summary["report"])
    unisolir_report = pd.DataFrame(unisolir_df)

    with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
        unisolir_report.to_excel(writer, sheet_name='unisolir', index=False)
        isolir_report.to_excel(writer, sheet_name='report', index=False)

    return summary

def isolir_from_gsheet(sheet_id: str, worksheet_gid: str):
    df = read_google_sheet(sheet_id, worksheet_gid)
    insert_to_db(df)
    # df = df.head(100)

    # return df.replace({np.nan: None}).to_dict(orient="records")

    # Filter GPON,XPON,TPLINK,Static,null
    mask = (
        df["IP Address / Secret"].astype(str).str.contains(r"[A-Za-z]") &
        df["IP Address / Secret"].astype(str).str.contains(r"\d") &
        df["mas Mirza"].isna()
    )

    # Filter GPON,XPON,TPLINK,Static,null
    isolir_df = df[mask]
    
    # Insert GPON,XPON,TPLINK,Static,null
    unisolir_df = df[~mask]
    
    # isolir_df = isolir_df.replace({np.nan: None}).to_dict(orient="records")
    unisolir_df = unisolir_df.replace({np.nan: None}).to_dict(orient="records")
    
    # return {
    #     "isolir": {
    #         "data": isolir_df,
    #         "count" : len(isolir_df)
    #         },
    #     "no-isolir": {
    #         "data":unisolir_df,
    #         "count": len(unisolir_df)
    #         }
    # }

    usernames = isolir_df['IP Address / Secret'].values.tolist()

    summary = {
        "total_input": len(usernames),
        "processed": [],
        "unisolir" : unisolir_df,
        "report" : []
    }

    for username in usernames:
        result = isolir_user_all_routers(username)

        summary["processed"].append(result)
        
        summary["report"].append({
        "username": username,
        "disconnected": (",").join(result["disconnected"]),
        "status": result["status"],
        "errors": result["errors"],
        "found_secret":  (",").join(result["found_on"]),
    })
        
    excel_file = 'isolir_report.xlsx'
    
    # unisolir_xl = unisolir_df.to_excel()
    isolir_report = pd.DataFrame(summary["report"])
    unisolir_report = pd.DataFrame(unisolir_df)

    with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
        unisolir_report.to_excel(writer, sheet_name='unisolir', index=False)
        isolir_report.to_excel(writer, sheet_name='report', index=False)

    return summary

def insert_to_db(df):

    dtype ={
        'No': types.SMALLINT(),
        'Nominal Pembayaran': types.Numeric(12,2)
    }

    try:
        with engine.begin() as conn:
            conn.execute(text("TRUNCATE TABLE isolir_list"))
            df.to_sql(
                "isolir_list",
                con=conn,
                if_exists="append",
                index=False,
                chunksize=500,
                method="multi",
                dtype=dtype
            )
    except Exception as e:
        raise e


def import_billing_from_url(url: str | None = None) -> dict:
    """
    Download billing export file from a remote URL (defaulting to EBILLING_EXPORT_URL or passed url),
    parse the file and replace existing billing records in the database.
    """
    target_url = url or os.getenv(
        "EBILLING_EXPORT_URL",
        "https://e.ebilling.id/export/data_pelanggan_admin.php?data_account=23213&data_lokasi=12719"
    )

    response = requests.get(target_url, timeout=60)
    response.raise_for_status()

    with tempfile.NamedTemporaryFile(suffix=".xls", delete=False) as tmp:
        tmp.write(response.content)
        tmp_path = tmp.name

    try:
        filename = "ebilling_export.xls"
        records = import_billing_data(tmp_path, filename)

        if not records:
            raise ValueError("No valid billing records found in downloaded file")

        insert_billing_records(records)

        return {
            "status": "OK",
            "rows_imported": len(records),
            "source_url": target_url
        }
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)