#!/usr/bin/env python3
"""Validate an /ultracook fan-out run manifest.

This is the structural companion to `validate_decomposition.py`: it verifies
that the run-state document has the expected sections, then delegates the
behavioural decomposition checks to the decomposition validator.
"""

from __future__ import annotations

import re
import sys
from typing import cast

from easy_cheese.shared.manifest_io import (  # noqa: E402
    ManifestLoadError,
    read_mapping_arg_or_stdin,
)
from easy_cheese.shared.schema import (  # noqa: E402
    non_empty_string,
    required_keys,
    string_list,
    type_name,
)

from . import curd, wiring  # noqa: E402
from .validate_decomposition import (  # noqa: E402
    validate_manifest as validate_decomposition,
)
from .validate_pr_plan import validate_pr_plan  # noqa: E402

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
POWER = {"cheap", "default", "powerful"}
POWER_RANK = {"cheap": 0, "default": 1, "powerful": 2}
RESOLVED_POWER = POWER | {"unknown"}
EFFORT = {"low", "medium", "high"}
TOPOLOGY = {"inline", "sequential", "parallel", "fan-out-fan-in"}
POST_REVIEW_PHASES = {"post_review_complete", "pr_publish_complete"}
OID_RE = re.compile(r"(?:[0-9A-Fa-f]{40}|[0-9A-Fa-f]{64})")
DIFF_HASH_RE = re.compile(r"sha256:[0-9A-Fa-f]{64}")


def _validate_seed(seed: object) -> list[str]:
    if not isinstance(seed, dict):
        return [f"seed must be an object, got {type_name(seed)}"]
    seed_dict = cast("dict[str, object]", seed)
    errors = required_keys(seed_dict, ("items",), "seed")
    items = seed_dict.get("items")
    if not isinstance(items, list):
        errors.append("seed.items must be a list")
        return errors
    item_list = cast("list[object]", items)
    for index, item in enumerate(item_list, start=1):
        where = f"seed.items[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{where} must be an object, got {type_name(item)}")
            continue
        item_dict = cast("dict[str, object]", item)
        errors.extend(required_keys(item_dict, ("description", "files", "status"), where))
        errors.extend(non_empty_string(item_dict, "description", where))
        errors.extend(string_list(item_dict.get("files"), f"{where}.files", non_empty=True))
        if item_dict.get("status") not in SEED_STATUSES:
            errors.append(f"{where}.status must be one of pending|completed|failed")
    return errors


def _validate_curds(curds: object) -> list[str]:
    if not isinstance(curds, list):
        return ["curds must be a list"]
    errors: list[str] = []
    curd_list = cast("list[object]", curds)
    for index, c in enumerate(curd_list, start=1):
        where = f"curds[{index}]"
        if not isinstance(c, dict):
            errors.append(f"{where} must be an object, got {type_name(c)}")
            continue
        c_dict = cast("dict[str, object]", c)
        errors.extend(curd.lifecycle_errors(c_dict, where))
        if c_dict.get("status") == "completed" and "review_context" not in c_dict:
            errors.append(f"{where}.review_context is required when status is completed")
        if "review_context" in c_dict:
            errors.extend(
                _validate_review_context(c_dict["review_context"], f"{where}.review_context")
            )
    return errors


def _validate_wiring(wiring_list: object) -> list[str]:
    if not isinstance(wiring_list, list):
        return ["wiring must be a list"]
    errors: list[str] = []
    items = cast("list[object]", wiring_list)
    for index, item in enumerate(items, start=1):
        where = f"wiring[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{where} must be an object, got {type_name(item)}")
            continue
        item_dict = cast("dict[str, object]", item)
        errors.extend(wiring.lifecycle_errors(item_dict, where))
    return errors


def _enum_error(mapping: dict[str, object], key: str, allowed: set[str], where: str) -> list[str]:
    if key not in mapping:
        return []
    value = mapping[key]
    if isinstance(value, str) and value in allowed:
        return []
    return [f"{where}.{key} must be one of {'|'.join(sorted(allowed))}"]


