import re

def parse_rupiah(value) -> int:
    """
    Convert Indonesian Rupiah string to integer.
    Example:
      'Rp. 150,000' -> 150000
      'Rp150.000'   -> 150000
      '150000'      -> 150000
    """
    if value is None:
        return 0

    if isinstance(value, (int, float)):
        return int(value)

    # Convert to string
    s = str(value)

    # Remove Rp, dots, commas, spaces
    s = re.sub(r"[^\d]", "", s)

    if s == "":
        return 0

    return int(s)
