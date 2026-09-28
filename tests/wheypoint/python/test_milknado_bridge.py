"""The easy-cheese half of the milknado seam: a ref, an edge, a presence gate."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from easy_cheese_schemas import WheypointDelta, WheypointRecord
from easy_cheese_schemas.contracts import EdgeKind, WorkEdge

from easy_cheese.shared.wheypoint import (
    commit,
    milknado_bridge,
    resolve,
    resolve_cli,
    storage,
)

from conftest import WORK_ID, Promotion

PROJECT = "paulnsorensen-easy-cheese"
NODE_REF = f"milknado:{PROJECT}/node-1"


def _bound_record(
    corpus_root: Path, make_promotion: Callable[..., Promotion]
) -> WheypointRecord:
    store = storage.WorkStore.open(WORK_ID, corpus_root=corpus_root)
    seed = make_promotion()
    store.promote(seed.record, seed.revision, seed.markdown)
    delta = WheypointDelta(
        work_id=WORK_ID,
        expected_revision_id=seed.record.revision_id,
        add_edges=(WorkEdge(to=NODE_REF, kind=EdgeKind.CHECKPOINTS),),
    )
    return commit.commit(delta, store=store).record


def test_ac17_a_checkpoints_edge_to_a_milknado_node_is_accepted_without_a_digest(
    corpus_root: Path, make_promotion: Callable[..., Promotion]
) -> None:
    record = _bound_record(corpus_root, make_promotion)

    assert [(edge.to, edge.kind) for edge in record.edges] == [
        (NODE_REF, EdgeKind.CHECKPOINTS)
    ]
    assert record.edges[0].revision_id == record.revision_id
    assert record.artifact_links == []


def test_ac17_bind_is_inactive_without_milknado_and_bound_with_it(
    tmp_path: Path, corpus_root: Path, make_promotion: Callable[..., Promotion]
) -> None:
    record = _bound_record(corpus_root, make_promotion)
    repo = tmp_path / "repo"
    repo.mkdir()
    wheypoint_ref = f"wheypoint:{PROJECT}/{WORK_ID}"

    inactive = milknado_bridge.bind(record, repo_root=repo)
    (repo / milknado_bridge.MILKNADO_DIRNAME).mkdir()
    bound = milknado_bridge.bind(record, repo_root=repo)

    assert inactive == milknado_bridge.BridgeState(
        state="bridge-inactive", node_ref=NODE_REF, wheypoint_ref=wheypoint_ref
    )
    assert bound == milknado_bridge.BridgeState(
        state="bound", node_ref=NODE_REF, wheypoint_ref=wheypoint_ref
    )
    assert milknado_bridge.payload(bound) == {
        "state": "bound",
        "node_ref": NODE_REF,
        "wheypoint_ref": wheypoint_ref,
    }


def test_ac17_a_record_with_no_checkpoints_edge_is_unbound(
    tmp_path: Path, make_promotion: Callable[..., Promotion]
) -> None:
    (tmp_path / milknado_bridge.MILKNADO_DIRNAME).mkdir()

    state = milknado_bridge.bind(make_promotion().record, repo_root=tmp_path)

    assert state.state == "unbound"
    assert state.node_ref is None


@pytest.mark.parametrize("present", [False, True], ids=["absent", "present"])
def test_ac17_resolve_reports_the_bridge_without_changing_dispatch(
    present: bool,
    tmp_path: Path,
    corpus_root: Path,
    make_promotion: Callable[..., Promotion],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ = _bound_record(corpus_root, make_promotion)
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.chdir(repo)
    baseline = resolve_cli.resolve_payload(
        resolve.resolve(WORK_ID, corpus_root=corpus_root), WORK_ID
    )
    if present:
        (repo / milknado_bridge.MILKNADO_DIRNAME).mkdir()

    payload = resolve_cli.resolve_payload(
        resolve.resolve(WORK_ID, corpus_root=corpus_root), WORK_ID
    )

    assert payload["bridge"] == {
        "state": "bound" if present else "bridge-inactive",
        "node_ref": NODE_REF,
        "wheypoint_ref": f"wheypoint:{PROJECT}/{WORK_ID}",
    }
    assert payload["dispatchable"] == baseline["dispatchable"]
    assert payload["outcome"] == baseline["outcome"]


def test_ac17_resolve_without_a_record_carries_no_bridge(corpus_root: Path) -> None:
    payload = resolve_cli.resolve_payload(
        resolve.resolve("no-such-work", corpus_root=corpus_root), "no-such-work"
    )

    assert payload["record"] is None
    assert payload["bridge"] is None


def test_ac17_gate_mapping_is_the_four_row_table() -> None:
    assert [
        (row.wheypoint, row.milknado) for row in milknado_bridge.GATE_MAPPING
    ] == [
        ("gated question", "pending goal review"),
        ("resolve", "accepted review"),
        ("active blocker", "blocked node"),
        ("checkpoint", "snapshot receipt"),
    ]
