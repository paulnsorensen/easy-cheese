def parse_amount(raw):
    """Parse a currency string into a float, or None if invalid."""
    try:
        return float(raw)
    except ValueError:
        return None
