"""Canonical JSON, SHA-256 digests, and the record digests built on them.

The digests are the whole integrity story: if two structurally identical
payloads can hash differently, or a tampered field can hash the same, every
later validation is decoration. These tests pin exact bytes and exact hashes
rather than "a digest was produced".
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from typing import Protocol, cast

import attrs
import pytest
from attrs import evolve
from easy_cheese_schemas import (
    EntryKind,
    NextAction,
    NextMove,
    ProposedEntry,
    WheypointDelta,
    WheypointRecord,
    WheypointRevision,
)

from easy_cheese.skills.wheypoint import canonical, records


class _HasRevision(Protocol):
    revision: WheypointRevision


EMPTY_SHA256 = "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def test_object_keys_are_sorted_and_separators_are_compact() -> None:
    payload = {"b": 1, "a": {"d": 2, "c": [3, {"f": 4, "e": 5}]}}
    assert canonical.canonical_bytes(payload) == (
        b'{"a":{"c":[3,{"e":5,"f":4}],"d":2},"b":1}'
    )


def test_text_is_utf8_rather_than_escaped_ascii() -> None:
    assert canonical.canonical_bytes({"k": "café \U0001f9c0"}) == (
        '{"k":"café \U0001f9c0"}'.encode()
    )


@pytest.mark.parametrize(
    ("value", "where"),
    [
        ({"a": float("nan")}, "value.a"),
        ({"a": [1.0, float("inf")]}, "value.a[1]"),
        ({"a": {"b": float("-inf")}}, "value.a.b"),
    ],
)
def test_non_finite_numbers_are_rejected_with_their_location(
    value: dict[str, object], where: str
) -> None:
    with pytest.raises(canonical.CanonicalJsonError) as excinfo:
        _ = canonical.canonical_bytes(value)
    assert where in str(excinfo.value)
    assert "finite" in str(excinfo.value)


def test_finite_floats_are_accepted() -> None:
    assert canonical.canonical_bytes({"a": 1.5}) == b'{"a":1.5}'


def test_non_string_keys_are_rejected_rather_than_coerced() -> None:
    with pytest.raises(canonical.CanonicalJsonError) as excinfo:
        _ = canonical.canonical_bytes({1: "one"})
    assert "keys must be strings" in str(excinfo.value)


def test_non_json_values_are_rejected() -> None:
    with pytest.raises(canonical.CanonicalJsonError) as excinfo:
        _ = canonical.canonical_bytes({"a": {1, 2}})
    assert "value.a is not JSON data: set" in str(excinfo.value)


def test_digest_of_empty_payload_is_the_known_sha256() -> None:
    assert canonical.digest_bytes(b"") == EMPTY_SHA256


def test_digest_text_hashes_the_utf8_encoding() -> None:
    expected = hashlib.sha256("café".encode()).hexdigest()
    assert canonical.digest_text("café") == f"sha256:{expected}"


def test_digest_value_is_independent_of_key_order() -> None:
    assert canonical.digest_value({"a": 1, "b": 2}) == canonical.digest_value(
        {"b": 2, "a": 1}
    )


def test_digest_value_hashes_the_canonical_bytes() -> None:
    payload = {"b": [1, 2], "a": "x"}
    assert canonical.digest_value(payload) == canonical.digest_bytes(
        canonical.canonical_bytes(payload)
    )


def test_unstructure_round_trips_through_structure(
    make_record: Callable[..., WheypointRecord],
) -> None:
    record = make_record(gating=True)
    payload = records.unstructure(record)
    next_action = cast(dict[str, object], payload["next_action"])
    assert next_action["move"] == "cook"
    assert records.structure(payload, WheypointRecord) == record


def test_structure_reports_the_offending_field_instead_of_returning_junk() -> None:
    payload = records.unstructure(WheypointDelta(work_id="w", expected_revision_id="r"))
    payload["work_id"] = "NOT AN ID"
    with pytest.raises(records.RecordError) as excinfo:
        _ = records.structure(payload, WheypointDelta)
    assert "work_id" in str(excinfo.value)


def test_structure_rejects_a_payload_that_is_not_a_mapping() -> None:
    with pytest.raises(records.RecordError):
        _ = records.structure(["not", "a", "mapping"], WheypointRecord)


def test_record_digest_ignores_the_pointer_at_its_own_receipt(
    make_record: Callable[..., WheypointRecord],
) -> None:
    record = make_record()
    moved = evolve(record, revision_digest="sha256:" + "9" * 64)
    assert records.record_digest(moved) == records.record_digest(record)


def test_record_digest_covers_every_other_field(
    make_record: Callable[..., WheypointRecord],
) -> None:
    record = make_record()
    assert records.record_digest(evolve(record, orientation="tampered")) != (
        records.record_digest(record)
    )
    assert records.record_digest(evolve(record, revision_number=2)) != (
        records.record_digest(record)
    )


def test_record_digest_covers_protected_entries(
    make_record: Callable[..., WheypointRecord],
) -> None:
    plain = make_record()
    gated = make_record(gating=True)
    assert records.record_digest(plain) != records.record_digest(gated)


def test_revision_digest_covers_every_field(
    make_promotion: Callable[..., _HasRevision],
) -> None:
    revision: WheypointRevision = make_promotion().revision
    assert records.revision_digest(revision) != records.revision_digest(
        evolve(revision, preserved_entry_ids=["d-one"])
    )


def test_request_fingerprint_separates_omission_from_explicit_empty() -> None:
    omitted = WheypointDelta(work_id="work-0001", expected_revision_id="rev-0001")
    emptied = WheypointDelta(
        work_id="work-0001", expected_revision_id="rev-0001", working_context=[]
    )
    assert records.request_fingerprint(omitted) != records.request_fingerprint(emptied)


def test_request_fingerprint_is_stable_for_an_identical_replay() -> None:
    def build() -> WheypointDelta:
        return WheypointDelta(
            work_id="work-0001",
            expected_revision_id="rev-0001",
            orientation="same request",
            next_action=NextAction(move=NextMove.PRESS, orientation="harden"),
            add_questions=[ProposedEntry(kind=EntryKind.QUESTION, summary="why?")],
        )

    assert records.request_fingerprint(build()) == records.request_fingerprint(build())


def test_canonical_payload_of_a_record_is_sorted_utf8_json(
    make_record: Callable[..., WheypointRecord],
) -> None:
    payload = records.canonical_payload(make_record())
    assert payload.startswith(b'{"artifact_links":[],"blockers":[],"created":')
    assert payload.endswith(b'"working_context":["src/wheypoint/storage.py"]}')


def test_v3_fields_at_their_default_leave_v2_canonical_bytes_untouched(
    make_record: Callable[..., WheypointRecord],
) -> None:
    """ADR wheypoint-ergonomics-004: additive v3 fields are omitted at default."""
    record = make_record()
    payload = records.unstructure(record)
    assert "notes" not in payload and "directives" not in payload
    next_action = cast(dict[str, object], payload["next_action"])
    assert "tasks" not in next_action and "parallel" not in next_action
    for entry in cast(list[dict[str, object]], payload["decisions"]):
        assert "quote" not in entry
    # A v2-shaped payload structures back and re-serializes byte-identically.
    reloaded = records.structure(payload, WheypointRecord)
    assert records.canonical_payload(reloaded) == records.canonical_payload(record)
    assert records.record_digest(reloaded) == records.record_digest(record)
    # Setting a v3 field changes the bytes; clearing it restores them.
    with_notes = evolve(record, notes="body")
    assert "notes" in records.unstructure(with_notes)
    assert records.canonical_payload(evolve(with_notes, notes=None)) == records.canonical_payload(record)

def test_a_since3_dict_factory_field_is_omitted_only_while_empty() -> None:
    """A future field declared with `factory=dict` follows the same rule as
    `factory=list`: omitted at its declared-empty default, kept once set."""

    @attrs.define(frozen=True)
    class _WithDictFactory:
        payload: dict[str, int] = attrs.field(factory=dict, metadata={"since": 3})

    assert records.unstructure(_WithDictFactory()) == {}
    assert records.unstructure(_WithDictFactory(payload={"a": 1})) == {"payload": {"a": 1}}


def test_ac17_the_v3_golden_record_pins_canonical_bytes_and_digests() -> None:
    import json
    from pathlib import Path

    from easy_cheese_schemas import SCHEMA_VERSION, WheypointRevision

    fixtures = Path(__file__).resolve().parents[1] / "fixtures"
    raw = (fixtures / "golden-record-v3.json").read_bytes()
    pins = cast(dict[str, object], json.loads((fixtures / "golden-record-v3.pins.json").read_text(encoding="utf-8")))
    record = records.structure(cast(object, json.loads(raw)), WheypointRecord)
    revision = records.structure(
        cast(object, json.loads((fixtures / "golden-revision-v3.json").read_bytes())), WheypointRevision
    )
    bump = (
        f"canonical bytes changed for schema_version {SCHEMA_VERSION}: bump SCHEMA_VERSION "
        + f"to {SCHEMA_VERSION + 1}, regenerate the golden, and mark the new fields metadata={{'since': N}}"
    )
    assert pins["schema_version"] == SCHEMA_VERSION, bump
    assert records.canonical_payload(record) == raw, bump
    assert records.record_digest(record) == pins["record_digest"], bump
    assert records.revision_digest(revision) == pins["revision_digest"], bump
    mutated = raw.replace(b"Golden v3 record.", b"Golden v3 record!")
    assert records.record_digest(records.structure(cast(object, json.loads(mutated)), WheypointRecord)) != pins["record_digest"]
