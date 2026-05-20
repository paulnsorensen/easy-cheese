"""Tests for skills/briesearch/scripts/confidence_cap.py.

Cover the confidence-cap rubric documented in skills/briesearch/references/synthesis.md
and the curd acceptance criterion:
  - single low-quality source caps at don't know
  - 3 concordant high-quality recent sources cap at certain
  - mixed inputs cap at speculating
  - empty list exits 2 with ERROR
  - all-stale caps at don't know
  - conflicting sources cap at don't know
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "skills" / "briesearch" / "scripts" / "confidence_cap.py"


@pytest.fixture(scope="module")
def mod() -> ModuleType:
    spec = importlib.util.spec_from_file_location("confidence_cap", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["confidence_cap"] = module
    spec.loader.exec_module(module)
    return module


def _write_sources(tmp_path: Path, sources: list[dict]) -> Path:
    p = tmp_path / "sources.json"
    p.write_text(json.dumps(sources), encoding="utf-8")
    return p


class TestRubric:
    """Direct calls to cap() exercising each branch of the decision table."""

    def test_single_low_quality_caps_at_dont_know(self, mod: ModuleType) -> None:
        result = mod.cap([
            {"url": "u", "quality": "low", "age_days": 10, "concordance": "agrees"},
        ])
        assert result["confidence"] == "don't know"
        assert result["justification"]

    def test_single_high_quality_still_caps_at_dont_know(self, mod: ModuleType) -> None:
        # Per synthesis.md: single source caps below certain; curd default treats
        # single source as the don't-know branch regardless of quality.
        result = mod.cap([
            {"url": "u", "quality": "high", "age_days": 10, "concordance": "agrees"},
        ])
        assert result["confidence"] == "don't know"

    def test_three_concordant_high_recent_cap_at_certain(self, mod: ModuleType) -> None:
        sources = [
            {"url": f"u{i}", "quality": "high", "age_days": 30, "concordance": "agrees"}
            for i in range(3)
        ]
        result = mod.cap(sources)
        assert result["confidence"] == "certain"
        assert "concordant" in result["justification"] or "3" in result["justification"]

    def test_mixed_quality_caps_at_dont_know_due_to_any_low(self, mod: ModuleType) -> None:
        # Any low-quality source caps at don't know per the rubric ordering.
        sources = [
            {"url": "u1", "quality": "high", "age_days": 30, "concordance": "agrees"},
            {"url": "u2", "quality": "medium", "age_days": 30, "concordance": "agrees"},
            {"url": "u3", "quality": "low", "age_days": 30, "concordance": "agrees"},
        ]
        result = mod.cap(sources)
        assert result["confidence"] == "don't know"

    def test_two_high_quality_concordant_caps_at_speculating(self, mod: ModuleType) -> None:
        # Two sources of corroborating high-quality evidence: rubric says speculating
        # (not enough for certain; not weak enough for don't know).
        sources = [
            {"url": "u1", "quality": "high", "age_days": 30, "concordance": "agrees"},
            {"url": "u2", "quality": "high", "age_days": 30, "concordance": "agrees"},
        ]
        result = mod.cap(sources)
        assert result["confidence"] == "speculating"

    def test_mixed_medium_and_high_caps_at_speculating(self, mod: ModuleType) -> None:
        sources = [
            {"url": "u1", "quality": "high", "age_days": 30, "concordance": "agrees"},
            {"url": "u2", "quality": "medium", "age_days": 30, "concordance": "agrees"},
            {"url": "u3", "quality": "medium", "age_days": 30, "concordance": "neutral"},
        ]
        result = mod.cap(sources)
        assert result["confidence"] == "speculating"

    def test_all_stale_caps_at_dont_know(self, mod: ModuleType) -> None:
        sources = [
            {"url": f"u{i}", "quality": "high", "age_days": 400, "concordance": "agrees"}
            for i in range(3)
        ]
        result = mod.cap(sources)
        assert result["confidence"] == "don't know"
        assert "stale" in result["justification"].lower() or "365" in result["justification"]

    def test_conflicting_caps_at_dont_know(self, mod: ModuleType) -> None:
        sources = [
            {"url": "u1", "quality": "high", "age_days": 30, "concordance": "agrees"},
            {"url": "u2", "quality": "high", "age_days": 30, "concordance": "conflicts"},
            {"url": "u3", "quality": "high", "age_days": 30, "concordance": "agrees"},
        ]
        result = mod.cap(sources)
        assert result["confidence"] == "don't know"
        assert "conflict" in result["justification"].lower()

    def test_empty_list_raises_cli_error(self, mod: ModuleType) -> None:
        with pytest.raises(mod.cli.CliError, match="no sources provided"):
            mod.cap([])

    def test_three_high_with_one_stale_does_not_reach_certain(self, mod: ModuleType) -> None:
        sources = [
            {"url": "u1", "quality": "high", "age_days": 30, "concordance": "agrees"},
            {"url": "u2", "quality": "high", "age_days": 30, "concordance": "agrees"},
            {"url": "u3", "quality": "high", "age_days": 500, "concordance": "agrees"},
        ]
        # Not all_recent, so it must drop below certain — neither low nor stale-only
        # nor conflict, so the residual bucket is speculating.
        result = mod.cap(sources)
        assert result["confidence"] == "speculating"


class TestValidation:
    def test_invalid_quality_raises(self, mod: ModuleType) -> None:
        with pytest.raises(mod.cli.CliError, match="quality"):
            mod.cap([
                {"url": "u", "quality": "great", "age_days": 1, "concordance": "agrees"},
            ])

    def test_invalid_concordance_raises(self, mod: ModuleType) -> None:
        with pytest.raises(mod.cli.CliError, match="concordance"):
            mod.cap([
                {"url": "u", "quality": "high", "age_days": 1, "concordance": "maybe"},
            ])

    def test_negative_age_raises(self, mod: ModuleType) -> None:
        with pytest.raises(mod.cli.CliError, match="age_days"):
            mod.cap([
                {"url": "u", "quality": "high", "age_days": -1, "concordance": "agrees"},
            ])

    def test_non_dict_source_raises(self, mod: ModuleType) -> None:
        with pytest.raises(mod.cli.CliError, match="must be an object"):
            mod.cap(["not a dict"])  # type: ignore[list-item]


class TestCli:
    """End-to-end through the cli.run wiring."""

    def _run(self, *args: str, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT_PATH), *args],
            capture_output=True,
            text=True,
            input=stdin,
        )

    def test_empty_list_exits_two_with_error(self, tmp_path: Path) -> None:
        p = _write_sources(tmp_path, [])
        result = self._run("--sources", str(p))
        assert result.returncode == 2
        assert result.stderr.strip().startswith("ERROR:")
        assert "no sources provided" in result.stderr

    def test_single_low_plain_text_output(self, tmp_path: Path) -> None:
        p = _write_sources(tmp_path, [
            {"url": "u", "quality": "low", "age_days": 10, "concordance": "agrees"},
        ])
        result = self._run("--sources", str(p))
        assert result.returncode == 0
        assert "confidence: don't know" in result.stdout

    def test_three_high_json_output(self, tmp_path: Path) -> None:
        sources = [
            {"url": f"u{i}", "quality": "high", "age_days": 30, "concordance": "agrees"}
            for i in range(3)
        ]
        p = _write_sources(tmp_path, sources)
        result = self._run("--sources", str(p), "--json")
        assert result.returncode == 0
        payload = json.loads(result.stdout)
        assert payload["confidence"] == "certain"
        assert payload["justification"]

    def test_stdin_dash_reads_sources(self) -> None:
        body = json.dumps([
            {"url": "u", "quality": "low", "age_days": 10, "concordance": "agrees"},
        ])
        result = self._run("--sources", "-", stdin=body)
        assert result.returncode == 0
        assert "don't know" in result.stdout

    def test_invalid_json_exits_two(self, tmp_path: Path) -> None:
        p = tmp_path / "bad.json"
        p.write_text("{not json", encoding="utf-8")
        result = self._run("--sources", str(p))
        assert result.returncode == 2
        assert "ERROR:" in result.stderr
        assert "invalid JSON" in result.stderr

    def test_missing_file_exits_two(self, tmp_path: Path) -> None:
        result = self._run("--sources", str(tmp_path / "nope.json"))
        assert result.returncode == 2
        assert "ERROR:" in result.stderr

    def test_non_list_top_level_exits_two(self, tmp_path: Path) -> None:
        p = tmp_path / "obj.json"
        p.write_text('{"k": 1}', encoding="utf-8")
        result = self._run("--sources", str(p))
        assert result.returncode == 2
        assert "must be a JSON list" in result.stderr
