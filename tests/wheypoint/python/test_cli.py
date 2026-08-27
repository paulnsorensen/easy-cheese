"""The bundle's four commands: one line of JSON out, and an exit code to match.

Every test drives `wheypoint.main` the way the bundle does -- a subcommand name
in `argv[0]` -- and asserts the parsed payload and the exit code together,
because a caller that reads one without the other cannot tell a refusal from an
answer.
"""

from __future__ import annotations

import io
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from easy_cheese_schemas import (
    EntryKind,
    NextAction,
    NextMove,
    ProposedEntry,
    SessionProvenance,
    WheypointDelta,
)

from easy_cheese.skills.wheypoint import commit, records, storage, wheypoint

from conftest import WORK_ID, Promotion

CAPTURED_AT = "2026-08-02T00:00:00Z"


def _run(
    command: str, *args: str, stdin: str = ""
) -> tuple[int, dict[str, Any]]:
    """Invoke the CLI the way the bundle does and parse its single JSON line."""
    out = io.StringIO()
    status = wheypoint.main(
        [command, *args], stdin=io.StringIO(stdin), stdout=out
    )
    lines = out.getvalue().splitlines()
    assert len(lines) == 1, f"expected exactly one JSON line, got {lines!r}"
    return status, json.loads(lines[0])


def _genesis_delta(**overrides: object) -> WheypointDelta:
    fields: dict[str, object] = {
        "work_id": WORK_ID,
        "expected_revision_id": commit.GENESIS_PARENT,
        "orientation": "Wave 4 owns the CLI.\nThe second line is not the title.",
        "working_context": ["src/wheypoint/wheypoint.py"],
        "next_action": NextAction(
            move=NextMove.COOK,
            orientation="Ship the four commands.",
            artifact=".cheese/cook/wheypoint-pyz-cli.md",
        ),
        "session_provenance": SessionProvenance(captured_at=CAPTURED_AT),
    }
    fields.update(overrides)
    return WheypointDelta(**fields)  # type: ignore[arg-type]


def _delta_json(delta: WheypointDelta) -> str:
    return json.dumps(records.unstructure(delta))


@pytest.fixture
def store(corpus_root: Path) -> storage.WorkStore:
    """The store the CLI itself will open, via the same env contract."""
    return storage.WorkStore.open(WORK_ID, corpus_root=corpus_root)


def test_commit_creates_the_first_record_from_a_genesis_delta_on_stdin(
    store: storage.WorkStore,
) -> None:
    delta = _genesis_delta(
        add_decisions=[
            ProposedEntry(kind=EntryKind.DECISION, summary="Four subcommands.")
        ]
    )

    status, payload = _run("commit", stdin=_delta_json(delta))

    assert status == 0
    assert payload["ok"] is True
    assert payload["command"] == "commit"
    assert payload["replayed"] is False
    assert payload["work_id"] == WORK_ID
    assert payload["revision_number"] == 1
    assert payload["parent_revision_id"] is None
    assert payload["status"] == "ok"
    revision_id = payload["revision_id"]
    assert payload["projection_path"] == f"projections/1-{revision_id}.md"
    assert payload["record"]["revision_id"] == revision_id
    assert payload["record"]["title"] == "Wave 4 owns the CLI."
    assert payload["record"]["created"] == CAPTURED_AT
    assert [d["summary"] for d in payload["record"]["decisions"]] == [
        "Four subcommands."
    ]
    assert payload["markdown"].splitlines()[0] == "status: ok"

    # The command wrote through the canonical store, not a private copy.
    written = store.read_record()
    assert written is not None
    assert written.revision_id == revision_id
    assert payload["record"] == records.unstructure(written)


def test_commit_replays_an_identical_request_instead_of_writing_twice(
    store: storage.WorkStore,
) -> None:
    created = _run("commit", stdin=_delta_json(_genesis_delta()))[1]
    body = _delta_json(
        _genesis_delta(
            expected_revision_id=created["revision_id"],
            orientation="Submitted twice.",
        )
    )

    first_status, first = _run("commit", stdin=body)
    second_status, second = _run("commit", stdin=body)

    assert (first_status, second_status) == (0, 0)
    assert first["replayed"] is False
    assert second["replayed"] is True
    assert second["revision_id"] == first["revision_id"]
    assert len(list(store.revisions_dir.glob("*.json"))) == 2


