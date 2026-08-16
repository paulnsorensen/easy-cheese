"""Tests for ultracook wiring_topo_sort.py."""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
import yaml

import build_pyz
from easy_cheese_schemas import manifest
from easy_cheese_schemas.wiring_graph import compute_waves

BUNDLE = build_pyz.cached_bundle("ultracook")


def _wiring(*entries: tuple[str, list[str]]) -> list[dict]:
    return [{"id": wid, "depends_on": list(deps)} for wid, deps in entries]


def _write_manifest(path: Path, wiring: list[dict]) -> None:
    path.write_text(yaml.safe_dump({"wiring": wiring}, sort_keys=False), encoding="utf-8")


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(BUNDLE), "wiring_topo_sort", *args],
        capture_output=True,
        text=True,
    )


def test_manifest_and_fanout_share_cycle_wording(wiring: ModuleType) -> None:
    rows = [
        manifest.WiringRow("W1", "config_entry", "a", ["W2"], "pending"),
        manifest.WiringRow("W2", "config_entry", "b", ["W1"], "pending"),
    ]
    with pytest.raises(ValueError) as raised:
        manifest.reject_unschedulable_wiring(None, SimpleNamespace(name="wiring"), rows)
    expected = "the dependency graph has cycle W1 -> W2 -> W1"
    fanout_errors = wiring.graph_errors(
        [{"id": "W1", "depends_on": ["W2"]}, {"id": "W2", "depends_on": ["W1"]}]
    )
    assert str(raised.value) == f"wiring must be schedulable: {expected}"
    assert fanout_errors == [expected]


class TestComputeWaves:
    def test_linear_chain(self) -> None:
        # W1 <- W2 <- W3 must serialize into three single-item waves.
        wiring = [("W1", []), ("W2", ["W1"]), ("W3", ["W2"])]
        assert compute_waves(wiring) == [["W1"], ["W2"], ["W3"]]

    def test_branching_dag(self) -> None:
        # Two independent children of W1 must land in the same second wave —
        # the whole point of waves is to surface parallelism for dispatch.
        wiring = [("W1", []), ("W2", ["W1"]), ("W3", ["W1"])]
        assert compute_waves(wiring) == [["W1"], ["W2", "W3"]]

    def test_empty_wiring_returns_empty(self) -> None:
        assert compute_waves([]) == []

    def test_cycle_raises_value_error(self) -> None:
        # A->B->A would deadlock the dispatcher — fail loudly with the cycle
        # ids so the operator can locate it without re-running.
        wiring = [("W1", ["W2"]), ("W2", ["W1"])]
        with pytest.raises(ValueError, match=r"the dependency graph has cycle W1 -> W2 -> W1"):
            compute_waves(wiring)

    def test_self_loop_is_ignored(self) -> None:
        # A wiring item depending on itself is meaningless, not a cycle —
        # strip it so the dispatcher can still make progress.
        wiring = [("W1", ["W1"])]
        assert compute_waves(wiring) == [["W1"]]

    def test_unknown_dep_treated_as_satisfied(self) -> None:
        # `depends_on` legitimately references curds too; deps outside the
        # wiring set must not block topo sort.
        wiring = [("W1", ["curd-3"])]
        assert compute_waves(wiring) == [["W1"]]

    def test_wave_ordering_is_deterministic(self) -> None:
        # IDs within a wave are sorted so output is stable across runs.
        wiring = [("W3", []), ("W1", []), ("W2", [])]
        assert compute_waves(wiring) == [["W1", "W2", "W3"]]

    def test_shared_with_bundled_wiring_topo_sort(self) -> None:
        # src/fanout/wiring_topo_sort.py re-binds this name from
        # easy_cheese_schemas.wiring_graph; an identity check proves the
        # fanout CLI truly consumes the shared implementation, not a fork.
        module = importlib.import_module("wiring_topo_sort")
        assert module.compute_waves is compute_waves


class TestCLI:
    def test_linear_chain_plain_text(self, tmp_path: Path) -> None:
        manifest = tmp_path / "manifest.yaml"
        _write_manifest(
            manifest, _wiring(("W1", []), ("W2", ["W1"]), ("W3", ["W2"]))
        )
        result = _run_cli("--manifest", str(manifest))
        assert result.returncode == 0, result.stderr
        assert result.stdout == "wave 1: W1\nwave 2: W2\nwave 3: W3\n"

    def test_branching_dag_plain_text(self, tmp_path: Path) -> None:
        manifest = tmp_path / "manifest.yaml"
        _write_manifest(
            manifest, _wiring(("W1", []), ("W2", ["W1"]), ("W3", ["W1"]))
        )
        result = _run_cli("--manifest", str(manifest))
        assert result.returncode == 0, result.stderr
        assert result.stdout == "wave 1: W1\nwave 2: W2, W3\n"

    def test_json_output_shape(self, tmp_path: Path) -> None:
        manifest = tmp_path / "manifest.yaml"
        _write_manifest(
            manifest, _wiring(("W1", []), ("W2", ["W1"]), ("W3", ["W1"]))
        )
        result = _run_cli("--manifest", str(manifest), "--json")
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout) == {"waves": [["W1"], ["W2", "W3"]]}

    def test_empty_wiring_emits_nothing(self, tmp_path: Path) -> None:
        manifest = tmp_path / "manifest.yaml"
        manifest.write_text(yaml.safe_dump({"wiring": []}), encoding="utf-8")
        result = _run_cli("--manifest", str(manifest))
        assert result.returncode == 0, result.stderr
        assert result.stdout == ""

    def test_missing_manifest_exits_two(self, tmp_path: Path) -> None:
        # A nonexistent path is a usage-shaped error per cli.run, so exit 2
        # (not 1) — the dispatcher distinguishes "bad invocation" from "valid
        # invocation, content failed".
        missing = tmp_path / "does-not-exist.yaml"
        result = _run_cli("--manifest", str(missing))
        assert result.returncode == 2
        assert "manifest not found" in result.stderr

    def test_cycle_exits_two(self, tmp_path: Path) -> None:
        manifest = tmp_path / "manifest.yaml"
        _write_manifest(manifest, _wiring(("W1", ["W2"]), ("W2", ["W1"])))
        result = _run_cli("--manifest", str(manifest))
        assert result.returncode == 2
        assert "the dependency graph has cycle W1 -> W2 -> W1" in result.stderr


    def test_missing_manifest_flag_exits_two(self, tmp_path: Path) -> None:
        # argparse's own missing-required-arg path also exits 2; check that
        # the CLI surface doesn't accidentally silently default the path.
        result = _run_cli()
        assert result.returncode == 2

    def test_accepts_json_manifest(self, tmp_path: Path) -> None:
        # manifest_io tries JSON before YAML; a .json manifest must also work
        # so callers don't need to pre-convert.
        manifest = tmp_path / "manifest.json"
        manifest.write_text(
            json.dumps({"wiring": [{"id": "W1", "depends_on": []}]}),
            encoding="utf-8",
        )
        result = _run_cli("--manifest", str(manifest))
        assert result.returncode == 0, result.stderr
        assert result.stdout == "wave 1: W1\n"
