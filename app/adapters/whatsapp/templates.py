"""
Predefined WhatsApp Broadcast Templates Configuration.
"""

from typing import Any, Dict

TEMPLATES: Dict[str, Dict[str, Any]] = {
    "isolir_info": {
        "name": "isolir_info",
        "description": "isolir_info (Isolir Notification & Payment Reminder)",
        "language_code": "id",
        "phone_column": "Tlp",
        "header_columns": [],
        "body_columns": [
            "ID Pelanggan",
            "Nama Pelanggan",
            "Alamat",
            "Nama Langganan",
            "Tanggal Jatuh Tempo",
            "Nominal Pembayaran",
            "__NO_VALUE__",
            "Nominal Pembayaran",
            "Link Tripay",
        ],
        "currency_columns": [
            "Nominal Pembayaran",
        ],
        "buttons": [
            {
                "index": 0,
                "sub_type": "url",
                "column": "Link Tripay",
            }
        ],
    },
    "test_template": {
        "name": "test_template",
        "description": "test_template (Isolir Notification & Payment Reminder)",
        "language_code": "id",
        "phone_column": "Tlp",
        "header_columns": [],
        "body_columns": [
            "ID Pelanggan",
            "Nama Pelanggan",
            "Alamat",
            "Nama Langganan",
            "Tanggal Jatuh Tempo",
            "Nominal Pembayaran",
            "__NO_VALUE__",
            "Nominal Pembayaran",
            "Link Tripay",
        ],
        "currency_columns": [
            "Nominal Pembayaran",
        ],
        "buttons": [
            {
                "index": 0,
                "sub_type": "url",
                "column": "Link Tripay",
            }
        ],
    },
    "kwitansi_pembayaran": {
        "name": "kwitansi_pembayaran",
        "description": "kwitansi_pembayaran (Payment Receipt Notification)",
        "language_code": "id",
        "phone_column": "Tlp",
        "header_columns": [],
        "body_columns": [
            "Nama Pelanggan",
            "Alamat",
            "Nominal Pembayaran",
            "Nama Langganan",
            "__NO_VALUE__",
            "Bulan",
            "Bukti",
        ],
        "currency_columns": [
            "Nominal Pembayaran",
        ],
        "buttons": [],
    },
}


def get_all_templates() -> Dict[str, Dict[str, Any]]:
    """Return all available predefined templates."""
    return TEMPLATES


def get_template(name: str) -> Dict[str, Any]:
    """Retrieve template configuration by name."""
    return TEMPLATES.get(name, {})
