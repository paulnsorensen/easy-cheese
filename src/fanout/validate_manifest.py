#!/usr/bin/env python3
"""Validate an /ultracook fan-out run manifest.

This is the structural companion to `validate_decomposition.py`: it verifies
that the run-state document has the expected sections, then delegates the
behavioural decomposition checks to the decomposition validator.
"""

from __future__ import annotations

import sys
from typing import Any

import curd  # noqa: E402
import wiring  # noqa: E402
from manifest_io import ManifestLoadError, read_mapping_arg_or_stdin  # noqa: E402
from schema import non_empty_string, required_keys, string_list, type_name  # noqa: E402
from validate_decomposition import validate_manifest as validate_decomposition  # noqa: E402
from validate_pr_plan import validate_pr_plan  # noqa: E402

PHASES = {
    "gate_approved",
    "seed_complete",
    "curds_complete",
    "merge_complete",
    "wiring_complete",
    "final_merge_complete",
    "post_review_complete",
    "pr_publish_complete",
}
SEED_STATUSES = {"pending", "completed", "failed"}


def _validate_seed(seed: object) -> list[str]:
    if not isinstance(seed, dict):
        return [f"seed must be an object, got {type_name(seed)}"]
    errors = required_keys(seed, ("items",), "seed")
    items = seed.get("items")
    if not isinstance(items, list):
        errors.append("seed.items must be a list")
        return errors
    for index, item in enumerate(items, start=1):
        where = f"seed.items[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{where} must be an object, got {type_name(item)}")
            continue
        errors.extend(required_keys(item, ("description", "files", "status"), where))
        errors.extend(non_empty_string(item, "description", where))
        errors.extend(string_list(item.get("files"), f"{where}.files", non_empty=True))
        if item.get("status") not in SEED_STATUSES:
            errors.append(f"{where}.status must be one of pending|completed|failed")
    return errors


def _validate_curds(curds: object) -> list[str]:
    if not isinstance(curds, list):
        return ["curds must be a list"]
    errors: list[str] = []
    for index, c in enumerate(curds, start=1):
        where = f"curds[{index}]"
        if not isinstance(c, dict):
            errors.append(f"{where} must be an object, got {type_name(c)}")
            continue
        errors.extend(curd.lifecycle_errors(c, where))
    return errors


def _validate_wiring(wiring_list: object) -> list[str]:
    if not isinstance(wiring_list, list):
        return ["wiring must be a list"]
    errors: list[str] = []
    for index, item in enumerate(wiring_list, start=1):
        where = f"wiring[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{where} must be an object, got {type_name(item)}")
            continue
        errors.extend(wiring.lifecycle_errors(item, where))
    return errors


def _validate_post_review(post_review: object) -> list[str]:
    if post_review is None:
        return []
    if not isinstance(post_review, dict):
        return [f"post_review must be an object, got {type_name(post_review)}"]
    errors: list[str] = []
    for key in ("press_slug", "age_slug", "cure_slug"):
        if key in post_review:
            errors.extend(non_empty_string(post_review, key, "post_review"))
    for key in ("findings_applied", "findings_deferred"):
        if key in post_review:
            value = post_review[key]
            if not isinstance(value, int) or value < 0:
                errors.append(f"post_review.{key} must be an integer >= 0")
    return errors


def validate_run_manifest(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = (
        "slug",
        "spec_path",
        "created",
        "phase",
        "quality_gates",
        "host_capabilities",
        "seed",
        "curds",
        "wiring",
    )
    errors.extend(required_keys(manifest, required, "manifest"))
    for key in ("slug", "spec_path", "created"):
        errors.extend(non_empty_string(manifest, key, "manifest"))
    if manifest.get("phase") not in PHASES:
        errors.append("manifest.phase must be a known phase")
    errors.extend(string_list(manifest.get("quality_gates"), "manifest.quality_gates", non_empty=True))
    if not isinstance(manifest.get("host_capabilities"), dict):
        errors.append("manifest.host_capabilities must be an object")

    errors.extend(_validate_seed(manifest.get("seed")))
    errors.extend(_validate_curds(manifest.get("curds")))
    errors.extend(_validate_wiring(manifest.get("wiring")))
    errors.extend(_validate_post_review(manifest.get("post_review")))
    if "pr_plan" in manifest:
        pr_plan = manifest.get("pr_plan")
        if not isinstance(pr_plan, dict):
            errors.append("manifest.pr_plan must be an object")
        else:
            errors.extend(f"manifest.pr_plan.{error}" for error in validate_pr_plan(pr_plan))

    if "phase_summary" in manifest and not isinstance(manifest["phase_summary"], str):
        errors.append("manifest.phase_summary must be a string")
    if "carry_forward" in manifest:
        errors.extend(string_list(manifest.get("carry_forward"), "manifest.carry_forward"))

    errors.extend(validate_decomposition(manifest))
    return errors


def main(argv: list[str]) -> int:
    try:
        manifest = read_mapping_arg_or_stdin(argv, "usage: validate_manifest.py [<manifest.yaml|json>]")
    except ManifestLoadError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2 if str(exc).startswith("usage:") else 1

    errors = validate_run_manifest(manifest)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print(f"\nFAIL: {len(errors)} validation error(s)", file=sys.stderr)
        return 1

    print(f"OK: {len(manifest.get('curds', []))} curd(s), manifest valid")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
