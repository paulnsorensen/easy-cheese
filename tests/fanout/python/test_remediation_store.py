"""Containment and size-bound tests for the remediation state store."""
from __future__ import annotations

from pathlib import Path

import pytest
from easy_cheese.shared.fanout.remediation_store import (
    MAX_STATE_BYTES,
    StateStoreError,
    initial_state,
    load_state,
    publish_state,
    run_lock,
    scope_state_path,
)
from easy_cheese_schemas import (
    RemediationCursor,
    RemediationScopeKey,
    RemediationScopeKind,
    SourcePlanRef,
)

DIGEST = f"sha256:{'a' * 64}"


def _scope() -> RemediationScopeKey:
    return RemediationScopeKey(
        run_id="run-1",
        source_plan_ref=SourcePlanRef(plan_id="plan-1", revision=1, digest=DIGEST),
        scope_kind=RemediationScopeKind.CURD,
        scope_id="curd-1",
    )


def test_round_trip_publishes_and_reloads(tmp_path: Path) -> None:
    scope = _scope()
    path = scope_state_path(tmp_path, scope)
    published = publish_state(tmp_path, path, initial_state(scope, state_id="s1"))
    assert published.cursor is RemediationCursor.AWAITING_REVIEW
    assert load_state(tmp_path, path) == published


def test_publish_refuses_path_outside_root(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside.json"
    with pytest.raises(StateStoreError):
        _ = publish_state(root, outside, initial_state(_scope(), state_id="s1"))
    assert not outside.exists()


def test_load_refuses_path_outside_root(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    scope = _scope()
    outside = tmp_path / "outside.json"
    _ = publish_state(tmp_path, outside, initial_state(scope, state_id="s1"))
    with pytest.raises(StateStoreError):
        _ = load_state(root, root / ".." / "outside.json")


def test_load_refuses_oversize_file(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    _ = path.write_bytes(b" " * (MAX_STATE_BYTES + 1))
    with pytest.raises(StateStoreError, match="exceeds"):
        _ = load_state(tmp_path, path)


def test_run_lock_rejects_second_holder_and_keeps_inode(tmp_path: Path) -> None:
    with run_lock(tmp_path, "run-1") as lock:
        assert lock.exists()
        with pytest.raises(StateStoreError, match="locked by another"):
            with run_lock(tmp_path, "run-1"):
                pass
        assert lock.exists()
    assert lock.exists()
