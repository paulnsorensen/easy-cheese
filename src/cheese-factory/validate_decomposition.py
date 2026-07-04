#!/usr/bin/env python3
"""Validate a cheese-factory decomposition manifest. Exit 0 on success, 1 on errors (one per line on stderr)."""
from __future__ import annotations

import sys

import curd  # noqa: E402
import wiring  # noqa: E402
from manifest_io import ManifestLoadError, read_mapping_arg_or_stdin  # noqa: E402


# ---------------------------------------------------------------------------
# Pipeline-policy check (not an entity invariant)
# ---------------------------------------------------------------------------


def check_minimum_curd_count(curds: list[dict]) -> str | None:
    """The spec routes to /ultracook below five curds."""
    if len(curds) < 5:
        return (
            f"only {len(curds)} curd(s) — /cheese-factory requires at least 5; "
            f"use /ultracook for smaller decompositions"
        )
    return None


def validate_manifest(manifest: dict) -> list[str]:
    errors: list[str] = []
    curds = manifest.get("curds", [])
    if not isinstance(curds, list):
        return ["manifest.curds must be a list"]

    too_few = check_minimum_curd_count(curds)
    if too_few:
        errors.append(too_few)

    for c in curds:
        if not isinstance(c, dict):
            errors.append(f"non-dict curd entry: {c!r}")
            continue
        errors.extend(curd.behaviour_errors(c))

    errors.extend(curd.disjoint_files_errors(curds))

    wiring_list = manifest.get("wiring", [])
    if not isinstance(wiring_list, list):
        errors.append("manifest.wiring must be a list")
    else:
        errors.extend(wiring.graph_errors(wiring_list))

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
