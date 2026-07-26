"""Deterministic scorer interfaces for strictly local model snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Mapping, Protocol, Sequence

from .contracts import DependencyInventoryV1, FusionProfile, ModelLock, ScoresV1
from .model_lock import ModelLockError, model_profile_digest, verify_local_snapshot

ARCTIC_S_MODEL = "snowflake/snowflake-arctic-embed-s"
BGE_M3_MODEL = "BAAI/bge-m3"
NLI_MODEL = "cross-encoder/nli-deberta-v3-base"


@dataclass(frozen=True)
class ScoringPair:
    pair_id: str
    left: str
    right: str


@dataclass(frozen=True)
class BgeM3Evidence:
    dense: float
    sparse: float
    colbert: float


@dataclass(frozen=True)
class BidirectionalNliEvidence:
    left_entails_right: float
    right_entails_left: float
    left_contradicts_right: float
    right_contradicts_left: float


class ScorerProtocol(Protocol):
    runtime: str
    runtime_digest: str


class ArcticSAdapter(ScorerProtocol, Protocol):
    def score(self, snapshot: Path, pairs: Sequence[ScoringPair]) -> dict[str, float]: ...


class BgeM3Adapter(ScorerProtocol, Protocol):
    modes: tuple[str, ...]

    def score(self, snapshot: Path, pairs: Sequence[ScoringPair]) -> dict[str, BgeM3Evidence]: ...


class NliAdapter(ScorerProtocol, Protocol):
    def diagnose(self, snapshot: Path, pairs: Sequence[ScoringPair]) -> dict[str, BidirectionalNliEvidence]: ...


def dependency_inventory_digest(dependencies: Mapping[str, str]) -> str:
    """Hash the frozen runtime dependency inventory deterministically."""
    return sha256(
        json.dumps(dict(dependencies), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _verify_dependency_inventory(
    inventory: DependencyInventoryV1, locks: tuple[ModelLock, ...]
) -> None:
    if not inventory.dependencies:
        raise ModelLockError("frozen dependency inventory is empty")
    if any(not name or not version for name, version in inventory.dependencies.items()):
        raise ModelLockError("frozen dependency inventory contains an empty entry")
    if inventory.inventory_digest != dependency_inventory_digest(inventory.dependencies):
        raise ModelLockError("frozen dependency inventory digest mismatch")
    for lock in locks:
        if lock.runtime not in inventory.dependencies:
            raise ModelLockError(f"runtime is absent from frozen dependency inventory: {lock.runtime}")


def _verify_adapter(adapter: object, lock: ModelLock, model_id: str) -> None:
    if lock.model_id != model_id:
        raise ModelLockError(f"expected {model_id}, got {lock.model_id}")
    if getattr(adapter, "runtime", None) != lock.runtime:
        raise ModelLockError(f"runtime drift for {model_id}")
    if getattr(adapter, "runtime_digest", None) != lock.runtime_digest:
        raise ModelLockError(f"runtime digest drift for {model_id}")


def _require_complete(pair_ids: set[str], values: dict[str, object], evidence_name: str) -> None:
    if set(values) != pair_ids:
        raise ModelLockError(f"{evidence_name} must cover every labeled pair exactly once")


class LocalScoringRunner:
    """Preflights frozen dependencies, artifacts, and adapters before scoring."""

    def __init__(self, arctic: ArcticSAdapter, bge: BgeM3Adapter, nli: NliAdapter) -> None:
        self._arctic = arctic
        self._bge = bge
        self._nli = nli

    def score(
        self,
        pairs: Sequence[ScoringPair],
        arctic_lock: ModelLock,
        arctic_snapshot: Path,
        bge_lock: ModelLock,
        bge_snapshot: Path,
        nli_lock: ModelLock,
        nli_snapshot: Path,
        fusion_profile: FusionProfile,
        dependency_inventory: DependencyInventoryV1,
    ) -> tuple[ScoresV1, ...]:
        pair_ids = [pair.pair_id for pair in pairs]
        if len(pair_ids) != len(set(pair_ids)):
            raise ModelLockError("pair ids must be unique")

        locks = (arctic_lock, bge_lock, nli_lock)
        _verify_dependency_inventory(dependency_inventory, locks)
        arctic_path = verify_local_snapshot(arctic_lock, arctic_snapshot).path
        bge_path = verify_local_snapshot(bge_lock, bge_snapshot).path
        nli_path = verify_local_snapshot(nli_lock, nli_snapshot).path
        _verify_adapter(self._arctic, arctic_lock, ARCTIC_S_MODEL)
        _verify_adapter(self._bge, bge_lock, BGE_M3_MODEL)
        _verify_adapter(self._nli, nli_lock, NLI_MODEL)
        if tuple(self._bge.modes) != ("dense", "sparse", "colbert"):
            raise ModelLockError("BGE-M3 must expose dense, sparse, and colbert modes")

        arctic = self._arctic.score(arctic_path, pairs)
        bge = self._bge.score(bge_path, pairs)
        nli = self._nli.diagnose(nli_path, pairs)
        expected = set(pair_ids)
        _require_complete(expected, arctic, "Arctic-S evidence")
        _require_complete(expected, bge, "BGE-M3 evidence")
        _require_complete(expected, nli, "bidirectional NLI evidence")
        from .fusion import fuse, fusion_profile_digest

        profile_digest = model_profile_digest(locks)
        fused_digest = fusion_profile_digest(fusion_profile)

        return tuple(
            ScoresV1(
                model_profile_digest=profile_digest,
                fusion_profile_digest=fused_digest,
                pair_id=pair_id,
                dense=bge[pair_id].dense,
                sparse=bge[pair_id].sparse,
                colbert=bge[pair_id].colbert,
                fused=fuse(bge[pair_id], fusion_profile.weights),
            )
            for pair_id in pair_ids
        )