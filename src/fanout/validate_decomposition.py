#!/usr/bin/env python3
"""Validate an /ultracook fan-out decomposition manifest. Exit 0 on success, 1 on errors (one per line on stderr)."""
from __future__ import annotations

import sys

import curd  # noqa: E402
import wiring  # noqa: E402
from manifest_io import ManifestLoadError, read_mapping_arg_or_stdin  # noqa: E402
from mode import PARALLEL_THRESHOLD  # noqa: E402


# ---------------------------------------------------------------------------
# Well-formedness (not an entity invariant)
# ---------------------------------------------------------------------------


def check_minimum_curd_count(curds: list[dict]) -> str | None:
    """A decomposition is well-formed only with at least one curd. Fewer than
    `PARALLEL_THRESHOLD` curds is valid — it routes to linear /ultracook rather
    than parallel fan-out — so the only count that fails is zero."""
    if len(curds) < 1:
        return "decomposition has no curds; at least one is required"
    return None


def validate_manifest(manifest: dict) -> list[str]:
    errors: list[str] = []
    curds = manifest.get("curds", [])
    if not isinstance(curds, list):
        return ["manifest.curds must be a list"]

    ill_formed = check_minimum_curd_count(curds)
    if ill_formed:
        errors.append(ill_formed)

    for c in curds:
        if not isinstance(c, dict):
            errors.append(f"non-dict curd entry: {c!r}")
            continue
        errors.extend(curd.behaviour_errors(c))

    # File-disjointness only matters when curds fan out in parallel; a linear
    # (< PARALLEL_THRESHOLD) decomposition is one unit, trivially disjoint.
    if len(curds) >= PARALLEL_THRESHOLD:
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
