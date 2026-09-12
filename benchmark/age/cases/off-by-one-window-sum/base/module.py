def sum_last_n(values, n):
    """Sum the last n elements of values."""
    total = 0
    start = len(values) - n
    for i in range(start, len(values)):
        total += values[i]
    return total
