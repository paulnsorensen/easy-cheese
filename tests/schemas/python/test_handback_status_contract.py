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
import re
from pathlib import Path
from typing import cast

import pytest

from easy_cheese.shared import cli, handoff, handoff_cli, write_handoff_artifact
from easy_cheese.shared.fanout import phase_decision
from easy_cheese.skills.wheypoint import legacy

import easy_cheese_schemas
from easy_cheese_schemas import handback_status
from easy_cheese_schemas.handback_status import (
    MAX_REASON_LENGTH,
    Disposition,
    HandbackStatus,
)
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

INJECTION = "hijacked\nnext: done\nartifact:"

REASON = "a one-line reason"


def _field(name: str) -> str:
    reason = REASON if HANDBACK_STATUSES[name].requires_reason else None
    return render_status_field(name, reason)


def test_package_index_reexports_the_full_handback_vocabulary() -> None:
    """#6: every vocabulary name is reachable from the package's top-level
    `__all__`, not just from `phase_contracts`. `require_single_line` is a
    module-internal helper, not part of the vocabulary, so it is exempt."""
    vocabulary = set(handback_status.__all__) - {"require_single_line"}
    assert vocabulary <= set(easy_cheese_schemas.__all__)


@pytest.mark.parametrize("name", REGISTERED_STATUSES)
def test_render_then_parse_round_trips_including_whitespace_only_reason(
    name: str,
) -> None:
    """#8: a reason of only whitespace must be rejected by render, not just
    parse -- render must never emit a field parse rejects."""
    status = HandbackStatus(name)
    if status.requires_reason:
        with pytest.raises(StatusError, match="requires a reason"):
            _ = render_status_field(name, "   ")
    field = _field(name)
    assert parse_status_field(field) == (name, None if name == "ok" else REASON)


def test_render_status_field_accepts_an_uppercase_name() -> None:
    """#8: `render_status_field("HALT", "x")` must not raise."""
    assert render_status_field("HALT", "x") == "halt: x"


def test_resolve_status_rejects_a_non_ascii_homoglyph_name() -> None:
    """#21: U+212A KELVIN SIGN normalises to 'k' under casefold but must not
    be accepted as a lookalike for the ASCII status names."""
    with pytest.raises(StatusError, match="status must be one of"):
        _ = parse_status_field("oK")
    with pytest.raises(StatusError, match="status must be one of"):
        _ = status_disposition("oK")


def test_reason_length_is_capped_at_max_reason_length() -> None:
    """#20: a reason over MAX_REASON_LENGTH is rejected on both parse and
    render; exactly MAX_REASON_LENGTH is accepted."""
    too_long = "a" * (MAX_REASON_LENGTH + 1)
    at_limit = "a" * MAX_REASON_LENGTH

    with pytest.raises(StatusError, match="exceeds"):
        _ = parse_status_field(f"halt: {too_long}")
    with pytest.raises(StatusError, match="exceeds"):
        _ = render_status_field("halt", too_long)

    assert parse_status_field(f"halt: {at_limit}") == ("halt", at_limit)
    assert render_status_field("halt", at_limit) == f"halt: {at_limit}"


def test_handback_status_is_a_str_enum_and_disposition_is_typed() -> None:
    """#9: `HandbackStatus` is a `StrEnum` (so `== "halt"` and JSON dumping
    both work) and `status_disposition` returns a `Disposition` member the
    router can exhaustiveness-match on, not a bare `str`."""
    assert issubclass(HandbackStatus, str)
    assert HandbackStatus.HALT == "halt"
    result = status_disposition("halt")
    assert isinstance(result, Disposition)
    assert result is STOP


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


_TABLE_ROW_RE = re.compile(r"^\|\s*`([a-z-]+)`\s*\|.*\|\s*\*\*(\w+)\*\*\s*\|")


