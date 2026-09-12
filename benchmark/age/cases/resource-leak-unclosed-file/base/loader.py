def read_config(path):
    """Read and return the contents of a config file."""
    f = open(path)
    data = f.read()
    f.close()
    return data
