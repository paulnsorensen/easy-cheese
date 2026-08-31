"""Execution telemetry for one Press attempt.

Press is a healthy gate: the measured runs show a low error rate and a
reviewer-heavy specialist mix, so nothing here changes routing. What the
aggregate numbers cannot answer is *where* a run errored, *why* it delegated,
and whether the production-source boundary actually held. This module turns
one attempt's observations into a normalized record that answers those three
questions.

Pure function -- no clock, no file reads, no git. The record is a
deterministic function of the request, so the caller can replay it and every
derived field is testable without a fixture repository. Callers append the
emitted record next to the attempt's other artifacts; nothing is uploaded and
no external service is required.
"""

from __future__ import annotations

from collections import Counter
from enum import Enum
from pathlib import PurePosixPath
from typing import cast

from easy_cheese.shared.paths import validate_slug

from .press_route import Outcome, coerce_outcome

# Press owns at most three attempts per slug (attempt 3 is the terminal
# third RED), and `repair_cycles` counts the corrective Cook continuations
# already completed -- so attempt N always carries N-1 completed cycles.
MAX_ATTEMPTS = 3

# An operation that failed once inside a single attempt is transient; the same
# phase/operation pair failing again in that attempt is the recurring,
# operation-level failure worth investigating.
RECURRING_THRESHOLD = 2


class Phase(str, Enum):
    """Press flow steps, in the order SKILL.md's Flow section lists them."""

    # Resolved dynamically by value from the request, never by attribute.
    READ = "read"  # noqa: V107
    ATTACK = "attack"  # noqa: V107
    CLASSIFY = "classify"  # noqa: V107
    ROUTE = "route"  # noqa: V107
    REPORT = "report"  # noqa: V107
    HANDOFF = "handoff"  # noqa: V107


class FileClass(str, Enum):
    """Boundary-relevant classes for a path an attempt changed."""

    TESTS = "tests"
    METADATA = "metadata"
    PRODUCTION_SOURCE = "production_source"


# Path taxonomy. Press runs against arbitrary projects, so the rules are
# language-agnostic conventions, not this repository's layout. Anything that
# matches nothing falls through to production_source: the conservative default
# flags an unrecognized path for review instead of hiding it.
_TEST_DIRS = frozenset({"test", "tests", "spec", "specs", "testing", "__tests__"})
_TEST_STEM_SUFFIXES = ("_test", "_spec", ".test", ".spec")
_TEST_SUFFIXES = frozenset({".bats", ".feature"})
_METADATA_DIRS = frozenset({"docs", "doc"})
_METADATA_SUFFIXES = frozenset(
    {".md", ".rst", ".txt", ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".lock"}
)
_METADATA_NAMES = frozenset(
    {"LICENSE", "NOTICE", "CODEOWNERS", ".gitignore", ".gitattributes"}
)

_TOOL_ERROR_KEYS = frozenset({"phase", "operation"})
_DELEGATION_KEYS = frozenset({"role", "purpose"})


def classify_path(path: str) -> FileClass:
    """Classify one repository-relative path for the Press boundary audit."""
    pure = PurePosixPath(path)
    if {part.lower() for part in pure.parts[:-1]} & _TEST_DIRS:
        return FileClass.TESTS
    suffix = pure.suffix.lower()
    stem = pure.stem.lower()
    if suffix in _TEST_SUFFIXES:
        return FileClass.TESTS
    if stem.startswith("test_") or stem.endswith(_TEST_STEM_SUFFIXES):
        return FileClass.TESTS
    if (
        pure.name in _METADATA_NAMES
        or suffix in _METADATA_SUFFIXES
        or pure.parts[0].lower() in _METADATA_DIRS
    ):
        return FileClass.METADATA
    return FileClass.PRODUCTION_SOURCE


