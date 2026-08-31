"""Unit coverage for the shared Mold-to-Cook publication gateway."""
from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest
from easy_cheese_schemas import (
    ContractValidationError,
    PublishedArtifact,
    normalize_agent_output,
)

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
    # NBSP (U+00A0): json.loads rejects it as whitespace, str.strip removes it
    raw = chr(0xA0) + json.dumps(DOC) + chr(0xA0)
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


def test_select_repair_trailing_comma_with_curly_quote_string_content() -> None:
    """Trailing comma plus a curly-quoted string value: the curly quotes sit
    inside straight-quote-delimited string content, so quote normalization
    never touches them and only the trailing-comma repair applies -- a single
    unambiguous candidate that preserves the curly quotes as prose."""
    raw = '{"a": "‘x’",}'
    candidate, subset = publication._select_repair(raw)  # pyright: ignore[reportPrivateUsage]
    assert subset == (2,)
    assert json.loads(candidate) == {"a": "‘x’"}


def test_select_repair_unrecoverable_raises() -> None:
    with pytest.raises(publication.UnrecoverableSyntaxError):
        _ = publication._select_repair("not json at all")  # pyright: ignore[reportPrivateUsage]


def test_normalize_quotes_preserves_curly_quote_inside_string_content() -> None:
    """A curly apostrophe that is prose content of a straight-quoted string
    value must survive untouched -- only curly quotes outside string content
    are structural repair targets."""
    raw = '{"a": "it’s fine"}'
    text, actions = publication.syntax_normalize(raw)
    assert actions == ()
    assert json.loads(text) == {"a": "it’s fine"}


def test_remove_trailing_comma_preserves_comma_inside_string_content() -> None:
    """A comma immediately followed by a closing bracket character that is
    prose content of a string value must survive untouched -- only a trailing
    comma outside string content is a repair target."""
    raw = '{"a": "x, ]" ,}'
    text, actions = publication.syntax_normalize(raw)
    assert [a.action.value for a in actions] == ["remove_trailing_comma"]
    assert json.loads(text) == {"a": "x, ]"}


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


def test_publish_rejects_tampered_payload_on_replay(tmp_path: Path) -> None:
    """A replayed operation_id must revalidate that the persisted payload file
    still matches the digest recorded in the pointer -- a corrupted-but-
    schema-valid payload swapped in after the first publish must not be
    silently accepted as the original."""
    first = _publish(tmp_path, raw_text=json.dumps(DOC), operation_id="op-tamper")
    payload_path = publication._uri_to_path(  # pyright: ignore[reportPrivateUsage]
        first.pointer.payload.uri, tmp_path
    )
    tampered_doc = {
        **DOC,
        "payload": {**cast("dict[str, object]", DOC["payload"]), "objective": "Tampered"},
    }
    other_canonical = normalize_agent_output(json.dumps(tampered_doc), INVOCATION)
    _ = payload_path.write_bytes(other_canonical.canonical_bytes)
    with pytest.raises(publication.PayloadDigestMismatchError):
        _ = _publish(tmp_path, raw_text=json.dumps(DOC), operation_id="op-tamper")


def test_publish_race_same_request_rehydrates_identical_artifact(
    tmp_path: Path,
) -> None:
    """A racing reveal for the same operation_id with the same request must
    surface FileExistsError from _atomic_reveal and rehydrate the winner's
    PublishedArtifact rather than erroring or overwriting it."""
    winner_holder: list[PublishedArtifact] = []

    def _race_winner() -> None:
        winner_holder.append(
            _publish(tmp_path, raw_text=json.dumps(DOC), operation_id="op-race-same")
        )

    result = _publish(
        tmp_path,
        raw_text=json.dumps(DOC),
        operation_id="op-race-same",
        _before_reveal=_race_winner,
    )

    assert len(winner_holder) == 1
    winner = winner_holder[0]
    assert result.pointer == winner.pointer
    assert result.canonical.value == winner.canonical.value
    assert list((tmp_path / "pointers").glob(".*")) == []


def test_publish_race_conflicting_request_raises_idempotency_conflict(
    tmp_path: Path,
) -> None:
    """A racing reveal for the same operation_id with a different request must
    surface IdempotencyConflictError from the FileExistsError branch, not a
    bare FileExistsError, and must leave no temp residue in pointers/."""
    doc_payload = cast("dict[str, object]", DOC["payload"])
    other_doc = {**DOC, "payload": {**doc_payload, "objective": "A racing objective"}}

    def _race_conflict() -> None:
        _ = _publish(
            tmp_path, raw_text=json.dumps(other_doc), operation_id="op-race-conflict"
        )

    with pytest.raises(publication.IdempotencyConflictError):
        _ = _publish(
            tmp_path,
            raw_text=json.dumps(DOC),
            operation_id="op-race-conflict",
            _before_reveal=_race_conflict,
        )

    assert list((tmp_path / "pointers").glob(".*")) == []


def test_publish_receipt_only_when_syntax_actions_nonempty(tmp_path: Path) -> None:
    clean = _publish(tmp_path, raw_text=json.dumps(DOC), operation_id="op-clean")
    assert clean.normalization_receipt is None
    assert clean.pointer.normalization_receipt is None

    # NBSP (U+00A0): json.loads rejects it as whitespace, str.strip removes it
    repaired_raw = chr(0xA0) + json.dumps(DOC) + chr(0xA0)
    repaired = _publish(
        tmp_path, raw_text=repaired_raw, operation_id="op-repaired"
    )
    assert repaired.normalization_receipt is not None
    assert repaired.pointer.normalization_receipt is not None
