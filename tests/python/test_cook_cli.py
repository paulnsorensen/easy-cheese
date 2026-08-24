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
import cook_cli  # noqa: E402


def test_normalize_rejects_host_owned_field(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = cook_cli.main(
        [
            "normalize.py",
            str(FIXTURES / "host_owned_writer_view.json"),
            "--invocation",
            str(FIXTURES / "clean_invocation.json"),
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "$.payload.plan_id supplies host-owned field 'plan_id'" in captured.err


def test_normalize_rejects_invocation_key_inside_document(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = cook_cli.main(
        [
            "normalize.py",
            str(FIXTURES / "document_with_embedded_invocation.json"),
            "--invocation",
            str(FIXTURES / "clean_invocation.json"),
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "host-owned field" in captured.err
    assert "$.invocation" in captured.err


def test_normalize_rejects_deeply_nested_document(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = cook_cli.main(
        [
            "normalize.py",
            str(FIXTURES / "deeply_nested_document.json"),
            "--invocation",
            str(FIXTURES / "clean_invocation.json"),
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.err.startswith("ERROR:")
    assert "MAX_CONTRACT_DEPTH" in captured.err
    assert "Traceback" not in captured.err


def test_normalize_rejects_duplicate_key_document(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = cook_cli.main(
        [
            "normalize.py",
            str(FIXTURES / "duplicate_key_document.json"),
            "--invocation",
            str(FIXTURES / "clean_invocation.json"),
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "duplicate field 'kind'" in captured.err


def test_normalize_rejects_unsupported_contract_version(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = cook_cli.main(
        [
            "normalize.py",
            str(FIXTURES / "clean_writer_view.json"),
            "--invocation",
            str(FIXTURES / "unsupported_major_invocation.json"),
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "unsupported contract version 99.0" in captured.err
    assert "expected" in captured.err


def test_normalize_emits_canonical_json_for_clean_payload(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = cook_cli.main(
        [
            "normalize.py",
            str(FIXTURES / "clean_writer_view.json"),
            "--invocation",
            str(FIXTURES / "clean_invocation.json"),
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    canonical = json.loads(captured.out)
    assert set(canonical) == {"value", "digest", "version"}
    assert canonical["value"]["plan_id"] == "curdplan-cook-cli-normalize-1"
    assert canonical["value"]["objective"] == "Ship the approved behavior"
    assert canonical["digest"].startswith("sha256:")
    assert canonical["version"]["major"] == "1"
    # Re-encoding must reproduce the same bytes: the CLI's stdout is already canonical.
    assert json.dumps(canonical, sort_keys=True, separators=(",", ":")) == captured.out.strip()


def test_validate_rejects_nonconforming_payload(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = cook_cli.main(
        [
            "validate.py",
            str(FIXTURES / "nonconforming_writer_view.json"),
            "--schema",
            "agent-writer-view",
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "$.kind" in captured.err


def test_validate_accepts_conforming_payload(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = cook_cli.main(
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
    exit_code = cook_cli.main(
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


def test_main_dispatches_via_argv1_when_argv0_is_not_a_verb(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = cook_cli.main(
        [
            "cook_cli.py",
            "validate",
            str(FIXTURES / "conforming_writer_view.json"),
            "--schema",
            "agent-writer-view",
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""


def test_main_rejects_unknown_command(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = cook_cli.main(["cook_cli.py", "bogus"])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert captured.err == "ERROR: expected a 'normalize' or 'validate' command\n"


def test_validate_accepts_versioned_curd_plan_payload(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """normalize's own canonical output is a versioned CurdPlan carrying
    contract_version and digest; validate must accept it — the exact case the
    missing supported_version argument rejected, and the coherence contract
    between the two subcommands."""
    exit_code = cook_cli.main(
        [
            "normalize.py",
            str(FIXTURES / "clean_writer_view.json"),
            "--invocation",
            str(FIXTURES / "clean_invocation.json"),
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 0, captured.err
    plan_value = json.loads(captured.out)["value"]
    assert plan_value["contract_version"]["major"] == "1"
    payload_path = tmp_path / "curd-plan.json"
    payload_path.write_text(json.dumps(plan_value), encoding="utf-8")

    exit_code = cook_cli.main(
        ["validate.py", str(payload_path), "--schema", "curd-plan"]
    )
    captured = capsys.readouterr()
    assert exit_code == 0, captured.err
    assert captured.err == ""