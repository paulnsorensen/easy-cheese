"""The projection is a handoff: the shared parser must read every state.

Cheese and every other consumer read a Wheypoint note through
`parse_handoff_slug()`. These tests hold the generated document against that
grammar for each derived status and for each `next:` move the schema declares.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from attrs import evolve
from easy_cheese_schemas import (
    Durability,
    NextAction,
    NextMove,
    WheypointRecord,
    WheypointStatus,
)
from easy_cheese_schemas.handback_status import MAX_REASON_LENGTH, status_disposition

from easy_cheese.shared.handoff import parse_handoff_slug
from easy_cheese.skills.wheypoint import projection


def test_an_ok_projection_parses_as_a_shared_handoff(
    make_record: Callable[..., WheypointRecord],
) -> None:
    record = make_record()
    built, markdown = projection.build_projection(
        record, durability=Durability.CANONICAL_LOCAL
    )

    slug = parse_handoff_slug(markdown)

    assert built.status is WheypointStatus.OK
    assert slug.status == "ok"
    assert slug.reason is None
    assert slug.disposition == "proceed"
    assert slug.next_skill == record.next_action.move.value
    assert slug.artifact == record.next_action.artifact
    assert slug.orientation == record.next_action.orientation.splitlines()[0]


def test_a_gated_projection_carries_the_reason_the_grammar_requires(
    make_record: Callable[..., WheypointRecord],
) -> None:
    built, markdown = projection.build_projection(
        make_record(gating=True), durability=Durability.CANONICAL_LOCAL
    )

    slug = parse_handoff_slug(markdown)

    assert built.status is WheypointStatus.GATED
    assert slug.status == "gated"
    assert slug.reason == "1 open gating entry: q-durability"
    assert slug.disposition == "stop"


@pytest.mark.parametrize("move", list(NextMove))
def test_every_declared_move_survives_the_shared_parser(
    make_record: Callable[..., WheypointRecord], move: NextMove
) -> None:
    """`cut` is in the schema vocabulary, so it must reach a consumer too."""
    record = make_record()
    action = evolve(record.next_action, move=move)
    _, markdown = projection.build_projection(
        evolve(record, next_action=action), durability=Durability.CANONICAL_LOCAL
    )

    assert parse_handoff_slug(markdown).next_skill == move.value


def test_a_projection_without_an_artifact_parses_as_a_shared_handoff(
    make_record: Callable[..., WheypointRecord],
) -> None:
    record = make_record()
    action = NextAction(move=NextMove.HOLD, orientation="Waiting on the gate.")
    _, markdown = projection.build_projection(
        evolve(record, next_action=action), durability=Durability.CANONICAL_LOCAL
    )

    slug = parse_handoff_slug(markdown)

    assert slug.artifact is None
    assert slug.orientation == "Waiting on the gate."


def test_the_wheypoint_pins_stay_out_of_the_shared_preamble(
    make_record: Callable[..., WheypointRecord],
) -> None:
    """The pins live in the body, so the shared optional keys stay unclaimed."""
    _, markdown = projection.build_projection(
        make_record(), durability=Durability.REPO_SNAPSHOT
    )

    slug = parse_handoff_slug(markdown)

    assert slug.taste_test is None
    assert slug.durable_flags is None
    assert slug.baseline is None
    assert "work_id: work-0001" in markdown


def test_a_long_gate_list_still_fits_the_reason_limit() -> None:
    ids = [f"q-{index:04d}" for index in range(200)]

    reason = projection.gated_reason(ids)

    assert len(reason) <= MAX_REASON_LENGTH
    assert reason.startswith("200 open gating entries: q-0000")
    assert status_disposition("gated") == "stop"
