"""Work edges: keyed merge at commit, reciprocals pending on read and applied later."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from easy_cheese_schemas import (
    NextAction,
    NextMove,
    SessionProvenance,
    WheypointDelta,
    WheypointRecord,
)
from easy_cheese_schemas.contracts import EdgeKind, WorkEdge, WorkEdgeKey

from easy_cheese.shared.wheypoint import (
    checkpoint,
    commit,
    edges,
    lint,
    storage,
)

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


def _lint(store: storage.WorkStore) -> lint.LintReport:
    return lint.lint_work(
        store,
        project_key=PROJECT,
        git_object_exists=lambda _obj: True,
        artifact_digest=lambda _path: None,
    )


def _linked(corpus_root: Path) -> tuple[storage.WorkStore, storage.WorkStore]:
    a = _genesis(corpus_root, "alpha")
    b = _genesis(corpus_root, "beta")
    _ = _next(a, add_edges=[WorkEdge(to=_ref("beta"), kind=EdgeKind.RELATES_TO)])
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
                kind=EdgeKind.RELATES_TO,
                revision_id="rev-forged",
                rationale="shares the ref grammar",
            )
        ],
    )

    record = a.read_record()
    assert record is not None and record.revision_number == 2
    stamped = WorkEdge(
        to=_ref("beta"),
        kind=EdgeKind.RELATES_TO,
        revision_id=result.revision.revision_id,
        rationale="shares the ref grammar",
    )
    assert record.edges == (stamped,)
    assert result.revision.applied_edges == (stamped,)
    assert b.record_path.read_bytes() == target_bytes


def test_ac8_the_target_reports_link_pending_until_its_next_checkpoint(
    corpus_root: Path,
) -> None:
    a, b = _linked(corpus_root)
    source = a.read_record()
    assert source is not None

    report = _lint(b)

    assert report.codes == (lint.LintCode.LINK_PENDING,)
    assert not any(lint.gates_continuation(f) for f in report.findings)
    assert "alpha@" in report.findings[0].detail
    assert report.pending == (
        edges.PendingEdge(
            source_ref=_ref("alpha"),
            source_work_id="alpha",
            source_revision_id=source.revision_id,
            kind=EdgeKind.RELATES_TO,
            to=_ref("alpha"),
        ),
    )
    assert _lint(a).pending == ()


def test_ac8_the_targets_next_checkpoint_applies_the_reciprocal_host_side(
    corpus_root: Path,
) -> None:
    a, b = _linked(corpus_root)
    source = a.read_record()
    assert source is not None

    result = _next(b)

    reciprocal = WorkEdge(
        to=_ref("alpha"),
        kind=EdgeKind.RELATES_TO,
        revision_id=result.revision.revision_id,
        rationale=f"reciprocal of relates_to from {_ref('alpha')}@{source.revision_id}",
    )
    target = b.read_record()
    assert target is not None and target.edges == (reciprocal,)
    assert result.revision.applied_edges == (reciprocal,)
    assert _lint(b).codes == ()
    assert _lint(a).codes == ()


def test_ac9_remove_edges_removes_the_edge_by_its_normalized_key(
    corpus_root: Path,
) -> None:
    a, _ = _linked(corpus_root)

    result = _next(
        a,
        remove_edges=[
            WorkEdgeKey(to=f"WHEYPOINT:{PROJECT}/beta/", kind=EdgeKind.RELATES_TO)
        ],
    )

    record = a.read_record()
    assert record is not None and record.edges == ()
    assert result.revision.removed_edges == (
        WorkEdgeKey(to=_ref("beta"), kind=EdgeKind.RELATES_TO),
    )
    assert result.revision.applied_edges == ()


def test_ac9_removing_an_edge_the_record_does_not_hold_is_refused(
    corpus_root: Path,
) -> None:
    a, _ = _linked(corpus_root)
    before = a.record_path.read_bytes()

    with pytest.raises(commit.CommitError, match="unknown-edge"):
        _ = _next(
            a, remove_edges=[WorkEdgeKey(to=_ref("beta"), kind=EdgeKind.INFORMS)]
        )

    assert a.record_path.read_bytes() == before


def test_ac11_a_committed_record_with_edges_lints_its_projection_clean(
    corpus_root: Path,
) -> None:
    a, _ = _linked(corpus_root)
    record = a.read_record()
    assert record is not None

    markdown = a.projection_path(record.revision_number, record.revision_id).read_text(
        encoding="utf-8"
    )

    assert "## Links" in markdown and "## Lineage" in markdown
    assert f"- relates_to {_ref('beta')} @{record.revision_id}" in markdown
    assert lint.LintCode.PROJECTION_DIGEST_MISMATCH not in _lint(a).codes


def test_genesis_honours_add_edges_without_a_pending_scan(corpus_root: Path) -> None:
    b = _genesis(corpus_root, "beta")
    _ = _next(b, add_edges=[WorkEdge(to=_ref("gamma"), kind=EdgeKind.RELATES_TO)])

    a = _genesis(
        corpus_root,
        "gamma",
        add_edges=[WorkEdge(to=_ref("beta"), kind=EdgeKind.INFORMS)],
    )

    record = a.read_record()
    assert record is not None
    assert record.edges == (
        WorkEdge(
            to=_ref("beta"), kind=EdgeKind.INFORMS, revision_id=record.revision_id
        ),
    )
    assert [p.source_work_id for p in _lint(a).pending] == ["beta"]


def test_an_empty_add_edges_keeps_every_edge(corpus_root: Path) -> None:
    a, _ = _linked(corpus_root)
    before = a.read_record()
    assert before is not None

    _ = _next(a, add_edges=())

    after = a.read_record()
    assert after is not None and after.edges == before.edges


def test_a_kind_without_a_reciprocal_leaves_the_target_with_nothing_pending(
    corpus_root: Path,
) -> None:
    a = _genesis(corpus_root, "alpha")
    b = _genesis(corpus_root, "beta")
    _ = _next(a, add_edges=[WorkEdge(to=_ref("beta"), kind=EdgeKind.IMPLEMENTS)])

    assert _lint(b).pending == ()


def test_a_pinned_link_still_names_the_target() -> None:
    source = edges.merge_edges(
        (),
        [WorkEdge(to=_ref("beta") + "@rev-0001#q-1", kind=EdgeKind.SUPERSEDES)],
        None,
        revision_id="rev-a",
    )
    assert source.edges[0].to == _ref("beta") + "@rev-0001#q-1"


def test_the_reciprocal_of_a_pinned_supersedes_link_is_superseded_by(
    corpus_root: Path,
) -> None:
    a = _genesis(corpus_root, "alpha")
    b = _genesis(corpus_root, "beta")
    _ = _next(
        a, add_edges=[WorkEdge(to=_ref("beta") + "@rev-0001", kind=EdgeKind.SUPERSEDES)]
    )

    assert [(p.kind, p.to) for p in _lint(b).pending] == [
        (EdgeKind.SUPERSEDED_BY, _ref("alpha"))
    ]


def test_re_adding_a_held_key_refreshes_its_rationale_and_pin() -> None:
    held = WorkEdge(
        to=_ref("beta"), kind=EdgeKind.INFORMS, revision_id="rev-old", rationale="old"
    )

    merged = edges.merge_edges(
        (held,),
        [
            WorkEdge(
                to=f"wheypoint:{PROJECT}/beta/",
                kind=EdgeKind.INFORMS,
                revision_id="rev-forged",
                rationale="new",
            )
        ],
        None,
        revision_id="rev-new",
    )

    refreshed = WorkEdge(
        to=_ref("beta"), kind=EdgeKind.INFORMS, revision_id="rev-new", rationale="new"
    )
    assert merged.edges == (refreshed,)
    assert merged.applied == (refreshed,)
    assert merged.removed == ()


def test_the_same_target_under_two_kinds_is_two_edges() -> None:
    merged = edges.merge_edges(
        (),
        [
            WorkEdge(to=_ref("beta"), kind=EdgeKind.INFORMS),
            WorkEdge(to=_ref("beta"), kind=EdgeKind.RELATES_TO),
        ],
        None,
        revision_id="rev-a",
    )
    assert [edges.edge_key(e) for e in merged.edges] == [
        (_ref("beta"), EdgeKind.INFORMS),
        (_ref("beta"), EdgeKind.RELATES_TO),
    ]


def test_an_unknown_removal_key_raises_an_edge_error() -> None:
    with pytest.raises(edges.EdgeError, match="unknown-edge"):
        _ = edges.merge_edges(
            (),
            None,
            [WorkEdgeKey(to=_ref("beta"), kind=EdgeKind.INFORMS)],
            revision_id="rev-a",
        )


def test_a_pending_reciprocal_already_held_is_not_applied_twice() -> None:
    held = WorkEdge(to=_ref("alpha"), kind=EdgeKind.RELATES_TO, revision_id="rev-b")
    pending = edges.PendingEdge(
        source_ref=_ref("alpha"),
        source_work_id="alpha",
        source_revision_id="rev-a",
        kind=EdgeKind.RELATES_TO,
        to=_ref("alpha"),
    )

    merged = edges.apply_pending_reciprocals((held,), (pending,), revision_id="rev-c")

    assert merged.edges == (held,)
    assert merged.applied == ()


def test_every_reciprocal_kind_maps_back_to_its_source_kind() -> None:
    for kind, reciprocal in edges.RECIPROCAL.items():
        assert edges.RECIPROCAL[reciprocal] is kind
    assert EdgeKind.IMPLEMENTS not in edges.RECIPROCAL


def test_build_delta_forwards_edge_additions_and_removals(
    make_record: Callable[..., WheypointRecord],
) -> None:
    add = (WorkEdge(to=_ref("beta"), kind=EdgeKind.RELATES_TO),)
    remove = (WorkEdgeKey(to=_ref("gamma"), kind=EdgeKind.INFORMS),)

    delta = checkpoint.build_delta(
        checkpoint.CheckpointIntent(
            work_id="alpha", add_edges=add, remove_edges=remove
        ),
        make_record(work_id="alpha"),
    )

    assert delta.add_edges == add
    assert delta.remove_edges == remove
