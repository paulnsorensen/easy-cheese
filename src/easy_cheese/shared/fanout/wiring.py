"""Wiring node entity — the single home for all wiring validation rules.

Two layered functions:
  graph_errors     — DAG invariants, checked at every pipeline stage.
  lifecycle_errors — run-manifest-only: id format, type, file, depends_on, status.
"""
from __future__ import annotations

import re
from typing import cast

from easy_cheese.shared.schema import (  # noqa: E402
    non_empty_string,
    required_keys,
    string_list,
)
from easy_cheese_schemas.wiring_graph import cycle_errors

WIRING_TYPES = {
    "barrel_export",
    "di_registration",
    "route_wiring",
    "event_subscription",
    "config_entry",
}

_WIRING_ID_RE = re.compile(r"^W[0-9]+$")
_WORK_STATUSES = {"pending", "running", "completed", "failed"}


def graph_errors(wiring: list[object]) -> list[str]:
    """Collection invariants at every stage: acyclic DAG and known dependencies."""
    wiring_list = [cast("dict[str, object]", w) for w in wiring if isinstance(w, dict)]
    ids = {w.get("id") for w in wiring_list if isinstance(w.get("id"), str)}
    errors: list[str] = []

    def _string_deps(w: dict[str, object]) -> list[str]:
        deps = w.get("depends_on")
        if not isinstance(deps, list):
            return []
        items = cast("list[object]", deps)
        return [d for d in items if isinstance(d, str)]

    for w in wiring_list:
        wid = w.get("id", "?")
        for dep in _string_deps(w):
            # Only wiring-format ids (W<n>) must resolve within the wiring set.
            # Deps outside it — typically curd ids — are legitimate and ignored.
            if _WIRING_ID_RE.match(dep) and dep not in ids:
                errors.append(f"wiring {wid}: depends_on references unknown id {dep!r}")

    known: dict[str, list[str]] = {
        cast(str, w["id"]): _string_deps(w)
        for w in wiring_list
        if isinstance(w.get("id"), str)
    }
    errors.extend(cycle_errors(known.items()))
    return errors


def lifecycle_errors(node: dict[str, object], where: str) -> list[str]:
    """Run-manifest-only lifecycle checks for a single wiring node.

    The caller passes ``where`` (e.g. "wiring[1]") so error messages carry
    the same index-prefix the per-node loop produced before extraction.
    """
    errors: list[str] = []
    errors.extend(required_keys(node, ("id", "type", "file", "depends_on", "status"), where))
    wid = node.get("id")
    if not isinstance(wid, str) or not _WIRING_ID_RE.match(wid):
        errors.append(f"{where}.id must match W<number>")
    if node.get("type") not in WIRING_TYPES:
        errors.append(f"{where}.type must be a known wiring type")
    errors.extend(non_empty_string(node, "file", where))
    errors.extend(string_list(node.get("depends_on"), f"{where}.depends_on"))
    if node.get("status") not in _WORK_STATUSES:
        errors.append(f"{where}.status must be one of pending|running|completed|failed")
    return errors
