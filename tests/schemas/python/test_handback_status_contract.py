"""Every handback producer and consumer speaks one status vocabulary.

The regression these lock down: before the vocabulary moved into
``easy_cheese_schemas.phase_contracts`` each seam carried its own grammar, so
``gated:`` -- a status ``/wheypoint`` derives and ``continue-resume.md``
documents -- was rejected by the shared preamble parser and read as "proceed"
by ``/ultracook``'s phase router, which spawned the next phase through a gate
that existed to stop it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from easy_cheese.shared import cli, handoff, handoff_cli, write_handoff_artifact
from easy_cheese.shared.fanout import phase_decision
from easy_cheese.skills.wheypoint import legacy

from easy_cheese_schemas.phase_contracts import (
    DISPOSITIONS,
    HANDBACK_STATUSES,
    PROCEED,
    REGISTERED_STATUSES,
    RETRY,
    STOP,
    StatusError,
    parse_status_field,
    render_status_field,
    status_disposition,
)

REASON = "a one-line reason"


def _field(name: str) -> str:
    return render_status_field(name, None if name == "ok" else REASON)


def _all_statuses() -> list[str]:
    return list(REGISTERED_STATUSES)


def test_vocabulary_pins_every_status_name_and_disposition() -> None:
    assert REGISTERED_STATUSES == (
        "ok",
        "ok-with-concerns",
        "needs-context",
        "gated",
        "halt",
    )
    assert {name: HANDBACK_STATUSES[name].disposition for name in HANDBACK_STATUSES} == {
        "ok": PROCEED,
        "ok-with-concerns": PROCEED,
        "needs-context": RETRY,
        "gated": STOP,
        "halt": STOP,
    }
    assert HANDBACK_STATUSES["ok"].requires_reason is False
    assert all(
        HANDBACK_STATUSES[name].requires_reason
        for name in REGISTERED_STATUSES
        if name != "ok"
    )
    assert set(DISPOSITIONS) == {PROCEED, RETRY, STOP}


@pytest.mark.parametrize("name", _all_statuses())
def test_status_field_round_trips_through_the_shared_grammar(name: str) -> None:
    field = _field(name)
    parsed = parse_status_field(field)
    assert parsed == (name, None if name == "ok" else REASON)
    assert render_status_field(*parsed) == field


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("DONE_WITH_CONCERNS: x", "status must be one of"),
        ("NEEDS_CONTEXT: x", "status must be one of"),
        ("okay", "status must be one of"),
        ("halt", "halt status requires a reason"),
        ("gated:   ", "gated status requires a reason"),
        ("ok: fine", "ok status takes no reason"),
    ],
)
def test_status_field_rejects_values_outside_the_vocabulary(
    value: str, message: str
) -> None:
    with pytest.raises(StatusError, match=message):
        _ = parse_status_field(value)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("  HALT", ("halt", None)),
        ("Halt: x", ("halt", "x")),
        (" gated ", ("gated", None)),
        ("Gated: a decision", ("gated", "a decision")),
        ("NEEDS-CONTEXT: more", ("needs-context", "more")),
        ("  OK  ", ("ok", None)),
    ],
)
def test_reader_tolerance_normalises_case_and_a_missing_reason(
    value: str, expected: tuple[str, str | None]
) -> None:
    """Readers of an already-emitted field route it; they never re-grade it.

    A status that arrived bare or shouted must still resolve to its declared
    disposition -- falling back to "proceed" is the exact mismatch this
    vocabulary exists to remove.
    """
    assert parse_status_field(value, require_reason=False) == expected


def test_reader_tolerance_never_widens_the_vocabulary() -> None:
    with pytest.raises(StatusError, match="status must be one of"):
        _ = parse_status_field("haltish: x", require_reason=False)
    with pytest.raises(StatusError, match="ok status takes no reason"):
        _ = parse_status_field("ok: fine", require_reason=False)


def test_render_rejects_a_reason_the_status_does_not_carry() -> None:
    with pytest.raises(StatusError, match="ok status takes no reason"):
        _ = render_status_field("ok", REASON)
    with pytest.raises(StatusError, match="halt status requires a reason"):
        _ = render_status_field("halt", None)
    with pytest.raises(StatusError, match="status must be one of"):
        _ = status_disposition("unknown")


@pytest.mark.parametrize("name", _all_statuses())
def test_preamble_parser_accepts_every_status_a_producer_may_render(name: str) -> None:
    slug = handoff.HandoffSlug(
        status=name,
        halt_reason=None if name == "ok" else REASON,
        next_skill="age",
        artifact=None,
        orientation="did the work",
    )
    rendered = handoff.render_handoff_slug(slug)
    assert rendered.splitlines()[0] == f"status: {_field(name)}"

    parsed = handoff.parse_handoff_slug(rendered + "\n")
    assert parsed == slug
    assert parsed.disposition == HANDBACK_STATUSES[name].disposition


def test_preamble_parser_reports_the_full_vocabulary_on_a_bad_status() -> None:
    with pytest.raises(handoff.HandoffParseError, match="status must be one of"):
        _ = handoff.parse_handoff_slug(
            "status: NEEDS_CONTEXT\nnext: age\nartifact: \norientation\n"
        )


@pytest.mark.parametrize("name", _all_statuses())
def test_handoff_cli_render_accepts_every_registered_status(
    name: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert (
        handoff_cli.main(
            [
                "render",
                "--status",
                _field(name),
                "--next",
                "age",
                "--orientation",
                "did the work",
            ]
        )
        == 0
    )
    assert capsys.readouterr().out.splitlines()[0] == f"status: {_field(name)}"


def test_handoff_cli_parse_publishes_the_disposition(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    artifact = tmp_path / "note.md"
    _ = artifact.write_text(
        f"status: gated: {REASON}\nnext: cook\nartifact: \nblocked on a decision\n",
        encoding="utf-8",
    )

    assert handoff_cli.main(["parse", "--file", str(artifact)]) == 0
    payload = cast("dict[str, object]", json.loads(capsys.readouterr().out))
    assert payload["status"] == "gated"
    assert payload["halt_reason"] == REASON
    assert payload["disposition"] == STOP


@pytest.mark.parametrize("name", _all_statuses())
def test_artifact_writer_accepts_every_registered_status(
    name: str, tmp_path: Path
) -> None:
    target = write_handoff_artifact.write_artifact(
        slug="demo",
        status=_field(name),
        next_skill="age",
        artifact="",
        orientation="cook completed its curds",
        body=None,
        root=tmp_path,
        phase="cook",
    )

    assert target.read_text(encoding="utf-8").splitlines()[0] == f"status: {_field(name)}"


def test_artifact_writer_rejects_an_unknown_status_before_creating_directories(
    tmp_path: Path,
) -> None:
    with pytest.raises(cli.CliError, match="status must be one of"):
        _ = write_handoff_artifact.write_artifact(
            slug="demo",
            status="DONE_WITH_CONCERNS",
            next_skill="age",
            artifact="",
            orientation="must not be written",
            body=None,
            root=tmp_path,
            phase="cook",
        )

    assert not (tmp_path / ".cheese").exists()


@pytest.mark.parametrize(
    ("status", "action", "next_phase"),
    [
        ("ok", "spawn", "press"),
        (f"ok-with-concerns: {REASON}", "spawn", "press"),
        (f"needs-context: {REASON}", "needs_context", "cook"),
        (f"gated: {REASON}", "halt", None),
        (f"halt: {REASON}", "halt", None),
    ],
)
def test_phase_router_routes_each_status_by_its_declared_disposition(
    status: str, action: str, next_phase: str | None
) -> None:
    verdict = phase_decision.decide(0, status)

    assert verdict["action"] == action
    assert verdict["next_phase"] == next_phase


def test_phase_router_rejects_a_status_outside_the_vocabulary() -> None:
    with pytest.raises(cli.CliError, match="status must be one of"):
        _ = phase_decision.decide(0, "haltish")


def test_legacy_reader_never_accepts_a_status_the_runtime_cannot_route() -> None:
    for name in REGISTERED_STATUSES:
        decoded, reason = legacy._parse_legacy_status(_field(name))  # pyright: ignore[reportPrivateUsage]
        assert decoded == name
        assert reason == (None if name == "ok" else REASON)
        assert status_disposition(decoded) in DISPOSITIONS

    with pytest.raises(legacy.LegacyDecodeError, match="status must be one of"):
        _ = legacy._parse_legacy_status("gated-ish: x")  # pyright: ignore[reportPrivateUsage]


def test_legacy_reader_keeps_its_bare_reason_optional_tolerance() -> None:
    assert legacy._parse_legacy_status("halt") == ("halt", None)  # pyright: ignore[reportPrivateUsage]
    assert legacy._parse_legacy_status("gated") == ("gated", None)  # pyright: ignore[reportPrivateUsage]


def test_needs_context_re_dispatches_the_same_phase_with_its_reason() -> None:
    """`needs-context` is a request for more input, not a failure.

    The phase index does not advance and the exit message carries the worker's
    stated gap, so the orchestrator re-dispatches the identical phase with the
    missing context rather than halting the run or walking past the shortfall.
    """
    verdict = phase_decision.decide(1, f"needs-context: {REASON}")

    assert verdict["action"] == "needs_context"
    assert verdict["next_phase"] == "press"
    assert REASON in verdict["exit_message"]
    assert "re-dispatch the same phase" in verdict["exit_message"]


def test_ok_with_concerns_proceeds_but_keeps_its_reason_on_the_wire() -> None:
    """A proceed status that still has something to say must not lose it."""
    slug = handoff.parse_handoff_slug(
        f"status: ok-with-concerns: {REASON}\nnext: age\nartifact: \ndid the work\n"
    )

    assert slug.status == "ok-with-concerns"
    assert slug.halt_reason == REASON
    assert slug.disposition == PROCEED
