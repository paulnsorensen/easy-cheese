"""Direct main(argv) coverage for src/cook's normalize and validate CLIs.

Curd-5 (build-pyz-wiring) execs these modules through the built cook.pyz
dispatcher with the same argv contract exercised here.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "cook_payloads"

sys.path.insert(0, str(REPO_ROOT / "src" / "cook"))
import normalize  # noqa: E402
import validate  # noqa: E402


def test_normalize_rejects_host_owned_field(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = normalize.main(["normalize.py", str(FIXTURES / "host_owned_writer_view.json")])
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "$.payload.plan_id supplies host-owned field 'plan_id'" in captured.err


def test_normalize_emits_canonical_json_for_clean_payload(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = normalize.main(
        ["normalize.py", str(FIXTURES / "clean_writer_view_with_invocation.json")]
    )
    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    canonical = json.loads(captured.out)
    assert canonical["plan_id"] == "curdplan-cook-cli-normalize-1"
    assert canonical["objective"] == "Ship the approved behavior"
    # Re-encoding must reproduce the same bytes: the CLI's stdout is already canonical.
    assert json.dumps(canonical, sort_keys=True, separators=(",", ":")) == captured.out.strip()


def test_validate_rejects_nonconforming_payload(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = validate.main(
        [
            "validate.py",
            str(FIXTURES / "nonconforming_writer_view.json"),
            "--schema",
            "agent-writer-view",
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.err.startswith("ERROR:")
    assert captured.err.strip() != "ERROR:"


def test_validate_accepts_conforming_payload(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = validate.main(
        [
            "validate.py",
            str(FIXTURES / "conforming_writer_view.json"),
            "--schema",
            "agent-writer-view",
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""


def test_validate_rejects_unknown_schema_slug(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = validate.main(
        [
            "validate.py",
            str(FIXTURES / "conforming_writer_view.json"),
            "--schema",
            "no-such-contract",
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "unknown schema slug" in captured.err
