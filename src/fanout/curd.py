"""Curd entity — the single home for all curd validation rules.

Two layered functions:
  behaviour_errors  — content rules, checked at every pipeline stage.
  lifecycle_errors  — run-manifest-only: id, status, retry_count.
  disjoint_files_errors — cross-curd file collision, checked at every stage.
"""
from __future__ import annotations

import re

from schema import required_keys  # noqa: E402

# A behaviour sentence joining two distinct verbs with "and" usually means
# the curd should be split. We flag the simple case: "<verb> X and <verb> Y"
# where each verb is a present-tense action word. Intentionally permissive —
# "X and Y" (no second verb) is fine.
_TWO_VERB_AND = re.compile(
    r"\b(adds|extracts|renames|fixes|removes|updates|implements|creates|deletes|wires|registers|exposes|replaces)\b"
    r".*?\band\b\s+"
    r"\b(adds|extracts|renames|fixes|removes|updates|implements|creates|deletes|wires|registers|exposes|replaces)\b",
    re.IGNORECASE,
)

_WORK_STATUSES = {"pending", "running", "completed", "failed"}


def _one_behaviour(curd: dict) -> str | None:
    behavior = curd.get("behavior", "")
    if not isinstance(behavior, str) or not behavior.strip():
        return f"curd {curd.get('id', '?')}: missing or empty 'behavior'"
    if _TWO_VERB_AND.search(behavior):
        return (
            f"curd {curd.get('id', '?')}: behaviour joins two verbs with 'and' "
            f"({behavior!r}) — split into two curds"
        )
    return None


def _acceptance(curd: dict) -> str | None:
    ac = curd.get("acceptance_criterion", "")
    if not isinstance(ac, str) or not ac.strip():
        return f"curd {curd.get('id', '?')}: missing or empty 'acceptance_criterion'"
    return None


def _test_target(curd: dict) -> str | None:
    tt = curd.get("test_target", "")
    if not isinstance(tt, str) or not tt.strip():
        return f"curd {curd.get('id', '?')}: missing or empty 'test_target'"
    if "&&" in tt or ";" in tt or "||" in tt:
        return (
            f"curd {curd.get('id', '?')}: test_target chains multiple commands "
            f"({tt!r}) — split the curd"
        )
    return None


def behaviour_errors(curd: dict) -> list[str]:
    """Content rules checked at every pipeline stage."""
    errors: list[str] = []
    for check in (_one_behaviour, _acceptance, _test_target):
        err = check(curd)
        if err:
            errors.append(err)
    return errors


def lifecycle_errors(curd: dict, where: str) -> list[str]:
    """Run-manifest-only lifecycle checks: id, status, retry_count.

    The caller passes ``where`` (e.g. "curds[1]") so error messages carry
    the same index-prefix the per-curd loop produces.

    Intentionally does NOT re-check behavior/acceptance_criterion/test_target/files —
    those are covered by behaviour_errors and disjoint_files_errors (dedup contract).
    """
    errors: list[str] = []
    errors.extend(required_keys(curd, ("id", "status", "retry_count"), where))
    if not isinstance(curd.get("id"), int) or curd.get("id", 0) < 1:
        errors.append(f"{where}.id must be an integer >= 1")
    if curd.get("status") not in _WORK_STATUSES:
        errors.append(f"{where}.status must be one of pending|running|completed|failed")
    retry_count = curd.get("retry_count")
    if not isinstance(retry_count, int) or not 0 <= retry_count <= 1:
        errors.append(f"{where}.retry_count must be 0 or 1")
    return errors


def disjoint_files_errors(curds: list[dict]) -> list[str]:
    """Cross-curd file collision + missing/empty files. Skips non-dict entries."""
    errors: list[str] = []
    file_to_curd: dict[str, int | str] = {}
    for curd in curds:
        if not isinstance(curd, dict):
            continue
        curd_id = curd.get("id", "?")
        files = curd.get("files", [])
        if not isinstance(files, list) or not files:
            errors.append(f"curd {curd_id}: missing or empty 'files'")
            continue
        for f in files:
            if not isinstance(f, str):
                errors.append(f"curd {curd_id}: non-string file entry: {f!r}")
                continue
            if f in file_to_curd:
                errors.append(
                    f"file {f!r} appears in curd {file_to_curd[f]} and curd {curd_id} — "
                    f"curds must be file-disjoint (move shared content to seed or wiring)"
                )
            else:
                file_to_curd[f] = curd_id
    return errors