def test_commit_refuses_a_genesis_delta_over_a_live_record(
    store: storage.WorkStore,
) -> None:
    _run("commit", stdin=_delta_json(_genesis_delta()))
    before = store.record_path.read_bytes()

    status, payload = _run(
        "commit", stdin=_delta_json(_genesis_delta(orientation="A second creation."))
    )

    assert status == 1
    assert payload["ok"] is False
    assert payload["command"] == "commit"
    assert payload["error"]["code"] == "genesis-conflict"
    assert "never replaces a live one" in payload["error"]["message"]
    assert store.record_path.read_bytes() == before


def test_commit_reports_a_stale_parent_as_its_own_code(
    store: storage.WorkStore,
) -> None:
    created = _run("commit", stdin=_delta_json(_genesis_delta()))[1]
    _run(
        "commit",
        stdin=_delta_json(
            _genesis_delta(
                expected_revision_id=created["revision_id"],
                orientation="First writer wins.",
            )
        ),
    )

    status, payload = _run(
        "commit",
        stdin=_delta_json(
            _genesis_delta(
                expected_revision_id=created["revision_id"],
                orientation="Second writer loses.",
            )
        ),
    )

    assert status == 1
    assert payload["error"]["code"] == "stale-parent"


def test_commit_refuses_a_delta_that_the_kernel_will_not_apply(
    store: storage.WorkStore,
) -> None:
    status, payload = _run(
        "commit",
        stdin=_delta_json(_genesis_delta(next_action=None)),
    )

    assert status == 1
    assert payload["error"]["code"] == "commit-refused"
    assert "next_action" in payload["error"]["message"]
    assert store.read_record() is None


def test_commit_refuses_stdin_that_is_not_json(corpus_root: Path) -> None:
    status, payload = _run("commit", stdin="not json at all")

    assert status == 1
    assert payload["error"]["code"] == "invalid-json"


def test_commit_refuses_json_that_is_not_a_delta(corpus_root: Path) -> None:
    status, payload = _run("commit", stdin=json.dumps({"work_id": WORK_ID}))

    assert status == 1
    assert payload["error"]["code"] == "invalid-delta"


def test_commit_refuses_a_work_id_that_is_not_a_safe_path_segment(
    corpus_root: Path,
) -> None:
    status, payload = _run(
        "commit", stdin=json.dumps({"work_id": "../escape", "expected_revision_id": "genesis"})
    )

    assert status == 1
    assert payload["error"]["code"] in {"invalid-delta", "storage-error"}


def test_show_returns_the_current_record(store: storage.WorkStore) -> None:
    created = _run("commit", stdin=_delta_json(_genesis_delta()))[1]

    status, payload = _run("show", "--work-id", WORK_ID)

    assert status == 0
    assert payload["ok"] is True
    assert payload["command"] == "show"
    assert payload["work_id"] == WORK_ID
    assert payload["status"] == "ok"
    assert payload["revision_id"] == created["revision_id"]
    assert payload["revision_number"] == 1
    assert payload["record"] == created["record"]


def test_show_refuses_work_that_has_no_record(corpus_root: Path) -> None:
    status, payload = _run("show", "--work-id", WORK_ID)

    assert status == 1
    assert payload["ok"] is False
    assert payload["error"]["code"] == "record-missing"


def test_show_refuses_an_unsafe_work_id(corpus_root: Path) -> None:
    status, payload = _run("show", "--work-id", "../escape")

    assert status == 1
    assert payload["error"]["code"] == "storage-error"


def test_resolve_reports_a_committed_work_id_as_dispatchable(
    store: storage.WorkStore,
) -> None:
    created = _run("commit", stdin=_delta_json(_genesis_delta()))[1]

    status, payload = _run("resolve", "--ref", WORK_ID)

    assert status == 0
    assert payload["ok"] is True
    assert payload["command"] == "resolve"
    assert payload["outcome"] == "authoritative"
    assert payload["dispatchable"] is True
    assert payload["source"] == "work-id"
    assert payload["work_id"] == WORK_ID
    assert payload["record"] == created["record"]
    assert payload["findings"] == []


