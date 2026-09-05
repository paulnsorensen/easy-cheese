"""Unit coverage for Cook's normalize and validate contract handlers.

These tests call the handlers in-process, so they cover the host-side error
grammar that the bundle integration tests in ``test_cook_contract_accept.py``
cannot reach without a rebuilt archive.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from easy_cheese_schemas import canonical_digest
from easy_cheese.skills.cook.contract_handlers import normalize_main, validate_main

CURD_PLAN_SCHEMA_URI = "https://schemas.easy-cheese.dev/curd-plan"

DOCUMENT: dict[str, object] = {
    "kind": "curd_plan",
    "payload": {
        "objective": "Ship the approved behavior",
        "curds": [
            {
                "key": "runtime",
                "outcome": "Implement strict validation",
                "scope": {"paths": ["src/runtime.py"]},
                "outputs": ["Validated contract"],
                "criteria": [
                    {
                        "description": "Unknown fields reject",
                        "check": "uv run pytest tests/test_runtime.py",
                    }
                ],
            }
        ],
    },
}

INVOCATION: dict[str, object] = {
    "plan_id": "curdplan-cook-handler-1",
    "contract_version": {
        "schema_uri": CURD_PLAN_SCHEMA_URI,
        "major": "1",
        "minor": "0",
    },
}


def _write(path: Path, payload: object) -> Path:
    _ = path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _normalize(
    tmp_path: Path, capsysbinary: pytest.CaptureFixture[bytes]
) -> tuple[int, dict[str, object]]:
    document = _write(tmp_path / "document.json", DOCUMENT)
    invocation = _write(tmp_path / "invocation.json", INVOCATION)
    code = normalize_main([str(document), "--invocation", str(invocation)])
    raw = capsysbinary.readouterr().out
    return code, cast(dict[str, object], json.loads(raw or b"{}"))


def test_normalize_emits_the_canonical_wrapper(
    tmp_path: Path, capsysbinary: pytest.CaptureFixture[bytes]
) -> None:
    code, wrapper = _normalize(tmp_path, capsysbinary)

    assert code == 0
    assert sorted(wrapper) == ["digest", "value", "version"]
    value = cast(dict[str, object], wrapper["value"])
    assert value["plan_id"] == INVOCATION["plan_id"]
    assert value["objective"] == "Ship the approved behavior"
    assert value["revision"] == 1
    curds = cast(list[dict[str, object]], value["curds"])
    assert [curd["curd_id"] for curd in curds] == [
        "curdplan-cook-handler-1/curd/1"
    ]
    criteria = cast(list[dict[str, object]], curds[0]["criteria"])
    assert [criterion["criterion_id"] for criterion in criteria] == [
        "curdplan-cook-handler-1/curd/1/criterion/1"
    ]
    version = cast(dict[str, object], wrapper["version"])
    assert version["schema_uri"] == CURD_PLAN_SCHEMA_URI


def test_normalize_digest_matches_the_canonical_value(
    tmp_path: Path, capsysbinary: pytest.CaptureFixture[bytes]
) -> None:
    """The bytes-derived digest equals the value-derived digest."""
    _, wrapper = _normalize(tmp_path, capsysbinary)

    assert wrapper["digest"] == canonical_digest(wrapper["value"])


def test_normalize_reports_an_invalid_utf8_document_as_a_contract_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    document = tmp_path / "document.json"
    _ = document.write_bytes(b'{"kind": "curd_plan", "payload": "\xff\xfe"}')
    invocation = _write(tmp_path / "invocation.json", INVOCATION)

    code = normalize_main([str(document), "--invocation", str(invocation)])

    assert code == 1
    err = capsys.readouterr().err
    assert err.startswith("ERROR:")
    assert "invalid JSON" in err


def test_normalize_reports_an_invalid_utf8_invocation_as_an_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    document = _write(tmp_path / "document.json", DOCUMENT)
    invocation = tmp_path / "invocation.json"
    _ = invocation.write_bytes(b'{"plan_id": "\xff\xfe"}')

    code = normalize_main([str(document), "--invocation", str(invocation)])

    assert code == 1
    assert capsys.readouterr().err.startswith("ERROR: invalid invocation JSON:")


def test_validate_reports_an_invalid_utf8_payload_as_a_contract_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    payload = tmp_path / "payload.json"
    _ = payload.write_bytes(b'{"contract_version": "\xff\xfe"}')

    code = validate_main([str(payload), "--schema", "curd-plan"])

    assert code == 1
    err = capsys.readouterr().err
    assert err.startswith("ERROR:")
    assert "invalid JSON" in err


def test_validate_accepts_the_normalized_plan(
    tmp_path: Path, capsysbinary: pytest.CaptureFixture[bytes]
) -> None:
    """The two verbs agree: normalize output passes validate unchanged."""
    _, wrapper = _normalize(tmp_path, capsysbinary)
    payload = _write(tmp_path / "payload.json", wrapper["value"])

    code = validate_main([str(payload), "--schema", "curd-plan"])

    assert code == 0
    assert "conforms to 'curd-plan'" in capsysbinary.readouterr().out.decode()
