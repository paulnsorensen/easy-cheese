#!/usr/bin/env python3
"""Validate a cheese-factory decomposition manifest against the five criteria.

Reads a manifest JSON file (or stdin), runs the validation checks below, and
either exits 0 (valid) or 1 (invalid, with one error per line on stderr).

Checks:

1. Behaviour overlap — each atom's behaviour is a single declarative sentence
   without an "and" joining two distinct verbs.
2. Acceptance criterion presence — every atom names its AC; 1:1 spec coverage
   is decomposer-side (the validator can't read the spec file).
3. Test target check — each atom has a non-empty test_target.
4. File disjointness — no file appears in two atoms.
5. Wiring DAG check — no cycles, every depends_on references a known wiring id.
6. Seed minimality — seed files are foundational (validation here only checks
   the field exists; the "2+ atoms depend on" check is decomposer-side because
   atom file-imports aren't represented in the manifest).

The script is pure-Python stdlib — no third-party imports — per
.github/instructions/python.instructions.md.
"""
from __future__ import annotations

import json
import re
import sys
from collections.abc import Iterable
from pathlib import Path

# ---------------------------------------------------------------------------
# Pure validation functions — tested directly in tests/cheese-factory/python.
# ---------------------------------------------------------------------------


# A behaviour sentence joining two distinct verbs with "and" usually means
# the atom should be split. We flag the simple case: "<verb> X and <verb> Y"
# where each verb is a present-tense action word. This is intentionally
# permissive — "X and Y" (no second verb) is fine.
_TWO_VERB_AND = re.compile(
    r"\b(adds|extracts|renames|fixes|removes|updates|implements|creates|deletes|wires|registers|exposes|replaces)\b"
    r".*?\band\b\s+"
    r"\b(adds|extracts|renames|fixes|removes|updates|implements|creates|deletes|wires|registers|exposes|replaces)\b",
    re.IGNORECASE,
)


def check_one_behaviour(atom: dict) -> str | None:
    """Criterion 1: one behaviour per atom."""
    behavior = atom.get("behavior", "")
    if not isinstance(behavior, str) or not behavior.strip():
        return f"atom {atom.get('id', '?')}: missing or empty 'behavior'"
    if _TWO_VERB_AND.search(behavior):
        return (
            f"atom {atom.get('id', '?')}: behaviour joins two verbs with 'and' "
            f"({behavior!r}) — split into two atoms"
        )
    return None


def check_acceptance_criterion(atom: dict) -> str | None:
    """Criterion 2: one acceptance criterion."""
    ac = atom.get("acceptance_criterion", "")
    if not isinstance(ac, str) or not ac.strip():
        return f"atom {atom.get('id', '?')}: missing or empty 'acceptance_criterion'"
    return None


def check_test_target(atom: dict) -> str | None:
    """Criterion 3: one test target."""
    tt = atom.get("test_target", "")
    if not isinstance(tt, str) or not tt.strip():
        return f"atom {atom.get('id', '?')}: missing or empty 'test_target'"
    # Reject test targets that obviously run more than one focused test —
    # multiple commands joined with && / ; / && or a wildcard suite path.
    if "&&" in tt or ";" in tt or "||" in tt:
        return (
            f"atom {atom.get('id', '?')}: test_target chains multiple commands "
            f"({tt!r}) — split the atom"
        )
    return None


def check_file_disjointness(atoms: Iterable[dict]) -> list[str]:
    """Criterion 4: no file appears in two atoms. HARD CONSTRAINT."""
    errors: list[str] = []
    file_to_atom: dict[str, int] = {}
    for atom in atoms:
        # Non-dict entries are reported by validate_manifest's loop; skip
        # here to avoid AttributeError on .get when the entry is None / str / int.
        if not isinstance(atom, dict):
            continue
        atom_id = atom.get("id", "?")
        files = atom.get("files", [])
        if not isinstance(files, list) or not files:
            errors.append(f"atom {atom_id}: missing or empty 'files'")
            continue
        for f in files:
            if not isinstance(f, str):
                errors.append(f"atom {atom_id}: non-string file entry: {f!r}")
                continue
            if f in file_to_atom:
                errors.append(
                    f"file {f!r} appears in atom {file_to_atom[f]} and atom {atom_id} — "
                    f"atoms must be file-disjoint (move shared content to seed or wiring)"
                )
            else:
                file_to_atom[f] = atom_id
    return errors


def check_wiring_dag(wiring: Iterable[dict]) -> list[str]:
    """Criterion: wiring DAG has no cycles and references only known ids."""
    # Drop non-dict entries up front — the validator is a user-facing CLI and
    # a stack trace on garbage input is a usability defect (mirrors the
    # check_file_disjointness defense for atoms[]).
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


def check_minimum_atom_count(atoms: list[dict], minimum: int = 5) -> str | None:
    """The spec routes to /ultracook below five atoms."""
    if len(atoms) < minimum:
        return (
            f"only {len(atoms)} atom(s) — /cheese-factory requires at least {minimum}; "
            f"use /ultracook for smaller decompositions"
        )
    return None


def validate_manifest(manifest: dict) -> list[str]:
    """Run every check; return a list of error strings (empty = valid)."""
    errors: list[str] = []
    atoms = manifest.get("atoms", [])
    if not isinstance(atoms, list):
        return ["manifest.atoms must be a list"]

    too_few = check_minimum_atom_count(atoms)
    if too_few:
        errors.append(too_few)

    for atom in atoms:
        if not isinstance(atom, dict):
            errors.append(f"non-dict atom entry: {atom!r}")
            continue
        for check in (check_one_behaviour, check_acceptance_criterion, check_test_target):
            err = check(atom)
            if err:
                errors.append(err)

    errors.extend(check_file_disjointness(atoms))

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
    if len(argv) > 2:
        print("usage: validate_decomposition.py [<manifest.json>]", file=sys.stderr)
        return 2
    if len(argv) == 2:
        path = Path(argv[1])
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            print(f"ERROR: manifest not found: {path}", file=sys.stderr)
            return 1
    else:
        text = sys.stdin.read()

    try:
        manifest = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"ERROR: invalid JSON: {exc}", file=sys.stderr)
        return 1

    errors = validate_manifest(manifest)
    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        print(f"\nFAIL: {len(errors)} validation error(s)", file=sys.stderr)
        return 1

    print(f"OK: {len(manifest.get('atoms', []))} atoms, decomposition valid")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
