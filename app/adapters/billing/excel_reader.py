import pandas as pd

def read_billing_excel(file_path: str) -> pd.DataFrame:
    """
    Read billing Excel file.
    Supports:
    - real .xls/.xlsx
    - HTML-based .xls
    """

    try:
        df = pd.read_excel(file_path)
        return df
    except Exception as e:
        # fallback for HTML-based XLS
        tables = pd.read_html(file_path, converters={
        "Tlp": lambda x: str(x)
        })
        
        df = tables[0]

        if not tables:
            raise ValueError("No tables found in Excel file")
        return df