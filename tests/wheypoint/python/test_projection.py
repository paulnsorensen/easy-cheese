"""Canonical projection Markdown: render, parse, derive, and pin.

A projection is generated, so it round-trips exactly; it is also the file a
human may edit, so parsing derives status from the gating entries and ignores
whatever the document claims, and the digest covers every other byte.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from attrs import evolve
from easy_cheese_schemas import (
    Durability,
    NextAction,
    NextMove,
    WheypointProjection,
    WheypointStatus,
)

import projection
import records

SRC = Path(__file__).resolve().parents[3] / "src" / "wheypoint"


def test_a_built_projection_derives_everything_from_the_record(
    make_record: Any,
) -> None:
    record = make_record()
    built, markdown = projection.build_projection(
        record, durability=Durability.CANONICAL_LOCAL
    )

    assert built.work_id == record.work_id
    assert built.revision_id == record.revision_id
    assert built.schema_version == record.schema_version
    assert built.record_digest == records.record_digest(record)
    assert built.next_action == record.next_action
    assert built.gating_entry_ids == []
    assert built.status is WheypointStatus.OK
    assert built.projection_digest == projection.projection_digest_of_text(markdown)


def test_the_rendered_preamble_carries_the_whole_contract(make_record: Any) -> None:
    record = make_record()
    built, markdown = projection.build_projection(
        record, durability=Durability.REPO_SNAPSHOT
    )
    preamble = markdown.splitlines()[:10]

    assert preamble == [
        "status: ok",
        "next: cook",
        "artifact: .cheese/cook/wheypoint-record-store-projection.md",
        "work_id: work-0001",
        "revision_id: rev-0001",
        f"record_digest: {built.record_digest}",
        f"projection_digest: {built.projection_digest}",
        "durability: repo-snapshot",
        f"schema_version: {record.schema_version}",
        "Implement the canonical record runtime.",
    ]


def test_an_active_gate_derives_gated_and_shows_its_dossier(
    make_record: Any,
) -> None:
    built, markdown = projection.build_projection(
        make_record(gating=True), durability=Durability.CANONICAL_LOCAL
    )
    assert built.status is WheypointStatus.GATED
    assert built.gating_entry_ids == ["q-durability"]
    assert markdown.splitlines()[0] == "status: gated"
    assert "- q-durability" in markdown
    assert "Durability default" in markdown


@pytest.mark.parametrize("gating", [False, True])
def test_render_and_parse_round_trip_exactly(make_record: Any, gating: bool) -> None:
    built, markdown = projection.build_projection(
        make_record(gating=gating), durability=Durability.PUBLISHED
    )
    assert projection.render(built) == markdown
    assert projection.parse(markdown) == built


@pytest.mark.parametrize("durability", list(Durability))
def test_every_durability_level_round_trips(
    make_record: Any, durability: Durability
) -> None:
    built, markdown = projection.build_projection(
        make_record(), durability=durability
    )
    assert projection.parse(markdown).durability is durability


def test_a_next_action_without_an_artifact_round_trips(make_record: Any) -> None:
    record = make_record(
        next_action=NextAction(move=NextMove.DONE, orientation="nothing left")
    )
    built, markdown = projection.build_projection(
        record, durability=Durability.CANONICAL_LOCAL
    )
    assert "artifact: \n" in markdown
    assert projection.parse(markdown).next_action.artifact is None
    assert projection.parse(markdown) == built


def test_a_hand_written_ok_over_an_open_gate_is_not_believed(
    make_record: Any,
) -> None:
    _, markdown = projection.build_projection(
        make_record(gating=True), durability=Durability.CANONICAL_LOCAL
    )
    forged = markdown.replace("status: gated", "status: ok", 1)

    parsed = projection.parse(forged)
    assert parsed.gating_entry_ids == ["q-durability"]
    assert parsed.status is WheypointStatus.GATED


def test_the_status_line_is_not_part_of_the_projections_identity(
    make_record: Any,
) -> None:
    built, markdown = projection.build_projection(
        make_record(gating=True), durability=Durability.CANONICAL_LOCAL
    )
    forged = markdown.replace("status: gated", "status: ok", 1)
    # Rewriting the derived line is still tampering with the artifact.
    assert projection.projection_digest_of_text(forged) != built.projection_digest


def test_editing_the_body_breaks_the_digest(make_record: Any) -> None:
    built, markdown = projection.build_projection(
        make_record(), durability=Durability.CANONICAL_LOCAL
    )
    edited = markdown.replace(
        "Implement the canonical record runtime.", "Ship it, whatever"
    )
    assert projection.projection_digest_of_text(edited) != built.projection_digest
    assert projection.projection_digest_of_text(markdown) == built.projection_digest


def test_rewriting_only_the_digest_line_does_not_launder_the_document(
    make_record: Any,
) -> None:
    built, markdown = projection.build_projection(
        make_record(), durability=Durability.CANONICAL_LOCAL
    )
    edited = markdown.replace("Wave 2 owns", "Wave 9 owns")
    laundered = edited.replace(
        f"projection_digest: {built.projection_digest}",
        f"projection_digest: {projection.projection_digest_of_text(edited)}",
    )
    parsed = projection.parse(laundered)
    assert parsed.projection_digest == projection.projection_digest_of_text(laundered)
    # ...but the record digest it quotes no longer matches the tampered record,
    # which is what a reader validates against.
    assert parsed.record_digest == built.record_digest


@pytest.mark.parametrize(
    "broken",
    [
        "status: ok\n",
        "next:cook",
        "durability: eventually-maybe",
        "record_digest: not-a-digest",
        "next: teleport",
    ],
)
def test_a_malformed_document_is_a_parse_error_not_a_guess(
    make_record: Any, broken: str
) -> None:
    _, markdown = projection.build_projection(
        make_record(), durability=Durability.CANONICAL_LOCAL
    )
    if broken == "status: ok\n":
        damaged = markdown.replace("status: ok\n", "", 1)
    else:
        key = broken.split(":")[0]
        damaged = "\n".join(
            broken if line.startswith(f"{key}:") else line
            for line in markdown.splitlines()
        )
    with pytest.raises(projection.ProjectionParseError):
        projection.parse(damaged)


def test_a_truncated_document_is_a_parse_error(make_record: Any) -> None:
    _, markdown = projection.build_projection(
        make_record(), durability=Durability.CANONICAL_LOCAL
    )
    with pytest.raises(projection.ProjectionParseError):
        projection.parse("\n".join(markdown.splitlines()[:5]))


def test_a_gated_projection_without_a_dossier_is_rejected(make_record: Any) -> None:
    built, _ = projection.build_projection(
        make_record(gating=True), durability=Durability.CANONICAL_LOCAL
    )
    with pytest.raises(ValueError, match="decision_dossier"):
        evolve(built, decision_dossier=[])


def test_a_caller_cannot_hand_build_an_ok_projection_over_a_gate(
    make_record: Any,
) -> None:
    built, _ = projection.build_projection(
        make_record(gating=True), durability=Durability.CANONICAL_LOCAL
    )
    assert isinstance(built, WheypointProjection)
    # There is no status field to set; the only lever is the gating list, and
    # emptying it makes the document say something different, not something
    # false about the same document.
    assert not hasattr(built, "_status")
    assert "status" not in records.unstructure(built)


def test_the_runtime_never_reaches_for_git() -> None:
    sources = sorted(SRC.glob("*.py"))
    assert [path.name for path in sources] == [
        "canonical.py",
        "projection.py",
        "records.py",
        "storage.py",
    ]
    for path in sources:
        text = path.read_text(encoding="utf-8")
        assert "subprocess" not in text, path.name
        assert "git " not in text.replace("# ", ""), path.name