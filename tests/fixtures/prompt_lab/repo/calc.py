"""Small numeric helpers used by the agent laboratory fixture tasks."""


def mean(values: list[float]) -> float:
    """Return the arithmetic mean of a non-empty list."""
    if not values:
        raise ValueError("mean of empty list")
    return sum(values) / len(values)


def clamp(value: float, low: float, high: float) -> float:
    """Return value limited to the closed range [low, high]."""
    if low > high:
        raise ValueError("low must not exceed high")
    return max(low, min(value, high))


def median(values: list[float]) -> float:
    """Return the median of a non-empty list."""
    if not values:
        raise ValueError("median of empty list")
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2
