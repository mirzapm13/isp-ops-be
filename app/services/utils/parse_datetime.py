from datetime import datetime
import pandas as pd

def parse_datetime(value) -> datetime | None:
    """
    Normalize datetime strictly in format:
    YYYY/MM/DD HH:MM:SS
    Example: 2026/01/15 15:35:41
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None

    if isinstance(value, datetime):
        return value

    s = str(value).strip()

    if s == "":
        return None

    try:
        return datetime.strptime(s, "%Y/%m/%d %H:%M:%S")
    except ValueError as e:
        raise ValueError(
            f"Invalid Waktu Entry format (expected YYYY/MM/DD HH:MM:SS): {value!r}"
        ) from e