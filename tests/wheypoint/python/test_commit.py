"""The commit transaction: carry-forward, idempotency, conflict, compaction."""

from __future__ import annotations

import os
import re
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Protocol, cast

import attrs
import pytest
from attrs import Attribute, evolve
from easy_cheese_schemas import (
    ArtifactLink,
    DecisionFork,
    DossierOption,
    EntryKind,
    EntryState,
    EntryTransition,
    NextAction,
    NextMove,
    ProposedEntry,
    ProtectedEntry,
    SessionProvenance,
    TransitionAction,
    WheypointDelta,
    WheypointRecord,
    WheypointStatus,
)

from easy_cheese.skills.wheypoint import commit, records, storage

from conftest import PLACEHOLDER_DIGEST, WORK_ID, Promotion


class _RevisionLineage(Protocol):
    rehydrated_from_revision_id: str | None


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
    return WheypointDelta(**fields)  # pyright: ignore[reportArgumentType]


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


def test_resolving_the_last_gate_must_clear_the_dossier_it_carried(
    store: storage.WorkStore, make_promotion: Callable[..., Promotion]
) -> None:
    """Carry-forward keeps the dossier a silent delta did not speak about, and
    an unanswered fork under `status: ok` is exactly the misfire the schema
    now refuses -- so closing the last gate has to say so in the same delta."""
    seed = _seed(store, make_promotion, gating=True)
    resolve = EntryTransition(
        entry_id="q-durability",
        action=TransitionAction.RESOLVE,
        rationale="canonical-local it is",
    )

    with pytest.raises(commit.CommitError, match="does not produce a legal record"):
        _ = commit.commit(
            _delta(seed.record.revision_id, transitions=[resolve]), store=store
        )

    result = commit.commit(
        _delta(seed.record.revision_id, transitions=[resolve], decision_dossier=[]),
        store=store,
    )

    assert result.record.decision_dossier == []
    assert result.record.status is WheypointStatus.OK


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
    _ = _seed(twin, make_promotion)
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
        _ = commit.commit(
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
        _ = commit.commit(
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
    field_names = {
        field.name
        for field in cast(tuple["Attribute[object]", ...], attrs.fields(WheypointDelta))
    }
    assert not [name for name in field_names if "remove" in name or "delete" in name]
    assert "delete" not in {action.value for action in TransitionAction}
    with pytest.raises(TypeError):
        _ = EntryTransition(entry_id="d-keep", action=TransitionAction.RESOLVE)  # pyright: ignore[reportCallIssue]


def test_a_lost_parent_receipt_blocks_the_next_revision(
    store: storage.WorkStore, make_promotion: Callable[..., Promotion]
) -> None:
    seed = _seed(store, make_promotion)
    store.revision_path(
        seed.record.revision_number, seed.record.revision_id
    ).unlink()

    with pytest.raises(commit.CommitError, match="has no immutable receipt"):
        _ = commit.commit(
            _delta(seed.record.revision_id, orientation="Extend a broken chain."),
            store=store,
        )

    assert _revision_files(store) == []


def test_a_record_quoting_the_wrong_receipt_digest_blocks_the_next_revision(
    store: storage.WorkStore, make_promotion: Callable[..., Promotion]
) -> None:
    seed = _seed(store, make_promotion)
    tampered = evolve(seed.record, revision_digest=PLACEHOLDER_DIGEST)
    _ = store.record_path.write_bytes(records.canonical_payload(tampered))

    with pytest.raises(commit.CommitError, match="does not match the digest"):
        _ = commit.commit(
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


def test_a_promotion_that_died_before_the_record_swap_is_finished_by_the_retry(
    store: storage.WorkStore,
    make_promotion: Callable[..., Promotion],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The quiet crash window: the pair landed, the record swap did not.

    Treating the complete-but-unnamed pair as a replay would answer the retry
    with `replayed: true` over the *stale* record -- the agent hands off
    believing checkpoint two is saved while every reader serves checkpoint one,
    and the next delta built on what it was handed is refused as stale-parent.
    The retry must finish the promotion instead.
    """
    seed = _seed(store, make_promotion)
    delta = _delta(seed.record.revision_id, orientation="Checkpoint two.")
    real_replace = os.replace

    def crash_on_record(src: str, dst: str) -> None:
        if Path(dst).name == storage.RECORD_FILENAME:
            raise OSError("power loss")
        real_replace(src, dst)

    monkeypatch.setattr(os, "replace", crash_on_record)
    with pytest.raises(OSError, match="power loss"):
        _ = commit.commit(delta, store=store)
    monkeypatch.setattr(os, "replace", real_replace)

    # Precisely the state the reviewer reproduced: two complete revisions,
    # nothing reported incomplete, and record.json still naming the first.
    crashed = store.recover()
    assert [file.revision.revision_number for file in crashed.complete] == [1, 2]
    assert crashed.incomplete == ()
    assert store.read_record() == seed.record

    result = commit.commit(delta, store=store)

    assert result.replayed is False
    assert result.revision.revision_number == 2
    assert result.record.orientation == "Checkpoint two."
    # The claim the caller is handed is the claim the store can serve.
    settled = store.read_record()
    assert settled == result.record
    assert settled is not None
    assert settled.revision_id == result.revision.revision_id
    assert store.recover().consistent

    # And a delta built on the revision it returned is not stale.
    third = commit.commit(
        _delta(result.revision.revision_id, orientation="Checkpoint three."),
        store=store,
    )
    assert third.revision.revision_number == 3
    assert _revision_files(store) == [
        f"1-{seed.record.revision_id}.json",
        f"2-{result.revision.revision_id}.json",
        f"3-{third.revision.revision_id}.json",
    ]


def test_a_replay_whose_record_has_moved_on_is_still_a_replay(
    store: storage.WorkStore, make_promotion: Callable[..., Promotion]
) -> None:
    """The finishing path must not swallow the ordinary replay: a receipt the
    record has already moved *past* is settled history, and re-promoting it
    would roll the record backwards over everything since."""
    seed = _seed(store, make_promotion)
    delta = _delta(seed.record.revision_id, orientation="Checkpoint two.")
    second = commit.commit(delta, store=store)
    third = commit.commit(
        _delta(second.revision.revision_id, orientation="Checkpoint three."),
        store=store,
    )

    again = commit.commit(delta, store=store)

    assert again.replayed is True
    assert again.revision == second.revision
    assert again.record == third.record
    assert store.read_record() == third.record


def test_a_changed_request_against_a_stale_parent_promotes_nothing(
    store: storage.WorkStore, make_promotion: Callable[..., Promotion]
) -> None:
    seed = _seed(store, make_promotion)
    winner = commit.commit(
        _delta(seed.record.revision_id, orientation="First writer wins."), store=store
    )
    after_winner = _revision_files(store)

    with pytest.raises(commit.StaleParentError) as raised:
        _ = commit.commit(
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
        _ = start.wait(timeout=5)
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

    lineage = cast(_RevisionLineage, cast(object, result.revision))
    assert lineage.rehydrated_from_revision_id == seed.record.revision_id
    assert result.revision.session_provenance == provenance
    # Evidence only: the authority the record carries has nowhere to put a
    # session, so nothing downstream can select on one.
    assert "session_provenance" not in {
        field.name
        for field in cast(tuple["Attribute[object]", ...], attrs.fields(WheypointRecord))
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
        _ = commit.commit(
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
        _ = commit.commit(
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
        _ = commit.commit(
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


GENESIS_CAPTURED_AT = "2026-08-02T00:00:00Z"


def _projection_files(store: storage.WorkStore) -> list[str]:
    return sorted(path.name for path in store.projections_dir.glob("*.md"))


def _genesis_delta(**overrides: object) -> WheypointDelta:
    fields: dict[str, object] = {
        "orientation": "Genesis orientation.\nA second line the title drops.",
        "working_context": ["src/wheypoint/commit.py"],
        "next_action": NextAction(
            move=NextMove.COOK,
            orientation="Write the wheypoint CLI.",
            artifact=".cheese/cook/wheypoint-pyz-cli.md",
        ),
        "session_provenance": SessionProvenance(captured_at=GENESIS_CAPTURED_AT),
    }
    fields.update(overrides)
    return _delta(commit.GENESIS_PARENT, **fields)


def test_genesis_creates_the_first_record_when_the_store_is_empty(
    store: storage.WorkStore,
) -> None:
    assert store.read_record() is None

    result = commit.commit(
        _genesis_delta(
            add_decisions=[
                ProposedEntry(kind=EntryKind.DECISION, summary="Genesis is a commit.")
            ]
        ),
        store=store,
    )

    record = result.record
    assert result.replayed is False
    assert record.revision_number == 1
    assert result.revision.revision_number == 1
    assert result.revision.parent_revision_id is None
    assert record.work_id == WORK_ID
    # A genesis record answers to its own work id and takes its title from the
    # first line of the orientation it was given.
    assert record.slug == WORK_ID
    assert record.title == "Genesis orientation."
    assert record.created == GENESIS_CAPTURED_AT
    assert record.project_key == "paulnsorensen-easy-cheese"
    assert record.orientation == "Genesis orientation.\nA second line the title drops."
    assert record.working_context == ["src/wheypoint/commit.py"]
    assert [entry.summary for entry in record.decisions] == ["Genesis is a commit."]
    assert result.revision.applied_additions == list(record.decisions)
    assert result.revision.preserved_entry_ids == []
    assert result.revision.applied_transitions == []

    revision_id = result.revision.revision_id
    assert record.revision_id == revision_id
    assert re.fullmatch(r"rev-[0-9a-f]{12}", revision_id)
    assert _revision_files(store) == [f"1-{revision_id}.json"]
    assert _projection_files(store) == [f"1-{revision_id}.md"]
    assert store.read_record() == record
    assert store.read_revision(1, revision_id) == result.revision
    assert store.recover().problems == ()


def test_a_genesis_delta_against_a_live_record_promotes_nothing(
    store: storage.WorkStore, make_promotion: Callable[..., Promotion]
) -> None:
    """The anti-wipe guard: creation over a live record would drop every
    protected entry it carries, so it is refused before anything is written."""
    seed = _seed(store, make_promotion, gating=True)
    before_record = store.record_path.read_bytes()
    before_revisions = _revision_files(store)
    before_projections = _projection_files(store)

    with pytest.raises(commit.GenesisConflictError) as raised:
        _ = commit.commit(_genesis_delta(), store=store)

    assert seed.record.revision_id in str(raised.value)
    assert store.record_path.read_bytes() == before_record
    assert _revision_files(store) == before_revisions
    assert _projection_files(store) == before_projections
    assert store.read_record() == seed.record


def test_a_genesis_delta_never_orphans_history_whose_record_is_gone(
    store: storage.WorkStore, make_promotion: Callable[..., Promotion]
) -> None:
    """The anti-wipe guard keys on the history, not on record.json: a lost
    record must not let genesis start a second lineage over live revisions."""
    seed = _seed(store, make_promotion, gating=True)
    store.record_path.unlink()
    before_revisions = _revision_files(store)
    before_projections = _projection_files(store)

    with pytest.raises(commit.GenesisConflictError) as raised:
        _ = commit.commit(_genesis_delta(), store=store)

    assert seed.record.revision_id in str(raised.value)
    assert _revision_files(store) == before_revisions
    assert _projection_files(store) == before_projections
    assert store.read_record() is None


def test_a_genesis_delta_is_refused_over_receipts_whose_projections_are_gone(
    store: storage.WorkStore, make_promotion: Callable[..., Promotion]
) -> None:
    """Completeness is not the question. A store holding only the receipts
    still holds the work, and genesis beside it starts a second lineage that
    nothing ever mentions."""
    seed = _seed(store, make_promotion, gating=True)
    store.record_path.unlink()
    store.projection_path(1, seed.record.revision_id).unlink()
    before_revisions = _revision_files(store)

    with pytest.raises(commit.GenesisConflictError) as raised:
        _ = commit.commit(_genesis_delta(), store=store)

    assert seed.record.revision_id in str(raised.value)
    assert _revision_files(store) == before_revisions
    assert _projection_files(store) == []
    assert store.read_record() is None


def test_a_genesis_delta_is_refused_over_projections_whose_receipts_are_gone(
    store: storage.WorkStore, make_promotion: Callable[..., Promotion]
) -> None:
    """The salvage case: an operator copies the readable `projections/*.md` out
    of a backup and not the opaque receipts, then starts the slug again. The
    prior orientation, decisions and blockers are right there in the same
    directory, so genesis over them is the erasure this guard exists for."""
    seed = _seed(store, make_promotion, gating=True)
    store.record_path.unlink()
    store.revision_path(1, seed.record.revision_id).unlink()
    orphan = f"1-{seed.record.revision_id}.md"

    # A one-sided store is visible at all: the scan reports the readable half.
    assert store.recover().incomplete == (
        f"{orphan}: no revision receipt names this projection",
    )

    with pytest.raises(commit.GenesisConflictError) as raised:
        _ = commit.commit(_genesis_delta(), store=store)

    assert seed.record.revision_id in str(raised.value)
    assert _revision_files(store) == []
    assert _projection_files(store) == [orphan]
    assert store.read_record() is None


def test_a_genesis_that_died_before_the_record_swap_is_finished_by_the_retry(
    store: storage.WorkStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The guard above refuses genesis over any file at all, so the one genesis
    that *may* land on its own pair is the retry of the request that wrote it:
    the receipt names this exact request, and finishing it writes the record
    the interrupted attempt was about to write."""
    delta = _genesis_delta()
    real_replace = os.replace

    def crash_on_record(src: str, dst: str) -> None:
        if Path(dst).name == storage.RECORD_FILENAME:
            raise OSError("power loss")
        real_replace(src, dst)

    monkeypatch.setattr(os, "replace", crash_on_record)
    with pytest.raises(OSError, match="power loss"):
        _ = commit.commit(delta, store=store)
    monkeypatch.setattr(os, "replace", real_replace)
    assert store.read_record() is None
    assert store.recover().latest_complete is not None

    result = commit.commit(delta, store=store)

    assert store.read_record() == result.record
    assert store.recover().consistent
    assert _revision_files(store) == [f"1-{result.revision.revision_id}.json"]
    assert _projection_files(store) == [f"1-{result.revision.revision_id}.md"]


def test_an_unreadable_record_is_named_rather_than_raised_as_a_decode_error(
    store: storage.WorkStore, make_promotion: Callable[..., Promotion]
) -> None:
    """It already failed closed; it failed closed with a Python exception name.
    The operator is told which file to look at instead."""
    seed = _seed(store, make_promotion)
    _ = store.record_path.write_bytes(b"{ not json")

    with pytest.raises(commit.CommitError, match=storage.RECORD_FILENAME):
        _ = commit.commit(
            _delta(seed.record.revision_id, orientation="Over a broken record."),
            store=store,
        )

    with pytest.raises(commit.CommitError, match=storage.RECORD_FILENAME):
        _ = commit.commit(_genesis_delta(), store=store)

    assert _revision_files(store) == [f"1-{seed.record.revision_id}.json"]
    assert store.record_path.read_bytes() == b"{ not json"


def test_an_identical_genesis_replay_returns_the_original_revision(
    store: storage.WorkStore,
) -> None:
    delta = _genesis_delta(
        add_decisions=[
            ProposedEntry(kind=EntryKind.DECISION, summary="Genesis is a commit.")
        ]
    )
    first = commit.commit(delta, store=store)

    second = commit.commit(delta, store=store)

    assert second.replayed is True
    assert second.revision == first.revision
    assert second.record == first.record
    revision_id = first.revision.revision_id
    assert _revision_files(store) == [f"1-{revision_id}.json"]
    assert _projection_files(store) == [f"1-{revision_id}.md"]


def test_a_different_genesis_delta_over_a_live_record_still_conflicts(
    store: storage.WorkStore,
) -> None:
    first = commit.commit(_genesis_delta(), store=store)

    with pytest.raises(commit.GenesisConflictError) as raised:
        _ = commit.commit(
            _genesis_delta(orientation="A different genesis entirely."), store=store
        )

    assert first.revision.revision_id in str(raised.value)
    assert store.read_record() == first.record
    assert _revision_files(store) == [f"1-{first.revision.revision_id}.json"]


def test_a_first_delta_against_an_empty_store_must_name_genesis(
    store: storage.WorkStore,
) -> None:
    with pytest.raises(commit.CommitError, match="'genesis'"):
        _ = commit.commit(
            _delta("rev-000000000001", orientation="There is no parent yet."),
            store=store,
        )

    assert store.read_record() is None
    assert not store.revisions_dir.exists()


def test_a_genesis_delta_cannot_declare_compaction(store: storage.WorkStore) -> None:
    with pytest.raises(commit.CommitError, match="cannot declare compaction"):
        _ = commit.commit(
            _genesis_delta(
                compacted=True, rehydrated_from_revision_id="rev-000000000001"
            ),
            store=store,
        )

    assert store.read_record() is None


def test_a_genesis_delta_cannot_carry_transitions(store: storage.WorkStore) -> None:
    with pytest.raises(commit.CommitError, match="no existing entries to transition"):
        _ = commit.commit(
            _genesis_delta(
                transitions=[
                    EntryTransition(
                        entry_id="d-ghost",
                        action=TransitionAction.WITHDRAW,
                        rationale="Nothing to withdraw.",
                    )
                ]
            ),
            store=store,
        )

    assert store.read_record() is None


@pytest.mark.parametrize(
    "missing", ["orientation", "working_context", "next_action"]
)
def test_a_genesis_delta_must_carry_the_state_it_has_no_parent_for(
    store: storage.WorkStore, missing: str
) -> None:
    with pytest.raises(commit.CommitError, match=f"must carry .*{missing}"):
        _ = commit.commit(_genesis_delta(**{missing: None}), store=store)

    assert store.read_record() is None
    assert not store.revisions_dir.exists()


def test_a_genesis_delta_must_carry_the_capture_time_it_is_created_at(
    store: storage.WorkStore,
) -> None:
    with pytest.raises(commit.CommitError, match="session_provenance.captured_at"):
        _ = commit.commit(_genesis_delta(session_provenance=None), store=store)

    assert store.read_record() is None


def test_genesis_ids_are_derived_from_the_request_not_the_corpus(
    tmp_path: Path, corpus_root: Path
) -> None:
    """Two independent corpora given the same genesis request agree on names."""
    _ = corpus_root
    delta = _genesis_delta(
        add_questions=[
            ProposedEntry(kind=EntryKind.QUESTION, summary="Is genesis derived?")
        ]
    )
    first = commit.commit(
        delta, store=storage.WorkStore.open(WORK_ID, corpus_root=tmp_path / "a")
    )
    second = commit.commit(
        delta, store=storage.WorkStore.open(WORK_ID, corpus_root=tmp_path / "b")
    )

    assert first.revision.revision_id == second.revision.revision_id
    assert first.record.work_id == second.record.work_id
    assert [entry.entry_id for entry in first.record.questions] == [
        entry.entry_id for entry in second.record.questions
    ]
    assert first.revision.record_digest == second.revision.record_digest


def test_a_normal_delta_applies_on_top_of_a_genesis_record(
    store: storage.WorkStore,
) -> None:
    created = commit.commit(_genesis_delta(), store=store)

    second = commit.commit(
        _delta(
            created.record.revision_id,
            orientation="Wave 4 owns the CLI.",
            add_decisions=[
                ProposedEntry(kind=EntryKind.DECISION, summary="Four subcommands.")
            ],
        ),
        store=store,
    )

    assert second.revision.parent_revision_id == created.revision.revision_id
    assert second.record.revision_number == 2
    assert second.record.orientation == "Wave 4 owns the CLI."
    # Everything genesis established that the delta did not speak to carries.
    assert second.record.created == created.record.created
    assert second.record.slug == created.record.slug
    assert second.record.title == created.record.title
    assert store.read_record() == second.record
    assert store.recover().problems == ()