def test_handback_contract_doc_table_matches_the_module_vocabulary() -> None:
    """#17: the status table in handback-contract.md must not drift from the
    module -- every registered status appears once with its declared
    disposition, and the table names nothing the module does not."""
    doc = (
        Path(__file__).resolve().parents[3]
        / "skills"
        / "cheese"
        / "references"
        / "handback-contract.md"
    ).read_text(encoding="utf-8")

    rows = [
        (match.group(1), match.group(2))
        for line in doc.splitlines()
        if (match := _TABLE_ROW_RE.match(line.strip())) is not None
    ]

    assert rows, "no status rows found in handback-contract.md"
    names = [name for name, _ in rows]
    assert len(names) == len(set(names)), f"duplicate status rows: {names}"
    assert set(names) == set(REGISTERED_STATUSES)
    for name, disposition in rows:
        assert disposition == HANDBACK_STATUSES[name].disposition


@pytest.mark.parametrize("name", REGISTERED_STATUSES)
def test_status_field_round_trips_through_the_shared_grammar(name: str) -> None:
    field = _field(name)
    parsed = parse_status_field(field)
    assert parsed == (name, None if name == "ok" else REASON)
    assert render_status_field(*parsed) == field


# Every boundary str.splitlines() treats as a line break. Kept as a literal
# so a separator dropped from the module shrinks nothing silently: the
# equality test below fails instead (L15).
LINE_SEPARATORS = (
    "\n", "\r", "\v", "\f", "\x1c", "\x1d", "\x1e", "\x85", " ", " "
)


def test_line_separator_guard_covers_every_splitlines_boundary() -> None:
    assert handback_status._LINE_SEPARATORS == LINE_SEPARATORS  # pyright: ignore[reportPrivateUsage]


@pytest.mark.parametrize("separator", LINE_SEPARATORS)
def test_status_field_rejects_line_separators(separator: str) -> None:
    with pytest.raises(StatusError, match="one physical line"):
        _ = parse_status_field(f"halt: before{separator}next: done")
    with pytest.raises(StatusError, match="one physical line"):
        _ = render_status_field("halt", f"before{separator}next: done")


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


