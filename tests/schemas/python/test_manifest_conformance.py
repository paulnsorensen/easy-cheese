"""RunManifest: src/fanout/validate_manifest.py vs easy_cheese_schemas.RunManifest.

The run manifest is the largest of the four contracts and the only one a
`--resume` reads to decide what already happened, so it is also where the two
sources of truth are furthest apart. Every divergence below is enumerated
rather than skipped: the table is the ledger, and `assert_table_is_honest`
fails the suite the moment a row's label stops matching what the two sides
actually do.
"""

from __future__ import annotations

from typing import Any

import pytest
from easy_cheese_schemas import RunManifest
from schema_conformance import (
    Case,
    Validator,
    agreed_invalid,
    agreed_valid,
    agreeing,
    assert_conforms,
    assert_table_is_honest,
    curd_records,
    divergent,
    ids,
    looser,
    review_context,
    run_manifest,
    stricter,
    wiring_row,
)

# The consistency rules validate_manifest.py enforces over agent_resolution and
# the review fields, which the attrs types do not carry in v0.1. Documented as
# "Not enforced in v0.1" in docs/easy-cheese-schemas.md and retired by the
# migration follow-up that moves the validator onto these types.
UNMODELLED = "v0.1 gap: rule lives only in validate_manifest.py"


def without(key: str) -> dict[str, Any]:
    payload = run_manifest()
    del payload[key]
    return payload


def top(**fields: Any) -> dict[str, Any]:
    payload = run_manifest()
    payload.update(fields)
    return payload


def first_curd(**fields: Any) -> dict[str, Any]:
    payload = run_manifest()
    payload["curds"][0].update(fields)
    return payload


def lone_curd(**fields: Any) -> dict[str, Any]:
    payload = top(curds=curd_records(1))
    payload["curds"][0].update(fields)
    return payload


def lone_curd_without(key: str) -> dict[str, Any]:
    payload = top(curds=curd_records(1))
    del payload["curds"][0][key]
    return payload


def shared_curd_files() -> dict[str, Any]:
    payload = run_manifest()
    payload["curds"][1]["files"] = list(payload["curds"][0]["files"])
    return payload


def resolution(**fields: Any) -> dict[str, Any]:
    payload = run_manifest()
    payload["agent_resolution"].update(fields)
    return payload


def resolved(**fields: Any) -> dict[str, Any]:
    payload = run_manifest()
    payload["agent_resolution"]["resolved"].update(fields)
    return payload


def power(value: str) -> dict[str, Any]:
    payload = run_manifest()
    payload["agent_resolution"]["attempts"][0]["power"] = value
    payload["agent_resolution"]["resolved"]["power"] = value
    return payload


def substituted_type() -> dict[str, Any]:
    payload = run_manifest()
    payload["agent_resolution"]["attempts"][0]["type"] = "generalist"
    payload["agent_resolution"]["attempts"][0]["reason"] = "substituted"
    payload["agent_resolution"]["resolved"]["type"] = "generalist"
    return payload


def prompt_only_write() -> dict[str, Any]:
    payload = run_manifest()
    payload["agent_resolution"]["permission_enforcement"] = "prompt-only"
    payload["agent_resolution"]["request"]["permissions"] = "write"
    payload["agent_resolution"]["degraded"] = True
    return payload


def duplicate_accepted_attempt() -> dict[str, Any]:
    payload = run_manifest()
    attempts = payload["agent_resolution"]["attempts"]
    attempts.append(dict(attempts[0]))
    return payload