def _resolution_request_errors(
    value_dict: dict[str, object],
) -> tuple[list[str], dict[str, object] | None]:
    errors: list[str] = []
    request_value = value_dict.get("request")
    if not isinstance(request_value, dict):
        errors.append("agent_resolution.request must be an object")
        return errors, None
    request = cast("dict[str, object]", request_value)
    request_fields = (
        "work",
        "preferred_types",
        "required_tools",
        "permissions",
        "isolation",
        "minimum_power",
        "effort",
    )
    errors.extend(required_keys(request, request_fields, "agent_resolution.request"))
    errors.extend(non_empty_string(request, "work", "agent_resolution.request"))
    for key in ("preferred_types", "required_tools"):
        errors.extend(
            string_list(
                request.get(key),
                f"agent_resolution.request.{key}",
                non_empty=True,
            )
        )
    errors.extend(
        _enum_error(
            request,
            "permissions",
            {"read-only", "write"},
            "agent_resolution.request",
        )
    )
    errors.extend(
        _enum_error(
            request,
            "isolation",
            {"none", "fresh-context", "isolated-worktree"},
            "agent_resolution.request",
        )
    )
    errors.extend(
        _enum_error(request, "minimum_power", POWER, "agent_resolution.request")
    )
    errors.extend(_enum_error(request, "effort", EFFORT, "agent_resolution.request"))
    return errors, request


def _resolution_attempts_errors(
    value_dict: dict[str, object],
) -> tuple[list[str], list[object] | None]:
    errors: list[str] = []
    attempts_value = value_dict.get("attempts")
    if not isinstance(attempts_value, list) or not attempts_value:
        errors.append("agent_resolution.attempts must be a non-empty list")
        return errors, None
    attempts = cast("list[object]", attempts_value)
    for index, attempt in enumerate(attempts, start=1):
        where = f"agent_resolution.attempts[{index}]"
        if not isinstance(attempt, dict):
            errors.append(f"{where} must be an object")
            continue
        attempt_dict = cast("dict[str, object]", attempt)
        errors.extend(
            required_keys(
                attempt_dict, ("type", "model", "power", "result", "reason"), where
            )
        )
        for key in ("type", "model", "reason"):
            errors.extend(non_empty_string(attempt_dict, key, where))
        errors.extend(_enum_error(attempt_dict, "power", RESOLVED_POWER, where))
        errors.extend(_enum_error(attempt_dict, "result", {"accepted", "rejected"}, where))
    return errors, attempts


def _resolution_resolved_errors(
    value_dict: dict[str, object],
) -> tuple[list[str], dict[str, object] | None]:
    errors: list[str] = []
    resolved_value = value_dict.get("resolved")
    if not isinstance(resolved_value, dict):
        errors.append("agent_resolution.resolved must be an object")
        return errors, None
    resolved = cast("dict[str, object]", resolved_value)
    errors.extend(
        required_keys(
            resolved, ("type", "model", "power", "effort", "topology"),
            "agent_resolution.resolved",
        )
    )
    for key in ("type", "model"):
        errors.extend(non_empty_string(resolved, key, "agent_resolution.resolved"))
    errors.extend(
        _enum_error(resolved, "power", RESOLVED_POWER, "agent_resolution.resolved")
    )
    errors.extend(_enum_error(resolved, "effort", EFFORT, "agent_resolution.resolved"))
    errors.extend(
        _enum_error(resolved, "topology", TOPOLOGY, "agent_resolution.resolved")
    )
    return errors, resolved


