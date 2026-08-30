"""Curd-block validator — the spec-locked decomposition schema.

This is a *distinct* concept from src/fanout/curd.py's manifest-lifecycle
entity (behavior/acceptance_criterion/status/retry_count), which validates an
/ultracook *run manifest*'s in-flight curd records once a run exists. The curd
block validated here is the *decomposition artifact* the spec's "Seam schemas
(locked)" section defines (see specs/subagent-routing-overhaul.md) — produced
by either /mold's curdle step or /cook's fallback decompose gate, before any
run manifest exists. Field names intentionally do not overlap with curd.py's;
the two modules are not merged and do not import each other.

Schema:

    curds:
      - slug: <kebab>
        contract: <one paragraph>
        files: [<disjoint allowlist>]
        test_target: <command or test id>
        acceptance: [<verifiable checks>]
        seed: [<frozen interfaces this curd implements>]
        est_edit_lines: <int, declared estimate of source+test edit lines>
    waves: [[<slug>, ...], ...]   # <=4 slugs per wave
    decomposer: {source: mold | cook, model: <id>, prompt_version: <hash>}
"""
from __future__ import annotations

import sys
from typing import cast

from easy_cheese.shared.manifest_io import (
    ManifestLoadError,
    parse_mapping,
    read_mapping_arg_or_stdin,
)
from easy_cheese.shared.schema import (
    disjoint_errors,
    non_empty_string,
    required_keys,
    string_list,
)

MAX_WAVE_SIZE = 4
MIN_CURD_SURFACE = 25
_CURD_REQUIRED_KEYS = ("slug", "contract", "files", "test_target", "acceptance", "seed", "est_edit_lines")
_DECOMPOSER_SOURCES = ("mold", "cook")


class CurdBlockError(ValueError):
    """Raised when a curd block violates the locked schema."""


def _curd_errors(curd: object, where: str) -> list[str]:
    if not isinstance(curd, dict):
        return [f"{where} must be a mapping"]
    curd = cast("dict[str, object]", curd)

    errors = required_keys(curd, _CURD_REQUIRED_KEYS, where)
    for key in ("slug", "contract", "test_target"):
        if key in curd:
            errors.extend(non_empty_string(curd, key, where))
    if "files" in curd:
        errors.extend(string_list(curd["files"], f"{where}.files", non_empty=True))
    if "acceptance" in curd:
        errors.extend(string_list(curd["acceptance"], f"{where}.acceptance", non_empty=True))
    if "seed" in curd:
        errors.extend(string_list(curd["seed"], f"{where}.seed"))
    if "est_edit_lines" in curd:
        errors.extend(_est_edit_lines_errors(curd, where))
    return errors


def _est_edit_lines_errors(curd: dict[str, object], where: str) -> list[str]:
    value = curd["est_edit_lines"]
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        return [f"{where}.est_edit_lines must be a positive integer"]
    if value < MIN_CURD_SURFACE:
        slug = curd.get("slug", "?")
        return [
            f"{where}.est_edit_lines={value} is below the surface floor of "
            + f"{MIN_CURD_SURFACE} — curd {slug!r} is a MERGE CANDIDATE: merge it "
            + "into a sibling curd rather than dispatch a fresh coder for it"
        ]
    return []


def _disjoint_files_errors(curds: list[dict[str, object]]) -> list[str]:
    """Cross-curd file collision — the core file-disjointness invariant."""
    return disjoint_errors(
        cast("list[object]", curds),
        id_key="slug",
        message=lambda f, first, second: (
            f"file {f!r} appears in curd {first!r} and curd {second!r} — "
            "curd files must be pairwise disjoint"
        ),
    )


def _wave_errors(waves: object, known_slugs: set[str]) -> list[str]:
    if not isinstance(waves, list):
        return ["block.waves must be a list"]
    wave_items = cast("list[object]", waves)

    errors: list[str] = []
    for index, wave in enumerate(wave_items, start=1):
        where = f"waves[{index}]"
        if not isinstance(wave, list):
            errors.append(f"{where} must be a list of slugs")
            continue
        wave_slugs = cast("list[object]", wave)
        if len(wave_slugs) > MAX_WAVE_SIZE:
            errors.append(f"{where} has {len(wave_slugs)} slugs, exceeding the max of {MAX_WAVE_SIZE}")
        for slug in wave_slugs:
            if slug not in known_slugs:
                errors.append(f"{where} references unknown slug {slug!r}")
    return errors


def _decomposer_errors(decomposer: object) -> list[str]:
    where = "decomposer"
    if not isinstance(decomposer, dict):
        return [f"{where} must be a mapping"]
    decomposer = cast("dict[str, object]", decomposer)

    errors = required_keys(decomposer, ("source", "model", "prompt_version"), where)
    if "source" in decomposer and decomposer["source"] not in _DECOMPOSER_SOURCES:
        errors.append(f"{where}.source must be one of {_DECOMPOSER_SOURCES}")
    for key in ("model", "prompt_version"):
        if key in decomposer:
            errors.extend(non_empty_string(decomposer, key, where))
    return errors


def validate_curd_block(block: object) -> list[str]:
    """Return every schema violation in `block`; an empty list means valid."""
    if not isinstance(block, dict):
        return ["curd block must be a mapping"]
    block = cast("dict[str, object]", block)

    errors = required_keys(block, ("curds", "waves", "decomposer"), "block")
    curds_field = block.get("curds")
    curds_items: list[object]
    if "curds" in block and not isinstance(curds_field, list):
        errors.append("block.curds must be a list")
        curds_items = []
    elif isinstance(curds_field, list):
        curds_items = cast("list[object]", curds_field)
        if not curds_items:
            errors.append("block.curds must be a non-empty list — a block with no curds is undispatchable")
    else:
        curds_items = []
    curds = [cast("dict[str, object]", c) for c in curds_items if isinstance(c, dict)]
    for index, curd in enumerate(curds_items, start=1):
        errors.extend(_curd_errors(curd, f"curds[{index}]"))

    errors.extend(_disjoint_files_errors(curds))

    known_slugs: set[str] = set()
    for c in curds:
        slug = c.get("slug")
        if isinstance(slug, str):
            known_slugs.add(slug)
    if "waves" in block:
        errors.extend(_wave_errors(block["waves"], known_slugs))

    if "decomposer" in block:
        errors.extend(_decomposer_errors(block["decomposer"]))

    return errors


def parse_curd_block(source: dict[str, object] | str) -> dict[str, object]:
    """Parse (if a YAML/JSON string) and validate a curd block.

    Raises CurdBlockError with every violation joined into one message; never
    returns a falsy value in place of raising.
    """
    block = parse_mapping(source) if isinstance(source, str) else source
    errors = validate_curd_block(block)
    if errors:
        raise CurdBlockError("; ".join(errors))
    return block


def main(argv: list[str]) -> int:
    try:
        block = read_mapping_arg_or_stdin(argv, "usage: curd_block.py [<block.yaml|json>]")
    except ManifestLoadError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2 if str(exc).startswith("usage:") else 1

    errors = validate_curd_block(block)
    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        print(f"\nFAIL: {len(errors)} validation error(s)", file=sys.stderr)
        return 1

    print("OK: valid curd block")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
