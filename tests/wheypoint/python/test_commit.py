"""The commit transaction: carry-forward, idempotency, conflict, compaction."""

from __future__ import annotations

import re
import threading
from collections.abc import Callable
from pathlib import Path

import attrs
import pytest
from attrs import evolve
from easy_cheese_schemas import (
    ArtifactLink,
    DecisionFork,
    DossierOption,
    EntryKind,
    EntryState,
    EntryTransition,
    ProposedEntry,
    ProtectedEntry,
    SessionProvenance,
    TransitionAction,
    WheypointDelta,
    WheypointRecord,
    WheypointStatus,
)

import commit
import records
import storage

from conftest import PLACEHOLDER_DIGEST, WORK_ID, Promotion


def _entry(entry_id: str, kind: EntryKind, *, gates: bool = False) -> ProtectedEntry:
    return ProtectedEntry(
        entry_id=entry_id,
        kind=kind,
        summary=f"{entry_id} summary",
        state=EntryState.ACTIVE,
        blocks_continuation=gates,
    )


def _seed(
    store: storage.WorkStore,
    make_promotion: Callable[..., Promotion],
    **overrides: object,
) -> Promotion:
    """Put one consistent genesis promotion in `store` and return it."""
    promotion = make_promotion(**overrides)
    store.promote(promotion.record, promotion.revision, promotion.markdown)
    return promotion


def _delta(parent: str, **overrides: object) -> WheypointDelta:
    fields: dict[str, object] = {"work_id": WORK_ID, "expected_revision_id": parent}
    fields.update(overrides)
    return WheypointDelta(**fields)  # type: ignore[arg-type]


@pytest.fixture
def store(corpus_root: Path) -> storage.WorkStore:
    return storage.WorkStore.open(WORK_ID, corpus_root=corpus_root)


def test_commit_promotes_the_next_revision_and_swaps_the_record(
    store: storage.WorkStore, make_promotion: Callable[..., Promotion]
) -> None:
    seed = _seed(store, make_promotion)

    result = commit.commit(
        _delta(
            seed.record.revision_id,
            orientation="Wave 3 owns the commit transaction.",
            add_decisions=[
                ProposedEntry(kind=EntryKind.DECISION, summary="Ids are derived.")
            ],
        ),
        store=store,
    )

    assert result.replayed is False
    assert result.revision.parent_revision_id == seed.record.revision_id
    assert result.revision.revision_number == 2
    assert result.record.revision_id == result.revision.revision_id
    assert result.record.orientation == "Wave 3 owns the commit transaction."
    assert [entry.summary for entry in result.record.decisions] == ["Ids are derived."]
    assert result.revision.applied_additions == list(result.record.decisions)
    assert result.revision.applied_transitions == []

    # The store now reads back exactly what was returned, with both immutable
    # files present and record.json pointing at them.
    assert store.read_record() == result.record
    assert (
        store.read_revision(2, result.revision.revision_id) == result.revision
    )
    assert store.projection_path(2, result.revision.revision_id).read_text(
        encoding="utf-8"
    ) == result.markdown
    assert store.recover().problems == ()


def test_narrowed_delta_preserves_omitted_protected_state(
    store: storage.WorkStore,
    make_record: Callable[..., WheypointRecord],
    make_promotion: Callable[..., Promotion],
) -> None:
    parent = make_record(
        decisions=[_entry("d-keep", EntryKind.DECISION)],
        questions=[_entry("q-keep", EntryKind.QUESTION)],
        blockers=[_entry("b-keep", EntryKind.BLOCKER)],
        artifact_links=[ArtifactLink(path=".cheese/cook/wave-2.md")],
    )
    seed = _seed(store, make_promotion, record=parent)

    result = commit.commit(
        _delta(seed.record.revision_id, orientation="Only the orientation moved."),
        store=store,
    )

    assert [entry.entry_id for entry in result.record.decisions] == ["d-keep"]
    assert [entry.entry_id for entry in result.record.questions] == ["q-keep"]
    assert [entry.entry_id for entry in result.record.blockers] == ["b-keep"]
    assert result.record.artifact_links == parent.artifact_links
    assert result.revision.preserved_entry_ids == ["d-keep", "q-keep", "b-keep"]
    assert result.revision.applied_additions == []


