"""Work edges: keyed merge at commit; an edge writes only the record that holds it."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from easy_cheese_schemas import (
    ArtifactLink,
    NextAction,
    NextMove,
    SessionProvenance,
    WheypointDelta,
    WheypointRecord,
)
from easy_cheese_schemas.contracts import EdgeKind, WorkEdge, WorkEdgeKey

from easy_cheese.shared import paths
from easy_cheese.shared.wheypoint import (
    checkpoint,
    commit,
    edges,
    refs,
    resolve as resolve_mod,
    storage,
)
from work_check import Checked, check_work

PROJECT = "paulnsorensen-easy-cheese"


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
        "working_context": ["src/easy_cheese/shared/wheypoint/edges.py"],
        "next_action": NextAction(move=NextMove.COOK, orientation="Keep going."),
        "session_provenance": SessionProvenance(captured_at="2026-08-02T00:00:00Z"),
        "notes": f"First record of {work_id}.",
    }
    fields.update(overrides)
    _ = commit.commit(
        WheypointDelta(**fields),  # pyright: ignore[reportArgumentType]
        store=store,
    )
    return store


def _next(store: storage.WorkStore, **overrides: object) -> commit.CommitResult:
    current = store.read_record()
    assert current is not None
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


def _lint(store: storage.WorkStore) -> Checked:
    return check_work(store, project_key=PROJECT)


def _linked(corpus_root: Path) -> tuple[storage.WorkStore, storage.WorkStore]:
    a = _genesis(corpus_root, "alpha")
    b = _genesis(corpus_root, "beta")
    _ = _next(a, add_edges=[WorkEdge(to=_ref("beta"), kind=EdgeKind.SUPERSEDES)])
    return a, b


def test_ac8_a_link_writes_one_revision_on_the_initiating_record_only(
    corpus_root: Path,
) -> None:
    a = _genesis(corpus_root, "alpha")
    b = _genesis(corpus_root, "beta")
    target_bytes = b.record_path.read_bytes()

    result = _next(
        a,
        add_edges=[
            WorkEdge(
                to=_ref("beta"),
                kind=EdgeKind.SUPERSEDES,
                revision_id="rev-forged",
                rationale="shares the ref grammar",
            )
        ],
    )

    record = a.read_record()
    assert record is not None and record.revision_number == 2
    stamped = WorkEdge(
        to=_ref("beta"),
        kind=EdgeKind.SUPERSEDES,
        revision_id=result.revision.revision_id,
        rationale="shares the ref grammar",
    )
    assert record.edges == (stamped,)
    assert result.revision.applied_edges == (stamped,)
    assert b.record_path.read_bytes() == target_bytes


def test_ac9_remove_edges_removes_the_edge_by_its_normalized_key(
    corpus_root: Path,
) -> None:
    a, _ = _linked(corpus_root)

    result = _next(
        a,
        remove_edges=[
            WorkEdgeKey(to=f"WHEYPOINT:{PROJECT}/beta/", kind=EdgeKind.SUPERSEDES)
        ],
    )

    record = a.read_record()
    assert record is not None and record.edges == ()
    assert result.revision.removed_edges == (
        WorkEdgeKey(to=_ref("beta"), kind=EdgeKind.SUPERSEDES),
    )
    assert result.revision.applied_edges == ()


def test_ac9_removing_an_edge_the_record_does_not_hold_is_refused(
    corpus_root: Path,
) -> None:
    a, _ = _linked(corpus_root)
    before = a.record_path.read_bytes()

    with pytest.raises(commit.CommitError, match="unknown-edge"):
        _ = _next(
            a, remove_edges=[WorkEdgeKey(to=_ref("beta"), kind=EdgeKind.CHECKPOINTS)]
        )

    assert a.record_path.read_bytes() == before


def test_a_committed_record_with_edges_lints_its_projection_clean(
    corpus_root: Path,
) -> None:
    a, _ = _linked(corpus_root)
    record = a.read_record()
    assert record is not None

    markdown = a.projection_path(record.revision_number, record.revision_id).read_text(
        encoding="utf-8"
    )

    assert "## Links" in markdown and "## Lineage" not in markdown
    assert f"- supersedes {_ref('beta')} @{record.revision_id}" in markdown
    assert _lint(a).codes == ()

def test_genesis_honours_add_edges(corpus_root: Path) -> None:
    a = _genesis(
        corpus_root,
        "gamma",
        add_edges=[WorkEdge(to=_ref("beta"), kind=EdgeKind.CHECKPOINTS)],
    )

    record = a.read_record()
    assert record is not None
    assert record.edges == (
        WorkEdge(
            to=_ref("beta"), kind=EdgeKind.CHECKPOINTS, revision_id=record.revision_id
        ),
    )

def test_an_empty_add_edges_keeps_every_edge(corpus_root: Path) -> None:
    a, _ = _linked(corpus_root)
    before = a.read_record()
    assert before is not None

    _ = _next(a, add_edges=())

    after = a.read_record()
    assert after is not None and after.edges == before.edges



def test_a_pinned_link_still_names_the_target() -> None:
    source = edges.merge_edges(
        (),
        [WorkEdge(to=_ref("beta") + "@rev-0001#q-1", kind=EdgeKind.SUPERSEDES)],
        None,
        revision_id="rev-a",
    )
    assert source.edges[0].to == _ref("beta") + "@rev-0001#q-1"



def test_re_adding_a_held_key_refreshes_its_rationale_and_pin() -> None:
    held = WorkEdge(
        to=_ref("beta"), kind=EdgeKind.CHECKPOINTS, revision_id="rev-old", rationale="old"
    )

    merged = edges.merge_edges(
        (held,),
        [
            WorkEdge(
                to=f"wheypoint:{PROJECT}/beta/",
                kind=EdgeKind.CHECKPOINTS,
                revision_id="rev-forged",
                rationale="new",
            )
        ],
        None,
        revision_id="rev-new",
    )

    refreshed = WorkEdge(
        to=_ref("beta"), kind=EdgeKind.CHECKPOINTS, revision_id="rev-new", rationale="new"
    )
    assert merged.edges == (refreshed,)
    assert merged.applied == (refreshed,)
    assert merged.removed == ()


def test_the_same_target_under_two_kinds_is_two_edges() -> None:
    merged = edges.merge_edges(
        (),
        [
            WorkEdge(to=_ref("beta"), kind=EdgeKind.CHECKPOINTS),
            WorkEdge(to=_ref("beta"), kind=EdgeKind.SUPERSEDES),
        ],
        None,
        revision_id="rev-a",
    )
    assert [edges.edge_key(e) for e in merged.edges] == [
        (_ref("beta"), EdgeKind.CHECKPOINTS),
        (_ref("beta"), EdgeKind.SUPERSEDES),
    ]


def test_an_unknown_removal_key_raises_an_edge_error() -> None:
    with pytest.raises(edges.EdgeError, match="unknown-edge"):
        _ = edges.merge_edges(
            (),
            None,
            [WorkEdgeKey(to=_ref("beta"), kind=EdgeKind.CHECKPOINTS)],
            revision_id="rev-a",
        )


def test_build_delta_forwards_edge_additions_and_removals(
    make_record: Callable[..., WheypointRecord],
) -> None:
    add = (WorkEdge(to=_ref("beta"), kind=EdgeKind.SUPERSEDES),)
    remove = (WorkEdgeKey(to=_ref("gamma"), kind=EdgeKind.CHECKPOINTS),)

    delta = checkpoint.build_delta(
        checkpoint.CheckpointIntent(
            work_id="alpha", add_edges=add, remove_edges=remove
        ),
        make_record(work_id="alpha"),
    )

    assert delta.add_edges == add
    assert delta.remove_edges == remove


def test_ac8_an_unpinned_wheypoint_artifact_link_pins_the_target_revision(
    corpus_root: Path,
) -> None:
    a = _genesis(corpus_root, "alpha")
    b = _genesis(corpus_root, "beta")
    target = b.read_record()
    assert target is not None
    digest = refs.digester(Path(corpus_root), paths.corpus_home())

    _ = _next(
        a,
        add_edges=[WorkEdge(to=_ref("beta"), kind=EdgeKind.SUPERSEDES)],
        add_artifact_links=[ArtifactLink(path=f"{PROJECT}/beta", ref=_ref("beta"))],
    )
    _ = _next(b)

    record = a.read_record()
    assert record is not None
    assert [link.ref for link in record.artifact_links] == [
        f"{_ref('beta')}@{target.revision_id}"
    ]
    assert [edge.to for edge in record.edges] == [_ref("beta")]
    report = check_work(
        a, project_key=PROJECT, git_object_exists=lambda _o: True, artifact_digest=digest
    )
    assert report.codes == ()
    resolution = resolve_mod.resolve(
        "alpha",
        corpus_root=corpus_root,
        project_key=PROJECT,
        git_object_exists=lambda _o: True,
        artifact_digest=digest,
    )
    assert resolution.outcome is resolve_mod.ResolutionOutcome.AUTHORITATIVE


def _moved_target_link(corpus_root: Path) -> tuple[storage.WorkStore, str, str]:
    """`alpha` links `beta` unpinned, then `beta` moves; returns both pins."""
    a = _genesis(corpus_root, "alpha")
    b = _genesis(corpus_root, "beta")
    first = b.read_record()
    assert first is not None
    _ = _next(
        a, add_artifact_links=[ArtifactLink(path=f"{PROJECT}/beta", ref=_ref("beta"))]
    )
    moved = _next(b)
    return a, first.revision_id, moved.record.revision_id


def test_re_adding_an_unpinned_record_link_repins_the_one_link_it_holds(
    corpus_root: Path,
) -> None:
    a, _, moved = _moved_target_link(corpus_root)

    result = _next(
        a, add_artifact_links=[ArtifactLink(path=f"{PROJECT}/beta", ref=_ref("beta"))]
    )

    assert [link.ref for link in result.record.artifact_links] == [
        f"{_ref('beta')}@{moved}"
    ]


def test_an_unpinned_record_ref_removes_the_link_it_pinned(corpus_root: Path) -> None:
    a, _, _ = _moved_target_link(corpus_root)

    result = _next(a, remove_artifact_links=[_ref("beta")])

    assert result.record.artifact_links == []


def test_a_pinned_record_ref_removes_only_the_link_at_that_pin(
    corpus_root: Path,
) -> None:
    a, _, moved = _moved_target_link(corpus_root)
    before = a.record_path.read_bytes()

    with pytest.raises(commit.CommitError, match="does not carry"):
        _ = _next(a, remove_artifact_links=[f"{_ref('beta')}@{moved}"])

    assert a.record_path.read_bytes() == before


def test_commit_refuses_a_caller_authored_forked_from_edge(
    corpus_root: Path,
) -> None:
    a = _genesis(corpus_root, "alpha")
    _ = _genesis(corpus_root, "beta")
    before = a.record_path.read_bytes()

    with pytest.raises(commit.CommitError, match=r"^host-only-edge: "):
        _ = _next(
            a,
            add_edges=[WorkEdge(to=_ref("beta"), kind=EdgeKind.FORKED_FROM)],
        )

    assert a.record_path.read_bytes() == before
