"""Tests for src/fanout/milknado.py — engine-seam probe.

Locks acceptance #4: milknado.probe() returns "engine", "tracker", or None, and
parallel mode runs to completion with milknado entirely absent (probe → None,
native fan-out), proven by stubbing the tool surface away.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from easy_cheese.shared.fanout import milknado

REPO_ROOT = Path(__file__).resolve().parents[3]
BUNDLE = REPO_ROOT / "skills/cook/scripts/cook.pyz"

ENGINE = ["milknado_todo_claim", "milknado_node_verify"]
ENGINE_PREFIXED = [
    "mcp__milknado__milknado_todo_claim",
    "mcp__milknado__milknado_node_verify",
]
TRACKER = ["mcp__milknado__milknado_todo_add"]


class TestProbe:
    def test_tool_surface_stubbed_away_degrades_to_none(self) -> None:
        # AC4: with the milknado surface absent, parallel mode falls to native.
        assert milknado.probe([]) is None

    def test_tracker_when_only_todo_add(self) -> None:
        assert milknado.probe(TRACKER) == "tracker"

    def test_engine_when_claim_and_verify(self) -> None:
        assert milknado.probe(ENGINE) == "engine"

    def test_engine_matches_mcp_prefixed_names(self) -> None:
        assert milknado.probe(ENGINE_PREFIXED) == "engine"

    def test_engine_requires_both_tools(self) -> None:
        # todo_claim alone is not the engine seam; with no todo_add it is None.
        assert milknado.probe(["milknado_todo_claim"]) is None

    def test_engine_wins_over_tracker(self) -> None:
        # A full surface (claim + verify + add) classifies as engine, not tracker.
        assert milknado.probe(ENGINE + TRACKER) == "engine"

    def test_unrelated_tools_are_none(self) -> None:
        assert milknado.probe(["mcp__tilth__tilth_search", "Bash"]) is None


class TestProbeEnvFallback:
    def test_none_when_env_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(milknado.TOOLS_ENV, raising=False)
        assert milknado.probe() is None

    def test_reads_tracker_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(milknado.TOOLS_ENV, "mcp__milknado__milknado_todo_add")
        assert milknado.probe() == "tracker"

    def test_reads_engine_from_env_comma_separated(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(
            milknado.TOOLS_ENV, "milknado_todo_claim, milknado_node_verify"
        )
        assert milknado.probe() == "engine"


class TestCli:
    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(BUNDLE), "milknado", *args],
            capture_output=True,
            text=True,
        )

    def test_empty_tools_prints_none(self) -> None:
        result = self._run("--tools", "")
        assert result.returncode == 0
        assert result.stdout.strip() == "none"

    def test_tracker(self) -> None:
        result = self._run("--tools", "mcp__milknado__milknado_todo_add")
        assert result.returncode == 0
        assert result.stdout.strip() == "tracker"

    def test_engine(self) -> None:
        result = self._run("--tools", "milknado_todo_claim,milknado_node_verify")
        assert result.returncode == 0
        assert result.stdout.strip() == "engine"
