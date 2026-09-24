"""Contract tests for Mold's follow-up disposition and publication protocol."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MOLD = REPO_ROOT / "skills" / "mold" / "SKILL.md"
HANDSHAKE = REPO_ROOT / "skills" / "mold" / "references" / "handshake.md"
CURDLE = REPO_ROOT / "skills" / "mold" / "references" / "curdle.md"
ADR = REPO_ROOT / "skills" / "mold" / "references" / "adr.md"
MODES = REPO_ROOT / "skills" / "mold" / "references" / "modes.md"
CURD_COUNT = REPO_ROOT / "skills" / "mold" / "references" / "curd-count.md"
SCOPED_DOCS = (MOLD, HANDSHAKE, CURDLE, ADR)
EARLY_CURDS = REPO_ROOT / "skills" / "mold" / "references" / "early-curds.md"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _section(path: Path, heading: str) -> str:
    body = _text(path)
    marker = f"## {heading}"
    match = re.search(rf"(?m)^{re.escape(marker)}", body)
    assert match, f"heading {marker!r} not found in {path}"
    start = match.start()
    end = body.find("\n## ", start + len(marker))
    return body[start:] if end == -1 else body[start:end]


def _assert_in_order(body: str, *phrases: str) -> None:
    folded = body.casefold()
    positions = [folded.index(phrase.casefold()) for phrase in phrases]
    assert positions == sorted(positions), f"phrases out of order: {phrases}"


def _assert_phrases(path: Path, *phrases: str) -> None:
    body = _text(path).casefold()
    missing = [phrase for phrase in phrases if phrase.casefold() not in body]
    assert not missing, f"{path.relative_to(REPO_ROOT)} missing: {missing}"


def test_scoped_documents_exist() -> None:
    missing = [str(path) for path in SCOPED_DOCS if not path.exists()]
    assert not missing, f"Mold follow-up routing files moved or renamed: {missing}"


def test_user_key_requires_cook_intent_without_inference() -> None:
    section = _section(HANDSHAKE, "User key")
    for phrase in (
        "intent to Cook the displayed scope or plan",
        "cook it",
        "cook this",
        "explicit `/cook` selection",
        "general approval of the design",
        "unrelated or ambiguous approval",
        "exact proposal",
    ):
        assert phrase.casefold() in section.casefold()


def test_user_key_binds_a_literal_response_to_the_exact_proposal() -> None:
    section = _section(HANDSHAKE, "User key")
    assert "Judge the key by intent" in section
    assert "literal response" in section
    assert "exact proposal" in section
    assert "approval to write the spec" not in section


def test_candidate_collection_is_non_committing_dialogue_state() -> None:
    _assert_phrases(
        MOLD,
        "every non-goal and explicit dialogue deferral",
        "follow-up candidate",
        "[FOLLOW-UP?]",
    )
    _assert_phrases(
        HANDSHAKE,
        "within `Decided`",
        "does not create",
    )


def test_followup_batch_covers_grouping_discovery_and_publication_consent() -> None:
    _assert_phrases(
        HANDSHAKE,
        "Before a runnable handoff",
        "independently deliverable units",
        "GitHub Issues",
        "roadmap goals",
        "semantic match",
        "grouping",
        "destination",
        "action",
        "user must select any external",
        "when no candidates exist",
    )


def test_followup_disposition_stays_inside_one_user_owned_gate() -> None:
    section = _section(HANDSHAKE, "Follow-up disposition (inside the non-goals audit)")
    _assert_in_order(
        section,
        "dispose of every follow-up candidate in one batch",
        "group related candidates",
        "when discovery is available",
        "recommend one destination per unit",
        "user must select any external",
        "record accepted units for Curdle",
    )
    for phrase in (
        "extends the existing `Non-goals audit` gate",
        "does not add or rename a gate",
        "No external create/link action runs without the user's selection",
    ):
        assert phrase.casefold() in section.casefold()


def test_disposition_rules_keep_scope_boundaries_distinct() -> None:
    _assert_phrases(
        HANDSHAKE,
        "non-goal only",
        "create no follow-up artifact",
        "no action choice",
        "discrete, independently actionable work",
        "coordinated, milestone-scale, or dependency-linked work",
        "local issue draft",
        "publication is not desired or available",
    )
    _assert_phrases(
        CURDLE,
        "rejected direction",
        "not a follow-up candidate",
    )


def test_spec_template_records_deferred_followups() -> None:
    body = _text(CURDLE)
    non_goals = body.index("## Non-goals")
    deferred = body.index("## Deferred follow-ups", non_goals)
    approach = body.index("## Approach", deferred)
    assert non_goals < deferred < approach
    _assert_phrases(
        CURDLE,
        "deterministic follow-up ID",
        "destination",
        "prepared | linked | created",
        "reference",
    )


def test_local_curdle_is_write_ahead_and_spec_is_authoritative() -> None:
    _assert_phrases(
        CURDLE,
        "two-phase Curdle",
        "Phase one",
        "before any external call",
        "`$SPEC` is the authoritative",
        "durable project corpus",
        "local issue drafts",
        "auxiliary",
        "mold-follow-up-routing-F001",
    )


def test_two_phase_curdle_orders_local_state_before_publication_and_handoff() -> None:
    section = _section(CURDLE, "Two-phase Curdle for accepted follow-ups")
    _assert_in_order(
        section,
        "Phase one",
        "before any external call",
        "Phase two",
        "exact deterministic follow-up ID",
        "before creation",
        "before the implementation handoff",
    )
    for phrase in (
        "only units whose approved action is **create/link now**",
        "local issue draft destination completes as `prepared` in phase one",
        "when that skill and its required capability are available",
        "keep the follow-up prepared",
        "continue without blocking the approved spec",
    ):
        assert phrase.casefold() in section.casefold()


def test_external_publication_is_recoverable_and_idempotent() -> None:
    _assert_phrases(
        CURDLE,
        "Phase two",
        "host GitHub capability",
        "`gh`",
        "/wiki-roadmap",
        "exact deterministic follow-up ID",
        "before creation",
        "SHALL NOT create a duplicate",
        "publication fails",
        "keep the follow-up prepared",
        "continue",
        "before the implementation handoff",
    )


def test_mold_handoff_waits_for_user_selection_and_reconciliation() -> None:
    flow = _section(MOLD, "Flow")
    _assert_in_order(
        flow,
        "Write the validated draft",
        "publish follow-ups only after their own approval",
        "after reconciliation",
        "If the user selects Cook",
        "Dispatch only a ready pointer",
    )

    handoff = _section(MOLD, "Handoff")
    _assert_in_order(
        handoff,
        "A draft offers no Cook command",
        "explicit Cook selection",
        "consumer-valid canonical `HandoffPointer`",
    )

    followups = _section(HANDSHAKE, "Follow-up disposition (inside the non-goals audit)")
    _assert_in_order(
        followups,
        "writes local artifacts first",
        "user selects a follow-up action",
        "publishes that approved follow-up",
        "reconciles state and references",
        "before any implementation handoff",
    )


def test_mold_saves_draft_before_cook_consent_and_persists_typed_plan() -> None:
    flow = _section(MOLD, "Flow")
    _assert_in_order(
        flow,
        "5. **Plan and validate**",
        "6. **Readiness check**",
        "7. **Curdle**",
        "8. **Offer Cook or keep shaping**",
    )

    gate = _section(MOLD, "Execution gate")
    _assert_in_order(
        gate,
        "save a validated parent spec or early curd mini-spec",
        "Never start Cook from a saved spec",
        "user must select the exact curd",
        "Bind that literal selection",
    )

    procedure = _section(CURDLE, "Pre-approval typed planner dispatch")
    _assert_in_order(
        procedure,
        "1. **Dispatch**",
        "2. **Validate and normalize**",
        "`N curds / M waves`",
        "Persist the draft spec and host-validated `PlannerResult` and `CurdPlan`",
    )


def test_early_curd_route_selection_stays_separate_from_scope_approval() -> None:
    selection = _section(EARLY_CURDS, "Cook selection")
    _assert_in_order(
        selection,
        "Ask one route question",
        "Record the selected route beside the child",
        "Execute only that route",
        "For **Cook here in isolation**",
        "For **Cook in another worktree**",
    )
    assert "approval envelope binds the scope or plan, not the dispatch route" in selection.casefold()
    assert "without starting local Cook or publishing a local execution pointer" in selection


def test_mold_never_hardcodes_transient_spec_paths() -> None:
    offenders = [
        str(path.relative_to(REPO_ROOT))
        for path in (MOLD, CURDLE, MODES, CURD_COUNT)
        if ".cheese/specs/" in _text(path)
    ]
    assert not offenders, (
        "Mold must pass the resolver-owned durable spec path downstream: "
        + ", ".join(offenders)
    )


def test_spec_retention_language_matches_durable_corpus_contract() -> None:
    contradiction = re.compile(
        r"\b(?:the )?spec(?:ification)?s?\s+(?:is|are|remain)\s+transient\b",
        re.IGNORECASE,
    )
    offenders = [
        str(path.relative_to(REPO_ROOT))
        for path in SCOPED_DOCS
        if contradiction.search(_text(path))
    ]
    assert not offenders, (
        "Mold contradicts the durable spec-corpus contract in: " + ", ".join(offenders)
    )
    _assert_phrases(ADR, "durable project corpus")
