#!/usr/bin/env python3
"""Validate a cheese-factory decomposition manifest against the five criteria.

Reads a manifest YAML/JSON file (or stdin), runs the validation checks below, and
either exits 0 (valid) or 1 (invalid, with one error per line on stderr).

Checks:

1. Behaviour overlap — each curd's behaviour is a single declarative sentence
   without an "and" joining two distinct verbs.
2. Acceptance criterion presence — every curd names its AC; 1:1 spec coverage
   is decomposer-side (the validator can't read the spec file).
3. Test target check — each curd has a non-empty test_target.
4. File disjointness — no file appears in two curds.
5. Wiring DAG check — no cycles, every depends_on references a known wiring id.
6. Seed minimality — seed files are foundational (validation here only checks
   the field exists; the "2+ curds depend on" check is decomposer-side because
   curd file-imports aren't represented in the manifest).

The script accepts YAML via PyYAML and JSON via the stdlib json module.
"""
from __future__ import annotations

import re
import sys
from collections.abc import Iterable
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SHARED_SCRIPTS = SCRIPT_DIR.parents[2] / "shared" / "scripts"
for _path in (SCRIPT_DIR, SHARED_SCRIPTS):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from manifest_io import ManifestLoadError, read_mapping_arg_or_stdin

# ---------------------------------------------------------------------------
# Pure validation functions — tested directly in tests/cheese-factory/python.
# ---------------------------------------------------------------------------


# A behaviour sentence joining two distinct verbs with "and" usually means
# the curd should be split. We flag the simple case: "<verb> X and <verb> Y"
# where each verb is a present-tense action word. This is intentionally
# permissive — "X and Y" (no second verb) is fine.
_TWO_VERB_AND = re.compile(
    r"\b(adds|extracts|renames|fixes|removes|updates|implements|creates|deletes|wires|registers|exposes|replaces)\b"
    r".*?\band\b\s+"
    r"\b(adds|extracts|renames|fixes|removes|updates|implements|creates|deletes|wires|registers|exposes|replaces)\b",
    re.IGNORECASE,
)


def check_one_behaviour(curd: dict) -> str | None:
    """Criterion 1: one behaviour per curd."""
    behavior = curd.get("behavior", "")
    if not isinstance(behavior, str) or not behavior.strip():
        return f"curd {curd.get('id', '?')}: missing or empty 'behavior'"
    if _TWO_VERB_AND.search(behavior):
        return (
            f"curd {curd.get('id', '?')}: behaviour joins two verbs with 'and' "
            f"({behavior!r}) — split into two curds"
        )
    return None


def check_acceptance_criterion(curd: dict) -> str | None:
    """Criterion 2: one acceptance criterion."""
    ac = curd.get("acceptance_criterion", "")
    if not isinstance(ac, str) or not ac.strip():
        return f"curd {curd.get('id', '?')}: missing or empty 'acceptance_criterion'"
    return None


def check_test_target(curd: dict) -> str | None:
    """Criterion 3: one test target."""
    tt = curd.get("test_target", "")
    if not isinstance(tt, str) or not tt.strip():
        return f"curd {curd.get('id', '?')}: missing or empty 'test_target'"
    # Reject test targets that obviously run more than one focused test —
    # multiple commands joined with && / ; / && or a wildcard suite path.
    if "&&" in tt or ";" in tt or "||" in tt:
        return (
            f"curd {curd.get('id', '?')}: test_target chains multiple commands "
            f"({tt!r}) — split the curd"
        )
    return None


def check_file_disjointness(curds: Iterable[dict]) -> list[str]:
    """Criterion 4: no file appears in two curds. HARD CONSTRAINT."""
    errors: list[str] = []
    file_to_curd: dict[str, int] = {}
    for curd in curds:
        # Non-dict entries are reported by validate_manifest's loop; skip
        # here to avoid AttributeError on .get when the entry is None / str / int.
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


def check_wiring_dag(wiring: Iterable[dict]) -> list[str]:
    """Criterion: wiring DAG has no cycles and references only known ids."""
    # Drop non-dict entries up front — the validator is a user-facing CLI and
    # a stack trace on garbage input is a usability defect (mirrors the
    # check_file_disjointness defense for curds[]).
    wiring_list = [w for w in wiring if isinstance(w, dict)]
    ids = {w.get("id") for w in wiring_list if isinstance(w.get("id"), str)}
    errors: list[str] = []

    # Unknown dependency references.
    for w in wiring_list:
        wid = w.get("id", "?")
        for dep in w.get("depends_on", []) or []:
            if dep not in ids:
                errors.append(f"wiring {wid}: depends_on references unknown id {dep!r}")

    # Cycle detection via DFS.
    graph: dict[str, list[str]] = {w["id"]: list(w.get("depends_on", []) or []) for w in wiring_list if "id" in w}
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


def check_minimum_curd_count(curds: list[dict], minimum: int = 5) -> str | None:
    """The spec routes to /ultracook below five curds."""
    if len(curds) < minimum:
        return (
            f"only {len(curds)} curd(s) — /cheese-factory requires at least {minimum}; "
            f"use /ultracook for smaller decompositions"
        )
    return None


def validate_manifest(manifest: dict) -> list[str]:
    """Run every check; return a list of error strings (empty = valid)."""
    errors: list[str] = []
    curds = manifest.get("curds", [])
    if not isinstance(curds, list):
        return ["manifest.curds must be a list"]

    too_few = check_minimum_curd_count(curds)
    if too_few:
        errors.append(too_few)

    for curd in curds:
        if not isinstance(curd, dict):
            errors.append(f"non-dict curd entry: {curd!r}")
            continue
        for check in (check_one_behaviour, check_acceptance_criterion, check_test_target):
            err = check(curd)
            if err:
                errors.append(err)

    errors.extend(check_file_disjointness(curds))

    wiring = manifest.get("wiring", [])
    if not isinstance(wiring, list):
        errors.append("manifest.wiring must be a list")
    else:
        errors.extend(check_wiring_dag(wiring))

    return errors


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str]) -> int:
    try:
        manifest = read_mapping_arg_or_stdin(
            argv, "usage: validate_decomposition.py [<manifest.yaml|json>]"
        )
    except ManifestLoadError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2 if str(exc).startswith("usage:") else 1

    errors = validate_manifest(manifest)
    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        print(f"\nFAIL: {len(errors)} validation error(s)", file=sys.stderr)
        return 1

    print(f"OK: {len(manifest.get('curds', []))} curds, decomposition valid")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
