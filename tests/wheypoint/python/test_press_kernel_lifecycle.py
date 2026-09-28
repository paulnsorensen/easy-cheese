"""Adversarial kernel lifecycle checks: double fork races, sticky unlinks,
interrupted-promotion replay under sibling fork/link pressure, and unpinned
re-add/remove of a wheypoint artifact link.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from easy_cheese_schemas import (
    ArtifactLink,
    EntryKind,
    EntryState,
    NextAction,
    NextMove,
    ProposedEntry,
    SessionProvenance,
    TransitionAction,
    WheypointDelta,
    WheypointRecord,
)
from easy_cheese_schemas.contracts import EdgeKind, WorkEdge, WorkEdgeKey

from easy_cheese.shared.wheypoint import (
    commit,
    fork,
    records,
    shape,
    storage,
)

PROJECT = "paulnsorensen-easy-cheese"
CAPTURED = SessionProvenance(captured_at="2026-09-28T00:00:00Z")


def _ref(work_id: str) -> str:
    return f"wheypoint:{PROJECT}/{work_id}"


def _genesis(
    corpus_root: Path, work_id: str, **overrides: object
) -> storage.WorkStore:
    store = storage.WorkStore.open(work_id, corpus_root=corpus_root)
    fields: dict[str, object] = {
        "work_id": work_id,
        "expected_revision_id": commit.GENESIS_PARENT,
        "orientation": f"Genesis of {work_id}.",
        "working_context": ["src/easy_cheese/shared/wheypoint/commit.py"],
        "next_action": NextAction(move=NextMove.COOK, orientation="Keep going."),
        "session_provenance": CAPTURED,
        "notes": f"First record of {work_id}.",
    }
    fields.update(overrides)
    _ = commit.commit(
        WheypointDelta(**fields),  # pyright: ignore[reportArgumentType]
        store=store,
    )
    return store


def _record(store: storage.WorkStore) -> WheypointRecord:
    record = store.read_record()
    assert record is not None
    return record


def _next(store: storage.WorkStore, **overrides: object) -> commit.CommitResult:
    current = _record(store)
    fields: dict[str, object] = {
        "work_id": store.work_id,
        "expected_revision_id": current.revision_id,
        "notes": f"Revision {current.revision_number + 1}.",
    }
    fields.update(overrides)
    return commit.commit(
        WheypointDelta(**fields),  # pyright: ignore[reportArgumentType]
        store=store,
    )


def _fork(corpus_root: Path, parent: str, child: str, **overrides: object) -> commit.CommitResult:
    fields: dict[str, object] = {
        "parent": parent,
        "child": child,
        "corpus_root": corpus_root,
        "session_provenance": CAPTURED,
        "orientation": f"Child {child}.\nOwns the moved question.",
    }
    fields.update(overrides)
    return fork.fork(**fields)  # pyright: ignore[reportArgumentType]


def _revision_files(corpus_root: Path) -> set[Path]:
    return set(corpus_root.glob("work/*/revisions/*.json"))


def _child_entry(record: WheypointRecord, kind: EntryKind) -> str:
    return next(e.entry_id for e in record.questions + record.directives if e.kind is kind)


def _interrupt(
    monkeypatch: pytest.MonkeyPatch, store: storage.WorkStore, delta: WheypointDelta
) -> commit.CommitResult:
    """Commit `delta`, but leave the record at its old bytes: a stranded pair."""
    old = store.record_path.read_bytes()
    real = storage.WorkStore.promote

    def interrupted(
        self: storage.WorkStore,
        record: WheypointRecord,
        revision: object,
        markdown: str,
    ) -> None:
        real(self, record, revision, markdown)  # pyright: ignore[reportArgumentType]
        _ = self.record_path.write_bytes(old)

    monkeypatch.setattr(storage.WorkStore, "promote", interrupted)
    result = commit.commit(delta, store=store)
    monkeypatch.setattr(storage.WorkStore, "promote", real)
    return result


def test_fork_second_move_of_a_pending_entry_is_refused_then_a_raced_fork_reconciles(
    corpus_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parent = _genesis(
        corpus_root,
        "parent",
        add_questions=[
            ProposedEntry(
                kind=EntryKind.QUESTION,
                summary="Who owns the shared question?",
                blocks_continuation=False,
            )
        ],
    )
    question = _record(parent).questions[0].entry_id

    _ = _fork(corpus_root, "parent", "child-a", move=[question])

    with pytest.raises(fork.ForkError, match=r"^already-forked: "):
        _ = _fork(corpus_root, "parent", "child-b", move=[question])
    record_path = storage.WorkStore.open("child-b", corpus_root=corpus_root).record_path
    assert not record_path.exists()

    def none_pending(
        _source: WheypointRecord, **_siblings: object
    ) -> tuple[object, ...]:
        return ()

    monkeypatch.setattr(fork, "pending_forks", none_pending)
    _ = _fork(corpus_root, "parent", "child-b", move=[question])
    monkeypatch.undo()

    reconciled = _next(parent)

    child_a = _record(storage.WorkStore.open("child-a", corpus_root=corpus_root))
    child_b = _record(storage.WorkStore.open("child-b", corpus_root=corpus_root))
    child_a_question = _child_entry(child_a, EntryKind.QUESTION)
    child_b_question = _child_entry(child_b, EntryKind.QUESTION)

    [entry] = [e for e in records.entries(_record(parent)) if e.entry_id == question]
    assert entry.state is EntryState.FORKED
    assert entry.successor == f"{_ref('child-a')}#{child_a_question}"
    assert entry.copies == (f"{_ref('child-b')}#{child_b_question}",)
    assert [
        (t.entry_id, t.action, t.successor)
        for t in reconciled.revision.applied_transitions
    ] == [(question, TransitionAction.FORK, f"{_ref('child-a')}#{child_a_question}")]

    again = _next(parent)
    assert again.revision.applied_transitions == []


def _linked(corpus_root: Path) -> tuple[storage.WorkStore, storage.WorkStore]:
    a = _genesis(corpus_root, "alpha")
    b = _genesis(corpus_root, "beta")
    _ = _next(a, add_edges=[WorkEdge(to=_ref("beta"), kind=EdgeKind.RELATES_TO)])
    return a, b


def test_target_side_unlink_of_a_reciprocal_stays_unlinked_across_checkpoints(
    corpus_root: Path,
) -> None:
    a, b = _linked(corpus_root)
    _ = _next(b)  # beta reconciles the reciprocal: beta holds relates_to -> alpha
    assert any(e.to == _ref("alpha") for e in _record(b).edges)

    _ = _next(
        b, remove_edges=[WorkEdgeKey(to=_ref("alpha"), kind=EdgeKind.RELATES_TO)]
    )

    a_result = _next(a)
    b_first = _next(b)
    b_second = _next(b)

    assert not any(e.to == _ref("alpha") for e in _record(b).edges)
    assert any(e.to == _ref("beta") for e in _record(a).edges)
    assert a_result.revision.applied_edges == ()
    assert (b_first.revision.applied_edges, b_second.revision.applied_edges) == (
        (),
        (),
    )
    report = shape.shape(scope="project", corpus_home=corpus_root.parent, project=PROJECT)
    assert report.pending == ()


def test_source_side_unlink_never_regains_the_edge(corpus_root: Path) -> None:
    a, b = _linked(corpus_root)
    _ = _next(b)

    _ = _next(a, remove_edges=[WorkEdgeKey(to=_ref("beta"), kind=EdgeKind.RELATES_TO)])

    a_first = _next(a)
    a_second = _next(a)
    b_first = _next(b)
    b_second = _next(b)

    assert _record(a).edges == ()
    assert (a_first.revision.applied_edges, a_second.revision.applied_edges) == (
        (),
        (),
    )
    assert (b_first.revision.applied_edges, b_second.revision.applied_edges) == (
        (),
        (),
    )


def test_retry_after_an_interrupted_promotion_replays_under_sibling_fork_and_link_pressure(
    corpus_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    a = _genesis(
        corpus_root,
        "alpha",
        add_questions=[
            ProposedEntry(
                kind=EntryKind.QUESTION, summary="Split me?", blocks_continuation=False
            )
        ],
    )
    current = _record(a)
    delta = WheypointDelta(
        work_id="alpha", expected_revision_id=current.revision_id, notes="Two."
    )
    files_before_interrupt = _revision_files(corpus_root)

    first = _interrupt(monkeypatch, a, delta)

    question = current.questions[0].entry_id
    _ = _fork(corpus_root, "alpha", "child-of-alpha", move=[question])
    sibling = _genesis(
        corpus_root,
        "sibling",
        add_edges=[WorkEdge(to=_ref("alpha"), kind=EdgeKind.RELATES_TO)],
    )
    del sibling

    retried = commit.commit(delta, store=a)

    assert retried.revision.revision_id == first.revision.revision_id
    assert _record(a).revision_id == first.revision.revision_id
    files_after = _revision_files(corpus_root)
    alpha_revisions = {p for p in files_after if p.parent.parent.name == "alpha"}
    alpha_revisions_before = {
        p for p in files_before_interrupt if p.parent.parent.name == "alpha"
    }
    assert len(alpha_revisions - alpha_revisions_before) == 1


def test_unpinned_relink_holds_one_link_pinned_to_the_new_revision_then_unlinks_clean(
    corpus_root: Path,
) -> None:
    a = _genesis(corpus_root, "alpha")
    b = _genesis(corpus_root, "beta")
    _ = _next(
        a, add_artifact_links=[ArtifactLink(path=f"{PROJECT}/beta", ref=_ref("beta"))]
    )
    first_pin = _record(a).artifact_links[0].ref
    moved = _next(b)

    relinked = _next(
        a, add_artifact_links=[ArtifactLink(path=f"{PROJECT}/beta", ref=_ref("beta"))]
    )

    assert [link.ref for link in relinked.record.artifact_links] == [
        f"{_ref('beta')}@{moved.record.revision_id}"
    ]
    assert relinked.record.artifact_links[0].ref != first_pin

    removed = _next(a, remove_artifact_links=[_ref("beta")])

    assert removed.record.artifact_links == []
