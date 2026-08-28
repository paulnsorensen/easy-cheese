#!/usr/bin/env python3
"""Validate an /ultracook fan-out decomposition manifest. Exit 0 on success, 1 on errors (one per line on stderr)."""
from __future__ import annotations

import sys

from easy_cheese.shared.manifest_io import (  # noqa: E402
    ManifestLoadError,
    read_mapping_arg_or_stdin,
)
from easy_cheese_schemas import Decomposition, DecomposedCurd, load  # noqa: E402

from . import wiring  # noqa: E402


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

    dict_curds = []
    for c in curds:
        if not isinstance(c, dict):
            errors.append(f"non-dict curd entry: {c!r}")
            continue
        dict_curds.append(c)

    # Content rules (behavior/acceptance_criterion/test_target/files shape)
    # live once in easy_cheese_schemas.DecomposedCurd, checked per curd so one
    # curd's failure never short-circuits another's. The cross-curd `files`
    # disjointness invariant lives on Decomposition.curds instead -- a
    # collection-level rule -- so it is checked separately over the same
    # dicts; when it fails, only its own message is kept, since a raised
    # collection validator would otherwise mask per-curd errors already
    # collected above.
    for c in dict_curds:
        errors.extend(load(c, DecomposedCurd, strict=True).problems)
    if dict_curds:
        collection = load({"curds": dict_curds, "wiring": []}, Decomposition, strict=True)
        errors.extend(problem for problem in collection.problems if "curds[" not in problem)

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
    sys.exit(main(sys.argv[1:]))
