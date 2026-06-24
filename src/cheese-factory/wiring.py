"""Wiring node entity — the single home for all wiring validation rules.

Two layered functions:
  graph_errors     — DAG invariants, checked at every pipeline stage.
  lifecycle_errors — run-manifest-only: id format, type, file, depends_on, status.
"""
from __future__ import annotations

import re

from schema import non_empty_string, required_keys, string_list  # noqa: E402

WIRING_TYPES = {
    "barrel_export",
    "di_registration",
    "route_wiring",
    "event_subscription",
    "config_entry",
}

_WIRING_ID_RE = re.compile(r"^W[0-9]+$")
_WORK_STATUSES = {"pending", "running", "completed", "failed"}


def graph_errors(wiring: list) -> list[str]:
    """Collection invariants at every stage: acyclic DAG and known depends_on ids."""
    wiring_list = [w for w in wiring if isinstance(w, dict)]
    ids = {w.get("id") for w in wiring_list if isinstance(w.get("id"), str)}
    errors: list[str] = []

    def _string_deps(w: dict) -> list[str]:
        deps = w.get("depends_on")
        return [d for d in deps if isinstance(d, str)] if isinstance(deps, list) else []

    for w in wiring_list:
        wid = w.get("id", "?")
        for dep in _string_deps(w):
            if dep not in ids:
                errors.append(f"wiring {wid}: depends_on references unknown id {dep!r}")

    graph: dict[str, list[str]] = {w["id"]: _string_deps(w) for w in wiring_list if isinstance(w.get("id"), str)}
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {node: WHITE for node in graph}

    def dfs(node: str, stack: list[str]) -> str | None:
        color[node] = GRAY
        stack.append(node)
        for nxt in graph.get(node, []):
            if nxt not in color:
                continue
            if color[nxt] == GRAY:
                cycle = stack[stack.index(nxt):] + [nxt]
                return " -> ".join(cycle)
            if color[nxt] == WHITE:
                cy = dfs(nxt, stack)
                if cy:
                    return cy
        stack.pop()
        color[node] = BLACK
        return None

    for node in list(graph):
        if color[node] == WHITE:
            cy = dfs(node, [])
            if cy:
                errors.append(f"wiring DAG has cycle: {cy}")
                break  # one cycle report is enough; user fixes & re-runs

    return errors


def lifecycle_errors(node: dict, where: str) -> list[str]:
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
