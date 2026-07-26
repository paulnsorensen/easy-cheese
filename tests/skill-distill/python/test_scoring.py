from __future__ import annotations

from pathlib import Path

import pytest

from skill_distill.contracts import DependencyInventoryV1, FusionProfile, ModelLock, ScoresV1
from skill_distill.model_lock import ModelLockError, snapshot_digest
from skill_distill.retrieval import (
    ARCTIC_S_MODEL,
    BGE_M3_MODEL,
    NLI_MODEL,
    BgeM3Evidence,
    BidirectionalNliEvidence,
    LocalScoringRunner,
    ScoringPair,
    dependency_inventory_digest,
)


class FakeArctic:
    runtime = "fake-runtime==1.0"
    runtime_digest = "d" * 64

    def __init__(self) -> None:
        self.calls = 0

    def score(self, snapshot: Path, pairs: object) -> dict[str, float]:
        self.calls += 1
        return {pair.pair_id: 0.25 for pair in pairs}


class FakeBge:
    runtime = "fake-runtime==1.0"
    runtime_digest = "d" * 64
    modes = ("dense", "sparse", "colbert")

    def __init__(self) -> None:
        self.paths: list[Path] = []

    def score(self, snapshot: Path, pairs: object) -> dict[str, BgeM3Evidence]:
        self.paths.append(snapshot)
        return {pair.pair_id: BgeM3Evidence(0.2, 0.3, 0.5) for pair in pairs}


class FakeNli:
    runtime = "fake-runtime==1.0"
    runtime_digest = "d" * 64

    def __init__(self) -> None:
        self.calls = 0

    def diagnose(self, snapshot: Path, pairs: object) -> dict[str, BidirectionalNliEvidence]:
        self.calls += 1
        return {
            pair.pair_id: BidirectionalNliEvidence(0.9, 0.8, 0.1, 0.2)
            for pair in pairs
        }


def _snapshot_lock(tmp_path: Path, model_id: str) -> tuple[ModelLock, Path]:
    snapshot = tmp_path / model_id.replace("/", "-")
    snapshot.mkdir()
    (snapshot / "artifact.bin").write_bytes(model_id.encode())
    return (
        ModelLock(
            model_id=model_id,
            artifact_revision="a" * 40,
            artifact_digest=snapshot_digest(snapshot),
            runtime="fake-runtime==1.0",
            runtime_digest="d" * 64,
        ),
        snapshot,
    )


def _fusion_profile() -> FusionProfile:
    return FusionProfile("split", "fold", (0.2, 0.3, 0.5), 1, "a" * 64, "b" * 64)


def _dependency_inventory() -> DependencyInventoryV1:
    dependencies = {"fake-runtime==1.0": "pinned"}
    return DependencyInventoryV1(
        inventory_digest=dependency_inventory_digest(dependencies),
        dependencies=dependencies,
    )


def test_local_scoring_collects_every_required_evidence_without_downloads(tmp_path: Path) -> None:
    arctic_lock, arctic_snapshot = _snapshot_lock(tmp_path, ARCTIC_S_MODEL)
    bge_lock, bge_snapshot = _snapshot_lock(tmp_path, BGE_M3_MODEL)
    nli_lock, nli_snapshot = _snapshot_lock(tmp_path, NLI_MODEL)
    arctic, bge, nli = FakeArctic(), FakeBge(), FakeNli()

    result = LocalScoringRunner(arctic, bge, nli).score(
        (ScoringPair("pair-1", "left", "right"),),
        arctic_lock,
        arctic_snapshot,
        bge_lock,
        bge_snapshot,
        nli_lock,
        nli_snapshot,
        _fusion_profile(),
        _dependency_inventory(),
    )

    assert isinstance(result[0], ScoresV1)
    assert result[0].fused == pytest.approx(0.38)
    assert bge.paths == [bge_snapshot.resolve()]
    assert arctic.calls == nli.calls == 1


def test_preflight_halts_before_any_adapter_runs_on_runtime_drift(tmp_path: Path) -> None:
    arctic_lock, arctic_snapshot = _snapshot_lock(tmp_path, ARCTIC_S_MODEL)
    bge_lock, bge_snapshot = _snapshot_lock(tmp_path, BGE_M3_MODEL)
    nli_lock, nli_snapshot = _snapshot_lock(tmp_path, NLI_MODEL)
    arctic, bge, nli = FakeArctic(), FakeBge(), FakeNli()
    bge.runtime_digest = "e" * 64

    with pytest.raises(ModelLockError, match="runtime digest drift"):
        LocalScoringRunner(arctic, bge, nli).score(
            (ScoringPair("pair-1", "left", "right"),),
            arctic_lock,
            arctic_snapshot,
            bge_lock,
            bge_snapshot,
            nli_lock,
            nli_snapshot,
            _fusion_profile(),
            _dependency_inventory(),
        )
    assert arctic.calls == nli.calls == 0
    assert bge.paths == []


def test_preflight_rejects_tampered_frozen_dependency_inventory(tmp_path: Path) -> None:
    arctic_lock, arctic_snapshot = _snapshot_lock(tmp_path, ARCTIC_S_MODEL)
    bge_lock, bge_snapshot = _snapshot_lock(tmp_path, BGE_M3_MODEL)
    nli_lock, nli_snapshot = _snapshot_lock(tmp_path, NLI_MODEL)
    arctic, bge, nli = FakeArctic(), FakeBge(), FakeNli()
    inventory = DependencyInventoryV1("0" * 64, {"fake-runtime==1.0": "pinned"})

    with pytest.raises(ModelLockError, match="inventory digest mismatch"):
        LocalScoringRunner(arctic, bge, nli).score(
            (ScoringPair("pair-1", "left", "right"),),
            arctic_lock,
            arctic_snapshot,
            bge_lock,
            bge_snapshot,
            nli_lock,
            nli_snapshot,
            _fusion_profile(),
            inventory,
        )
    assert arctic.calls == nli.calls == 0
    assert bge.paths == []


def test_preflight_rejects_undeclared_snapshot_file_before_adapters_run(tmp_path: Path) -> None:
    arctic_lock, arctic_snapshot = _snapshot_lock(tmp_path, ARCTIC_S_MODEL)
    bge_lock, bge_snapshot = _snapshot_lock(tmp_path, BGE_M3_MODEL)
    nli_lock, nli_snapshot = _snapshot_lock(tmp_path, NLI_MODEL)
    (bge_snapshot / "injected.bin").write_bytes(b"unexpected")
    arctic, bge, nli = FakeArctic(), FakeBge(), FakeNli()

    with pytest.raises(ModelLockError, match="undeclared files"):
        LocalScoringRunner(arctic, bge, nli).score(
            (ScoringPair("pair-1", "left", "right"),),
            arctic_lock,
            arctic_snapshot,
            bge_lock,
            bge_snapshot,
            nli_lock,
            nli_snapshot,
            _fusion_profile(),
            _dependency_inventory(),
        )
    assert arctic.calls == nli.calls == 0
    assert bge.paths == []