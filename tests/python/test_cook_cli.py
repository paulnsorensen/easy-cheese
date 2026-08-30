"""Behavioral coverage for Cook's public normalize and validate commands."""
from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest
from easy_cheese.skills.cook import commands

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "cook_payloads"

def test_normalize_rejects_host_owned_field(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = commands.main(
        [
            "normalize",
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
    exit_code = commands.main(
        [
            "normalize",
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
    exit_code = commands.main(
        [
            "normalize",
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
    exit_code = commands.main(
        [
            "normalize",
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
    exit_code = commands.main(
        [
            "normalize",
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
    exit_code = commands.main(
        [
            "normalize",
            str(FIXTURES / "clean_writer_view.json"),
            "--invocation",
            str(FIXTURES / "clean_invocation.json"),
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    canonical = cast(dict[str, object], json.loads(captured.out))
    assert set(canonical) == {"value", "digest", "version"}
    value = cast(dict[str, object], canonical["value"])
    assert value["plan_id"] == "curdplan-cook-cli-normalize-1"
    assert value["objective"] == "Ship the approved behavior"
    assert cast(str, canonical["digest"]).startswith("sha256:")
    version = cast(dict[str, object], canonical["version"])
    assert version["major"] == "1"
    # Re-encoding must reproduce the same bytes: the CLI's stdout is already canonical.
    assert json.dumps(canonical, sort_keys=True, separators=(",", ":")) == captured.out.strip()


def test_validate_rejects_nonconforming_payload(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = commands.main(
        [
            "validate",
            str(FIXTURES / "nonconforming_writer_view.json"),
            "--schema",
            "agent-writer-view",
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "$.kind" in captured.err


def test_validate_accepts_conforming_payload(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = commands.main(
        [
            "validate",
            str(FIXTURES / "conforming_writer_view.json"),
            "--schema",
            "agent-writer-view",
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""


def test_validate_rejects_unknown_schema_slug(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = commands.main(
        [
            "validate",
            str(FIXTURES / "conforming_writer_view.json"),
            "--schema",
            "no-such-contract",
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "unknown schema slug" in captured.err




def test_validate_accepts_versioned_curd_plan_payload(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """normalize's own canonical output is a versioned CurdPlan carrying
    contract_version and digest; validate must accept it — the exact case the
    missing supported_version argument rejected, and the coherence contract
    between the two subcommands."""
    exit_code = commands.main(
        [
            "normalize",
            str(FIXTURES / "clean_writer_view.json"),
            "--invocation",
            str(FIXTURES / "clean_invocation.json"),
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 0, captured.err
    plan_value = cast(dict[str, object], json.loads(captured.out)["value"])
    assert cast(dict[str, object], plan_value["contract_version"])["major"] == "1"
    payload_path = tmp_path / "curd-plan.json"
    _ = payload_path.write_text(json.dumps(plan_value), encoding="utf-8")

    exit_code = commands.main(
        ["validate", str(payload_path), "--schema", "curd-plan"]
    )
    captured = capsys.readouterr()
    assert exit_code == 0, captured.err
    assert captured.err == ""