def _require_str(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _require_int(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field} must be an integer")
    return value


def _require_list(value: object, field: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list")
    return cast(list[object], value)


def _require_entry(value: object, field: str, keys: frozenset[str]) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"each {field} entry must be a mapping")
    entry = cast(dict[str, object], value)
    if set(entry) != set(keys):
        raise ValueError(
            f"each {field} entry must contain exactly {', '.join(sorted(keys))}"
        )
    return entry


def _require_phase(value: object) -> Phase:
    phase = _require_str(value, "tool_errors[].phase")
    try:
        return Phase(phase)
    except ValueError as exc:
        allowed = ", ".join(member.value for member in Phase)
        raise ValueError(
            f"invalid phase {phase!r}; expected one of: {allowed}"
        ) from exc


def _require_attempt(value: object, repair_cycles: int) -> int:
    attempt = _require_int(value, "attempt")
    if not 1 <= attempt <= MAX_ATTEMPTS:
        raise ValueError(f"attempt must be between 1 and {MAX_ATTEMPTS}")
    if attempt != repair_cycles + 1:
        raise ValueError(
            f"attempt {attempt} contradicts repair_cycles {repair_cycles}; "
            + "attempt N carries N-1 completed corrective cycles"
        )
    return attempt


def _require_repair_cycles(value: object) -> int:
    repair_cycles = _require_int(value, "repair_cycles")
    if repair_cycles < 0:
        raise ValueError("repair_cycles must be a non-negative integer")
    return repair_cycles


def _operations(tool_errors: list[object]) -> list[dict[str, object]]:
    counts: Counter[tuple[str, str]] = Counter()
    for value in tool_errors:
        entry = _require_entry(value, "tool_errors", _TOOL_ERROR_KEYS)
        phase = _require_phase(entry["phase"])
        operation = _require_str(entry["operation"], "tool_errors[].operation")
        counts[(phase.value, operation)] += 1
    return [
        {
            "phase": phase,
            "operation": operation,
            "errors": errors,
            "recurring": errors >= RECURRING_THRESHOLD,
        }
        for (phase, operation), errors in sorted(counts.items())
    ]


def _delegations(delegations: list[object]) -> list[dict[str, object]]:
    recorded: list[dict[str, object]] = []
    for value in delegations:
        entry = _require_entry(value, "delegations", _DELEGATION_KEYS)
        recorded.append(
            {
                "role": _require_str(entry["role"], "delegations[].role"),
                "purpose": _require_str(entry["purpose"], "delegations[].purpose"),
            }
        )
    return recorded


def _changed_paths(changed_files: list[object]) -> list[str]:
    paths: list[str] = []
    for value in changed_files:
        text = _require_str(value, "changed_files[]")
        pure = PurePosixPath(text)
        if pure.is_absolute() or ".." in pure.parts:
            raise ValueError(
                f"changed_files entry {text!r} must be a repository-relative path"
            )
        paths.append(pure.as_posix())
    return paths


def telemetry_record(
    *,
    slug: object,
    attempt: object,
    outcome: object,
    repair_cycles: object,
    tool_errors: object,
    delegations: object,
    changed_files: object,
) -> dict[str, object]:
    """Return the normalized telemetry record for one Press attempt.

    Every request field is required; empty lists are how an attempt records
    "no tool errors", "no delegated agents", or "no changed files". The record
    never routes: it is evidence about a decision Press already made.
    """
    slug_error = validate_slug(slug)
    if slug_error is not None:
        raise ValueError(slug_error)
    resolved_outcome = coerce_outcome(outcome)
    cycles = _require_repair_cycles(repair_cycles)
    resolved_attempt = _require_attempt(attempt, cycles)
    operations = _operations(_require_list(tool_errors, "tool_errors"))
    recorded_delegations = _delegations(_require_list(delegations, "delegations"))
    paths = _changed_paths(_require_list(changed_files, "changed_files"))

    classified = [(path, classify_path(path)) for path in paths]
    production_source_files = sorted(
        {path for path, file_class in classified if file_class is FileClass.PRODUCTION_SOURCE}
    )
    return {
        "slug": slug,
        "attempt": resolved_attempt,
        "outcome": resolved_outcome.value,
        "repair_cycles": cycles,
        "changed_file_count": len(paths),
        "changed_file_classes": sorted(
            {file_class.value for _, file_class in classified}
        ),
        "production_source_files": production_source_files,
        # Press must not touch production source; when it did, the attempt can
        # only be honest by classifying itself `production_changed`. A record
        # that reports production paths under any other outcome is boundary
        # drift, flagged here for the audit rather than routed on.
        "boundary_consistent": (
            not production_source_files or resolved_outcome is Outcome.PRODUCTION_CHANGED
        ),
        "tool_error_count": sum(
            cast(int, operation["errors"]) for operation in operations
        ),
        "operations": operations,
        "delegations": recorded_delegations,
    }


__all__ = [
    "MAX_ATTEMPTS",
    "RECURRING_THRESHOLD",
    "FileClass",
    "Phase",
    "classify_path",
    "telemetry_record",
]
