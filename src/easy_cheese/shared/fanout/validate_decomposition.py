#!/usr/bin/env python3
"""Validate an /ultracook fan-out decomposition manifest. Exit 0 on success, 1 on errors (one per line on stderr)."""
from __future__ import annotations

import sys
from typing import cast

from attrs import validators

from easy_cheese.shared.manifest_io import (  # noqa: E402
    ManifestLoadError,
    read_mapping_arg_or_stdin,
)
from easy_cheese_schemas import DecomposedCurd, load  # noqa: E402
from easy_cheese_schemas.manifest import reject_shared_curd_files  # noqa: E402

from . import wiring  # noqa: E402


# ---------------------------------------------------------------------------
# Well-formedness (not an entity invariant)
# ---------------------------------------------------------------------------


class _CurdsField:
    """`reject_shared_curd_files` names the offending field from the attrs
    attribute it validates; called directly it needs the same name the schema
    gives it."""

    name: str = "curds"


_CURDS_FIELD = _CurdsField()


def _files_only(curd: dict[str, object]) -> DecomposedCurd | None:
    """The curd's `files` alone, for the cross-curd disjointness check on a curd
    the strict read rejected. Content rules have already reported against it, so
    they are disabled here; a `files` value the check cannot compare yields no
    curd at all."""
    files = curd.get("files")
    if not isinstance(files, list):
        return None
    paths = [path for path in cast("list[object]", files) if isinstance(path, str)]
    with validators.disabled():
        return DecomposedCurd(
            behavior="", acceptance_criterion="", files=paths, test_target=""
        )


def check_minimum_curd_count(curds: list[object]) -> str | None:
    """A decomposition is well-formed only with at least one curd. Fewer than
    `PARALLEL_THRESHOLD` curds is valid — it routes to linear /ultracook rather
    than parallel fan-out — so the only count that fails is zero."""
    if len(curds) < 1:
        return "decomposition has no curds; at least one is required"
    return None


def validate_manifest(manifest: dict[str, object]) -> list[str]:
    errors: list[str] = []
    curds_field = manifest.get("curds", [])
    if not isinstance(curds_field, list):
        return ["manifest.curds must be a list"]
    curds = cast("list[object]", curds_field)

    ill_formed = check_minimum_curd_count(curds)
    if ill_formed:
        errors.append(ill_formed)

    dict_curds: list[dict[str, object]] = []
    for c in curds:
        if not isinstance(c, dict):
            errors.append(f"non-dict curd entry: {c!r}")
            continue
        dict_curds.append(cast("dict[str, object]", c))

    # Content rules (behavior/acceptance_criterion/test_target/files shape)
    # live once in easy_cheese_schemas.DecomposedCurd, checked per curd so one
    # curd's failure never short-circuits another's. The cross-curd `files`
    # disjointness invariant is a collection-level rule, so it runs over every
    # curd: one that failed its own content rules still owns files that must
    # not collide with a sibling's.
    loaded: list[DecomposedCurd] = []
    for c in dict_curds:
        result = load(c, DecomposedCurd, strict=True)
        errors.extend(result.problems)
        curd = result.value if result.value is not None else _files_only(c)
        if curd is not None:
            loaded.append(curd)
    try:
        reject_shared_curd_files(None, _CURDS_FIELD, loaded)
    except ValueError as exc:
        errors.append(str(exc))

    wiring_field = manifest.get("wiring", [])
    if not isinstance(wiring_field, list):
        errors.append("manifest.wiring must be a list")
    else:
        wiring_list = cast("list[object]", wiring_field)
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

    curds_field = manifest.get("curds", [])
    curd_count = len(cast("list[object]", curds_field)) if isinstance(curds_field, list) else 0
    print(f"OK: {curd_count} curds, decomposition valid")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