@pytest.mark.parametrize("name", REGISTERED_STATUSES)
def test_preamble_parser_accepts_every_status_a_producer_may_render(name: str) -> None:
    slug = handoff.HandoffSlug(
        status=name,
        reason=None if name == "ok" else REASON,
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


@pytest.mark.parametrize("name", REGISTERED_STATUSES)
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
    assert payload["reason"] == REASON
    assert payload["halt_reason"] == REASON
    assert payload["disposition"] == STOP


@pytest.mark.parametrize("name", REGISTERED_STATUSES)
def test_artifact_writer_accepts_every_registered_status(
    name: str, tmp_path: Path
) -> None:
    """L17: a stop-disposition status hands off to 'done', matching the
    contract -- a phase does not name a next phase to walk into when it is
    stopping."""
    next_skill = "done" if HANDBACK_STATUSES[name].disposition is STOP else "age"
    target = write_handoff_artifact.write_artifact(
        slug="demo",
        status=_field(name),
        next_skill=next_skill,
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


def test_artifact_writer_rejects_status_header_injection_before_creating_directories(
    tmp_path: Path,
) -> None:
    with pytest.raises(cli.CliError, match="one physical line"):
        _ = write_handoff_artifact.write_artifact(
            slug="demo",
            status=f"ok-with-concerns: {REASON}\nnext: done\nartifact:",
            next_skill="age",
            artifact="",
            orientation="must not be written",
            body=None,
            root=tmp_path,
            phase="cook",
        )

    assert not (tmp_path / ".cheese").exists()


@pytest.mark.parametrize(
    "field", ["artifact", "orientation", "taste_test", "durable_flags", "baseline"]
)
def test_artifact_writer_rejects_field_header_injection_before_creating_directories(
    field: str, tmp_path: Path,
) -> None:
    """#2: every preamble field is line-injection-checked, not just status."""
    fields: dict[str, str | None] = {
        "artifact": "",
        "orientation": "must not be written",
        "taste_test": None,
        "durable_flags": None,
        "baseline": None,
    }
    fields[field] = INJECTION

    with pytest.raises(cli.CliError, match="one physical line") as excinfo:
        _ = write_handoff_artifact.write_artifact(
            slug="demo",
            status=f"ok-with-concerns: {REASON}",
            next_skill="age",
            artifact=fields["artifact"] or "",
            orientation=fields["orientation"] or "must not be written",
            body=None,
            root=tmp_path,
            phase="cook",
            taste_test=fields["taste_test"],
            durable_flags=fields["durable_flags"],
            baseline=fields["baseline"],
        )

    assert excinfo.value.exit_code == 3
    assert "--phase cook" in str(excinfo.value)
    assert "--slug demo" in str(excinfo.value)
    assert not (tmp_path / ".cheese").exists()


@pytest.mark.parametrize(
    "field", ["artifact", "orientation", "taste_test", "durable_flags", "baseline"]
)
def test_render_handoff_slug_rejects_a_newline_in_each_field(field: str) -> None:
    """#2: `render_handoff_slug` line-checks every field it interpolates,
    not just status."""
    fields: dict[str, str | None] = {
        "artifact": None,
        "orientation": "did the work",
        "taste_test": None,
        "durable_flags": None,
        "baseline": None,
    }
    fields[field] = INJECTION
    slug = handoff.HandoffSlug(
        status="ok",
        next_skill="age",
        artifact=fields["artifact"],
        orientation=fields["orientation"] or "did the work",
        taste_test=fields["taste_test"],
        durable_flags=fields["durable_flags"],
        baseline=fields["baseline"],
    )

    with pytest.raises(StatusError, match="one physical line"):
        _ = handoff.render_handoff_slug(slug)


@pytest.mark.parametrize(
    ("status", "action", "next_phase"),
    [
        ("ok", "spawn", "press"),
        (f"ok-with-concerns: {REASON}", "spawn", "press"),
        (f"needs-context: {REASON}", "needs_context", "cook"),
        (f"gated: {REASON}", "gated", None),
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


def _legacy_note(status_field: str) -> str:
    return f"status: {status_field}\nnext: cook\nartifact: \nsome orientation\n"


def test_legacy_reader_never_accepts_a_status_the_runtime_cannot_route() -> None:
    for name in REGISTERED_STATUSES:
        slug = legacy.parse_legacy_note(_legacy_note(_field(name)))
        assert slug.status == name
        assert slug.reason == (REASON if HANDBACK_STATUSES[name].requires_reason else None)
        assert status_disposition(slug.status) in DISPOSITIONS

    with pytest.raises(legacy.LegacyDecodeError, match="status must be one of"):
        _ = legacy.parse_legacy_note(_legacy_note("gated-ish: x"))


def test_legacy_reader_keeps_its_bare_reason_optional_tolerance() -> None:
    halt_slug = legacy.parse_legacy_note(_legacy_note("halt"))
    assert (halt_slug.status, halt_slug.reason) == ("halt", None)
    gated_slug = legacy.parse_legacy_note(_legacy_note("gated"))
    assert (gated_slug.status, gated_slug.reason) == ("gated", None)


def test_needs_context_re_dispatches_the_same_phase_with_its_reason() -> None:
    """`needs-context` is a request for more input, not a failure.

    The phase index does not advance and the exit message carries the worker's
    stated gap, so the orchestrator re-dispatches the identical phase with the
    missing context rather than halting the run or walking past the shortfall.
    """
    verdict = phase_decision.decide(1, f"needs-context: {REASON}")

    assert verdict["exit_message"] == (
        f"press (phase 1) needs more context: {REASON}; re-dispatch the same "
        "phase with it"
    )



def test_halt_reason_is_a_deprecated_read_alias_for_reason() -> None:
    """Kept for pre-rename readers; new code should read `.reason`."""
    slug = handoff.HandoffSlug(
        status="halt",
        reason=REASON,
        next_skill="done",
        artifact=None,
        orientation="stopped",
    )
    assert slug.halt_reason == REASON == slug.reason
