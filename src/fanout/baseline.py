#!/usr/bin/env python3
"""Classify a current test-failure list against a stored baseline.

Deterministic classifier for /ultracook's baseline-aware quality gate (#298):
prose agents never eyeball failure diffs (ADR-003) -- this module is the sole
place failure signatures are compared. A `FailureRecord`'s `signature` field
is expected to already carry the approved normalized form -- the first line
of the failure message, whitespace-normalized (see `normalize_signature`).

Taxonomy (keyed by suite+test_id):

- `identical` -- same test, same signature as baseline: record+continue.
- `new`       -- test not present in baseline.
- `changed`   -- same test, different signature (policy treats this the same
  as `new` -- a bounded fix, not a halt).
- `resolved`  -- test was in baseline, absent from current (now green).

Inputs:

    Reads `{"baseline": [...], "current": [...]}` JSON from stdin, each list
    holding FailureRecord objects (`suite`, `test_id`, `signature`).

Output (JSON):

    {"identical": [...], "new": [...], "changed": [...], "resolved": [...]}
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import TypedDict

# cli is co-staged in the bundled .pyz alongside this module
import cli


class FailureRecord(TypedDict):
    suite: str
    test_id: str
    signature: str


class Classification(TypedDict):
    identical: list[FailureRecord]
    new: list[FailureRecord]
    changed: list[FailureRecord]
    resolved: list[FailureRecord]


def normalize_signature(message: str) -> str:
    """First line of a failure message, whitespace-normalized (the approved
    signature rule)."""
    first_line = message.splitlines()[0] if message else ""
    return " ".join(first_line.split())


def _key(record: FailureRecord) -> tuple[str, str]:
    return (record["suite"], record["test_id"])


def classify(baseline: list[FailureRecord], current: list[FailureRecord]) -> Classification:
    """Pure diff of `current` against `baseline` by (suite, test_id) + signature."""
    baseline_by_key = {_key(record): record for record in baseline}
    current_by_key = {_key(record): record for record in current}

    identical: list[FailureRecord] = []
    new: list[FailureRecord] = []
    changed: list[FailureRecord] = []
    for key, record in current_by_key.items():
        base = baseline_by_key.get(key)
        if base is None:
            new.append(record)
        elif base["signature"] == record["signature"]:
            identical.append(record)
        else:
            changed.append(record)

    resolved = [
        record for key, record in baseline_by_key.items() if key not in current_by_key
    ]

    return {
        "identical": identical,
        "new": new,
        "changed": changed,
        "resolved": resolved,
    }


def _validate_records(value: object, field: str) -> list[FailureRecord]:
    """Shape-check a baseline/current payload value before it reaches the pure
    classify() -- a wrong-typed value here must surface as CliError, not an
    uncaught TypeError/KeyError once classify() starts indexing it."""
    if not isinstance(value, list):
        raise cli.CliError(f"{field} must be a list of failure records")
    for index, record in enumerate(value):
        if not isinstance(record, dict):
            raise cli.CliError(f"{field}[{index}] must be an object")
        missing = [key for key in ("suite", "test_id", "signature") if key not in record]
        if missing:
            raise cli.CliError(f"{field}[{index}] missing required key(s): {', '.join(missing)}")
    return value  # type: ignore[return-value]


def _cmd_classify(args: argparse.Namespace) -> None:
    try:
        payload = json.load(sys.stdin)
        baseline_arg = _validate_records(payload.get("baseline", []), "baseline")
        current_arg = _validate_records(payload.get("current", []), "current")
    except (json.JSONDecodeError, AttributeError) as exc:
        raise cli.CliError("expected a JSON object with baseline/current on stdin") from exc
    result = classify(baseline_arg, current_arg)
    cli.emit(result, json_mode=True)


def _setup(parser: argparse.ArgumentParser) -> None:
    parser.description = "Classify current failures against a stored baseline (reads JSON from stdin)."
    parser.set_defaults(func=_cmd_classify)


if __name__ == "__main__":
    cli.run(_setup)
