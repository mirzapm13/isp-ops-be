import re

def normalize_column_name(col: str) -> str:
    """
    Convert column name to snake_case and remove special characters.
    """
    col = col.strip().lower()

    # Replace separators with underscore
    col = re.sub(r"[ /+()-]+", "_", col)

    # Remove any remaining non-alphanumeric characters
    col = re.sub(r"[^a-z0-9_]", "", col)

    # Collapse multiple underscores
    col = re.sub(r"_+", "_", col)

    # Remove leading/trailing underscore
    col = col.strip("_")

    return col
