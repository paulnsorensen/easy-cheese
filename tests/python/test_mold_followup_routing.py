"""Contract tests for Mold's follow-up disposition and publication protocol."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MOLD = REPO_ROOT / "skills" / "mold" / "SKILL.md"
HANDSHAKE = REPO_ROOT / "skills" / "mold" / "references" / "handshake.md"
CURDLE = REPO_ROOT / "skills" / "mold" / "references" / "curdle.md"
ADR = REPO_ROOT / "skills" / "mold" / "references" / "adr.md"
SCOPED_DOCS = (MOLD, HANDSHAKE, CURDLE, ADR)


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _section(path: Path, heading: str) -> str:
    body = _text(path)
    marker = f"## {heading}"
    start = body.index(marker)
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


def test_candidate_collection_is_non_committing_dialogue_state() -> None:
    _assert_phrases(
        MOLD,
        "every non-goal and explicit dialogue deferral",
        "follow-up candidate",
        "[FOLLOW-UP?]",
        "within `Decided`",
        "does not create",
    )


def test_pre_curdle_batch_covers_grouping_discovery_and_approval() -> None:
    _assert_phrases(
        HANDSHAKE,
        "before the two-key handshake",
        "independently deliverable units",
        "GitHub Issues",
        "roadmap goals",
        "semantic match",
        "grouping",
        "splitting",
        "destination",
        "action",
        "user approves",
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
        "the user approves the destination",
        "record accepted units for Curdle",
    )
    for phrase in (
        "extends the existing `Non-goals audit` gate",
        "does not add or rename a gate",
        "the user approves grouping, splitting, semantic-match reuse, destination",
        "Mold settles none silently",
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


def test_mold_handoff_waits_for_followup_reconciliation() -> None:
    flow = _section(MOLD, "Flow")
    _assert_in_order(
        flow,
        "local artifacts and write-ahead prepared state",
        "publishes approved follow-ups",
        "reconciles their state and references into the durable spec",
        "curd-count",
        "handoff gate",
    )

    handoff = _section(MOLD, "Handoff")
    _assert_in_order(
        handoff,
        "phase-two publication attempts",
        "mechanical reconciliation",
        "curd-count",
        "shared handoff gate",
    )

    followups = _section(MOLD, "Follow-up candidates")
    _assert_in_order(
        followups,
        "after both keys pass",
        "writes local artifacts first",
        "publishes approved follow-ups",
        "reconciles their state and references into the durable spec",
        "only then renders the implementation handoff",
    )


def test_mold_never_hardcodes_transient_spec_paths() -> None:
    offenders = [
        str(path.relative_to(REPO_ROOT))
        for path in (MOLD, CURDLE)
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
