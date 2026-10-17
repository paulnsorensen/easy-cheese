"""Strict validators for untrusted mapping input.

Every helper takes an untyped value plus the name of the field it came from,
raises ``ValueError`` naming that field, and returns the narrowed value so the
caller keeps its type information. They are the one home for rules that were
re-typed privately per module: the bool-excluding integer check, the exact
key-set check that names missing and unknown keys separately, and the
repository-relative path rule.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import PurePosixPath
from typing import TypeGuard, cast

__all__ = [
    "is_int",
    "is_relative_path",
    "require_exact_keys",
    "require_int",
    "require_list",
    "require_mapping",
    "require_relative_path",
    "require_str",
]


def is_int(value: object) -> TypeGuard[int]:
    """True for an ``int`` that is not a ``bool`` (``True == 1`` otherwise passes)."""
    return isinstance(value, int) and not isinstance(value, bool)


def require_int(value: object, field: str) -> int:
    if not is_int(value):
        raise ValueError(f"{field} must be an integer")
    return value


def require_str(value: object, field: str) -> str:
    """A ``str`` with at least one non-whitespace character, returned unstripped."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def require_list(value: object, field: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list")
    return cast("list[object]", value)


def require_mapping(value: object, field: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be a mapping")
    return cast("dict[str, object]", value)


def require_exact_keys(
    values: Mapping[str, object],
    expected: Iterable[str],
    label: str,
    *,
    error: type[ValueError] = ValueError,
) -> None:
    """Reject ``values`` unless its key set is exactly ``expected``.

    Missing and unknown keys are reported separately, each sorted, so the
    caller can tell a truncated payload from a stale one. ``error`` selects
    the raised type for callers that own a ``ValueError`` subclass.
    """
    wanted = set(expected)
    missing = sorted(wanted - values.keys())
    unknown = sorted(values.keys() - wanted)
    if missing or unknown:
        details: list[str] = []
        if missing:
            details.append(f"missing {missing!r}")
        if unknown:
            details.append(f"unknown {unknown!r}")
        raise error(f"{label} keys mismatch: {', '.join(details)}")


def is_relative_path(value: object) -> TypeGuard[str]:
    """True for a non-blank POSIX path that cannot escape the repository.

    Rejects absolute paths, backslashes, a colon in the first segment,
    ``..`` segments, and NUL. ``"."`` and a trailing ``/`` pass: both stay
    inside the repository, and whether they name something useful is the
    caller's rule.
    """
    if not isinstance(value, str) or not value.strip():
        return False
    first = value.split("/", 1)[0]
    path = PurePosixPath(value)
    return not (
        path.is_absolute()
        or "\\" in value
        or ":" in first
        or ".." in path.parts
        or "\x00" in value
    )


def require_relative_path(value: object, field: str) -> str:
    """``is_relative_path`` as a check; a blank value is named as such."""
    text = require_str(value, field)
    if not is_relative_path(text):
        raise ValueError(f"{field} must be a repository-relative path")
    return text
