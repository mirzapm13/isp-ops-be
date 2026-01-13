import pandas as pd

def read_google_sheet(sheet_id: str, worksheet_gid: int = 0) -> pd.DataFrame:
    url = (
        f"https://docs.google.com/spreadsheets/d/{sheet_id}/export"
        f"?format=csv&gid={worksheet_gid}"
    )
    df = pd.read_csv(url, dtype=str)
    return df