def _resolution_scalar_errors(
    value_dict: dict[str, object],
    request: dict[str, object] | None,
    resolved: dict[str, object] | None,
) -> list[str]:
    errors: list[str] = []
    fallback_reason = value_dict.get("fallback_reason")
    if fallback_reason is not None and (
        not isinstance(fallback_reason, str) or not fallback_reason.strip()
    ):
        errors.append("agent_resolution.fallback_reason must be null or a non-empty string")
    degraded = value_dict.get("degraded")
    if not isinstance(degraded, bool):
        errors.append("agent_resolution.degraded must be a boolean")
    enforcement = value_dict.get("permission_enforcement")
    if enforcement not in {"tool-restricted", "prompt-only"}:
        errors.append(
            "agent_resolution.permission_enforcement must be tool-restricted|prompt-only"
        )
    if enforcement == "prompt-only" and degraded is not True:
        errors.append("agent_resolution prompt-only enforcement requires degraded=true")
    if (
        enforcement == "prompt-only"
        and request is not None
        and request.get("permissions") != "read-only"
    ):
        errors.append(
            "agent_resolution prompt-only enforcement requires a read-only request "
            + "and cannot satisfy a write request"
        )
    if resolved is not None and resolved.get("power") == "unknown" and degraded is not True:
        errors.append("agent_resolution unknown power requires degraded=true")
    return errors


def _resolution_cross_field_errors(
    value_dict: dict[str, object],
    request: dict[str, object] | None,
    attempts: list[object] | None,
    resolved: dict[str, object] | None,
) -> list[str]:
    errors: list[str] = []
    if not attempts:
        return errors

    degraded = value_dict.get("degraded")
    fallback_reason = value_dict.get("fallback_reason")

    accepted = [
        (index, cast("dict[str, object]", attempt))
        for index, attempt in enumerate(attempts)
        if isinstance(attempt, dict)
        and cast("dict[str, object]", attempt).get("result") == "accepted"
    ]
    if len(accepted) != 1:
        errors.append("agent_resolution must contain exactly one accepted attempt")

    minimum = request.get("minimum_power") if request is not None else None
    if isinstance(minimum, str) and minimum in POWER_RANK:
        for index, attempt in enumerate(attempts, start=1):
            if not isinstance(attempt, dict):
                continue
            attempt_dict = cast("dict[str, object]", attempt)
            power = attempt_dict.get("power")
            if (
                isinstance(power, str)
                and power in POWER_RANK
                and POWER_RANK[power] < POWER_RANK[minimum]
                and attempt_dict.get("result") != "rejected"
            ):
                errors.append(
                    f"agent_resolution.attempts[{index}] power {power} is below "
                    + f"request minimum {minimum}; known underpowered attempts must be rejected"
                )
        if resolved is not None:
            resolved_power = resolved.get("power")
            if (
                isinstance(resolved_power, str)
                and resolved_power in POWER_RANK
                and POWER_RANK[resolved_power] < POWER_RANK[minimum]
            ):
                errors.append(
                    f"agent_resolution.resolved power {resolved_power} is below "
                    + f"request minimum {minimum}"
                )

    if len(accepted) == 1:
        accepted_index, accepted_attempt = accepted[0]
        if accepted_attempt.get("power") == "unknown":
            if accepted_index != len(attempts) - 1:
                errors.append(
                    "agent_resolution unknown-power accepted attempt must be final"
                )
            if degraded is not True:
                errors.append(
                    "agent_resolution unknown-power accepted attempt requires degraded=true"
                )
        if resolved is not None and any(
            resolved.get(key) != accepted_attempt.get(key)
            for key in ("type", "model", "power")
        ):
            errors.append(
                "agent_resolution resolved type/model/power must match the accepted attempt"
            )

        preferred = request.get("preferred_types") if request is not None else None
        accepted_type = accepted_attempt.get("type")
        if isinstance(preferred, list) and preferred:
            if accepted_type == preferred[0]:
                if fallback_reason is not None:
                    errors.append(
                        "agent_resolution preferred exact acceptance requires "
                        + "fallback_reason=null"
                    )
            elif fallback_reason is None:
                errors.append(
                    "agent_resolution nonpreferred acceptance requires a non-null "
                    + "fallback_reason"
                )
    return errors


