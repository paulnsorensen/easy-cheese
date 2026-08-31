"""Unit coverage for the shared Mold-to-Cook publication gateway."""
from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest
from easy_cheese_schemas import ContractValidationError, PublishedArtifact

from easy_cheese.shared import publication

CURD_PLAN_SCHEMA_URI = "https://schemas.easy-cheese.dev/curd-plan"

DOC: dict[str, object] = {
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
    "plan_id": "curdplan-publication-gateway-1",
    "contract_version": {
        "schema_uri": CURD_PLAN_SCHEMA_URI,
        "major": "1",
        "minor": "0",
    },
}


def _publish(
    tmp_path: Path,
    *,
    raw_text: str,
    invocation: dict[str, object] = INVOCATION,
    operation_id: str = "op-1",
    _before_reveal: Callable[[], None] | None = None,
) -> PublishedArtifact:
    return publication.publish(
        raw_text,
        invocation,
        source_phase="mold",
        destination_phase="cook",
        payload_schema_uri=CURD_PLAN_SCHEMA_URI,
        operation_id=operation_id,
        artifact_root=tmp_path,
        _before_reveal=_before_reveal,
    )


def test_syntax_normalize_direct_parse_returns_no_actions() -> None:
    text, actions = publication.syntax_normalize(json.dumps(DOC))
    assert actions == ()
    assert json.loads(text) == DOC


def test_syntax_normalize_trim_whitespace_recovers() -> None:
    raw = " " + json.dumps(DOC) + " "
    text, actions = publication.syntax_normalize(raw)
    assert [a.action.value for a in actions] == ["trim_whitespace"]
    assert json.loads(text) == DOC


def test_syntax_normalize_normalize_quotes_recovers() -> None:
    raw = "{“a”: 1}"
    text, actions = publication.syntax_normalize(raw)
    assert [a.action.value for a in actions] == ["normalize_quotes"]
    assert json.loads(text) == {"a": 1}


def test_syntax_normalize_remove_trailing_comma_recovers() -> None:
    raw = '{"a": 1,}'
    text, actions = publication.syntax_normalize(raw)
    assert [a.action.value for a in actions] == ["remove_trailing_comma"]
    assert json.loads(text) == {"a": 1}


def test_select_repair_ambiguous_raises() -> None:
    """Trailing comma plus a curly-quoted string value: removing the comma alone
    parses (keeping the curly quotes as string content), and removing the comma
    while also normalizing quotes also parses, but to different text -- two
    distinct candidates, so `_select_repair` must reject rather than guess."""
    raw = '{"a": "‘x’",}'
    with pytest.raises(publication.AmbiguousSyntaxRepairError):
        _ = publication._select_repair(raw)  # pyright: ignore[reportPrivateUsage]


def test_select_repair_unrecoverable_raises() -> None:
    with pytest.raises(publication.UnrecoverableSyntaxError):
        _ = publication._select_repair("not json at all")  # pyright: ignore[reportPrivateUsage]


def test_publish_rejects_semantic_repair_of_wrong_enum_casing(tmp_path: Path) -> None:
    """Syntax repair never touches semantics: a syntactically valid but wrongly
    cased `kind` enum must still be rejected by the underlying semantics-strict
    normalizer, unweakened."""
    bad_doc = {**DOC, "kind": "CURD_PLAN"}
    with pytest.raises(ContractValidationError):
        _ = _publish(tmp_path, raw_text=json.dumps(bad_doc))


def test_publish_pointer_last_survives_crash_before_reveal(tmp_path: Path) -> None:
    def _boom() -> None:
        raise RuntimeError("simulated crash before pointer reveal")

    with pytest.raises(RuntimeError, match="simulated crash"):
        _ = _publish(
            tmp_path,
            raw_text=json.dumps(DOC),
            operation_id="op-crash",
            _before_reveal=_boom,
        )

    pointer_path = tmp_path / "pointers" / "op-crash.json"
    assert not pointer_path.exists()
    assert any((tmp_path / "payloads").glob("*.json"))

    artifact = _publish(tmp_path, raw_text=json.dumps(DOC), operation_id="op-crash")
    assert pointer_path.exists()
    assert artifact.pointer.operation_id == "op-crash"


def test_publish_is_idempotent_on_replay(tmp_path: Path) -> None:
    first = _publish(tmp_path, raw_text=json.dumps(DOC), operation_id="op-replay")
    second = _publish(tmp_path, raw_text=json.dumps(DOC), operation_id="op-replay")
    assert second.pointer == first.pointer
    assert second.canonical.value == first.canonical.value


def test_publish_rejects_conflicting_replay(tmp_path: Path) -> None:
    _ = _publish(tmp_path, raw_text=json.dumps(DOC), operation_id="op-conflict")
    doc_payload = cast("dict[str, object]", DOC["payload"])
    other_doc = {**DOC, "payload": {**doc_payload, "objective": "A different objective"}}
    with pytest.raises(publication.IdempotencyConflictError):
        _ = _publish(
            tmp_path, raw_text=json.dumps(other_doc), operation_id="op-conflict"
        )


def test_publish_receipt_only_when_syntax_actions_nonempty(tmp_path: Path) -> None:
    clean = _publish(tmp_path, raw_text=json.dumps(DOC), operation_id="op-clean")
    assert clean.normalization_receipt is None
    assert clean.pointer.normalization_receipt is None

    repaired_raw = " " + json.dumps(DOC) + " "
    repaired = _publish(
        tmp_path, raw_text=repaired_raw, operation_id="op-repaired"
    )
    assert repaired.normalization_receipt is not None
    assert repaired.pointer.normalization_receipt is not None