def test_resolve_answers_not_found_without_calling_it_a_failure(
    corpus_root: Path,
) -> None:
    status, payload = _run("resolve", "--ref", "work-9999")

    assert status == 0
    assert payload["ok"] is True
    assert payload["outcome"] == "not-found"
    assert payload["dispatchable"] is False


def test_resolve_refuses_a_reference_it_cannot_interpret(corpus_root: Path) -> None:
    status, payload = _run("resolve", "--ref", "   ")

    assert status == 1
    assert payload["ok"] is False
    assert payload["error"]["code"] == "invalid-reference"


def test_resolve_legacy_answers_not_found_for_an_absent_note(
    tmp_path: Path, corpus_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    status, payload = _run("resolve", "--ref", "no-such-note", "--legacy")

    assert status == 0
    assert payload["outcome"] == "not-found"
    assert payload["source"] == "legacy"
    assert payload["dispatchable"] is False


def test_lint_reports_a_clean_projection(
    tmp_path: Path, make_promotion: Callable[..., Promotion]
) -> None:
    document = tmp_path / "1-rev-0001.md"
    document.write_text(make_promotion().markdown, encoding="utf-8")

    status, payload = _run("lint", str(document))

    assert status == 0
    assert payload["ok"] is True
    assert payload["command"] == "lint"
    assert payload["path"] == str(document)
    assert payload["clean"] is True
    assert payload["findings"] == []
    assert payload["projection"]["work_id"] == WORK_ID


def test_lint_reports_findings_as_an_answer_not_a_refusal(tmp_path: Path) -> None:
    document = tmp_path / "missing.md"

    status, payload = _run("lint", str(document))

    assert status == 0
    assert payload["ok"] is True
    assert payload["clean"] is False
    assert [f["code"] for f in payload["findings"]] == ["projection-unreadable"]
    assert payload["projection"] is None


def test_the_subcommand_is_read_from_argv0_and_from_argv1_alike(
    corpus_root: Path,
) -> None:
    from_entry_point = io.StringIO()
    from_module = io.StringIO()

    # How the bundle dispatcher invokes it, and how the module runs directly.
    assert (
        wheypoint.main(
            ["show", "--work-id", WORK_ID], stdin=io.StringIO(), stdout=from_entry_point
        )
        == 1
    )
    assert (
        wheypoint.main(
            ["/bundle/wheypoint.py", "show", "--work-id", WORK_ID],
            stdin=io.StringIO(),
            stdout=from_module,
        )
        == 1
    )

    assert from_entry_point.getvalue() == from_module.getvalue()
    assert json.loads(from_entry_point.getvalue())["error"]["code"] == "record-missing"


def test_an_unknown_command_is_a_usage_error_in_the_same_json_shape() -> None:
    out = io.StringIO()

    status = wheypoint.main(["wheypoint.py", "destroy"], stdin=io.StringIO(), stdout=out)

    payload = json.loads(out.getvalue())
    assert status == 2
    assert payload["ok"] is False
    assert payload["command"] == "unknown"
    assert payload["error"]["code"] == "usage"
    assert "commit" in payload["error"]["message"]


def test_a_missing_required_argument_is_a_usage_error_not_a_traceback() -> None:
    status, payload = _run("show")

    assert status == 2
    assert payload["ok"] is False
    assert payload["command"] == "show"
    assert payload["error"]["code"] == "usage"


def test_every_reply_is_one_line_of_sorted_json(store: storage.WorkStore) -> None:
    out = io.StringIO()
    status = wheypoint.main(
        ["commit"], stdin=io.StringIO(_delta_json(_genesis_delta())), stdout=out
    )
    text = out.getvalue()

    assert status == 0
    assert text.endswith("\n")
    assert text.count("\n") == 1
    payload = json.loads(text)
    assert json.dumps(payload, sort_keys=True) + "\n" == text


def test_the_command_surface_is_exactly_four_commands() -> None:
    assert wheypoint.COMMANDS == ("commit", "resolve", "show", "lint")
    assert "create" not in wheypoint.COMMANDS
