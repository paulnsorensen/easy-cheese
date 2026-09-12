def append_item(item, bucket=None):
    """Append item to bucket, creating a new list if none given."""
    if bucket is None:
        bucket = []
    bucket.append(item)
    return bucket
