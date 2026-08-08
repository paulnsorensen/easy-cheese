"""Schema version tolerance: read a payload without trusting its vintage.

Every document and manifest carries a ``schema_version`` stamp, so a reader
built against version N can tell what it is holding before it acts on it --
current, one version behind, too old to read, or written by a newer producer.
A future stamp is not a rejection: recognized fields still parse, unknown ones
are ignored, and the caller gets ``FUTURE`` so it can decide.

``load`` never raises. It accumulates every problem it found as
``where.key must be ...`` strings, the same format shared/scripts/schema.py
emits, because the fan-out validators report all problems in one pass rather
than stopping at the first.

Two things make that possible and neither is cattrs' default. Structuring
coerces primitives -- ``str(v)``, ``int(v)``, ``list(v)`` -- so a payload that
is wrong is silently made right; the hooks below type-check instead, because a
reader asking "is this document trustworthy" must not be handed a repaired
copy of an untrustworthy one. And attrs validators run inside ``__init__``,
where cattrs cannot attribute their failures to a field, so structuring runs
with validators disabled and the field rules are applied afterwards over the
structured tree, which is also what makes ``curds[2].files must be ...``
possible.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import Enum, auto
from typing import Any, Generic, TypeVar, get_origin

import attrs
import cattrs
from attrs import define, field
from cattrs.cols import list_structure_factory
from cattrs.errors import AttributeValidationNote, IterableValidationNote
from cattrs.gen import make_dict_structure_fn

SCHEMA_VERSION = 1
MIN_READABLE = 1  # N-1 tolerance; widens as the schema evolves
STAMP_KEY = "schema_version"

T = TypeVar("T")

__all__ = [
    "MIN_READABLE",
    "SCHEMA_VERSION",
    "STAMP_KEY",
    "Loaded",
    "Provenance",
    "classify_stamp",
    "load",
]


def _exact(
    expected: type | tuple[type, ...], label: str, *, boolean: bool = False
) -> Any:
    """A structure hook that checks a primitive instead of calling it.

    ``bool`` and ``int`` stay distinct in both directions: ``True`` is not an
    integer field's value and ``1`` is not a flag's.

    A `str`-valued Enum is a `str` subclass, so cattrs dispatches it here
    ahead of its own Enum hook; the member lookup is delegated back rather than
    shadowed, which would let any string through as a phase or a status.
    """

    def hook(value: object, _type: Any = None) -> Any:
        if isinstance(_type, type) and issubclass(_type, Enum):
            try:
                return _type(value)
            except ValueError:
                allowed = ", ".join(str(member.value) for member in _type)
                raise ValueError(f"must be one of: {allowed}") from None
        if isinstance(value, bool) is not boolean or not isinstance(value, expected):
            raise TypeError(f"must be {label}, not {type(value).__name__}")
        return value

    return hook


def _guarded_list(type_: Any, converter: cattrs.BaseConverter) -> Any:
    """cattrs structures any iterable into a list, which turns a bare string
    into its characters. Require an actual list, then structure elements the
    ordinary way so per-index attribution survives."""
    structure = list_structure_factory(type_, converter)

    def hook(value: object, _type: Any = type_) -> Any:
        if not isinstance(value, list):
            raise TypeError(f"must be a list, not {type(value).__name__}")
        return structure(value, _type)

    return hook


def _guarded_class(type_: Any, converter: cattrs.BaseConverter) -> Any:
    """cattrs asks ``field_name in obj`` before reading a field, so a *string*
    payload answers with a substring test: every field name it does not happen
    to contain reads as absent, and a class whose fields all have defaults
    structures cleanly out of arbitrary text. Require an actual mapping first."""
    structure = make_dict_structure_fn(type_, converter)

    def hook(value: object, _type: Any = type_) -> Any:
        if not isinstance(value, Mapping):
            raise TypeError(f"must be an object, not {type(value).__name__}")
        return structure(value, _type)

    return hook


# Default converter semantics: unknown keys are ignored, which is exactly what
# a FUTURE-stamped payload needs. Schema types may explicitly reject a
# semantically misplaced key before it reaches this additive-field boundary.
_converter = cattrs.Converter()
_converter.register_structure_hook(str, _exact(str, "a string"))
_converter.register_structure_hook(bool, _exact(bool, "a boolean", boolean=True))
_converter.register_structure_hook(int, _exact(int, "an integer"))
_converter.register_structure_hook(float, _exact((int, float), "a number"))
_converter.register_structure_hook_factory(attrs.has, _guarded_class)
_converter.register_structure_hook_factory(
    lambda type_: get_origin(type_) is list, _guarded_list
)


class Provenance(Enum):
    CURRENT = auto()
    PRIOR = auto()
    UNSTAMPED = auto()
    STALE = auto()
    FUTURE = auto()


@define(frozen=True)
class Loaded(Generic[T]):
    """What a payload turned out to be: the value, its vintage, and what was
    wrong with it."""

    value: T | None
    provenance: Provenance
    problems: tuple[str, ...] = field(converter=tuple)


def classify_stamp(stamp: int | None) -> Provenance:
    """Provenance of a payload stamped `stamp`; None means it carried no stamp.

    A boolean is not a stamp: `True == 1` would otherwise read as CURRENT.
    """
    if stamp is None or isinstance(stamp, bool):
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

    strict=True  -> every field rule must hold; problems are accumulated and
                    `value` is None if there are any (except a malformed
                    `schema_version`, which is reported without discarding an
                    otherwise-valid payload -- so callers gate on
                    `value is not None`, not on `problems`).
    strict=False -> best-effort: documented defaults filled, every gap
                    recorded in problems, still returns a usable value unless a
                    mandatory field is missing or unusable.
    Neither mode raises: a `cls` that is not a schema type and a `raw` that is
    not a mapping are reported like any other problem.

    Strictness is the caller's call: markdown documents are read lenient (a
    human wrote them, so a missing optional field is a gap to report, not a
    rejection) while machine-written manifests are read strict.
    """
    where = getattr(cls, "__name__", type(cls).__name__)
    if not attrs.has(cls):
        return Loaded(None, Provenance.UNSTAMPED, (f"{where} is not a schema type",))
    if not isinstance(raw, Mapping):
        return Loaded(
            None,
            Provenance.UNSTAMPED,
            (f"{where} must be a mapping, not {type(raw).__name__}",),
        )

    problems: list[str] = []
    stamp = raw.get(STAMP_KEY)
    if stamp is not None and (isinstance(stamp, bool) or not isinstance(stamp, int)):
        problems.append(f"{where}.{STAMP_KEY} must be an integer")
        stamp = None
    provenance = classify_stamp(stamp)
    forbidden = tuple(
        field_name
        for field_name in getattr(cls, "__schema_forbidden_fields__", ())
        if field_name in raw
    )
    problems.extend(
        f"{where}.{field_name} is not supported; mode belongs to each TestContract"
        for field_name in forbidden
    )

    if strict:
        value, failures = _structure(dict(raw), cls, where)
        problems.extend(message for _, message in failures)
        if forbidden:
            value = None
        return Loaded(value, provenance, tuple(problems))

    value, gaps = _best_effort(raw, cls, where)
    if forbidden:
        value = None
    return Loaded(value, provenance, tuple(problems + gaps))


