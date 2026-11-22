"""Tests for the /age `severity` command, which adapts easy_cheese_review.severity."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import cast

REPO_ROOT = Path(__file__).resolve().parents[2]
SEVERITY_CLI = REPO_ROOT / "src" / "easy_cheese" / "skills" / "age" / "severity_cli.py"

class TestCli:
    def test_compute_subcommand(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(SEVERITY_CLI),
                "compute",
                "--dimension",
                "encapsulation",
                "--base",
                "high",
                "--location",
                "contract",
                "--fix-cost-later",
                "structural",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        assert json.loads(result.stdout) == "blocker"

    def test_bucket_subcommand(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SEVERITY_CLI), "bucket", "--files", "7"],
            capture_output=True,
            text=True,
            check=True,
        )
        assert json.loads(result.stdout) == "moderate"

    def test_bucket_multi_module(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(SEVERITY_CLI),
                "bucket",
                "--files",
                "2",
                "--modules",
                "2",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        assert json.loads(result.stdout) == "sprawling"

    def test_invalid_input_exits_nonzero(self) -> None:
        # --fix-cost-later "explosive" is rejected by RubricError -> fromargs.CliError -> exit 2
        result = subprocess.run(
            [
                sys.executable,
                str(SEVERITY_CLI),
                "compute",
                "--dimension",
                "encapsulation",
                "--base",
                "high",
                "--location",
                "contract",
                "--fix-cost-later",
                "explosive",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 2
        payload = cast("dict[str, object]", json.loads(result.stderr))
        assert payload["exit_code"] == 2
        assert "fix-cost-later" in str(payload["error"])

    def test_invalid_dimension_exits_two_with_error_prefix(self) -> None:
        # --dimension "vibes" is not in DIMENSIONS; fromargs.CliError emits a JSON error line
        result = subprocess.run(
            [
                sys.executable,
                str(SEVERITY_CLI),
                "compute",
                "--dimension",
                "vibes",
                "--base",
                "high",
                "--location",
                "contract",
                "--fix-cost-later",
                "contained",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 2
        payload = cast("dict[str, object]", json.loads(result.stderr))
        assert payload["exit_code"] == 2
        assert "dimension" in str(payload["error"])