def test_assigned_entry_ids_are_derived_from_the_request_not_the_clock(
    corpus_root: Path,
    store: storage.WorkStore,
    make_promotion: Callable[..., Promotion],
) -> None:
    seed = _seed(store, make_promotion)
    delta = _delta(
        seed.record.revision_id,
        add_questions=[
            ProposedEntry(
                kind=EntryKind.QUESTION,
                summary="Is the id stable?",
                blocks_continuation=False,
            )
        ],
    )

    first = commit.commit(delta, store=store)

    twin = storage.WorkStore.open(WORK_ID, corpus_root=corpus_root / "twin")
    _seed(twin, make_promotion)
    second = commit.commit(delta, store=twin)

    assigned = first.record.questions[0].entry_id
    assert re.fullmatch(r"q-[0-9a-f]{12}", assigned)
    assert second.record.questions[0].entry_id == assigned
    assert second.revision.revision_id == first.revision.revision_id


def _revision_files(store: storage.WorkStore) -> list[str]:
    return sorted(path.name for path in store.revisions_dir.glob("*.json"))


def test_transition_settles_the_entry_and_leaves_it_out_of_the_preserved_ledger(
    store: storage.WorkStore,
    make_record: Callable[..., WheypointRecord],
    make_promotion: Callable[..., Promotion],
) -> None:
    parent = make_record(
        decisions=[_entry("d-old", EntryKind.DECISION), _entry("d-new", EntryKind.DECISION)],
        questions=[_entry("q-open", EntryKind.QUESTION)],
    )
    seed = _seed(store, make_promotion, record=parent)

    result = commit.commit(
        _delta(
            seed.record.revision_id,
            transitions=[
                EntryTransition(
                    entry_id="d-old",
                    action=TransitionAction.SUPERSEDE,
                    rationale="d-new replaces it.",
                    target_entry_id="d-new",
                ),
                EntryTransition(
                    entry_id="q-open",
                    action=TransitionAction.RESOLVE,
                    rationale="Answered in wave 3.",
                ),
            ],
        ),
        store=store,
    )

    settled = result.record.decisions[0]
    assert settled.state is EntryState.SUPERSEDED
    assert settled.superseded_by == "d-new"
    assert settled.rationale == "d-new replaces it."
    resolved = result.record.questions[0]
    assert resolved.state is EntryState.RESOLVED
    assert resolved.rationale == "Answered in wave 3."
    # Only the untouched entry is preserved: a settled entry was applied, not
    # carried, and the ledgers must not double-count it.
    assert result.revision.preserved_entry_ids == ["d-new"]
    assert [t.entry_id for t in result.revision.applied_transitions] == [
        "d-old",
        "q-open",
    ]


def test_transition_naming_an_unknown_entry_promotes_nothing(
    store: storage.WorkStore, make_promotion: Callable[..., Promotion]
) -> None:
    seed = _seed(store, make_promotion)
    before = _revision_files(store)

    with pytest.raises(commit.CommitError, match="unknown entry 'd-ghost'"):
        commit.commit(
            _delta(
                seed.record.revision_id,
                transitions=[
                    EntryTransition(
                        entry_id="d-ghost",
                        action=TransitionAction.WITHDRAW,
                        rationale="Never existed.",
                    )
                ],
            ),
            store=store,
        )

    assert _revision_files(store) == before
    assert store.read_record() == seed.record


def test_transition_of_an_already_settled_entry_is_refused(
    store: storage.WorkStore,
    make_record: Callable[..., WheypointRecord],
    make_promotion: Callable[..., Promotion],
) -> None:
    settled = ProtectedEntry(
        entry_id="d-done",
        kind=EntryKind.DECISION,
        summary="Already withdrawn.",
        state=EntryState.WITHDRAWN,
        blocks_continuation=False,
        rationale="Superseded by wave 2.",
    )
    seed = _seed(store, make_promotion, record=make_record(decisions=[settled]))

    with pytest.raises(commit.CommitError, match="'d-done' is already withdrawn"):
        commit.commit(
            _delta(
                seed.record.revision_id,
                transitions=[
                    EntryTransition(
                        entry_id="d-done",
                        action=TransitionAction.RESOLVE,
                        rationale="Try again.",
                    )
                ],
            ),
            store=store,
        )


def test_a_delta_offers_no_way_to_remove_protected_state() -> None:
    # Acceptance: generic deletion is unavailable, so every state change has to
    # carry an entry id, an action, and a rationale.
    field_names = {field.name for field in attrs.fields(WheypointDelta)}
    assert not [name for name in field_names if "remove" in name or "delete" in name]
    assert "delete" not in {action.value for action in TransitionAction}
    with pytest.raises(TypeError):
        EntryTransition(entry_id="d-keep", action=TransitionAction.RESOLVE)  # type: ignore[call-arg]


