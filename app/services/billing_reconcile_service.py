import requests
import pandas as pd
from io import BytesIO
import os

from app.adapters.billing.excel_reader import read_billing_excel


def fetch_successful_payments_xls() -> pd.DataFrame:
    response = requests.get(
        os.getenv('PAID_URL'),
        timeout=30,
    )
    response.raise_for_status()

    content_type = response.headers.get("Content-Type", "")
    if "excel" not in content_type and "spreadsheet" not in content_type:
        # not fatal yet, but good guard
        pass

    return read_billing_excel(BytesIO(response.content))