def _structure(
    payload: dict[str, Any], cls: type[T], where: str
) -> tuple[T | None, list[tuple[str | None, str]]]:
    """Structure `payload`, then apply the field rules over the result.

    Each problem is paired with the top-level attribute it blames, so lenient
    mode knows what to drop.
    """
    try:
        with attrs.validators.disabled():
            value = _converter.structure(payload, cls)
    except Exception as exc:
        return None, _flatten(exc, where)
    failures = _field_problems(value, where)
    return (None, failures) if failures else (value, [])


def _best_effort(
    raw: Mapping[str, Any], cls: type[T], where: str
) -> tuple[T | None, list[str]]:
    """Structure what is recognizable, dropping each unusable optional field
    back to its documented default and recording why. A mandatory field that is
    missing or unusable has no default to fall back to, so it yields no value."""
    problems: list[str] = []
    payload: dict[str, Any] = {}
    for attribute in attrs.fields(cls):
        if attribute.name in raw:
            payload[attribute.name] = raw[attribute.name]
        elif attribute.default is attrs.NOTHING:
            problems.append(f"{where}.{attribute.name} is required")
        else:
            problems.append(f"{where}.{attribute.name} must be present; using default")

    optional = {
        attribute.name
        for attribute in attrs.fields(cls)
        if attribute.default is not attrs.NOTHING
    }
    while True:
        value, failures = _structure(payload, cls, where)
        for _, message in failures:
            if message not in problems:
                problems.append(message)
        if not failures:
            return value, problems
        droppable = {
            name for name, _ in failures if name in payload and name in optional
        }
        if not droppable:
            return None, problems
        for name in droppable:
            del payload[name]


