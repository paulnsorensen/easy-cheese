def build_header(name, value):
    """Build an HTTP-style header line as a string."""
    if isinstance(value, bytes):
        value = value.decode("utf-8")
    return name + ": " + value