def test_a_lost_parent_receipt_blocks_the_next_revision(
    store: storage.WorkStore, make_promotion: Callable[..., Promotion]
) -> None:
    seed = _seed(store, make_promotion)
    store.revision_path(
        seed.record.revision_number, seed.record.revision_id
    ).unlink()

    with pytest.raises(commit.CommitError, match="has no immutable receipt"):
        commit.commit(
            _delta(seed.record.revision_id, orientation="Extend a broken chain."),
            store=store,
        )

    assert _revision_files(store) == []


def test_a_record_quoting_the_wrong_receipt_digest_blocks_the_next_revision(
    store: storage.WorkStore, make_promotion: Callable[..., Promotion]
) -> None:
    seed = _seed(store, make_promotion)
    tampered = evolve(seed.record, revision_digest=PLACEHOLDER_DIGEST)
    store.record_path.write_bytes(records.canonical_payload(tampered))

    with pytest.raises(commit.CommitError, match="does not match the digest"):
        commit.commit(
            _delta(seed.record.revision_id, orientation="Extend a tampered chain."),
            store=store,
        )

    assert _revision_files(store) == [
        f"1-{seed.record.revision_id}.json",
    ]


def test_identical_replay_against_the_same_parent_returns_the_existing_revision(
    store: storage.WorkStore, make_promotion: Callable[..., Promotion]
) -> None:
    seed = _seed(store, make_promotion)
    delta = _delta(seed.record.revision_id, orientation="Submitted twice.")

    first = commit.commit(delta, store=store)
    after_first = _revision_files(store)
    second = commit.commit(delta, store=store)

    assert second.replayed is True
    assert second.revision == first.revision
    assert second.markdown == first.markdown
    assert second.projection.revision_id == first.revision.revision_id
    # A replay is not a write: no new receipt, and the record is untouched.
    assert _revision_files(store) == after_first
    assert store.read_record() == first.record


def test_a_changed_request_against_a_stale_parent_promotes_nothing(
    store: storage.WorkStore, make_promotion: Callable[..., Promotion]
) -> None:
    seed = _seed(store, make_promotion)
    winner = commit.commit(
        _delta(seed.record.revision_id, orientation="First writer wins."), store=store
    )
    after_winner = _revision_files(store)

    with pytest.raises(commit.StaleParentError) as raised:
        commit.commit(
            _delta(seed.record.revision_id, orientation="Second writer loses."),
            store=store,
        )

    assert f"current revision is {winner.revision.revision_id!r}" in str(raised.value)
    assert _revision_files(store) == after_winner
    assert store.read_record() == winner.record
    assert sorted(path.name for path in store.projections_dir.glob("*.md")) == [
        f"1-{seed.record.revision_id}.md",
        f"2-{winner.revision.revision_id}.md",
    ]


