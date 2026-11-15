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
    NextAction,
    NextMove,
    ProposedEntry,
    SessionProvenance,
    WheypointDelta,
    WheypointRecord,
)
from easy_cheese_schemas.contracts import EdgeKind, WorkEdge

from easy_cheese.shared.wheypoint import (
    commit,
    fork,
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


def test_retry_after_an_interrupted_promotion_replays_under_fork_and_edge_pressure(
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

    _ = _fork(corpus_root, "alpha", "child-of-alpha")
    sibling = _genesis(
        corpus_root,
        "sibling",
        add_edges=[WorkEdge(to=_ref("alpha"), kind=EdgeKind.SUPERSEDES)],
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
