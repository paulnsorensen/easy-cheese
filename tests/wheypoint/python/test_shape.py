"""Shape: the work graph as nodes, edges, and a deterministic Graphviz string."""

from __future__ import annotations

import shutil
import subprocess
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
)
from easy_cheese_schemas.contracts import EdgeKind, WorkEdge

from easy_cheese.shared.wheypoint import commit, fork, shape, storage

PROJECT = "paulnsorensen-easy-cheese"
_PROVENANCE = SessionProvenance(captured_at="2026-08-02T00:00:00Z")


def _ref(work_id: str) -> str:
    return f"wheypoint:{PROJECT}/{work_id}"


def _genesis(corpus_root: Path, work_id: str) -> storage.WorkStore:
    store = storage.WorkStore.open(work_id, corpus_root=corpus_root)
    _ = commit.commit(
        WheypointDelta(
            work_id=work_id,
            expected_revision_id=commit.GENESIS_PARENT,
            orientation=f"Genesis of {work_id}.",
            working_context=["src/easy_cheese/shared/wheypoint/shape.py"],
            next_action=NextAction(move=NextMove.COOK, orientation="Keep going."),
            session_provenance=_PROVENANCE,
            notes=f"First record of {work_id}.",
        ),
        store=store,
    )
    return store


def _next(store: storage.WorkStore, **overrides: object) -> None:
    current = store.read_record()
    assert current is not None
    fields: dict[str, object] = {
        "work_id": store.work_id,
        "expected_revision_id": current.revision_id,
        "notes": f"Revision {current.revision_number + 1}.",
    }
    fields.update(overrides)
    _ = commit.commit(
        WheypointDelta(**fields),  # pyright: ignore[reportArgumentType]
        store=store,
    )


def _link(store: storage.WorkStore, to: str, kind: EdgeKind) -> None:
    _next(store, add_edges=[WorkEdge(to=to, kind=kind)])


def _chain(corpus_root: Path) -> dict[str, storage.WorkStore]:
    """alpha relates_to beta, beta informs gamma; beta has not checkpointed since."""
    stores = {name: _genesis(corpus_root, name) for name in ("alpha", "beta", "gamma")}
    _link(stores["beta"], _ref("gamma"), EdgeKind.INFORMS)
    _link(stores["alpha"], _ref("beta"), EdgeKind.RELATES_TO)
    return stores


def _shape(corpus_root: Path, **kwargs: object) -> shape.ShapeReport:
    return shape.shape(
        scope="project",
        corpus_home=corpus_root.parent,
        project=PROJECT,
        **kwargs,  # pyright: ignore[reportArgumentType]
    )


def _pairs(edges: tuple[shape.ShapeEdge, ...]) -> set[tuple[str, str, str]]:
    return {(edge.from_ref, edge.to, edge.kind.value) for edge in edges}


def test_ac10_shape_returns_nodes_edges_and_a_deterministic_dot(
    corpus_root: Path,
) -> None:
    stores = _chain(corpus_root)

    first = _shape(corpus_root)
    second = _shape(corpus_root)

    assert [node.ref for node in first.nodes] == [
        _ref("alpha"),
        _ref("beta"),
        _ref("gamma"),
    ]
    assert _pairs(first.edges) == {
        (_ref("alpha"), _ref("beta"), "relates_to"),
        (_ref("beta"), _ref("gamma"), "informs"),
    }
    assert all(edge.revision_id is not None for edge in first.edges)
    assert first.dangling == ()
    assert first.dot == second.dot
    assert first.dot == shape.render_dot(first)
    assert first.dot.startswith("digraph wheypoint {")
    node_lines = [
        line for line in first.dot.splitlines() if "label=" in line and "->" not in line
    ]
    assert node_lines == sorted(node_lines)

    shutil.rmtree(stores["gamma"].root)
    broken = _shape(corpus_root)

    assert len(broken.nodes) == 2
    assert _pairs(broken.dangling) == {(_ref("beta"), _ref("gamma"), "informs")}
    assert "color=red" in broken.dot

    if shutil.which("dot") is None:
        pytest.skip("graphviz dot is not installed")
    rendered = subprocess.run(
        ["dot", "-Tsvg"],
        input=first.dot,
        capture_output=True,
        text=True,
        check=False,
    )
    assert rendered.returncode == 0, rendered.stderr
    assert "<svg" in rendered.stdout


