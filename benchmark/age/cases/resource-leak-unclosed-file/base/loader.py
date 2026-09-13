def read_config(path):
    """Read and return the contents of a config file."""
    with open(path) as f:
        return f.read()
