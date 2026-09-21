import os
import tempfile
import requests
import pandas as pd
from typing import List, Dict, Any


DEFAULT_EBILLING_URL = "https://e.ebilling.id/billing/admin/warga/data_warga_sudah_bayar_admin.php"


def normalize_phone_number(phone: Any) -> str:
    """
    Normalizes Indonesian phone numbers into international format without leading '+' (e.g. 628123456789).
    """
    if pd.isna(phone) or not phone:
        return ""
    
    clean = str(phone).strip()
    # Remove float decimal points if parsed as number
    if clean.endswith(".0"):
        clean = clean[:-2]
    
    # Keep digits only
    clean = "".join(filter(str.isdigit, clean))
    
    if clean.startswith("0"):
        clean = "62" + clean[1:]
    elif clean.startswith("8"):
        clean = "62" + clean
    
    return clean


def download_receipt_excel(data_account: str = "23213", tglskg: str | None = None, url: str | None = None) -> str:
    """
    Downloads receipt excel file from e.ebilling.id and saves to a temp file path.
    """
    target_url = url or DEFAULT_EBILLING_URL
    params = {}
    if "tglskg=" not in target_url:
        params["data_account"] = data_account
        if tglskg:
            params["tglskg"] = tglskg

    # print(target_url, data_account, tglskg)       

    response = requests.get(target_url, params=params, timeout=30)
    response.raise_for_status()

    with tempfile.NamedTemporaryFile(delete=False, suffix=".xls") as tmp:
        tmp.write(response.content)
        return tmp.name


def parse_receipt_excel(file_path: str) -> List[Dict[str, Any]]:
    """
    Parses the receipt Excel file starting at Row 3 (header index 2).
    Extracts required fields for WhatsApp Qiscus broadcast.
    """
    df = None
    try:
        df = pd.read_excel(file_path, header=0)
    except Exception:
        # Fallback for HTML-based XLS tables
        tables = pd.read_html(file_path, header=0, converters={"Tlp": str, "ID Pelanggan": str})
        if not tables:
            raise ValueError("No table found in Excel file")
        df = tables[0]

    if df is None or df.empty:
        return []

    # Clean up column names
    df.columns = [str(c).strip() for c in df.columns]

    records = []
    for _, row in df.iterrows():
        id_pelanggan = str(row.get("ID Pelanggan", "")).strip()
        if not id_pelanggan or id_pelanggan.lower() == "nan" or id_pelanggan.lower() == "unnamed: 1":
            continue

        raw_phone = row.get("Tlp", "")
        phone_number = normalize_phone_number(raw_phone)
        if not phone_number:
            continue

        # Extract Nominal (check both 'Standar Harga Dibayar' and 'Manfaat Pembayaran')
        # nominal = str(row.get("Standar Harga Dibayar", "") or row.get("Manfaat Pembayaran", "")).strip()

        records.append({
            "id_pelanggan": id_pelanggan,
            "nama_pelanggan": str(row.get("Nama Pelanggan", "")).strip(),
            "alamat": str(row.get("Alamat", "")).strip(),
            "nominal_pembayaran": str(row.get("Nominal Pembayaran", "")).strip(),
            "nama_langganan": str(row.get("Nama Langganan", "")).strip(),
            #Make keterangan none first
            # "keterangan_langganan": str(row.get("Keterangan Langganan", "")).strip(),
            "keterangan_langganan": " ",
            "bulan": str(row.get("Bulan", "")).strip(),
            "bukti_link": str(row.get("Bukti", "")).strip(),
            "phone_number": phone_number,
            "waktu_entry": str(row.get("Waktu Entry", "")).strip(),
        })

    return records