def _validate_agent_resolution(value: object) -> list[str]:
    if not isinstance(value, dict):
        return [f"agent_resolution must be an object, got {type_name(value)}"]
    value_dict = cast("dict[str, object]", value)
    errors = required_keys(
        value_dict,
        (
            "request",
            "attempts",
            "resolved",
            "fallback_reason",
            "degraded",
            "permission_enforcement",
        ),
        "agent_resolution",
    )

    request_errors, request = _resolution_request_errors(value_dict)
    errors.extend(request_errors)

    attempts_errors, attempts = _resolution_attempts_errors(value_dict)
    errors.extend(attempts_errors)

    resolved_errors, resolved = _resolution_resolved_errors(value_dict)
    errors.extend(resolved_errors)

    errors.extend(_resolution_scalar_errors(value_dict, request, resolved))
    errors.extend(_resolution_cross_field_errors(value_dict, request, attempts, resolved))
    return errors


def _validate_review_context(value: object, where: str) -> list[str]:
    if not isinstance(value, dict):
        return [f"{where} must be an object, got {type_name(value)}"]
    value_dict = cast("dict[str, object]", value)
    fields = ("base_commit", "reviewed_tree_oid", "diff_hash", "scope")
    errors = required_keys(value_dict, fields, where)
    for key in ("base_commit", "reviewed_tree_oid"):
        candidate = value_dict.get(key)
        if key in value_dict and (
            not isinstance(candidate, str) or OID_RE.fullmatch(candidate) is None
        ):
            errors.append(f"{where}.{key} must be exactly 40 or 64 hexadecimal characters")
    diff_hash = value_dict.get("diff_hash")
    if "diff_hash" in value_dict and (
        not isinstance(diff_hash, str) or DIFF_HASH_RE.fullmatch(diff_hash) is None
    ):
        errors.append(f"{where}.diff_hash must be sha256: followed by 64 hexadecimal characters")
    if "scope" in value_dict:
        errors.extend(string_list(value_dict["scope"], f"{where}.scope", non_empty=True))
    return errors


def _validate_post_review(post_review: object) -> list[str]:
    if post_review is None:
        return []
    if not isinstance(post_review, dict):
        return [f"post_review must be an object, got {type_name(post_review)}"]
    post_review_dict = cast("dict[str, object]", post_review)
    errors: list[str] = []
    errors.extend(required_keys(post_review_dict, ("review_context",), "post_review"))
    if "review_context" in post_review_dict:
        errors.extend(
            _validate_review_context(
                post_review_dict["review_context"], "post_review.review_context"
            )
        )
    for key in ("press_slug", "age_slug", "cure_slug"):
        if key in post_review_dict:
            errors.extend(non_empty_string(post_review_dict, key, "post_review"))
    for key in ("findings_applied", "findings_deferred"):
        if key in post_review_dict:
            value = post_review_dict[key]
            if not isinstance(value, int) or value < 0:
                errors.append(f"post_review.{key} must be an integer >= 0")
    return errors


def _validate_repair_dispatch(value: object, where: str) -> list[str]:
    if not isinstance(value, dict):
        return [f"{where} must be an object, got {type_name(value)}"]
    value_dict = cast("dict[str, object]", value)
    errors = required_keys(value_dict, ("slug", "branch"), where)
    for key in ("slug", "branch", "pr"):
        if key in value_dict:
            errors.extend(non_empty_string(value_dict, key, where))
    return errors


