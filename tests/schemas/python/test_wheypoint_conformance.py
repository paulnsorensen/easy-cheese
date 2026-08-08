"""Wheypoint continuity schemas: what a durable record will and will not accept.

Unlike the other suites in this directory there is no second source of truth to
conform against -- no hand-rolled validator describes these types yet -- so the
cases pin the rules themselves: the identifier and bound constants directly,
the protected-entry transition rules, the delta's omitted-versus-empty
distinction, and the derived-status truth table that keeps a caller from
declaring `ok` over an active gate.
"""

from __future__ import annotations

from typing import Any

import attrs
import pytest
from easy_cheese_schemas import (
    __all__ as schema_exports,
    SCHEMA_VERSION,
    ProposedEntry,
    Provenance,
    WheypointDelta,
    WheypointProjection,
    WheypointRecord,
    WheypointRevision,
    WheypointStatus,
    NextAction,
    NextMove,
    load,
)
from easy_cheese_schemas.wheypoint import (
    _DIGEST_RE,
    _ID_RE,
    _MAX_ID,
    _MAX_ITEMS,
    _MAX_LEDGER,
    _MAX_TEXT,
)

DIGEST = "sha256:" + "0" * 64
OTHER_DIGEST = "sha256:" + "1" * 64


def merged(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    return {**base, **overrides}


def dossier() -> list[dict[str, Any]]:
    return [
        {
            "fork": "store status or derive it",
            "options": [
                {
                    "option": "derive from protected entries",
                    "evidence": ["src/easy_cheese_schemas/wheypoint.py:1"],
                    "breaks": "callers that wrote a status literal",
                }
            ],
            "prior_leaning": "derive",
        }
    ]


def entry(entry_id: str, **overrides: Any) -> dict[str, Any]:
    return merged(
        {
            "entry_id": entry_id,
            "kind": "question",
            "summary": f"open question {entry_id}",
            "state": "active",
            "blocks_continuation": True,
            "rationale": None,
            "superseded_by": None,
        },
        overrides,
    )


def next_action(**overrides: Any) -> dict[str, Any]:
    return merged(
        {"move": "cook", "orientation": "schema types drafted", "artifact": None},
        overrides,
    )


def record(**overrides: Any) -> dict[str, Any]:
    return merged(
        {
            "schema_version": 1,
            "work_id": "wheypoint-continuity-kernel",
            "slug": "wheypoint-schema-contract",
            "title": "Wheypoint schema contract",
            "created": "2026-08-02T10:00:00Z",
            "project_key": "paulnsorensen-easy-cheese",
            "revision_id": "rev-0002",
            "revision_number": 2,
            "revision_digest": DIGEST,
            "orientation": "schema types drafted, tests failing",
            "working_context": ["src/easy_cheese_schemas/wheypoint.py"],
            "next_action": next_action(),
            "decision_dossier": [],
            "decisions": [],
            "questions": [],
            "blockers": [],
            "artifact_links": [],
        },
        overrides,
    )


def delta(**overrides: Any) -> dict[str, Any]:
    return merged(
        {"work_id": "wheypoint-continuity-kernel", "expected_revision_id": "rev-0002"},
        overrides,
    )


def revision(**overrides: Any) -> dict[str, Any]:
    return merged(
        {
            "schema_version": 1,
            "work_id": "wheypoint-continuity-kernel",
            "parent_revision_id": "rev-0002",
            "revision_id": "rev-0003",
            "revision_number": 3,
            "request_digest": DIGEST,
            "record_digest": OTHER_DIGEST,
            "applied_additions": [],
            "applied_transitions": [],
            "preserved_entry_ids": [],
            "rehydrated_from_revision_id": None,
            "session_provenance": None,
            "repository": {"branch": "main", "commit": "a" * 40},
            "projection_path": "projections/3-rev-0003.md",
            "projection_digest": DIGEST,
        },
        overrides,
    )


def projection(**overrides: Any) -> dict[str, Any]:
    return merged(
        {
            "schema_version": 1,
            "work_id": "wheypoint-continuity-kernel",
            "revision_id": "rev-0003",
            "record_digest": DIGEST,
            "projection_digest": OTHER_DIGEST,
            "next_action": next_action(),
            "gating_entry_ids": [],
            "decision_dossier": [],
            "durability": "canonical-local",
        },
        overrides,
    )


def structured(payload: dict[str, Any], cls: type) -> Any:
    loaded = load(payload, cls, strict=True)
    assert loaded.value is not None, (
        f"{cls.__name__} refused a payload it should accept: {loaded.problems}"
    )
    assert loaded.problems == ()
    return loaded.value


def refused(payload: dict[str, Any], cls: type) -> tuple[str, ...]:
    loaded = load(payload, cls, strict=True)
    assert loaded.value is None, f"{cls.__name__} accepted a payload it should refuse"
    assert loaded.problems, f"{cls.__name__} refused without saying why"
    return loaded.problems


def blames(problems: tuple[str, ...], path: str) -> bool:
    """True when some problem blames `path` itself or something under it: a
    failure reported at `session_provenance.session_id` is still a failure of
    `session_provenance`."""
    return any(
        problem.startswith((f"{path} ", f"{path}.", f"{path}["))
        for problem in problems
    )


# --- acceptance 1: the four types are public exports ------------------------


def test_the_four_types_are_public_exports() -> None:
    for exported in (
        WheypointRecord,
        WheypointDelta,
        WheypointRevision,
        WheypointProjection,
    ):
        assert exported.__name__ in schema_exports
        assert exported.__module__ == "easy_cheese_schemas.wheypoint"
        assert attrs.has(exported)
        assert exported.__attrs_attrs__ is not None
        assert attrs.resolve_types(exported) is exported


def test_the_four_types_are_frozen() -> None:
    value = structured(record(), WheypointRecord)
    with pytest.raises(attrs.exceptions.FrozenInstanceError):
        value.work_id = "other"  # type: ignore[misc]


def test_every_persisted_artifact_carries_its_own_vintage() -> None:
    """A revision and a projection are separate immutable files, so each has to
    say what it was written against: a receipt cannot inherit a vintage from a
    record that has moved on since."""
    for payload, cls in (
        (record(), WheypointRecord),
        (revision(), WheypointRevision),
        (projection(), WheypointProjection),
    ):
        stamped = load(
            merged(payload, {"schema_version": SCHEMA_VERSION}), cls, strict=True
        )
        assert stamped.provenance is Provenance.CURRENT
        assert stamped.value is not None, stamped.problems

        unstamped = load(
            {key: value for key, value in payload.items() if key != "schema_version"},
            cls,
            strict=True,
        )
        assert unstamped.provenance is Provenance.UNSTAMPED
        assert unstamped.value is None
        assert blames(unstamped.problems, f"{cls.__name__}.schema_version")


# --- the central bounds, tested directly ------------------------------------


def test_identifier_pattern_accepts_and_rejects_exactly() -> None:
    for good in ("rev-0003", "w1", "a" * _MAX_ID, "work.id_2"):
        assert _ID_RE.fullmatch(good), good
    for bad in ("", "-lead", "Upper", "has space", "a" * (_MAX_ID + 1), "sl/ash"):
        assert _ID_RE.fullmatch(bad) is None, bad


def test_digest_pattern_requires_lowercase_sha256() -> None:
    assert _DIGEST_RE.fullmatch(DIGEST)
    for bad in ("sha256:" + "A" * 64, "sha256:" + "0" * 63, "0" * 64, "md5:" + "0" * 32):
        assert _DIGEST_RE.fullmatch(bad) is None, bad


def test_text_bound_is_the_central_constant() -> None:
    structured(record(orientation="x" * _MAX_TEXT), WheypointRecord)
    problems = refused(record(orientation="x" * (_MAX_TEXT + 1)), WheypointRecord)
    assert blames(problems, "WheypointRecord.orientation")
    assert str(_MAX_TEXT) in " ".join(problems)


def test_collection_bound_is_the_central_constant() -> None:
    structured(record(working_context=["line"] * _MAX_ITEMS), WheypointRecord)
    problems = refused(record(working_context=["line"] * (_MAX_ITEMS + 1)), WheypointRecord)
    assert blames(problems, "WheypointRecord.working_context")
    assert str(_MAX_ITEMS) in " ".join(problems)


def test_bounded_collections_of_entries_are_capped() -> None:
    at_bound = [
        entry(f"q{index}", blocks_continuation=False) for index in range(_MAX_ITEMS)
    ]
    structured(record(questions=at_bound), WheypointRecord)
    problems = refused(
        record(questions=[*at_bound, entry("qx", blocks_continuation=False)]),
        WheypointRecord,
    )
    assert blames(problems, "WheypointRecord.questions")
    assert str(_MAX_ITEMS) in " ".join(problems)


def largest_legal_record() -> dict[str, Any]:
    """Every protected list at its cap, every question and blocker gating."""
    return record(
        decisions=[
            entry(f"d{index}", kind="decision", blocks_continuation=False)
            for index in range(_MAX_ITEMS)
        ],
        questions=[entry(f"q{index}") for index in range(_MAX_ITEMS)],
        blockers=[entry(f"b{index}", kind="blocker") for index in range(_MAX_ITEMS)],
        decision_dossier=dossier(),
    )


def test_the_largest_legal_record_round_trips_through_receipt_and_projection() -> None:
    """The ledgers aggregate the three per-kind lists, so a record the schema
    accepts must be describable by a receipt and a projection. A tighter ledger
    bound would force the commit transaction to truncate the preservation
    ledger, which is the silent drop of protected state this kernel prevents."""
    value = structured(largest_legal_record(), WheypointRecord)
    preserved = [
        protected.entry_id
        for protected in (*value.decisions, *value.questions, *value.blockers)
    ]
    assert len(preserved) == _MAX_LEDGER

    receipt = structured(
        revision(
            preserved_entry_ids=preserved,
            applied_additions=[
                entry(f"n{index}", kind="decision", blocks_continuation=False)
                for index in range(_MAX_LEDGER)
            ],
        ),
        WheypointRevision,
    )
    assert receipt.preserved_entry_ids == preserved
    assert len(receipt.applied_additions) == _MAX_LEDGER

    gating = list(value.gating_entry_ids)
    assert len(gating) == 2 * _MAX_ITEMS
    view = structured(
        projection(gating_entry_ids=gating, decision_dossier=dossier()),
        WheypointProjection,
    )
    assert view.gating_entry_ids == gating
    assert view.status is WheypointStatus.GATED


def test_the_ledger_bound_is_the_central_aggregate_constant() -> None:
    ids = [f"e{index}" for index in range(_MAX_LEDGER)]
    structured(revision(preserved_entry_ids=ids), WheypointRevision)
    problems = refused(revision(preserved_entry_ids=[*ids, "extra"]), WheypointRevision)
    assert blames(problems, "WheypointRevision.preserved_entry_ids")
    assert str(_MAX_LEDGER) in " ".join(problems)


# --- acceptance 2: malformed identifiers, text, digests, provenance ---------


@pytest.mark.parametrize(
    "bad", ["", "Upper-Case", "has space", "-leading", "a" * (_MAX_ID + 1), 7, None]
)
def test_record_rejects_a_malformed_work_id(bad: Any) -> None:
    assert blames(refused(record(work_id=bad), WheypointRecord), "WheypointRecord.work_id")


@pytest.mark.parametrize("bad", ["", "Rev-1", "rev 1", 3])
def test_delta_rejects_a_malformed_expected_revision(bad: Any) -> None:
    problems = refused(delta(expected_revision_id=bad), WheypointDelta)
    assert blames(problems, "WheypointDelta.expected_revision_id")


@pytest.mark.parametrize("bad", ["", "sha1:" + "0" * 40, "0" * 64, "sha256:" + "Z" * 64])
def test_record_rejects_a_malformed_revision_digest(bad: str) -> None:
    problems = refused(record(revision_digest=bad), WheypointRecord)
    assert blames(problems, "WheypointRecord.revision_digest")


def test_revision_rejects_a_malformed_request_digest() -> None:
    problems = refused(revision(request_digest="nope"), WheypointRevision)
    assert blames(problems, "WheypointRevision.request_digest")


@pytest.mark.parametrize(
    "provenance",
    [
        {"harness": "claude", "session_id": "NOT AN ID", "captured_at": None},
        {"harness": "", "session_id": "abc-123", "captured_at": None},
        {"harness": "claude", "session_id": "abc-123", "captured_at": "x" * (_MAX_TEXT + 1)},
        "claude:abc-123",
    ],
)
def test_revision_rejects_an_invalid_session_provenance_shape(provenance: Any) -> None:
    problems = refused(revision(session_provenance=provenance), WheypointRevision)
    assert blames(problems, "WheypointRevision.session_provenance")


def test_revision_rejects_a_non_hex_repository_commit() -> None:
    problems = refused(
        revision(repository={"branch": "main", "commit": "HEAD"}), WheypointRevision
    )
    assert blames(problems, "WheypointRevision.repository.commit")


def test_revision_accepts_a_genesis_parent_and_bare_repository_provenance() -> None:
    value = structured(
        revision(parent_revision_id=None, repository={"branch": None, "commit": None}),
        WheypointRevision,
    )
    assert value.parent_revision_id is None
    assert value.repository.branch is None


def test_revision_number_must_be_positive() -> None:
    assert blames(
        refused(revision(revision_number=0), WheypointRevision),
        "WheypointRevision.revision_number",
    )


def test_revision_preservation_ledger_holds_entry_ids() -> None:
    value = structured(revision(preserved_entry_ids=["d1", "q2"]), WheypointRevision)
    assert value.preserved_entry_ids == ["d1", "q2"]
    assert blames(
        refused(revision(preserved_entry_ids=["D1"]), WheypointRevision),
        "WheypointRevision.preserved_entry_ids",
    )


# --- acceptance 2: protected-entry transitions ------------------------------


def test_a_settled_entry_must_carry_its_rationale() -> None:
    problems = refused(
        record(questions=[entry("q1", state="resolved", rationale=None)]),
        WheypointRecord,
    )
    assert blames(problems, "WheypointRecord.questions[1].rationale")
    structured(
        record(questions=[entry("q1", state="resolved", rationale="answered in review")]),
        WheypointRecord,
    )


def test_a_superseded_entry_must_name_its_successor() -> None:
    problems = refused(
        record(
            questions=[entry("q1", state="superseded", rationale="folded into q2")]
        ),
        WheypointRecord,
    )
    assert blames(problems, "WheypointRecord.questions[1].superseded_by")
    structured(
        record(
            questions=[
                entry(
                    "q1",
                    state="superseded",
                    rationale="folded into q2",
                    superseded_by="q2",
                ),
                entry("q2", blocks_continuation=False),
            ]
        ),
        WheypointRecord,
    )


def test_an_active_entry_may_not_name_a_successor() -> None:
    problems = refused(
        record(questions=[entry("q1", superseded_by="q2")]), WheypointRecord
    )
    assert blames(problems, "WheypointRecord.questions[1].superseded_by")


def test_each_protected_list_holds_only_its_own_kind() -> None:
    problems = refused(record(decisions=[entry("q1")]), WheypointRecord)
    assert blames(problems, "WheypointRecord.decisions")


def test_a_decision_cannot_block_continuation() -> None:
    problems = refused(
        record(
            decisions=[entry("d1", kind="decision", blocks_continuation=True)],
        ),
        WheypointRecord,
    )
    assert blames(problems, "WheypointRecord.decisions[1].blocks_continuation")


def test_entry_ids_are_unique_across_every_protected_list() -> None:
    problems = refused(
        record(
            questions=[entry("x1", blocks_continuation=False)],
            blockers=[entry("x1", kind="blocker", blocks_continuation=False)],
        ),
        WheypointRecord,
    )
    assert blames(problems, "WheypointRecord.blockers")


def test_a_repeated_entry_id_is_blamed_on_the_list_it_appears_in() -> None:
    problems = refused(
        record(
            decisions=[entry("x1", kind="decision", blocks_continuation=False)],
            questions=[entry("x1", blocks_continuation=False)],
        ),
        WheypointRecord,
    )
    assert blames(problems, "WheypointRecord.questions")
    assert not blames(problems, "WheypointRecord.blockers")
    assert "'x1'" in " ".join(problems)

    within_one_list = refused(
        record(
            decisions=[entry("d1", kind="decision", blocks_continuation=False)] * 2
        ),
        WheypointRecord,
    )
    assert blames(within_one_list, "WheypointRecord.decisions")


@pytest.mark.parametrize("state", ["deleted", "gone", "", "ACTIVE"])
def test_an_unknown_entry_state_is_rejected(state: str) -> None:
    problems = refused(record(questions=[entry("q1", state=state)]), WheypointRecord)
    assert blames(problems, "WheypointRecord.questions[1].state")


# --- acceptance 2 + 3: the delta ------------------------------------------


def test_delta_additions_carry_no_entry_id() -> None:
    names = {attribute.name for attribute in attrs.fields(ProposedEntry)}
    assert "entry_id" not in names, (
        "the runtime assigns entry IDs; a delta that could name one could "
        "overwrite an existing protected entry"
    )
    value = structured(
        delta(add_questions=[{"kind": "question", "summary": "which store?", "blocks_continuation": True}]),
        WheypointDelta,
    )
    assert value.add_questions is not None
    assert not hasattr(value.add_questions[0], "entry_id")


def test_omitted_semantic_fields_stay_none_and_an_empty_list_is_explicit() -> None:
    omitted = structured(delta(), WheypointDelta)
    assert omitted.working_context is None
    assert omitted.add_questions is None
    assert omitted.decision_dossier is None

    explicit = structured(delta(working_context=[], add_questions=[]), WheypointDelta)
    assert explicit.working_context == []
    assert explicit.add_questions == []


def test_a_transition_names_an_entry_an_action_and_a_rationale() -> None:
    structured(
        delta(
            transitions=[
                {
                    "entry_id": "q1",
                    "action": "resolve",
                    "rationale": "answered by the spec",
                    "target_entry_id": None,
                }
            ]
        ),
        WheypointDelta,
    )
    for bad, path in (
        ({"entry_id": "Q1", "action": "resolve", "rationale": "x"}, "entry_id"),
        ({"entry_id": "q1", "action": "delete", "rationale": "x"}, "action"),
        ({"entry_id": "q1", "action": "resolve", "rationale": ""}, "rationale"),
    ):
        problems = refused(delta(transitions=[bad]), WheypointDelta)
        assert blames(problems, f"WheypointDelta.transitions[1].{path}"), problems


def test_supersede_requires_a_target_and_other_actions_forbid_one() -> None:
    structured(
        delta(
            transitions=[
                {
                    "entry_id": "q1",
                    "action": "supersede",
                    "rationale": "folded into q2",
                    "target_entry_id": "q2",
                }
            ]
        ),
        WheypointDelta,
    )
    for transition in (
        {"entry_id": "q1", "action": "supersede", "rationale": "folded"},
        {
            "entry_id": "q1",
            "action": "withdraw",
            "rationale": "obsolete",
            "target_entry_id": "q2",
        },
    ):
        problems = refused(delta(transitions=[transition]), WheypointDelta)
        assert blames(problems, "WheypointDelta.transitions[1].target_entry_id")


def test_one_entry_cannot_be_transitioned_twice_in_one_delta() -> None:
    problems = refused(
        delta(
            transitions=[
                {"entry_id": "q1", "action": "resolve", "rationale": "a"},
                {"entry_id": "q1", "action": "withdraw", "rationale": "b"},
            ]
        ),
        WheypointDelta,
    )
    assert blames(problems, "WheypointDelta.transitions")


def test_rehydration_evidence_requires_a_declared_compaction() -> None:
    problems = refused(
        delta(compacted=False, rehydrated_from_revision_id="rev-0002"), WheypointDelta
    )
    assert blames(problems, "WheypointDelta.rehydrated_from_revision_id")
    value = structured(
        delta(compacted=True, rehydrated_from_revision_id="rev-0002"), WheypointDelta
    )
    assert value.rehydrated_from_revision_id == "rev-0002"


def test_an_artifact_link_may_declare_a_digest_a_revision_and_coverage() -> None:
    value = structured(
        delta(
            add_artifact_links=[
                {
                    "path": ".cheese/cook/wheypoint.md",
                    "digest": DIGEST,
                    "revision_id": "rev-0002",
                    "covers_entry_ids": ["q1"],
                }
            ]
        ),
        WheypointDelta,
    )
    assert value.add_artifact_links is not None
    assert value.add_artifact_links[0].covers_entry_ids == ["q1"]
    bare = structured(
        delta(add_artifact_links=[{"path": ".cheese/cook/wheypoint.md"}]), WheypointDelta
    )
    assert bare.add_artifact_links is not None
    assert bare.add_artifact_links[0].digest is None
    problems = refused(
        delta(add_artifact_links=[{"path": "x", "digest": "deadbeef"}]), WheypointDelta
    )
    assert blames(problems, "WheypointDelta.add_artifact_links[1].digest")


# --- acceptance 3: status is derived, never stored --------------------------


def test_no_type_stores_a_status_field() -> None:
    for cls in (WheypointRecord, WheypointProjection, WheypointRevision):
        names = {attribute.name for attribute in attrs.fields(cls)}
        assert "status" not in names, f"{cls.__name__} stores a status independently"


def test_a_stored_status_key_is_ignored_rather_than_trusted() -> None:
    value = structured(
        projection(status="ok", gating_entry_ids=["q1"], decision_dossier=dossier()),
        WheypointProjection,
    )
    assert value.status is WheypointStatus.GATED


@pytest.mark.parametrize(
    ("questions", "blockers", "expected_gating"),
    [
        ([], [], ()),
        ([entry("q1", blocks_continuation=False)], [], ()),
        ([], [entry("b1", kind="blocker", blocks_continuation=False)], ()),
        ([entry("q1")], [], ("q1",)),
        ([], [entry("b1", kind="blocker")], ("b1",)),
        ([entry("q1")], [entry("b1", kind="blocker")], ("q1", "b1")),
        (
            [entry("q1", state="resolved", rationale="answered")],
            [entry("b1", kind="blocker", state="withdrawn", rationale="moot")],
            (),
        ),
        (
            [
                entry(
                    "q1",
                    state="superseded",
                    rationale="folded into q2",
                    superseded_by="q2",
                ),
                entry("q2", blocks_continuation=False),
            ],
            [],
            (),
        ),
    ],
)
def test_record_status_is_derived_from_active_blocking_entries(
    questions: list[dict[str, Any]],
    blockers: list[dict[str, Any]],
    expected_gating: tuple[str, ...],
) -> None:
    gated = bool(expected_gating)
    value = structured(
        record(
            questions=questions,
            blockers=blockers,
            decision_dossier=dossier() if gated else [],
        ),
        WheypointRecord,
    )
    assert value.gating_entry_ids == expected_gating
    assert value.status is (WheypointStatus.GATED if gated else WheypointStatus.OK)


def test_a_gated_record_requires_a_decision_dossier() -> None:
    problems = refused(
        record(questions=[entry("q1")], decision_dossier=[]), WheypointRecord
    )
    assert blames(problems, "WheypointRecord.decision_dossier")


def test_a_gated_projection_requires_a_decision_dossier() -> None:
    problems = refused(
        projection(gating_entry_ids=["q1"], decision_dossier=[]), WheypointProjection
    )
    assert blames(problems, "WheypointProjection.decision_dossier")
    value = structured(
        projection(gating_entry_ids=["q1"], decision_dossier=dossier()),
        WheypointProjection,
    )
    assert value.status is WheypointStatus.GATED


def test_an_ungated_projection_derives_ok() -> None:
    assert structured(projection(), WheypointProjection).status is WheypointStatus.OK


def test_a_decision_dossier_fork_needs_options_with_evidence() -> None:
    for bad, path in (
        ([{"fork": "which store", "options": []}], "options"),
        (
            [{"fork": "", "options": dossier()[0]["options"]}],
            "fork",
        ),
    ):
        problems = refused(record(decision_dossier=bad), WheypointRecord)
        assert blames(problems, f"WheypointRecord.decision_dossier[1].{path}"), problems


@pytest.mark.parametrize("level", ["canonical-local", "repo-snapshot", "published"])
def test_durability_levels(level: str) -> None:
    assert structured(projection(durability=level), WheypointProjection).durability.value == level


def test_an_unknown_durability_level_is_rejected() -> None:
    problems = refused(projection(durability="committed"), WheypointProjection)
    assert blames(problems, "WheypointProjection.durability")


def test_an_unknown_next_move_is_rejected() -> None:
    problems = refused(record(next_action=next_action(move="vibes")), WheypointRecord)
    assert blames(problems, "WheypointRecord.next_action.move")

def test_cut_round_trips_through_record_and_projection_with_receipt_pointer() -> None:
    receipt = ".cheese/cut/widget.json"
    payload = record(next_action=next_action(move="cut", artifact=receipt))

    value = structured(payload, WheypointRecord)
    assert isinstance(value.next_action, NextAction)
    assert value.next_action.move is NextMove.CUT
    assert value.next_action.artifact == receipt

    projected = structured(
        projection(next_action=next_action(move="cut", artifact=receipt)),
        WheypointProjection,
    )
    assert projected.next_action.move is NextMove.CUT
    assert projected.next_action.artifact == receipt