def test_two_concurrent_writers_on_one_parent_promote_exactly_one_revision(
    store: storage.WorkStore, make_promotion: Callable[..., Promotion]
) -> None:
    seed = _seed(store, make_promotion)
    start = threading.Barrier(2)
    outcomes: list[object] = []
    guard = threading.Lock()

    def writer(orientation: str) -> None:
        delta = _delta(seed.record.revision_id, orientation=orientation)
        start.wait(timeout=5)
        try:
            outcome: object = commit.commit(delta, store=store)
        except commit.CommitError as exc:
            outcome = exc
        with guard:
            outcomes.append(outcome)

    threads = [
        threading.Thread(target=writer, args=(f"Writer {index}.",))
        for index in range(2)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
        assert not thread.is_alive()

    promoted = [item for item in outcomes if isinstance(item, commit.CommitResult)]
    refused = [item for item in outcomes if isinstance(item, commit.StaleParentError)]
    assert len(promoted) == 1
    assert len(refused) == 1
    won = promoted[0]
    assert _revision_files(store) == [
        f"1-{seed.record.revision_id}.json",
        f"2-{won.revision.revision_id}.json",
    ]
    assert store.read_record() == won.record
    assert store.recover().problems == ()


def test_compaction_rehydrated_from_the_current_revision_is_accepted(
    store: storage.WorkStore, make_promotion: Callable[..., Promotion]
) -> None:
    seed = _seed(store, make_promotion)
    provenance = SessionProvenance(
        harness="claude-code", session_id="s-42", captured_at="2026-08-02T01:00:00Z"
    )

    result = commit.commit(
        _delta(
            seed.record.revision_id,
            orientation="Rehydrated after compaction.",
            compacted=True,
            rehydrated_from_revision_id=seed.record.revision_id,
            session_provenance=provenance,
        ),
        store=store,
    )

    assert result.revision.rehydrated_from_revision_id == seed.record.revision_id
    assert result.revision.session_provenance == provenance
    # Evidence only: the authority the record carries has nowhere to put a
    # session, so nothing downstream can select on one.
    assert "session_provenance" not in {
        field.name for field in attrs.fields(WheypointRecord)
    }


def test_compaction_rehydrated_from_a_superseded_revision_is_rejected(
    store: storage.WorkStore, make_promotion: Callable[..., Promotion]
) -> None:
    seed = _seed(store, make_promotion)
    second = commit.commit(
        _delta(seed.record.revision_id, orientation="Moved on."), store=store
    )
    after_second = _revision_files(store)

    with pytest.raises(commit.CommitError) as raised:
        commit.commit(
            _delta(
                second.revision.revision_id,
                orientation="Written from a stale memory.",
                compacted=True,
                rehydrated_from_revision_id=seed.record.revision_id,
            ),
            store=store,
        )

    assert "rehydrated from the current revision" in str(raised.value)
    assert _revision_files(store) == after_second
    assert store.read_record() == second.record


def test_a_new_gating_blocker_derives_gated_and_needs_a_dossier(
    store: storage.WorkStore, make_promotion: Callable[..., Promotion]
) -> None:
    seed = _seed(store, make_promotion)
    blocker = ProposedEntry(
        kind=EntryKind.BLOCKER,
        summary="Vendored cattrs is missing.",
        blocks_continuation=True,
    )
    fork = DecisionFork(
        fork="How to vendor cattrs",
        options=[
            DossierOption(
                option="pin the lock",
                evidence=["the build already hashes it"],
                breaks="nothing until the lock moves",
            )
        ],
    )

    with pytest.raises(commit.CommitError, match="does not produce a legal record"):
        commit.commit(
            _delta(seed.record.revision_id, add_blockers=[blocker]), store=store
        )
    assert _revision_files(store) == [f"1-{seed.record.revision_id}.json"]

    result = commit.commit(
        _delta(
            seed.record.revision_id, add_blockers=[blocker], decision_dossier=[fork]
        ),
        store=store,
    )

    gate = result.record.blockers[0].entry_id
    assert result.record.status is WheypointStatus.GATED
    assert result.projection.status is WheypointStatus.GATED
    assert result.projection.gating_entry_ids == [gate]
    assert result.markdown.splitlines()[0] == "status: gated"


def test_added_artifact_links_append_to_the_ones_already_carried(
    store: storage.WorkStore,
    make_record: Callable[..., WheypointRecord],
    make_promotion: Callable[..., Promotion],
) -> None:
    carried = ArtifactLink(path=".cheese/cook/wave-2.md")
    added = ArtifactLink(
        path=".cheese/cook/wave-3.md", digest=PLACEHOLDER_DIGEST
    )
    seed = _seed(store, make_promotion, record=make_record(artifact_links=[carried]))

    result = commit.commit(
        _delta(seed.record.revision_id, add_artifact_links=[added]), store=store
    )

    assert result.record.artifact_links == [carried, added]


def test_a_held_record_lock_blocks_the_transaction_until_it_is_released(
    store: storage.WorkStore, make_promotion: Callable[..., Promotion]
) -> None:
    seed = _seed(store, make_promotion)
    done = threading.Event()

    def writer() -> None:
        commit.commit(
            _delta(seed.record.revision_id, orientation="Waits for the lock."),
            store=store,
        )
        done.set()

    thread = threading.Thread(target=writer)
    with store.lock():
        thread.start()
        # The whole transaction is inside the lock, so nothing -- not even the
        # first immutable file -- may appear while another holder has it.
        assert done.wait(timeout=0.5) is False
        assert _revision_files(store) == [f"1-{seed.record.revision_id}.json"]
    thread.join(timeout=10)

    assert done.is_set()
    assert len(_revision_files(store)) == 2


def test_an_explicitly_emptied_field_replaces_while_an_omitted_one_carries(
    store: storage.WorkStore,
    make_record: Callable[..., WheypointRecord],
    make_promotion: Callable[..., Promotion],
) -> None:
    parent = make_record(working_context=["src/wheypoint/storage.py"])
    seed = _seed(store, make_promotion, record=parent)

    carried = commit.commit(
        _delta(seed.record.revision_id, orientation="Omits the context."), store=store
    )
    assert carried.record.working_context == ["src/wheypoint/storage.py"]

    emptied = commit.commit(
        _delta(carried.record.revision_id, working_context=[]), store=store
    )
    assert emptied.record.working_context == []
