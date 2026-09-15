"""Pure contextual planner for /age and /affinage review fan-out.

The coordinator gives :func:`route` a complete, evidence-bearing context
record.  The planner validates and canonicalizes that record, then applies a
fixed subject policy without reading the repository or observing host events.
All filesystem and dispatch work remains in the caller.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import cast

from easy_cheese_schemas.validate import (
    require_exact_keys,
    require_int,
    require_list,
    require_mapping,
    require_relative_path,
    require_str,
)

__all__ = [
    "DIMENSIONS",
    "OVERRIDE_FLAGS",
    "POLICY_VERSION",
    "RISK_MAPPINGS",
    "SUBJECTS",
    "check_execution",
    "route",
]

POLICY_VERSION = "age-review-plan.v1"

# These are the report dimensions.  The first ten retain their established
# names; conventions and altitude are intentionally first-class dimensions.
DIMENSIONS: tuple[str, ...] = (
    "correctness",
    "security",
    "encapsulation",
    "spec",
    "complexity",
    "deslop",
    "assertions",
    "nih",
    "efficiency",
    "telemetry",
    "conventions",
    "altitude",
)

# Review subjects are the independent procedures the coordinator can assign.
# Keep this order stable for canonical plan output.
SUBJECTS: tuple[str, ...] = (
    "changed-behavior",
    "removed-behavior",
    "caller-impact",
    "security",
    "spec-tests",
    "reuse",
    "simplification",
    "efficiency",
    "conventions",
    "altitude",
)

_OPTIONAL_SUBJECTS = (
    "security",
    "caller-impact",
    "removed-behavior",
    "spec-tests",
    "efficiency",
    "reuse",
    "simplification",
)

_COMPONENT_ROLES = frozenset(
    {"library", "application", "test", "build", "documentation", "other"}
)
_APPLICABILITY = frozenset({"yes", "no", "unknown"})
_SCOPE = frozenset({"diff", "overall"})
_EFFORTS = ("quick", "normal", "deep")
_WORKER_EFFORT = {"quick": "low", "normal": "medium", "deep": "high"}
_EFFORT_INDEX = {name: index for index, name in enumerate(_EFFORTS)}
_PROTECTED_SUBJECTS = ("conventions", "altitude")

# The old risk signals remain explicit, but now map to review procedures rather
# than dimensions.  The two final rows are the contextual signals introduced
# by the parity contract.
RISK_MAPPINGS: dict[str, str] = {
    "auth": "security",
    "secrets": "security",
    "crypto": "security",
    "tenant-isolation": "security",
    "payments": "changed-behavior",
    "ledgers": "changed-behavior",
    "irreversible-effects": "changed-behavior",
    "production-destructive": "changed-behavior",
    "concurrency": "changed-behavior",
    "idempotency": "changed-behavior",
    "ordering": "changed-behavior",
    "retries": "changed-behavior",
    "schema-migration": "caller-impact",
    "protocol-change": "caller-impact",
    "public-api-change": "caller-impact",
    "weak-integration-coverage": "spec-tests",
    "removed-protection": "removed-behavior",
    "hot-path": "efficiency",
}
OVERRIDE_FLAGS: frozenset[str] = frozenset(RISK_MAPPINGS)

_CONTEXT_KEYS = (
    "scope",
    "effort",
    "snapshot",
    "changed_paths",
    "surface_score",
    "components",
    "subjects",
    "risks",
    "is_subagent",
    "can_fan_out",
    "concurrency_limit",
)
_COMPONENT_KEYS = ("id", "role", "paths")
_SUBJECT_KEYS = ("subject", "applicability", "targets", "evidence")
_RISK_KEYS = ("flag", "state", "evidence")
_OBSERVATION_KEYS = ("assignment_ids", "one_message", "source")
_ASSIGNMENT_KEYS = ("id", "subjects", "targets", "effort", "reasons")

_AFFINAGE_COMMENT_BUMP = 10
_AFFINAGE_CI_BUMP_CLASSES = frozenset({"failing", "red", "flaky"})


def _mapping(value: object, field: str) -> dict[str, object]:
    result = require_mapping(value, field)
    if any(not isinstance(key, str) for key in cast("dict[object, object]", result)):
        raise ValueError(f"{field} keys must be strings")
    return result


def _exact(mapping: dict[str, object], keys: tuple[str, ...], field: str) -> None:
    require_exact_keys(mapping, keys, field)


def _bool(value: object, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field} must be a bool")
    return value


def _choice(
    value: object, field: str, choices: frozenset[str] | tuple[str, ...]
) -> str:
    text = require_str(value, field)
    if text not in choices:
        raise ValueError(f"{field} must be one of {sorted(choices)!r}")
    return text


def _unique_sorted(values: list[str], field: str) -> list[str]:
    if len(values) != len(set(values)):
        raise ValueError(f"{field} must not contain duplicates")
    return sorted(values)


def _paths(value: object, field: str) -> list[str]:
    values = require_list(value, field)
    paths = [
        require_relative_path(item, f"{field}[{index}]")
        for index, item in enumerate(values)
    ]
    return _unique_sorted(paths, field)


def _evidence(value: object, field: str, *, required: bool) -> list[str]:
    values = require_list(value, field)
    evidence = [
        require_str(item, f"{field}[{index}]") for index, item in enumerate(values)
    ]
    if required and not evidence:
        raise ValueError(f"{field} must contain evidence")
    return _unique_sorted(evidence, field)


def _surface_score(value: object) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("surface_score must be a number")
    try:
        number = float(value)
    except (OverflowError, ValueError) as exc:
        raise ValueError("surface_score must be a finite number") from exc
    if not math.isfinite(number) or number < 0:
        raise ValueError("surface_score must be a non-negative finite number")
    # Treat 1 and 1.0 as the same canonical input.  JSON has one numeric
    # domain, while Python callers can otherwise produce two encodings.
    if number.is_integer():
        return int(number)
    return number


def _nonnegative_int(value: object, field: str) -> int:
    number = require_int(value, field)
    if number < 0:
        raise ValueError(f"{field} must be non-negative")
    return number


def _positive_int_or_none(value: object, field: str) -> int | None:
    if value is None:
        return None
    number = require_int(value, field)
    if number <= 0:
        raise ValueError(f"{field} must be positive or null")
    return number


def _normalize_components(value: object) -> list[dict[str, object]]:
    rows = require_list(value, "components")
    normalized: list[dict[str, object]] = []
    seen: set[str] = set()
    for index, raw in enumerate(rows):
        row = _mapping(raw, f"components[{index}]")
        _exact(row, _COMPONENT_KEYS, f"components[{index}]")
        component_id = require_str(row["id"], f"components[{index}].id")
        if component_id in seen:
            raise ValueError(f"components contains duplicate id {component_id!r}")
        seen.add(component_id)
        role = _choice(row["role"], f"components[{index}].role", _COMPONENT_ROLES)
        normalized.append(
            {
                "id": component_id,
                "role": role,
                "paths": _paths(row["paths"], f"components[{index}].paths"),
            }
        )
    normalized.sort(key=lambda item: cast(str, item["id"]))
    return normalized


def _normalize_subjects(value: object) -> list[dict[str, object]]:
    rows = require_list(value, "subjects")
    if len(rows) != len(SUBJECTS):
        raise ValueError(
            f"subjects must contain exactly one row for each of {len(SUBJECTS)} subjects"
        )

    normalized_by_name: dict[str, dict[str, object]] = {}
    for index, raw in enumerate(rows):
        row = _mapping(raw, f"subjects[{index}]")
        _exact(row, _SUBJECT_KEYS, f"subjects[{index}]")
        subject = require_str(row["subject"], f"subjects[{index}].subject")
        if subject not in SUBJECTS:
            raise ValueError(
                f"subjects[{index}].subject must be one of {list(SUBJECTS)!r}"
            )
        if subject in normalized_by_name:
            raise ValueError(f"subjects contains duplicate subject {subject!r}")
        applicability = _choice(
            row["applicability"], f"subjects[{index}].applicability", _APPLICABILITY
        )
        targets = _paths(row["targets"], f"subjects[{index}].targets")
        if applicability != "no" and not targets:
            raise ValueError(
                f"subjects[{index}].targets must be non-empty for {applicability} applicability"
            )
        evidence = _evidence(
            row["evidence"],
            f"subjects[{index}].evidence",
            required=applicability == "no",
        )
        normalized_by_name[subject] = {
            "subject": subject,
            "applicability": applicability,
            "targets": targets,
            "evidence": evidence,
        }

    missing = [subject for subject in SUBJECTS if subject not in normalized_by_name]
    if missing:
        raise ValueError(f"subjects is missing rows for {missing!r}")
    return [normalized_by_name[subject] for subject in SUBJECTS]


def _normalize_risks(
    value: object, subjects: list[dict[str, object]]
) -> list[dict[str, object]]:
    rows = require_list(value, "risks")
    normalized_by_flag: dict[str, dict[str, object]] = {}
    applicability = {row["subject"]: row["applicability"] for row in subjects}
    for index, raw in enumerate(rows):
        row = _mapping(raw, f"risks[{index}]")
        _exact(row, _RISK_KEYS, f"risks[{index}]")
        flag = require_str(row["flag"], f"risks[{index}].flag")
        if flag not in RISK_MAPPINGS:
            raise ValueError(
                f"risks[{index}].flag is not a supported risk signal: {flag!r}"
            )
        if flag in normalized_by_flag:
            raise ValueError(f"risks contains duplicate flag {flag!r}")
        state = _choice(row["state"], f"risks[{index}].state", _APPLICABILITY)
        evidence = _evidence(row["evidence"], f"risks[{index}].evidence", required=True)
        mapped_subject = RISK_MAPPINGS[flag]
        if state in ("yes", "unknown") and applicability[mapped_subject] == "no":
            raise ValueError(
                f"risk {flag!r} contradicts subjects[{mapped_subject!r}].applicability='no'"
            )
        normalized_by_flag[flag] = {"flag": flag, "state": state, "evidence": evidence}
    return [normalized_by_flag[flag] for flag in sorted(normalized_by_flag)]


def _normalize_context(context: object) -> dict[str, object]:
    raw = _mapping(context, "context")
    _exact(raw, _CONTEXT_KEYS, "context")
    scope = _choice(raw["scope"], "context.scope", _SCOPE)
    effort = _choice(raw["effort"], "context.effort", _EFFORTS)
    snapshot = require_str(raw["snapshot"], "context.snapshot")
    subjects = _normalize_subjects(raw["subjects"])
    return {
        "scope": scope,
        "effort": effort,
        "snapshot": snapshot,
        "changed_paths": _paths(raw["changed_paths"], "context.changed_paths"),
        "surface_score": _surface_score(raw["surface_score"]),
        "components": _normalize_components(raw["components"]),
        "subjects": subjects,
        "risks": _normalize_risks(raw["risks"], subjects),
        "is_subagent": _bool(raw["is_subagent"], "context.is_subagent"),
        "can_fan_out": _bool(raw["can_fan_out"], "context.can_fan_out"),
        "concurrency_limit": _positive_int_or_none(
            raw["concurrency_limit"], "context.concurrency_limit"
        ),
    }


def _canonical_json(value: object) -> str:
    return json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def _digest(
    context: dict[str, object], entry: str, comments: int | None, ci_class: str | None
) -> str:
    request = {
        "context": context,
        "entry": entry,
        "comments": comments,
        "ci_class": ci_class,
    }
    return hashlib.sha256(_canonical_json(request).encode("utf-8")).hexdigest()


def _bump_effort(effort: str) -> str:
    index = _EFFORT_INDEX[effort]
    return _EFFORTS[min(index + 1, len(_EFFORTS) - 1)]


def _effective_effort(
    effort: str, entry: str, comments: int | None, ci_class: str | None
) -> tuple[str, list[str]]:
    if entry != "affinage":
        return effort, []
    comment_signal = comments is not None and comments >= _AFFINAGE_COMMENT_BUMP
    ci_signal = ci_class in _AFFINAGE_CI_BUMP_CLASSES
    if not comment_signal and not ci_signal:
        return effort, []
    bumped = _bump_effort(effort)
    if bumped == effort:
        return effort, []
    return bumped, ["affinage-workload-escalation"]


def _ordinary_limit(effort: str, score: int | float) -> tuple[int | None, str]:
    if score < 60:
        band = "small"
    elif score <= 250:
        band = "medium"
    else:
        band = "large"
    if effort == "quick":
        return 1, band
    if effort == "normal":
        return {"small": 1, "medium": 2, "large": 5}[band], band
    if band == "large":
        return None, band
    return {"small": 3, "medium": 5}[band], band


def _targets_for(
    subjects: list[str], by_subject: dict[str, dict[str, object]]
) -> list[str]:
    targets: set[str] = set()
    for subject in subjects:
        targets.update(cast(list[str], by_subject[subject]["targets"]))
    return sorted(targets)


def _assignment(
    assignment_id: str,
    subjects: list[str],
    targets: list[str],
    effort: str,
    reasons: list[str],
) -> dict[str, object]:
    return {
        "id": assignment_id,
        "subjects": sorted(subjects, key=SUBJECTS.index),
        "targets": list(targets),
        "effort": effort,
        "reasons": list(dict.fromkeys(reasons)),
    }


def _risk_by_subject(
    risks: list[dict[str, object]], state: str
) -> dict[str, list[tuple[str, str]]]:
    result: dict[str, list[tuple[str, str]]] = {subject: [] for subject in SUBJECTS}
    for risk in risks:
        flag = cast(str, risk["flag"])
        risk_state = cast(str, risk["state"])
        if risk_state == state:
            result[RISK_MAPPINGS[flag]].append((flag, risk_state))
    for values in result.values():
        values.sort()
    return result


def _max_effort(assignments: list[dict[str, object]]) -> str:
    effort_by_name = {"low": 0, "medium": 1, "high": 2}
    return max(
        (cast(str, assignment["effort"]) for assignment in assignments),
        key=lambda value: effort_by_name[value],
        default="low",
    )


def _chunk(ids: list[str], limit: int | None) -> list[list[str]]:
    if not ids:
        return []
    if limit is None:
        return [list(ids)]
    return [ids[index : index + limit] for index in range(0, len(ids), limit)]


def route(
    *,
    context: dict[str, object],
    entry: str = "age",
    comments: int | None = None,
    ci_class: str | None = None,
) -> dict[str, object]:
    """Validate contextual input and return a deterministic review plan.

    The function is deliberately pure: no repository, host, network, or
    dispatch observation is consulted.  ``entry='affinage'`` retains the
    existing comment/CI workload escalation before the contextual policy is
    applied.
    """
    entry = _choice(entry, "entry", frozenset({"age", "affinage"}))
    if entry == "age" and (comments is not None or ci_class is not None):
        raise ValueError("comments/ci_class require entry='affinage'")
    if comments is not None:
        comments = _nonnegative_int(comments, "comments")
    if ci_class is not None:
        ci_class = require_str(ci_class, "ci_class")

    normalized = _normalize_context(context)
    effective_effort, escalation_reasons = _effective_effort(
        cast(str, normalized["effort"]), entry, comments, ci_class
    )
    score = cast(int | float, normalized["surface_score"])
    scope = cast(str, normalized["scope"])
    subject_rows = cast(list[dict[str, object]], normalized["subjects"])
    by_subject = {cast(str, row["subject"]): row for row in subject_rows}
    applicable_subjects = [
        subject
        for subject in SUBJECTS
        if by_subject[subject]["applicability"] in ("yes", "unknown")
    ]
    relevant = list(SUBJECTS) if scope == "overall" else applicable_subjects
    risks = cast(list[dict[str, object]], normalized["risks"])
    risk_by_subject = _risk_by_subject(risks, "yes")
    unknown_risk_by_subject = _risk_by_subject(risks, "unknown")
    risk_subjects = {subject for subject in relevant if risk_by_subject[subject]}
    worker_effort = _WORKER_EFFORT[effective_effort]
    risk_effort = "high"
    ordinary_limit, band = _ordinary_limit(effective_effort, score)
    required_target_subjects = list(relevant)
    if scope != "overall" and effective_effort != "quick":
        required_target_subjects.extend(
            subject
            for subject in _PROTECTED_SUBJECTS
            if subject not in required_target_subjects
        )
    for subject in required_target_subjects:
        if not cast(list[str], by_subject[subject]["targets"]):
            raise ValueError(
                f"subjects[{subject!r}].targets must be non-empty for its planned assignment"
            )

    desired: list[dict[str, object]] = []

    def reasons_for(subject: str, base: list[str]) -> list[str]:
        reasons = list(base)
        for flag, _ in risk_by_subject[subject]:
            reasons.append(f"risk:{flag}")
        for flag, _ in unknown_risk_by_subject[subject]:
            reasons.append(f"risk-unknown:{flag}")
        return reasons

    if scope == "overall":
        for subject in relevant:
            risked = bool(risk_by_subject[subject])
            desired.append(
                _assignment(
                    subject,
                    [subject],
                    _targets_for([subject], by_subject),
                    risk_effort if risked else worker_effort,
                    reasons_for(subject, ["scope:overall-independent"]),
                )
            )
    else:
        protected = list(_PROTECTED_SUBJECTS) if effective_effort != "quick" else []
        ordinary = [subject for subject in relevant if subject not in protected]
        mandatory = [subject for subject in ordinary if subject in risk_subjects]
        optional = [
            subject
            for subject in _OPTIONAL_SUBJECTS
            if subject in ordinary
            and subject not in risk_subjects
            and not unknown_risk_by_subject[subject]
            and by_subject[subject]["applicability"] == "yes"
        ]

        full_separation = effective_effort == "deep" and band == "large"
        if full_separation:
            extracted_optional = [
                subject for subject in ordinary if subject not in risk_subjects
            ]
            general_subjects = []
        else:
            # Keep one general owner whenever ordinary work remains.  The
            # allowance counts general + optional specialists; risk specialists
            # are protected additions and do not consume that allowance.
            optional_budget = max((ordinary_limit or 1) - 1, 0)
            extracted_optional = optional[:optional_budget]
            general_subjects = [
                subject
                for subject in ordinary
                if subject not in risk_subjects and subject not in extracted_optional
            ]

        if general_subjects:
            general_reasons = ["ordinary-general"]
            if any(
                by_subject[subject]["applicability"] == "unknown"
                or unknown_risk_by_subject[subject]
                for subject in general_subjects
            ):
                general_reasons.append("includes-uncertain-context")
            desired.insert(
                0,
                _assignment(
                    "general",
                    general_subjects,
                    _targets_for(general_subjects, by_subject),
                    worker_effort,
                    general_reasons,
                ),
            )

        for subject in mandatory:
            desired.append(
                _assignment(
                    subject,
                    [subject],
                    _targets_for([subject], by_subject),
                    risk_effort,
                    reasons_for(subject, ["mandatory-risk"]),
                )
            )
        for subject in extracted_optional:
            desired.append(
                _assignment(
                    subject,
                    [subject],
                    _targets_for([subject], by_subject),
                    worker_effort,
                    ["optional-specialist"],
                )
            )
        for subject in protected:
            desired.append(
                _assignment(
                    subject,
                    [subject],
                    _targets_for([subject], by_subject),
                    risk_effort if risk_by_subject[subject] else worker_effort,
                    reasons_for(subject, [f"protected:{subject}"]),
                )
            )

    degraded_reasons: list[str] = []
    if cast(bool, normalized["is_subagent"]):
        degraded_reasons.append("subagent execution restriction")
    if not cast(bool, normalized["can_fan_out"]):
        degraded_reasons.append("agent fan-out unavailable")
    degraded_reason = "; ".join(degraded_reasons) if degraded_reasons else None

    if degraded_reason is not None:
        all_subjects = [
            subject
            for assignment in desired
            for subject in cast(list[str], assignment["subjects"])
        ]
        combined_reasons = ["combined-coverage", f"degraded:{degraded_reason}"]
        for risk in cast(list[dict[str, object]], normalized["risks"]):
            if risk["state"] in ("yes", "unknown"):
                combined_reasons.append(f"risk:{risk['flag']}")
        actual = (
            [
                _assignment(
                    "combined",
                    all_subjects,
                    _targets_for(all_subjects, by_subject),
                    _max_effort(desired),
                    combined_reasons,
                )
            ]
            if all_subjects
            else []
        )
    else:
        actual = desired

    actual_ids = [cast(str, assignment["id"]) for assignment in actual]
    dispatch_batches = _chunk(
        actual_ids, cast(int | None, normalized["concurrency_limit"])
    )
    verifier_available = not degraded_reasons
    candidate_batches = (
        [list(batch) for batch in dispatch_batches] if verifier_available else []
    )
    verification_status = (
        "planned"
        if verifier_available and actual
        else "not-required"
        if not actual
        else "unavailable"
    )
    verification: dict[str, object] = {
        "required": bool(actual),
        "status": verification_status,
        "candidate_batches": candidate_batches,
    }
    if not verifier_available:
        verification["reason"] = degraded_reason

    gap_required = effective_effort == "deep" and bool(actual)
    gap_sweep: dict[str, object] = {
        "required": gap_required,
        "after": "verification",
        "status": (
            "planned"
            if gap_required and verifier_available
            else "unavailable"
            if gap_required
            else "not-required"
        ),
    }
    if gap_required and not verifier_available:
        gap_sweep["reason"] = degraded_reason

    rationale = [
        f"scope:{scope}",
        f"effort:{effective_effort}",
        f"surface-band:{band}",
        f"ordinary-budget:{'full' if ordinary_limit is None else ordinary_limit}",
    ]
    rationale.extend(escalation_reasons)
    if scope == "overall":
        rationale.append("overall-forces-independent-subjects")
    for flag in sorted(
        cast(list[dict[str, object]], normalized["risks"]),
        key=lambda row: cast(str, row["flag"]),
    ):
        if flag["state"] in ("yes", "unknown"):
            rationale.append(
                f"risk:{flag['flag']}->{RISK_MAPPINGS[cast(str, flag['flag'])]}"
            )
    if effective_effort != "quick":
        for subject in _PROTECTED_SUBJECTS:
            rationale.append(f"protected:{subject}")
    if degraded_reason is not None:
        rationale.append(f"degraded:{degraded_reason}")

    owner_by_subject: dict[str, str] = {}
    reasons_by_subject: dict[str, list[str]] = {}
    for assignment in actual:
        assignment_id = cast(str, assignment["id"])
        for subject in cast(list[str], assignment["subjects"]):
            owner_by_subject[subject] = assignment_id
            reasons_by_subject[subject] = list(cast(list[str], assignment["reasons"]))

    dispositions: list[dict[str, object]] = []
    for subject in SUBJECTS:
        row = by_subject[subject]
        owner = owner_by_subject.get(subject)
        if owner is None:
            disposition_reasons = ["not-applicable"]
        else:
            disposition_reasons = reasons_by_subject[subject]
        dispositions.append(
            {
                "subject": subject,
                "applicability": row["applicability"],
                "targets": list(cast(list[str], row["targets"])),
                "evidence": list(cast(list[str], row["evidence"])),
                "owner": owner,
                "assigned": owner is not None,
                "reasons": disposition_reasons,
            }
        )

    plan: dict[str, object] = {
        "policy_version": POLICY_VERSION,
        "scope": scope,
        "input_digest": _digest(normalized, entry, comments, ci_class),
        "n": len(actual),
        "effort": effective_effort,
        "assignments": actual,
        "subject_dispositions": dispositions,
        "rationale": rationale,
        "verification": verification,
        "gap_sweep": gap_sweep,
        "dispatch_batches": dispatch_batches,
        "degraded_reason": degraded_reason,
    }
    # These fields make capability degradation explicit: ``assignments`` is
    # what can be dispatched, while ``desired_assignments`` is the policy plan
    # before a host restriction collapses independent work.
    if degraded_reason is not None:
        plan["desired_n"] = len(desired)
        plan["desired_assignments"] = desired
    return plan


def _validate_assignment_rows(
    value: object, field: str
) -> tuple[list[str], dict[str, list[str]], dict[str, str]]:
    rows = require_list(value, field)
    ids: list[str] = []
    subjects_by_assignment: dict[str, list[str]] = {}
    owner_by_subject: dict[str, str] = {}
    subject_order = {subject: index for index, subject in enumerate(SUBJECTS)}
    for index, raw in enumerate(rows):
        row_field = f"{field}[{index}]"
        row = _mapping(raw, row_field)
        _exact(row, _ASSIGNMENT_KEYS, row_field)
        assignment_id = require_str(row["id"], f"{row_field}.id")
        if assignment_id in ids:
            raise ValueError(f"{field} contains duplicate id {assignment_id!r}")
        ids.append(assignment_id)

        raw_subjects = require_list(row["subjects"], f"{row_field}.subjects")
        if not raw_subjects:
            raise ValueError(f"{row_field}.subjects must not be empty")
        subjects: list[str] = []
        for subject_index, raw_subject in enumerate(raw_subjects):
            subject = require_str(raw_subject, f"{row_field}.subjects[{subject_index}]")
            if subject not in SUBJECTS:
                raise ValueError(f"{field} contains unknown subject {subject!r}")
            if subject in subjects or subject in owner_by_subject:
                raise ValueError(f"{field} repeats subject {subject!r}")
            subjects.append(subject)
        if subjects != sorted(subjects, key=subject_order.__getitem__):
            raise ValueError(f"{row_field}.subjects are not in canonical order")
        _ = _paths(row["targets"], f"{row_field}.targets")
        _ = _choice(
            row["effort"],
            f"{row_field}.effort",
            frozenset({"low", "medium", "high"}),
        )
        _ = _evidence(row["reasons"], f"{row_field}.reasons", required=True)
        subjects_by_assignment[assignment_id] = subjects
        for subject in subjects:
            owner_by_subject[subject] = assignment_id
    return ids, subjects_by_assignment, owner_by_subject


def _validate_dispositions(
    plan: dict[str, object], expected_owner: dict[str, str]
) -> None:
    rows = require_list(plan.get("subject_dispositions"), "plan.subject_dispositions")
    if len(rows) != len(SUBJECTS):
        raise ValueError(
            "plan.subject_dispositions must contain every subject exactly once"
        )
    disposition_keys = (
        "subject",
        "applicability",
        "targets",
        "evidence",
        "owner",
        "assigned",
        "reasons",
    )
    seen: set[str] = set()
    for index, raw in enumerate(rows):
        field = f"plan.subject_dispositions[{index}]"
        row = _mapping(raw, field)
        _exact(row, disposition_keys, field)
        subject = require_str(row["subject"], f"{field}.subject")
        if subject not in SUBJECTS or subject in seen:
            raise ValueError(
                f"{field}.subject is not the canonical subject at this position"
            )
        if subject != SUBJECTS[index]:
            raise ValueError(f"{field}.subject is not in canonical order")
        seen.add(subject)
        applicability = _choice(
            row["applicability"], f"{field}.applicability", _APPLICABILITY
        )
        targets = _paths(row["targets"], f"{field}.targets")
        _ = _evidence(
            row["evidence"],
            f"{field}.evidence",
            required=applicability == "no",
        )
        owner_value = row["owner"]
        owner = (
            None if owner_value is None else require_str(owner_value, f"{field}.owner")
        )
        assigned = _bool(row["assigned"], f"{field}.assigned")
        expected = expected_owner.get(subject)
        if owner != expected or assigned != (expected is not None):
            raise ValueError(f"{field} does not match assignment ownership")
        if assigned and not targets:
            raise ValueError(
                f"{field}.targets must be non-empty for an assigned subject"
            )
        _ = _evidence(row["reasons"], f"{field}.reasons", required=True)


def _validate_plan(plan: object) -> list[str]:
    mapping = _mapping(plan, "plan")
    policy_version = require_str(mapping.get("policy_version"), "plan.policy_version")
    if policy_version != POLICY_VERSION:
        raise ValueError(
            f"plan.policy_version must be {POLICY_VERSION!r}, got {policy_version!r}"
        )
    scope = _choice(mapping.get("scope"), "plan.scope", _SCOPE)
    effort = _choice(mapping.get("effort"), "plan.effort", _EFFORTS)
    ids, assignments, owner_by_subject = _validate_assignment_rows(
        mapping.get("assignments"), "plan.assignments"
    )
    n = require_int(mapping.get("n"), "plan.n")
    if n != len(ids):
        raise ValueError(f"plan.n={n} does not match {len(ids)} assignments")

    batches = require_list(mapping.get("dispatch_batches"), "plan.dispatch_batches")
    flattened: list[str] = []
    for index, raw_batch in enumerate(batches):
        batch = require_list(raw_batch, f"plan.dispatch_batches[{index}]")
        if not batch:
            raise ValueError(f"plan.dispatch_batches[{index}] must not be empty")
        batch_ids: list[str] = []
        for item_index, item in enumerate(batch):
            item_id = require_str(item, f"plan.dispatch_batches[{index}][{item_index}]")
            if item_id in flattened or item_id in batch_ids:
                raise ValueError(
                    f"plan.dispatch_batches repeats assignment id {item_id!r}"
                )
            batch_ids.append(item_id)
        flattened.extend(batch_ids)
    if flattened != ids:
        raise ValueError(
            "plan.dispatch_batches must contain each assignment id exactly in plan order"
        )

    degraded_value = mapping.get("degraded_reason")
    degraded = degraded_value is not None
    if degraded:
        _ = require_str(degraded_value, "plan.degraded_reason")
        if ids != ["combined"]:
            raise ValueError("degraded plans must dispatch one combined assignment")
        desired_ids, desired_assignments, desired_owner = _validate_assignment_rows(
            mapping.get("desired_assignments"), "plan.desired_assignments"
        )
        desired_n = require_int(mapping.get("desired_n"), "plan.desired_n")
        if desired_n != len(desired_ids):
            raise ValueError(
                f"plan.desired_n={desired_n} does not match {len(desired_ids)} desired assignments"
            )
        if set(owner_by_subject) != set(desired_owner):
            raise ValueError("degraded assignments must preserve every desired subject")
    else:
        desired_assignments = assignments

    _validate_dispositions(mapping, owner_by_subject)
    assigned_subjects = set(owner_by_subject)
    independent_assignments = desired_assignments if degraded else assignments

    if scope == "overall":
        if assigned_subjects != set(SUBJECTS):
            raise ValueError("overall plans must assign every subject")
        if any(len(subjects) != 1 for subjects in independent_assignments.values()):
            raise ValueError("overall plans must assign each subject independently")
    elif effort != "quick":
        for protected in _PROTECTED_SUBJECTS:
            if not any(
                subjects == [protected] for subjects in independent_assignments.values()
            ):
                raise ValueError(
                    f"{effort} plans must reserve {protected!r} independently"
                )
    return ids


def _normalize_observed_ids(value: object) -> list[str]:
    values = require_list(value, "observations.assignment_ids")
    result: list[str] = []
    for index, item in enumerate(values):
        assignment_id = require_str(item, f"observations.assignment_ids[{index}]")
        if assignment_id in result:
            raise ValueError(
                f"observations.assignment_ids contains duplicate id {assignment_id!r}"
            )
        result.append(assignment_id)
    return result


def check_execution(
    *, plan: dict[str, object], observations: dict[str, object] | None
) -> dict[str, object]:
    """Compare planned IDs with reported IDs without authenticating execution.

    ``None`` means no observation was available.  A ``reported`` observation
    can be internally consistent, but remains explicitly unverified; even a
    ``host`` observation is only consistency-checked by this pure function.
    """
    planned_ids = _validate_plan(plan)
    plan_mapping = _mapping(plan, "plan")
    planned_batches = require_list(
        plan_mapping.get("dispatch_batches"), "plan.dispatch_batches"
    )
    expected_one_message = bool(planned_ids) and len(planned_batches) == 1
    if observations is None:
        return {
            "status": "unobserved",
            "consistent": False,
            "verified": False,
            "authenticated": False,
            "source": None,
            "planned_assignment_ids": planned_ids,
            "observed_assignment_ids": None,
            "missing_assignment_ids": planned_ids,
            "unexpected_assignment_ids": [],
            "one_message": None,
            "expected_one_message": expected_one_message,
            "errors": [],
            "warnings": [
                "dispatch observations unavailable; host execution was not authenticated"
            ],
        }

    observed = _mapping(observations, "observations")
    _exact(observed, _OBSERVATION_KEYS, "observations")
    observed_ids = _normalize_observed_ids(observed["assignment_ids"])
    one_message = _bool(observed["one_message"], "observations.one_message")
    source = _choice(
        observed["source"], "observations.source", frozenset({"host", "reported"})
    )

    planned_set = set(planned_ids)
    observed_set = set(observed_ids)
    missing = [
        assignment_id
        for assignment_id in planned_ids
        if assignment_id not in observed_set
    ]
    unexpected = sorted(
        assignment_id
        for assignment_id in observed_ids
        if assignment_id not in planned_set
    )
    ids_match = not missing and not unexpected
    consistent = ids_match and one_message == expected_one_message
    if consistent:
        status = "consistent" if source == "host" else "unverified"
    else:
        status = "inconsistent-unverified" if source == "reported" else "inconsistent"
    warnings = (
        ["reported observations are unverified"]
        if source == "reported"
        else [
            "host observations are consistency-checked only; execution is not authenticated"
        ]
    )
    errors: list[str] = []
    if missing:
        errors.append(f"missing assignments: {', '.join(missing)}")
    if unexpected:
        errors.append(f"unexpected assignments: {', '.join(unexpected)}")
    if one_message != expected_one_message:
        expected = "one" if expected_one_message else "multiple"
        errors.append(
            f"dispatch message form did not match planned {expected}-batch dispatch"
        )
    return {
        "status": status,
        "consistent": consistent,
        "verified": False,
        "authenticated": False,
        "source": source,
        "planned_assignment_ids": planned_ids,
        "observed_assignment_ids": observed_ids,
        "missing_assignment_ids": missing,
        "unexpected_assignment_ids": unexpected,
        "one_message": one_message,
        "expected_one_message": expected_one_message,
        "errors": errors,
        "warnings": warnings,
    }