def test_shape_lists_the_reciprocal_a_target_still_owes_as_pending(
    corpus_root: Path,
) -> None:
    _ = _chain(corpus_root)

    report = _shape(corpus_root)

    assert _pairs(report.pending) == {(_ref("beta"), _ref("alpha"), "relates_to")}
    assert all(edge.pending for edge in report.pending)
    assert "style=dashed" in report.dot


def test_shape_lists_an_unreconciled_fork_as_a_pending_forked_to_edge(
    corpus_root: Path,
) -> None:
    alpha = _genesis(corpus_root, "alpha")
    _next(
        alpha,
        add_questions=[
            ProposedEntry(
                kind=EntryKind.QUESTION,
                summary="Which store owns the child?",
                blocks_continuation=False,
            )
        ],
    )
    _ = fork.fork(
        parent="alpha",
        child="child",
        corpus_root=corpus_root,
        session_provenance=_PROVENANCE,
        orientation="Split the child off.",
    )

    report = _shape(corpus_root)

    owed = [edge for edge in report.pending if edge.kind is EdgeKind.FORKED_TO]
    assert len(owed) == 1
    assert owed[0].from_ref == _ref("alpha")
    assert owed[0].to.startswith(_ref("child") + "@")
    assert report.roots == (_ref("alpha"),)


def test_shape_lists_a_document_two_records_share(corpus_root: Path) -> None:
    stores = _chain(corpus_root)
    shared = "https://github.com/paulnsorensen/easy-cheese/pull/1"
    _link(stores["alpha"], shared, EdgeKind.IMPLEMENTS)
    _next(
        stores["gamma"],
        add_artifact_links=[ArtifactLink(path="docs/pr.md", ref=shared)],
    )
    _link(stores["beta"], "https://example.com/only-beta", EdgeKind.INFORMS)

    report = _shape(corpus_root)

    assert [(doc.ref, doc.records) for doc in report.documents] == [
        (shared, (_ref("alpha"), _ref("gamma")))
    ]
    assert report.dangling == ()


def test_shape_roots_exclude_records_that_are_forked_or_superseded(
    corpus_root: Path,
) -> None:
    stores = _chain(corpus_root)
    _link(stores["gamma"], _ref("alpha"), EdgeKind.SUPERSEDED_BY)
    beta = stores["beta"].read_record()
    assert beta is not None
    _ = commit.commit(
        WheypointDelta(
            work_id="beta",
            expected_revision_id=beta.revision_id,
            notes="Forked from alpha.",
        ),
        store=stores["beta"],
        fork_edge=WorkEdge(to=_ref("alpha"), kind=EdgeKind.FORKED_FROM),
    )

    report = _shape(corpus_root)

    assert report.roots == (_ref("alpha"),)


def test_shape_keeps_the_component_within_depth_of_a_work_id(
    corpus_root: Path,
) -> None:
    stores = _chain(corpus_root)
    _ = _genesis(corpus_root, "island")
    _ = _genesis(corpus_root, "delta")
    _link(stores["gamma"], _ref("delta"), EdgeKind.RELATES_TO)

    one_hop = _shape(corpus_root, work_id="beta", depth=1)
    unbounded = _shape(corpus_root, work_id="beta")

    assert [node.ref for node in one_hop.nodes] == [
        _ref("alpha"),
        _ref("beta"),
        _ref("gamma"),
    ]
    assert _pairs(one_hop.edges) == {
        (_ref("alpha"), _ref("beta"), "relates_to"),
        (_ref("beta"), _ref("gamma"), "informs"),
    }
    assert [node.ref for node in unbounded.nodes] == [
        _ref("alpha"),
        _ref("beta"),
        _ref("delta"),
        _ref("gamma"),
    ]


def test_shape_kinds_keep_only_those_edges_and_every_node(corpus_root: Path) -> None:
    _ = _chain(corpus_root)

    report = _shape(corpus_root, kinds=[EdgeKind.INFORMS])

    assert len(report.nodes) == 3
    assert _pairs(report.edges) == {(_ref("beta"), _ref("gamma"), "informs")}
    assert report.pending == ()


def test_machine_scope_reads_every_project_corpus(corpus_root: Path) -> None:
    _ = _chain(corpus_root)
    other = corpus_root.parent / "other-project"
    _ = _genesis(other, "omega")

    project = _shape(corpus_root)
    machine = shape.shape(scope="machine", corpus_home=corpus_root.parent, project=None)

    assert len(project.nodes) == 3
    assert "wheypoint:other-project/omega" in {node.ref for node in machine.nodes}
    assert len(machine.nodes) == 4