def _field_problems(instance: Any, where: str) -> list[tuple[str | None, str]]:
    """Run every attrs validator over an already-structured tree, attributing
    each failure to its full path. cattrs cannot do this itself: validators run
    inside ``__init__``, outside the per-attribute error handling."""
    problems: list[tuple[str | None, str]] = []
    for attribute in attrs.fields(type(instance)):
        value = getattr(instance, attribute.name)
        path = f"{where}.{attribute.name}"
        if attribute.validator is not None:
            try:
                attribute.validator(instance, attribute, value)
            except Exception as exc:
                problems.append(
                    (attribute.name, _house(path, attribute.name, str(exc)))
                )
                continue
        problems.extend(
            (attribute.name, message) for message in _nested_problems(value, path)
        )
    return problems


def _nested_problems(value: Any, path: str) -> list[str]:
    if attrs.has(type(value)):
        return [message for _, message in _field_problems(value, path)]
    if isinstance(value, list):
        return [
            message
            for index, item in enumerate(value, start=1)
            if attrs.has(type(item))
            for _, message in _field_problems(item, f"{path}[{index}]")
        ]
    return []


def _flatten(exc: BaseException, where: str) -> list[tuple[str | None, str]]:
    """Flatten a cattrs ClassValidationError (an ExceptionGroup) into house-format
    problems paired with the top-level attribute each one blames."""
    problems: list[tuple[str | None, str]] = []
    _collect(exc, (), where, problems)
    return problems


def _collect(
    exc: BaseException,
    path: tuple[tuple[str | None, str], ...],
    where: str,
    out: list[tuple[str | None, str]],
) -> None:
    path = path + _segments(exc)
    nested = getattr(exc, "exceptions", None)
    if nested:
        for sub in nested:
            _collect(sub, path, where, out)
        return
    blamed = path[0][0] if path else None
    rendered = where + "".join(text for _, text in path)
    leaf = path[-1][0] if path else None
    if not path:
        out.append((None, f"{where}: {exc}"))
    elif isinstance(exc, KeyError):
        out.append((blamed, f"{rendered} is required"))
    else:
        out.append((blamed, _house(rendered, leaf, str(exc))))


def _segments(exc: BaseException) -> tuple[tuple[str | None, str], ...]:
    """Where in the tree cattrs was when it raised. The notes are structural --
    ``AttributeValidationNote.name``, ``IterableValidationNote.index`` -- so the
    path is read off them rather than parsed out of their rendered text. List
    indexes are 1-based to match the fan-out validators' ``curds[1]``; a
    mapping's note carries its key there instead."""
    segments: list[tuple[str | None, str]] = []
    for note in getattr(exc, "__notes__", ()):
        if isinstance(note, AttributeValidationNote):
            segments.append((note.name, f".{note.name}"))
        elif isinstance(note, IterableValidationNote):
            index = note.index
            rendered = f"[{index + 1}]" if isinstance(index, int) else f"[{index!r}]"
            segments.append((None, rendered))
    return tuple(segments)


def _house(path: str, name: str | None, message: str) -> str:
    """Render one failure as ``where.key must be ...``. Validators and hooks
    already phrase the predicate; only the subject has to be replaced with the
    full path. Three subject spellings are recognized: the bare attribute name,
    the name with a list index appended (``carry_forward[2] must be ...``), and
    attrs' own quoted form (``'retry_count' must be <= 1: 5``)."""
    if name is not None:
        if message.startswith((f"{name} ", f"{name}[")):
            return f"{path}{message[len(name):]}"
        if message.startswith(f"'{name}' "):
            return f"{path}{message[len(name) + 2:]}"
    if message.startswith("must be"):
        return f"{path} {message}"
    return f"{path} must be valid: {message}"