CASES: list[Case] = [
    agreed_valid("valid manifest", run_manifest()),
    # --- field rules both sides carry ---------------------------------------
    agreed_invalid("missing slug", without("slug")),
    agreed_invalid("unknown phase", top(phase="nonsense")),
    agreed_invalid(
        "two-verb behavior",
        first_curd(behavior="Adds a parser and removes the old one"),
    ),
    agreed_invalid("chained test_target", first_curd(test_target="pytest a && pytest b")),
    agreed_invalid("retry_count above one", first_curd(retry_count=2)),
    agreed_invalid(
        "unknown seed item status",
        top(
            seed={
                "items": [
                    {
                        "description": "shared interface",
                        "files": ["src/iface.ts"],
                        "status": "bogus",
                    }
                ]
            }
        ),
    ),
    agreed_invalid(
        "truncated diff_hash in current_review",
        top(current_review={**review_context(), "diff_hash": "sha256:abc"}),
    ),
    agreed_invalid("empty attempts", resolution(attempts=[])),
    # --- no primitive coercion on either side -------------------------------
    agreed_invalid("quality_gates as a bare string", top(quality_gates="just check")),
    agreed_invalid("carry_forward as a bare string", top(carry_forward="note")),
    agreed_invalid("curd files as a bare string", first_curd(files="src/a.ts")),
    # --- collection invariants both sides carry -----------------------------
    agreed_invalid("two curds claiming the same file", shared_curd_files()),
    agreed_invalid(
        "wiring depends_on an unknown W-id", top(wiring=[wiring_row("W1", ["W9"])])
    ),
    agreed_invalid(
        "wiring DAG cycle",
        top(wiring=[wiring_row("W1", ["W2"]), wiring_row("W2", ["W1"])]),
    ),
    # --- STRICTER: only the types reject ------------------------------------
    stricter(
        "unknown plate_layout",
        top(plate_layout="trellis"),
        "validate_manifest.py never inspects plate_layout; PlateLayout does",
    ),
    stricter(
        "curd worktree_path as an int",
        first_curd(worktree_path=7),
        "the validator only type-checks worktree_path when it is a string",
    ),
    stricter(
        "host_capabilities with a non-bool value",
        top(host_capabilities={"gh": "yes"}),
        "the validator does not check host_capabilities values are booleans",
    ),
    stricter(
        "lone curd missing files",
        lone_curd_without("files"),
        "the validator only requires files below PARALLEL_THRESHOLD curds",
    ),
    stricter(
        "lone curd with empty files",
        lone_curd(files=[]),
        "the validator only requires files below PARALLEL_THRESHOLD curds",
    ),
    # --- LOOSER: only the validator rejects ---------------------------------
    looser(
        "phase post_review_complete without review fields",
        top(phase="post_review_complete"),
        f"{UNMODELLED}: post_review_complete requires current_review/post_review",
    ),
    looser(
        "completed curd without review_context",
        first_curd(status="completed"),
        f"{UNMODELLED}: a completed curd requires review_context",
    ),
    looser(
        "two accepted attempts",
        duplicate_accepted_attempt(),
        f"{UNMODELLED}: exactly one accepted attempt",
    ),
    looser(
        "resolved disagreeing with the accepted attempt",
        resolved(model="other-model"),
        f"{UNMODELLED}: resolved type/model/power must match the accepted attempt",
    ),
    looser(
        "resolved power below the request minimum",
        power("cheap"),
        f"{UNMODELLED}: attempt/resolved power must meet minimum_power",
    ),
    looser(
        "prompt-only enforcement with degraded false",
        resolution(permission_enforcement="prompt-only"),
        f"{UNMODELLED}: prompt-only enforcement requires degraded=true",
    ),
    looser(
        "prompt-only enforcement of a write request",
        prompt_only_write(),
        f"{UNMODELLED}: prompt-only enforcement cannot satisfy a write request",
    ),
    looser(
        "resolved power unknown with degraded false",
        power("unknown"),
        f"{UNMODELLED}: unknown power requires degraded=true",
    ),
    looser(
        "preferred-exact acceptance carrying a fallback_reason",
        resolution(fallback_reason="host substituted"),
        f"{UNMODELLED}: an exact acceptance requires fallback_reason=null",
    ),
    looser(
        "non-preferred acceptance with a null fallback_reason",
        substituted_type(),
        f"{UNMODELLED}: a non-preferred acceptance requires a fallback_reason",
    ),
]


def test_divergence_table_is_honest() -> None:
    assert_table_is_honest(CASES)


@pytest.mark.parametrize("case", agreeing(CASES), ids=ids(agreeing(CASES)))
def test_validator_and_type_agree(case: Case, run_manifest_validator: Validator) -> None:
    assert_conforms(case, run_manifest_validator, RunManifest)


@pytest.mark.parametrize("case", divergent(CASES), ids=ids(divergent(CASES)))
def test_known_divergence_still_holds(
    case: Case, run_manifest_validator: Validator
) -> None:
    assert_conforms(case, run_manifest_validator, RunManifest)
