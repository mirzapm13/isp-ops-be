from typing import Any, Dict, List
from urllib.parse import urlparse
import pandas as pd


def clean_value(value: Any) -> str:
    if pd.isna(value):
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def normalize_phone(value: Any) -> str:
    digits = "".join(ch for ch in clean_value(value) if ch.isdigit())
    if not digits:
        return ""
    if digits.startswith("62"):
        return "+" + digits
    if digits.startswith("0"):
        return "+62" + digits[1:]
    if digits.startswith("8"):
        return "+62" + digits
    return digits


def is_nominal_column(col_name: str) -> bool:
    if not col_name or col_name == "__NO_VALUE__":
        return False
    name = col_name.strip().lower().replace("_", " ")
    if "nominal" in name:
        return True
    if any(
        k in name
        for k in (
            "jumlah pembayaran",
            "total pembayaran",
            "nilai pembayaran",
            "total tagihan",
        )
    ):
        return True
    return False


def format_rupiah(value: Any) -> str:
    if pd.isna(value):
        return ""
    val_str = str(value).strip()
    if not val_str:
        return ""

    raw = val_str
    for prefix in ("rp.", "rp", "idr.", "idr"):
        if raw.lower().startswith(prefix):
            raw = raw[len(prefix) :].strip()
            break

    cleaned = raw.replace(" ", "")
    num = None
    try:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            num = round(value)
        else:
            if "." in cleaned and "," not in cleaned:
                parts = cleaned.split(".")
                if len(parts) > 1 and all(len(p) == 3 for p in parts[1:]):
                    num = int("".join(parts))
                else:
                    num = round(float(cleaned))
            elif "," in cleaned and "." not in cleaned:
                parts = cleaned.split(",")
                if len(parts) > 1 and all(len(p) == 3 for p in parts[1:]):
                    num = int("".join(parts))
                else:
                    num = round(float(cleaned))
            elif "." in cleaned and "," in cleaned:
                if cleaned.rfind(",") > cleaned.rfind("."):
                    cleaned_no_thousand = cleaned.replace(".", "").split(",")[0]
                    num = int(cleaned_no_thousand)
                else:
                    cleaned_no_thousand = cleaned.replace(",", "").split(".")[0]
                    num = int(cleaned_no_thousand)
            else:
                if cleaned.replace("-", "").isdigit():
                    num = int(cleaned)
                else:
                    num = round(float(cleaned))
    except Exception:
        num = None

    if num is not None:
        if num < 0:
            formatted_num = f"{abs(num):,}".replace(",", ".")
            return f"-Rp {formatted_num}"
        formatted_num = f"{num:,}".replace(",", ".")
        return f"Rp {formatted_num}"

    return val_str


def format_field_value(col: str, value: Any, currency_cols: Any = None) -> str:
    if col == "__NO_VALUE__":
        return "-"
    cleaned = clean_value(value)
    if not cleaned:
        return ""
    is_curr = (
        (col in currency_cols)
        if currency_cols is not None
        else is_nominal_column(col)
    )
    if is_curr:
        return format_rupiah(value)
    return cleaned


def remove_url_domain(url: str) -> str:
    parsed_url = urlparse(url)
    path_and_params = parsed_url.path
    if parsed_url.query:
        path_and_params += f"?{parsed_url.query}"
    return path_and_params


def find_matching_column(
    target: str, available_columns: List[str], default: str = "__NO_VALUE__"
) -> str:
    if not target or target == "__NO_VALUE__":
        return "__NO_VALUE__"
    if target in available_columns:
        return target
    norm_target = target.strip().lower().replace("_", " ")
    for col in available_columns:
        if col.strip().lower().replace("_", " ") == norm_target:
            return col
    return default


def resolve_preset_mapping(
    preset: Dict[str, Any], columns: List[str]
) -> Dict[str, Any]:
    parameter_columns = ["__NO_VALUE__"] + columns
    phone_col = preset.get("phone_column", "")
    matched_phone = find_matching_column(
        phone_col, columns, default=columns[0] if columns else ""
    )

    header_cols = [
        find_matching_column(col, parameter_columns)
        for col in preset.get("header_columns", [])
    ]
    body_cols = [
        find_matching_column(col, parameter_columns)
        for col in preset.get("body_columns", [])
    ]

    curr_cols = [
        find_matching_column(c, columns, default="")
        for c in preset.get("currency_columns", [])
    ]
    matched_curr = [c for c in curr_cols if c and c != "__NO_VALUE__"]
    if not matched_curr:
        matched_curr = [c for c in columns if is_nominal_column(c)]

    buttons = []
    for i, btn in enumerate(preset.get("buttons", [])):
        buttons.append(
            {
                "index": int(btn.get("index", i)),
                "sub_type": btn.get("sub_type", "quick_reply"),
                "column": find_matching_column(
                    btn.get("column", "__NO_VALUE__"), parameter_columns
                ),
            }
        )

    return {
        "template_name": preset.get("name", ""),
        "language_code": preset.get("language_code", "id"),
        "phone_column": matched_phone,
        "header_columns": header_cols,
        "body_columns": body_cols,
        "currency_columns": matched_curr,
        "buttons": buttons,
    }