def _validate_baseline(baseline: object) -> list[str]:
    if baseline is None:
        return []
    if not isinstance(baseline, dict):
        return [f"baseline must be an object, got {type_name(baseline)}"]
    baseline_dict = cast("dict[str, object]", baseline)
    errors: list[str] = []
    errors.extend(required_keys(baseline_dict, ("captured_at", "gates"), "baseline"))
    if "captured_at" in baseline_dict:
        errors.extend(non_empty_string(baseline_dict, "captured_at", "baseline"))
    if "gates" in baseline_dict:
        gates = baseline_dict["gates"]
        if not isinstance(gates, list):
            errors.append("baseline.gates must be a list")
        else:
            gate_list = cast("list[object]", gates)
            for index, gate in enumerate(gate_list, start=1):
                where = f"baseline.gates[{index}]"
                if not isinstance(gate, dict):
                    errors.append(f"{where} must be an object, got {type_name(gate)}")
                    continue
                gate_dict = cast("dict[str, object]", gate)
                errors.extend(required_keys(gate_dict, ("cmd", "failures"), where))
                if "cmd" in gate_dict:
                    errors.extend(non_empty_string(gate_dict, "cmd", where))
                if "failures" in gate_dict:
                    failures = gate_dict["failures"]
                    if not isinstance(failures, list):
                        errors.append(f"{where}.failures must be a list")
                    else:
                        failure_list = cast("list[object]", failures)
                        for f_index, failure in enumerate(failure_list, start=1):
                            f_where = f"{where}.failures[{f_index}]"
                            if not isinstance(failure, dict):
                                errors.append(
                                    f"{f_where} must be an object, got {type_name(failure)}"
                                )
                                continue
                            failure_dict = cast("dict[str, object]", failure)
                            errors.extend(
                                required_keys(
                                    failure_dict, ("suite", "test_id", "signature"), f_where
                                )
                            )
                            for key in ("suite", "test_id", "signature"):
                                if key in failure_dict:
                                    errors.extend(non_empty_string(failure_dict, key, f_where))
    if "repair_dispatch" in baseline_dict:
        errors.extend(
            _validate_repair_dispatch(
                baseline_dict["repair_dispatch"], "baseline.repair_dispatch"
            )
        )
    return errors


def validate_run_manifest(manifest: dict[str, object]) -> list[str]:
    errors: list[str] = []
    required = (
        "slug",
        "spec_path",
        "created",
        "phase",
        "quality_gates",
        "host_capabilities",
        "agent_resolution",
        "seed",
        "curds",
        "wiring",
    )
    errors.extend(required_keys(manifest, required, "manifest"))
    for key in ("slug", "spec_path", "created"):
        errors.extend(non_empty_string(manifest, key, "manifest"))
    if manifest.get("phase") not in PHASES:
        errors.append("manifest.phase must be a known phase")
    errors.extend(
        string_list(
            manifest.get("quality_gates"), "manifest.quality_gates", non_empty=True
        )
    )
    if not isinstance(manifest.get("host_capabilities"), dict):
        errors.append("manifest.host_capabilities must be an object")
    errors.extend(_validate_agent_resolution(manifest.get("agent_resolution")))
    if manifest.get("phase") in POST_REVIEW_PHASES:
        errors.extend(
            required_keys(manifest, ("current_review", "post_review"), "manifest")
        )

    errors.extend(_validate_seed(manifest.get("seed")))
    errors.extend(_validate_curds(manifest.get("curds")))
    errors.extend(_validate_wiring(manifest.get("wiring")))
    errors.extend(_validate_post_review(manifest.get("post_review")))
    errors.extend(_validate_baseline(manifest.get("baseline")))
    if "current_review" in manifest:
        errors.extend(_validate_review_context(manifest["current_review"], "current_review"))
    if "pr_plan" in manifest:
        pr_plan = manifest.get("pr_plan")
        if not isinstance(pr_plan, dict):
            errors.append("manifest.pr_plan must be an object")
        else:
            pr_plan_dict = cast("dict[str, object]", pr_plan)
            # validate_pr_plan now delegates to easy_cheese_schemas.PrPlan, whose
            # problems already carry a "PrPlan." prefix; swap it for
            # "manifest.pr_plan." instead of prepending on top of it.
            errors.extend(
                error.replace("PrPlan.", "manifest.pr_plan.", 1)
                for error in validate_pr_plan(pr_plan_dict)
            )

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

    curds = manifest.get("curds")
    curd_count = len(cast("list[object]", curds)) if isinstance(curds, list) else 0
    print(f"OK: {curd_count} curd(s), manifest valid")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
