"""Fork: one child genesis with one forked_from edge, and nothing else written."""

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
from easy_cheese_schemas.contracts import EdgeKind, WorkEdge, WorkEdgeKey

from easy_cheese.shared.wheypoint import commit, fork, storage
from work_check import check_work

PROJECT = "paulnsorensen-easy-cheese"
LINK = "https://example.com/spec"
CAPTURED = SessionProvenance(captured_at="2026-09-01T00:00:00Z")


def _ref(work_id: str) -> str:
    return f"wheypoint:{PROJECT}/{work_id}"


def _parent(corpus_root: Path, work_id: str = "parent") -> storage.WorkStore:
    store = storage.WorkStore.open(work_id, corpus_root=corpus_root)
    _ = commit.commit(
        WheypointDelta(
            work_id=work_id,
            expected_revision_id=commit.GENESIS_PARENT,
            orientation="Parent work.",
            working_context=["src/easy_cheese/shared/wheypoint/fork.py"],
            next_action=NextAction(move=NextMove.COOK, orientation="Keep going."),
            session_provenance=CAPTURED,
            add_questions=[
                ProposedEntry(
                    kind=EntryKind.QUESTION,
                    summary="Which store owns the edge?",
                    blocks_continuation=True,
                    rationale="The edge owner decides the write path.",
                )
            ],
            add_decisions=[
                ProposedEntry(
                    kind=EntryKind.DECISION, summary="Keep JSON.", rationale="digests"
                )
            ],
            add_artifact_links=[ArtifactLink(path=LINK, ref=LINK)],
        ),
        store=store,
    )
    return store


def _record(store: storage.WorkStore) -> WheypointRecord:
    record = store.read_record()
    assert record is not None
    return record


def _fork(corpus_root: Path, **overrides: object) -> commit.CommitResult:
    fields: dict[str, object] = {
        "parent": "parent",
        "child": "child",
        "corpus_root": corpus_root,
        "session_provenance": CAPTURED,
        "orientation": "Child work.\nOwns the edge question.",
    }
    fields.update(overrides)
    return fork.fork(**fields)  # pyright: ignore[reportArgumentType]


def _revision_files(corpus_root: Path) -> set[Path]:
    return set(corpus_root.glob("work/*/revisions/*.json"))


def test_ac7_fork_writes_only_the_child_genesis_with_one_forked_from_edge(
    corpus_root: Path,
) -> None:
    parent = _parent(corpus_root)
    before = _record(parent)
    parent_bytes = parent.record_path.read_bytes()
    files = _revision_files(corpus_root)

    result = _fork(corpus_root, links=[LINK])

    new_files = _revision_files(corpus_root) - files
    child = storage.WorkStore.open("child", corpus_root=corpus_root)
    assert [path.parent.parent.name for path in new_files] == ["child"]
    assert parent.record_path.read_bytes() == parent_bytes
    record = _record(child)
    assert record.revision_number == 1
    assert record.title == "Child work."
    assert record.questions == [] and record.decisions == []
    assert record.directives == []
    assert record.edges == (
        WorkEdge(
            to=f"{_ref('parent')}@{before.revision_id}",
            kind=EdgeKind.FORKED_FROM,
            revision_id=result.revision.revision_id,
        ),
    )
    assert [link.ref for link in record.artifact_links] == [LINK]


def test_a_forked_parent_gains_no_pending_state_and_both_records_check_clean(
    corpus_root: Path,
) -> None:
    parent = _parent(corpus_root)
    _ = _fork(corpus_root)
    child = storage.WorkStore.open("child", corpus_root=corpus_root)

    for store in (parent, child):
        assert check_work(store, project_key=PROJECT).codes == ()


def test_fork_refuses_an_existing_child(corpus_root: Path) -> None:
    _ = _parent(corpus_root)
    _ = _parent(corpus_root, "child")

    with pytest.raises(fork.ForkError, match=r"^fork-exists: "):
        _ = _fork(corpus_root)


def test_fork_refuses_an_unknown_parent(corpus_root: Path) -> None:
    with pytest.raises(fork.ForkError, match=r"^unknown-parent: "):
        _ = _fork(corpus_root)


def test_fork_refuses_a_link_the_parent_does_not_carry(corpus_root: Path) -> None:
    _ = _parent(corpus_root)

    with pytest.raises(fork.ForkError, match=r"^unknown-link: "):
        _ = _fork(corpus_root, links=["https://example.com/other"])


def test_commit_refuses_a_forked_from_or_forked_to_edge_in_a_delta(
    corpus_root: Path,
) -> None:
    _ = _parent(corpus_root)
    other = _parent(corpus_root, "other")
    before = other.record_path.read_bytes()
    current = _record(other)

    with pytest.raises(commit.CommitError, match=r"^host-only-edge: "):
        _ = commit.commit(
            WheypointDelta(
                work_id="other",
                expected_revision_id=current.revision_id,
                notes="Two.",
                add_edges=[WorkEdge(to=_ref("parent"), kind=EdgeKind.FORKED_FROM)],
            ),
            store=other,
        )

    assert other.record_path.read_bytes() == before


def test_commit_refuses_a_delta_that_removes_a_fork_edge(corpus_root: Path) -> None:
    _ = _parent(corpus_root)
    _ = _fork(corpus_root)
    child = storage.WorkStore.open("child", corpus_root=corpus_root)
    current = _record(child)
    [edge] = current.edges
    before = child.record_path.read_bytes()

    with pytest.raises(commit.CommitError, match=r"^host-only-edge: "):
        _ = commit.commit(
            WheypointDelta(
                work_id="child",
                expected_revision_id=current.revision_id,
                notes="Two.",
                remove_edges=[WorkEdgeKey(to=edge.to, kind=edge.kind)],
            ),
            store=child,
        )

    assert child.record_path.read_bytes() == before
