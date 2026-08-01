"""Schema version tolerance: read a payload without trusting its vintage.

Every document and manifest carries a ``schema_version`` stamp, so a reader
built against version N can tell what it is holding before it acts on it —
current, one version behind, too old to read, or written by a newer producer.
A future stamp is not a rejection: recognized fields still parse, unknown ones
are ignored, and the caller gets ``FUTURE`` so it can decide.

``load`` never raises. It accumulates every problem it found as
``where.key must be ...`` strings, the same format shared/scripts/schema.py
emits, because the fan-out validators report all problems in one pass rather
than stopping at the first.
"""

from __future__ import annotations

from collections.abc import Iterator
from enum import Enum, auto
from typing import Any, Generic, TypeVar

import attrs
import cattrs
from attrs import define

SCHEMA_VERSION = 1
MIN_READABLE = 1  # N-1 tolerance; widens as the schema evolves
STAMP_KEY = "schema_version"

T = TypeVar("T")

# Default converter semantics: unknown keys are ignored, which is exactly what
# a FUTURE-stamped payload needs.
_converter = cattrs.Converter()


class Provenance(Enum):
    CURRENT = auto()
    PRIOR = auto()
    UNSTAMPED = auto()
    STALE = auto()
    FUTURE = auto()


@define(frozen=True)
class Loaded(Generic[T]):
    value: T | None
    provenance: Provenance
    problems: list[str]


def classify_stamp(stamp: int | None) -> Provenance:
    """Provenance of a payload stamped `stamp`; None means it carried no stamp."""
    if stamp is None:
        return Provenance.UNSTAMPED
    if stamp > SCHEMA_VERSION:
        return Provenance.FUTURE
    if stamp == SCHEMA_VERSION:
        return Provenance.CURRENT
    if stamp >= MIN_READABLE:
        return Provenance.PRIOR
    return Provenance.STALE


def load(raw: dict[str, Any], cls: type[T], *, strict: bool) -> Loaded[T]:
    """Structure `raw` into `cls`, reporting problems instead of raising.

    strict=True  -> cattrs.structure; ClassValidationError flattened into
                    problems, value=None on failure.
    strict=False -> best-effort: documented defaults filled, every gap
                    recorded in problems, still returns a usable value.
    Neither mode raises.

    Strictness is the caller's call: markdown documents are read lenient (a
    human wrote them, so a missing optional field is a gap to report, not a
    rejection) while machine-written manifests are read strict.
    """
    where = cls.__name__
    problems: list[str] = []

    stamp = raw.get(STAMP_KEY)
    if stamp is not None and (isinstance(stamp, bool) or not isinstance(stamp, int)):
        problems.append(f"{where}.{STAMP_KEY} must be an integer")
        stamp = None
    provenance = classify_stamp(stamp)

    if strict:
        try:
            return Loaded(_converter.structure(raw, cls), provenance, problems)
        except Exception as exc:
            problems.extend(message for _, message in _flatten(exc, where))
            return Loaded(None, provenance, problems)

    value, gaps = _best_effort(raw, cls, where)
    return Loaded(value, provenance, problems + gaps)


def _best_effort(raw: dict[str, Any], cls: type[T], where: str) -> tuple[T | None, list[str]]:
    """Structure what is recognizable, dropping each unstructurable field back
    to its documented default and recording why."""
    problems: list[str] = []
    payload: dict[str, Any] = {}
    for attribute in attrs.fields(cls):
        if attribute.name in raw:
            payload[attribute.name] = raw[attribute.name]
        elif attribute.default is attrs.NOTHING:
            problems.append(f"{where}.{attribute.name} is required")
        else:
            problems.append(f"{where}.{attribute.name} must be present; using default")

    while True:
        try:
            return _converter.structure(payload, cls), problems
        except Exception as exc:
            failures = _flatten(exc, where)
            problems.extend(message for _, message in failures)
            droppable = {name for name, _ in failures if name in payload}
            if not droppable:
                return None, problems
            for name in droppable:
                del payload[name]


def _flatten(exc: BaseException, where: str) -> list[tuple[str | None, str]]:
    """Flatten a cattrs ClassValidationError (an ExceptionGroup) into house-format
    problems paired with the attribute each one blames."""
    problems: list[tuple[str | None, str]] = []
    for leaf in _leaves(exc):
        name = _blamed_attribute(leaf)
        if name is None:
            problems.append((None, f"{where} must be a structurable mapping: {leaf}"))
        elif isinstance(leaf, KeyError):
            problems.append((name, f"{where}.{name} is required"))
        else:
            problems.append((name, f"{where}.{name} must be valid: {leaf}"))
    return problems


def _leaves(exc: BaseException) -> Iterator[BaseException]:
    nested = getattr(exc, "exceptions", None)
    if not nested:
        yield exc
        return
    for sub in nested:
        yield from _leaves(sub)


_ATTRIBUTE_NOTE = " @ attribute "


def _blamed_attribute(exc: BaseException) -> str | None:
    """cattrs tags each leaf with a note like
    ``Structuring class Widget @ attribute count``."""
    for note in getattr(exc, "__notes__", ()):
        _, marker, name = note.partition(_ATTRIBUTE_NOTE)
        if marker:
            return name
    return None
