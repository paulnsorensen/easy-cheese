"""Tests for ultracook wiring_topo_sort.py."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest
import yaml

import build_pyz

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


class TestComputeWaves:
    def test_linear_chain(self, wiring_topo_sort: ModuleType) -> None:
        # W1 <- W2 <- W3 must serialize into three single-item waves.
        wiring = _wiring(("W1", []), ("W2", ["W1"]), ("W3", ["W2"]))
        assert wiring_topo_sort.compute_waves(wiring) == [["W1"], ["W2"], ["W3"]]

    def test_branching_dag(self, wiring_topo_sort: ModuleType) -> None:
        # Two independent children of W1 must land in the same second wave —
        # the whole point of waves is to surface parallelism for dispatch.
        wiring = _wiring(("W1", []), ("W2", ["W1"]), ("W3", ["W1"]))
        assert wiring_topo_sort.compute_waves(wiring) == [["W1"], ["W2", "W3"]]

    def test_empty_wiring_returns_empty(self, wiring_topo_sort: ModuleType) -> None:
        assert wiring_topo_sort.compute_waves([]) == []

    def test_cycle_raises_cli_error(self, wiring_topo_sort: ModuleType) -> None:
        # A->B->A would deadlock the dispatcher — fail loudly with the cycle
        # ids so the operator can locate it without re-running.
        wiring = _wiring(("W1", ["W2"]), ("W2", ["W1"]))
        with pytest.raises(wiring_topo_sort.cli.CliError) as exc_info:
            wiring_topo_sort.compute_waves(wiring)
        msg = str(exc_info.value)
        assert "cycle detected" in msg
        assert "W1" in msg and "W2" in msg

    def test_self_loop_is_ignored(self, wiring_topo_sort: ModuleType) -> None:
        # A wiring item depending on itself is meaningless, not a cycle —
        # strip it so the dispatcher can still make progress.
        wiring = _wiring(("W1", ["W1"]))
        assert wiring_topo_sort.compute_waves(wiring) == [["W1"]]

    def test_unknown_dep_treated_as_satisfied(self, wiring_topo_sort: ModuleType) -> None:
        # `depends_on` legitimately references curds too; deps outside the
        # wiring set must not block topo sort.
        wiring = _wiring(("W1", ["curd-3"]))
        assert wiring_topo_sort.compute_waves(wiring) == [["W1"]]

    def test_wave_ordering_is_deterministic(self, wiring_topo_sort: ModuleType) -> None:
        # IDs within a wave are sorted so output is stable across runs.
        wiring = _wiring(("W3", []), ("W1", []), ("W2", []))
        assert wiring_topo_sort.compute_waves(wiring) == [["W1", "W2", "W3"]]


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
        assert "cycle detected" in result.stderr

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
