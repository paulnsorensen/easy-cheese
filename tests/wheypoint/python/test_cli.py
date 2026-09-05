"""The bundle's four commands: one line of JSON out, and an exit code to match.

Every test drives `wheypoint.main` the way the bundle does -- a subcommand name
in `argv[0]` -- and asserts the parsed payload and the exit code together,
because a caller that reads one without the other cannot tell a refusal from an
answer.
"""

from __future__ import annotations

import io
import json
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

from easy_cheese_schemas import CheckpointIntent
from easy_cheese.skills.wheypoint import commit, records, storage, wheypoint

from conftest import WORK_ID, Promotion

CAPTURED_AT = "2026-08-02T00:00:00Z"


def _run(
    command: str, *args: str, stdin: str = ""
) -> tuple[int, dict[str, object]]:
    """Invoke the CLI the way the bundle does and parse its single JSON line."""
    out = io.StringIO()
    status = wheypoint.main(
        [command, *args], stdin=io.StringIO(stdin), stdout=out
    )
    lines = out.getvalue().splitlines()
    assert len(lines) == 1, f"expected exactly one JSON line, got {lines!r}"
    return status, json.loads(lines[0])








def _get(container: object, *path: str) -> object:
    value = container
    for key in path:
        value = cast(dict[str, object], value)[key]
    return value


@pytest.fixture(autouse=True)
def _cwd_outside_a_repository(  # pyright: ignore[reportUnusedFunction]
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Run every command from a directory that is not a git worktree.

    `commit` mirrors its projection into the repository it is invoked from, so
    a suite that stayed in the checkout would write notes into the working tree
    it is testing. Outside a repository there is no default mirror at all,
    which is also the state the durability assertions below are about.
    """
    monkeypatch.chdir(tmp_path)


@pytest.fixture
def store(corpus_root: Path) -> storage.WorkStore:
    """The store the CLI itself will open, via the same env contract."""
    return storage.WorkStore.open(WORK_ID, corpus_root=corpus_root)


def test_checkpoint_creates_the_first_record_from_an_intent_on_stdin(
    store: storage.WorkStore,
) -> None:
    status, payload = _run(
        "checkpoint",
        stdin=_first_intent(entries=[{"kind": "decision", "summary": "Four subcommands."}]),
    )

    assert status == 0
    assert payload["ok"] is True
    assert payload["command"] == "checkpoint"
    assert payload["replayed"] is False
    assert payload["work_id"] == WORK_ID
    assert payload["revision_number"] == 1
    assert payload["parent_revision_id"] is None
    assert payload["status"] == "ok"
    # The checkpoint has travelled nowhere; the caller is told so rather than
    # having to lint the store to find out.
    assert payload["durability"] == "canonical-local"
    revision_id = payload["revision_id"]
    assert payload["projection_path"] == f"projections/1-{revision_id}.md"
    assert _get(payload, "record", "revision_id") == revision_id
    assert _get(payload, "record", "title") == "Genesis orientation."
    assert _get(payload, "record", "created") == CAPTURED_AT
    decisions = cast(list[dict[str, object]], _get(payload, "record", "decisions"))
    assert [d["summary"] for d in decisions] == ["Four subcommands."]
    assert cast(str, payload["markdown"]).splitlines()[0] == "status: ok"

    # The command wrote through the canonical store, not a private copy.
    written = store.read_record()
    assert written is not None
    assert written.revision_id == revision_id
    assert payload["record"] == records.unstructure(written)


def test_checkpoint_replays_an_identical_request_instead_of_writing_twice(
    store: storage.WorkStore,
) -> None:
    created = _run("checkpoint", stdin=_first_intent())[1]
    body = _intent_json(
        base_revision_id=created["revision_id"],
        orientation="Submitted twice.",
        session={"captured_at": CAPTURED_AT},
    )

    first_status, first = _run("checkpoint", stdin=body)
    second_status, second = _run("checkpoint", stdin=body)

    assert (first_status, second_status) == (0, 0)
    assert first["replayed"] is False
    assert second["replayed"] is True
    assert second["revision_id"] == first["revision_id"]
    assert len(list(store.revisions_dir.glob("*.json"))) == 2


def test_checkpoint_refuses_a_genesis_intent_over_a_live_record(
    store: storage.WorkStore,
) -> None:
    _ = _run("checkpoint", stdin=_first_intent())
    before = store.record_path.read_bytes()

    status, payload = _run(
        "checkpoint",
        stdin=_first_intent(orientation="A second creation.", base_revision_id=commit.GENESIS_PARENT),
    )

    assert status == 1
    assert payload["ok"] is False
    assert payload["command"] == "checkpoint"
    assert _get(payload, "error", "code") == "genesis-conflict"
    assert "never replaces a live one" in cast(str, _get(payload, "error", "message"))
    assert store.record_path.read_bytes() == before


@pytest.mark.usefixtures("store")
def test_checkpoint_reports_a_stale_parent_as_its_own_code() -> None:
    created = _run("checkpoint", stdin=_first_intent())[1]
    _ = _run(
        "checkpoint",
        stdin=_intent_json(base_revision_id=created["revision_id"], orientation="First writer wins."),
    )

    status, payload = _run(
        "checkpoint",
        stdin=_intent_json(base_revision_id=created["revision_id"], orientation="Second writer loses."),
    )

    assert status == 1
    assert _get(payload, "error", "code") == "stale-parent"


def test_checkpoint_refuses_an_intent_without_a_next_move(
    store: storage.WorkStore,
) -> None:
    intent = cast(dict[str, object], json.loads(_first_intent()))
    del intent["next"], intent["artifact"]
    status, payload = _run("checkpoint", stdin=json.dumps(intent))

    assert status == 1
    assert _get(payload, "error", "code") == "invalid-intent"
    assert "next" in cast(str, _get(payload, "error", "message"))
    assert store.read_record() is None


@pytest.mark.usefixtures("corpus_root")
def test_checkpoint_refuses_stdin_that_is_not_json() -> None:
    status, payload = _run("checkpoint", stdin="not json at all")

    assert status == 1
    assert _get(payload, "error", "code") == "invalid-json"


@pytest.mark.usefixtures("corpus_root")
def test_checkpoint_refuses_json_that_is_not_an_intent() -> None:
    status, payload = _run("checkpoint", stdin=json.dumps({"work_id": WORK_ID, "bogus": 1}))

    assert status == 1
    assert _get(payload, "error", "code") == "invalid-intent"


@pytest.mark.usefixtures("corpus_root")
def test_checkpoint_refuses_a_work_id_that_is_not_a_safe_path_segment() -> None:
    status, payload = _run("checkpoint", stdin=json.dumps({"work_id": "../escape"}))

    assert status == 1
    assert _get(payload, "error", "code") in {"invalid-intent", "storage-error"}


@pytest.mark.usefixtures("corpus_root")
def test_an_unexpected_crash_is_exit_3_with_a_traceback_on_stderr(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def _boom(_args: object, _stdin: object) -> dict[str, object]:
        raise RuntimeError("boom")

    monkeypatch.setitem(wheypoint._RUNNERS, "show", _boom)  # pyright: ignore[reportPrivateUsage]

    status, payload = _run("show", "--work-id", WORK_ID)

    assert status == wheypoint.EXIT_INTERNAL
    assert _get(payload, "error", "code") == "internal-error"
    assert "RuntimeError" in capsys.readouterr().err


def test_checkpoint_mirrors_the_projection_into_an_explicit_note_dir(
    store: storage.WorkStore, tmp_path: Path
) -> None:
    notes = tmp_path / "handoffs"

    status, payload = _run(
        "checkpoint", "--note-dir", str(notes), stdin=_first_intent()
    )

    assert status == 0
    mirror = notes / f"{WORK_ID}.md"
    assert payload["note_path"] == str(mirror)
    markdown = cast(str, payload["markdown"])
    # The mirror is a byte-for-byte copy of the projection the corpus holds,
    # not a second rendering that could drift from the digest in the receipt.
    assert mirror.read_text(encoding="utf-8") == markdown
    stored = store.projection_path(1, cast(str, payload["revision_id"]))
    assert stored.read_text(encoding="utf-8") == markdown
    # The durability the caller is told is the one the document itself carries.
    assert payload["durability"] == "repo-snapshot"
    assert "durability: repo-snapshot" in markdown


@pytest.mark.usefixtures("store")
def test_checkpoint_replay_rewrites_the_identical_mirror(tmp_path: Path) -> None:
    notes = tmp_path / "handoffs"
    body = _first_intent(base_revision_id=commit.GENESIS_PARENT)

    first_status, first = _run("checkpoint", "--note-dir", str(notes), stdin=body)
    mirror = notes / f"{WORK_ID}.md"
    written = mirror.read_bytes()
    second_status, second = _run("checkpoint", "--note-dir", str(notes), stdin=body)

    assert (first_status, second_status) == (0, 0)
    assert first["replayed"] is False
    assert second["replayed"] is True
    assert second["note_path"] == first["note_path"]
    assert mirror.read_bytes() == written


@pytest.mark.usefixtures("store")
def test_checkpoint_no_note_overrides_an_explicit_note_dir(tmp_path: Path) -> None:
    notes = tmp_path / "handoffs"

    status, payload = _run(
        "checkpoint",
        "--note-dir",
        str(notes),
        "--no-note",
        stdin=_first_intent(),
    )

    assert status == 0
    assert payload["note_path"] is None
    assert not notes.exists()
    assert payload["durability"] == "canonical-local"
    assert "durability: canonical-local" in cast(str, payload["markdown"])


@pytest.mark.usefixtures("store")
def test_checkpoint_outside_a_repository_writes_no_mirror(tmp_path: Path) -> None:
    status, payload = _run("checkpoint", stdin=_first_intent())

    assert status == 0
    assert payload["note_path"] is None
    assert payload["durability"] == "canonical-local"
    assert not (tmp_path / ".cheese").exists()


@pytest.mark.usefixtures("store")
def test_checkpoint_defaults_the_mirror_to_the_enclosing_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    _ = subprocess.run(["git", "init", "--quiet"], cwd=checkout, check=True)
    monkeypatch.chdir(checkout)

    status, payload = _run("checkpoint", stdin=_first_intent())

    assert status == 0
    assert payload["durability"] == "repo-snapshot"
    note_path = Path(cast(str, payload["note_path"]))
    assert note_path.parts[-3:] == (".cheese", "notes", f"{WORK_ID}.md")
    mirror = checkout / ".cheese" / "notes" / f"{WORK_ID}.md"
    assert mirror.read_text(encoding="utf-8") == payload["markdown"]


@pytest.mark.usefixtures("store")
def test_checkpoint_refuses_when_the_note_dir_cannot_be_created(tmp_path: Path) -> None:
    blocker = tmp_path / "blocker"
    _ = blocker.write_text("not a directory\n", encoding="utf-8")

    status, payload = _run(
        "checkpoint",
        "--note-dir",
        str(blocker / "notes"),
        stdin=_first_intent(),
    )

    assert status == 1
    assert payload["ok"] is False
    assert _get(payload, "error", "code") == "note-unwritable"
    # The refusal lands before the promotion, so nothing was committed either.
    show_status, show_payload = _run("show", "--work-id", WORK_ID)
    assert show_status == 1
    assert _get(show_payload, "error", "code") == "record-missing"


@pytest.mark.usefixtures("store")
def test_show_returns_the_current_record() -> None:
    created = _run("checkpoint", stdin=_first_intent())[1]

    status, payload = _run("show", "--work-id", WORK_ID)

    assert status == 0
    assert payload["ok"] is True
    assert payload["command"] == "show"
    assert payload["work_id"] == WORK_ID
    assert payload["status"] == "ok"
    assert payload["revision_id"] == created["revision_id"]
    assert payload["revision_number"] == 1
    assert payload["record"] == created["record"]


@pytest.mark.usefixtures("corpus_root")
def test_show_refuses_work_that_has_no_record() -> None:
    status, payload = _run("show", "--work-id", WORK_ID)

    assert status == 1
    assert payload["ok"] is False
    assert _get(payload, "error", "code") == "record-missing"


@pytest.mark.usefixtures("corpus_root")
def test_show_refuses_an_unsafe_work_id() -> None:
    status, payload = _run("show", "--work-id", "../escape")

    assert status == 1
    assert _get(payload, "error", "code") == "storage-error"


@pytest.mark.usefixtures("store")
def test_resolve_reports_a_committed_work_id_as_dispatchable() -> None:
    created = _run("checkpoint", stdin=_first_intent())[1]

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


@pytest.mark.usefixtures("corpus_root")
def test_resolve_answers_not_found_without_calling_it_a_failure() -> None:
    status, payload = _run("resolve", "--ref", "work-9999")

    assert status == 0
    assert payload["ok"] is True
    assert payload["outcome"] == "not-found"
    assert payload["dispatchable"] is False


@pytest.mark.usefixtures("corpus_root")
def test_resolve_refuses_a_reference_it_cannot_interpret() -> None:
    status, payload = _run("resolve", "--ref", "   ")

    assert status == 1
    assert payload["ok"] is False
    assert _get(payload, "error", "code") == "invalid-reference"


@pytest.mark.usefixtures("corpus_root")
def test_resolve_legacy_answers_not_found_for_an_absent_note(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
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
    _ = document.write_text(make_promotion().markdown, encoding="utf-8")

    status, payload = _run("lint", str(document))

    assert status == 0
    assert payload["ok"] is True
    assert payload["command"] == "lint"
    assert payload["path"] == str(document)
    assert payload["clean"] is True
    assert payload["findings"] == []
    assert _get(payload, "projection", "work_id") == WORK_ID


def test_lint_reports_findings_as_an_answer_not_a_refusal(tmp_path: Path) -> None:
    document = tmp_path / "missing.md"

    status, payload = _run("lint", str(document))

    assert status == 0
    assert payload["ok"] is True
    assert payload["clean"] is False
    findings = cast(list[dict[str, object]], payload["findings"])
    assert [f["code"] for f in findings] == ["projection-unreadable"]
    assert payload["projection"] is None


@pytest.mark.usefixtures("corpus_root")
def test_the_subcommand_is_read_from_argv0_and_from_argv1_alike() -> None:
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
    entry_point_payload = cast(dict[str, object], json.loads(from_entry_point.getvalue()))
    assert _get(entry_point_payload, "error", "code") == "record-missing"


def test_an_unknown_command_is_a_usage_error_in_the_same_json_shape() -> None:
    out = io.StringIO()

    status = wheypoint.main(["wheypoint.py", "destroy"], stdin=io.StringIO(), stdout=out)

    payload = cast(dict[str, object], json.loads(out.getvalue()))
    assert status == 2
    assert payload["ok"] is False
    assert payload["command"] == "unknown"
    assert _get(payload, "error", "code") == "usage"
    assert "validate" in cast(str, _get(payload, "error", "message"))


def test_a_missing_required_argument_is_a_usage_error_not_a_traceback() -> None:
    status, payload = _run("show")

    assert status == 2
    assert payload["ok"] is False
    assert payload["command"] == "show"
    assert _get(payload, "error", "code") == "usage"


@pytest.mark.usefixtures("store")
def test_every_reply_is_one_line_of_sorted_json() -> None:
    out = io.StringIO()
    status = wheypoint.main(
        ["checkpoint"], stdin=io.StringIO(_first_intent()), stdout=out
    )
    text = out.getvalue()

    assert status == 0
    assert text.endswith("\n")
    assert text.count("\n") == 1
    payload = cast(dict[str, object], json.loads(text))
    assert json.dumps(payload, sort_keys=True) + "\n" == text


def test_the_command_surface_is_exactly_nine_commands() -> None:
    assert wheypoint.COMMANDS == (
        "checkpoint", "validate", "schema", "resolve", "show", "lint", "list", "log", "turns",
    )
    assert "commit" not in wheypoint.COMMANDS and "create" not in wheypoint.COMMANDS


# --------------------------------------------------------------------------
# v3 write path (spec wheypoint-ergonomics, curd 2): tracer tests per AC.
# --------------------------------------------------------------------------


def _intent_json(**fields: object) -> str:
    return json.dumps({"work_id": WORK_ID, **fields})


def _first_intent(**fields: object) -> str:
    base: dict[str, object] = {
        "orientation": "Genesis orientation.\nNot the title.",
        "working_context": ["src/easy_cheese/skills/wheypoint/checkpoint.py"],
        "next": "cook",
        "artifact": ".cheese/cook/wheypoint-ergonomics.md",
        "notes": "First record.",
        "session": {"captured_at": CAPTURED_AT},
    }
    base.update(fields)
    return _intent_json(**base)


def _error(payload: dict[str, object]) -> tuple[str, str]:
    error = cast(dict[str, str], payload["error"])
    return error["code"], error["message"]


@pytest.mark.usefixtures("store")
def test_ac1_an_unknown_key_is_refused_by_path_on_every_write_path() -> None:
    status, payload = _run("checkpoint", stdin=_first_intent(bogus=1))
    code, message = _error(payload)
    assert (status, code) == (1, "invalid-intent")
    assert "bogus" in message and "unknown field" in message

    status, payload = _run(
        "checkpoint",
        stdin=_first_intent(entries=[{"kind": "decision", "summary": "s", "nested_bogus": 1}]),
    )
    code, message = _error(payload)
    assert (status, code) == (1, "invalid-intent")
    assert "entries[" in message and "nested_bogus" in message

    # AC-10: the raw-delta surface is gone, so checkpoint is the only write path.
    status, payload = _run("commit", stdin="{}")
    assert (status, _error(payload)[0]) == (2, "usage")


@pytest.mark.usefixtures("store")
def test_ac3_entries_are_promoted_per_kind_with_their_rationale() -> None:
    status, payload = _run(
        "checkpoint",
        stdin=_first_intent(
            entries=[
                {"kind": "decision", "summary": "Keep canonical JSON.", "rationale": "digests need it"},
                {"kind": "question", "summary": "Bump or migrate?"},
                {"kind": "blocker", "summary": "Bundle is stale.", "blocks_continuation": False},
            ]
        ),
    )
    assert status == 0, payload
    decisions = cast(list[dict[str, object]], _get(payload, "record", "decisions"))
    assert decisions[0]["rationale"] == "digests need it"
    assert len(cast(list[object], _get(payload, "record", "questions"))) == 1
    assert len(cast(list[object], _get(payload, "record", "blockers"))) == 1


@pytest.mark.usefixtures("store")
def test_ac25_a_directive_keeps_its_quote_and_is_carried_forward() -> None:
    status, payload = _run(
        "checkpoint",
        stdin=_first_intent(
            entries=[{"kind": "directive", "summary": "Prose stays STE100.", "quote": "is it all in STE100?"}]
        ),
    )
    assert status == 0, payload
    directives = cast(list[dict[str, object]], _get(payload, "record", "directives"))
    assert directives[0]["quote"] == "is it all in STE100?"
    assert cast(str, directives[0]["entry_id"]).startswith("v-")

    status, payload = _run("checkpoint", stdin=_intent_json(orientation="Says nothing new."))
    assert status == 0, payload
    assert cast(list[dict[str, object]], _get(payload, "record", "directives")) == directives

    status, payload = _run(
        "checkpoint",
        stdin=_first_intent(entries=[{"kind": "directive", "summary": "x", "blocks_continuation": True}]),
    )
    assert status == 1 and "directive" in _error(payload)[1]


@pytest.mark.usefixtures("store")
def test_ac8_notes_are_stored_and_carried_forward_when_omitted() -> None:
    status, payload = _run("checkpoint", stdin=_first_intent(notes="Body of the record."))
    assert status == 0 and _get(payload, "record", "notes") == "Body of the record."
    status, payload = _run("checkpoint", stdin=_intent_json(orientation="Only orientation."))
    assert status == 0 and _get(payload, "record", "notes") == "Body of the record."
    status, payload = _run("checkpoint", stdin=_intent_json(notes="Replaced."))
    assert status == 0 and _get(payload, "record", "notes") == "Replaced."


@pytest.mark.usefixtures("store")
def test_ac9_tasks_persist_typed_and_an_empty_tasks_move_is_refused() -> None:
    task = {
        "slug": "curd-a",
        "intent": "cook",
        "repo": "easy-cheese",
        "branch": "cook/curd-a",
        "branch_from": "main",
        "command": "/cook .cheese/specs/curd-a.md",
    }
    status, payload = _run(
        "checkpoint",
        stdin=_first_intent(
            next="tasks",
            artifact=None,
            tasks=[task],
            parallel={"isolation": "worktree", "worktree_strategy": "create", "worktree_root": "../wt"},
        ),
    )
    assert status == 0, payload
    assert _get(payload, "record", "next_action", "tasks") == [{**task, "worktree": None}]
    assert _get(payload, "record", "next_action", "parallel", "worktree_strategy") == "create"

    status, payload = _run("checkpoint", stdin=_intent_json(next="tasks"))
    assert status == 1 and "tasks must be non-empty when move is 'tasks'" in _error(payload)[1]
    status, payload = _run("checkpoint", stdin=_intent_json(next="cook", artifact="x.md", tasks=[task]))
    assert status == 1 and "tasks may only be set when move is 'tasks'" in _error(payload)[1]


def test_ac4_ac5_ac6_ac23_artifact_links_are_a_set_pinned_by_the_host(
    store: storage.WorkStore, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    doc = tmp_path / "doc.md"
    _ = doc.write_text("hello\n", encoding="utf-8")

    status, payload = _run("checkpoint", stdin=_first_intent(artifact_links=[{"path": "doc.md"}]))
    assert status == 0, payload
    links = cast(list[dict[str, object]], _get(payload, "record", "artifact_links"))
    assert links[0]["digest"] == storage.file_digest(doc)
    assert links[0]["revision_id"] == _get(payload, "record", "revision_id")

    status, payload = _run(
        "checkpoint",
        stdin=_intent_json(artifact_links=[{"path": "doc.md", "covers_entry_ids": cast(list[str], [])}]),
    )
    assert status == 0, payload
    links = cast(list[dict[str, object]], _get(payload, "record", "artifact_links"))
    assert [link["path"] for link in links] == ["doc.md"]
    assert links[0]["revision_id"] == _get(payload, "record", "revision_id")

    before = store.read_record()
    status, payload = _run("checkpoint", stdin=_intent_json(artifact_links=[]))
    code, message = _error(payload)
    assert (status, code) == (1, "invalid-intent") and "artifact_links" in message
    assert store.read_record() == before

    status, payload = _run("checkpoint", stdin=_intent_json(remove_artifact_links=["nope.md"]))
    assert status == 1 and "does not carry" in _error(payload)[1]

    status, payload = _run("checkpoint", stdin=_intent_json(remove_artifact_links=["doc.md"]))
    assert status == 0 and _get(payload, "record", "artifact_links") == []


@pytest.mark.usefixtures("store")
def test_ac19_next_and_artifact_must_cohere() -> None:
    status, payload = _run("checkpoint", stdin=_first_intent(next="affinage", artifact="a report"))
    assert status == 1 and "PR#" in _error(payload)[1]
    status, payload = _run("checkpoint", stdin=_first_intent(next="affinage", artifact="PR#615"))
    assert status == 0, payload
    status, payload = _run("checkpoint", stdin=_intent_json(next="cook"))
    assert status == 1 and "artifact is required" in _error(payload)[1]


@pytest.mark.usefixtures("store")
def test_ac20_a_secret_pattern_refuses_the_checkpoint_naming_the_field() -> None:
    token = "ghp_" + "a" * 36
    status, payload = _run("checkpoint", stdin=_first_intent(orientation=f"token {token} pasted"))
    code, message = _error(payload)
    assert (status, code) == (1, "secret-pattern")
    assert message.startswith("orientation (GitHub token)")


def test_ac26_a_genesis_without_entries_or_notes_creates_no_store(
    store: storage.WorkStore,
) -> None:
    intent = cast(dict[str, object], json.loads(_first_intent()))
    del intent["notes"]
    status, payload = _run("checkpoint", stdin=json.dumps(intent))
    code, message = _error(payload)
    assert (status, code) == (1, "commit-refused")
    assert "first checkpoint must capture" in message
    assert store.read_record() is None
    assert not store.record_path.exists()


def test_ac10_checkpoint_compacted_commits_a_compacted_delta(
    store: storage.WorkStore, tmp_path: Path
) -> None:
    status, payload = _run("checkpoint", stdin=_first_intent())
    assert status == 0, payload
    current = store.read_record()
    assert current is not None
    proof = tmp_path / "proof.json"
    _ = proof.write_text(
        json.dumps(
            {
                "rehydrated_from_revision_id": current.revision_id,
                "rehydrated_record_digest": records.record_digest(current),
                "reconciled_entry_ids": [entry.entry_id for entry in records.entries(current)],
            }
        ),
        encoding="utf-8",
    )
    status, payload = _run(
        "checkpoint",
        "--compacted",
        str(proof),
        stdin=_intent_json(orientation="Rehydrated.", session={"harness": "claude", "session_id": "s-1"}),
    )
    assert status == 0, payload
    revision = store.find_complete_revision(cast(str, payload["revision_id"]))
    assert revision is not None and revision.compaction is not None
    assert revision.compaction.rehydrated_from_revision_id == current.revision_id

    _ = proof.write_text(json.dumps({"rehydrated_from_revision_id": current.revision_id}), encoding="utf-8")
    status, payload = _run("checkpoint", "--compacted", str(proof), stdin=_intent_json(orientation="x"))
    assert status == 1 and _error(payload)[0] == "invalid-compaction-proof"


def test_ac10_commit_is_no_longer_a_listed_command() -> None:
    from easy_cheese.skills.wheypoint import commands

    assert "commit" not in wheypoint.COMMANDS
    assert [command.name for command in commands.COMMANDS] == [
        "checkpoint", "validate", "schema", "resolve", "show", "lint", "list", "log", "turns", "handoff",
    ]


def test_ac11_validate_reports_every_problem_and_never_opens_the_store(
    store: storage.WorkStore,
) -> None:
    status, payload = _run("validate", stdin=_first_intent(bogus=1, compacted=True))
    assert status == 1
    problems = cast(list[str], _get(payload, "error", "problems"))
    assert any("bogus" in p for p in problems) and any("compacted" in p for p in problems)
    status, payload = _run("validate", stdin=_first_intent(next="affinage", artifact="x"))
    assert status == 1
    assert any("PR#" in p for p in cast(list[str], _get(payload, "error", "problems")))
    assert not store.record_path.exists()

    status, payload = _run("validate", stdin=_first_intent())
    assert (status, payload["valid"]) == (0, True)
    assert not store.record_path.exists()


def test_ac12_schema_prints_the_registered_json_schema() -> None:
    status, payload = _run("schema", "checkpoint-intent")
    assert status == 0
    schema = cast(dict[str, object], payload["schema"])
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert cast(str, schema["$id"]).endswith("/checkpoint-intent")
    assert "work_id" in json.dumps(schema)

    status, payload = _run("schema", "nope")
    assert (status, _error(payload)[0]) == (1, "unknown-contract")
    assert "checkpoint-intent" in cast(list[str], _get(payload, "error", "known"))


def test_ac13_list_prints_one_line_per_work_item(corpus_root: Path) -> None:
    _ = _run("checkpoint", stdin=_first_intent())
    _ = _run("checkpoint", stdin=_first_intent(work_id="other-work", orientation="Other.\nMore."))

    status, payload = _run("list")
    assert status == 0
    lines = cast(list[str], payload["lines"])
    assert len(lines) == 2
    assert lines[0].split("\t") == ["other-work", "1", "ok", "cook", "Other."]
    assert lines[1].split("\t")[0] == WORK_ID
    assert payload["corpus_root"] == str(corpus_root)


@pytest.mark.usefixtures("store")
def test_ac14_log_walks_revisions_oldest_first() -> None:
    _ = _run("checkpoint", stdin=_first_intent(entries=[{"kind": "decision", "summary": "One."}]))
    _ = _run("checkpoint", stdin=_intent_json(orientation="Second."))

    status, payload = _run("log", "--work-id", WORK_ID)
    assert status == 0
    lines = cast(list[str], payload["lines"])
    assert len(lines) == 2
    first, second = (line.split("\t") for line in lines)
    assert first[0] == "1" and second[0] == "2"
    assert first[2] == CAPTURED_AT and first[3] == "+1" and first[4] == "~0" and first[5] == "-"
    assert second[3] == "+0"

    status, payload = _run("log", "--work-id", "never-written")
    assert (status, _error(payload)[0]) == (1, "record-missing")


def _transcript(path: Path) -> None:
    entries = [
        {"type": "user", "timestamp": "2026-09-05T06:17:04Z", "message": {"content": "What are our gh issues?"}},
        {"type": "assistant", "timestamp": "2026-09-05T06:17:10Z", "message": {"content": [{"type": "text", "text": "ignored"}]}},
        {"type": "user", "timestamp": "2026-09-05T06:18:00Z", "message": {"content": [{"type": "tool_result", "content": "x"}]}},
        {"type": "user", "timestamp": "2026-09-05T06:18:30Z", "message": {"content": "<system-reminder>not the user</system-reminder>"}},
        {"type": "user", "timestamp": "2026-09-05T06:19:00Z", "message": {"content": [{"type": "text", "text": "Base directory for this skill: /x"}]}},
        {"type": "user", "timestamp": "2026-09-05T06:20:00Z", "message": {"content": [{"type": "text", "text": "Double down on ergonomics."}]}},
    ]
    _ = path.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")


def test_ac27_turns_prints_the_users_turns_from_a_transcript(tmp_path: Path) -> None:
    transcript = tmp_path / "s.jsonl"
    _transcript(transcript)
    status, payload = _run("turns", "--transcript", str(transcript))
    assert status == 0
    assert cast(list[str], payload["lines"]) == [
        "2026-09-05T06:17:04Z\tWhat are our gh issues?",
        "2026-09-05T06:20:00Z\tDouble down on ergonomics.",
    ]
    status, payload = _run("turns", "--transcript", str(tmp_path / "missing.jsonl"))
    assert (status, _error(payload)[0]) == (1, "transcript-missing")
    assert str(tmp_path / "missing.jsonl") in _error(payload)[1]


def test_ac28_turns_derives_the_projects_dir_and_never_guesses_a_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    cwd = tmp_path / "Dev" / "easy.cheese_x"
    cwd.mkdir(parents=True)
    projects = home / ".claude" / "projects" / str(cwd).replace("/", "-").replace(".", "-").replace("_", "-")
    projects.mkdir(parents=True)
    _transcript(projects / "aaa.jsonl")
    _transcript(projects / "bbb.jsonl")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(cwd)

    status, payload = _run("turns")
    assert (status, _error(payload)[0]) == (1, "session-required")
    candidates = cast(list[dict[str, str]], _get(payload, "error", "candidates"))
    assert sorted(c["session"] for c in candidates) == ["aaa", "bbb"]
    assert all(c["modified"].endswith("Z") for c in candidates)

    status, payload = _run("turns", "--session", "bbb")
    assert status == 0 and payload["transcript"] == str(projects / "bbb.jsonl")
    assert (payload["count"], payload["skipped_lines"]) == (2, 0)

# --- cure of the curd 2/3 review ------------------------------------------


@pytest.mark.usefixtures("store")
def test_cure_secret_scan_covers_every_string_field() -> None:
    token = "ghp_" + "b" * 36
    task = {"slug": "s", "intent": "cook", "repo": "r", "branch": "b", "branch_from": "main", "command": f"/cook --token {token}"}
    status, payload = _run("checkpoint", stdin=_first_intent(next="tasks", artifact=None, tasks=[task]))
    code, message = _error(payload)
    assert (status, code) == (1, "secret-pattern") and message.startswith("tasks[0].command")

    status, payload = _run(
        "checkpoint",
        stdin=_first_intent(
            decision_dossier=[{"fork": "f", "options": [{"option": "o", "evidence": [f"AKIA{'C' * 16}"], "breaks": "x"}], "prior_leaning": None}],
            entries=[{"kind": "question", "summary": "q", "blocks_continuation": True}],
        ),
    )
    assert status == 1 and _error(payload)[1].startswith("decision_dossier[0].options[0].evidence[0]")


def test_cure_a_compaction_proof_is_part_of_the_request_identity(
    store: storage.WorkStore,
) -> None:
    """The pending-mirror ledger key differs with and without a proof (dead-store regression)."""
    from easy_cheese_schemas import CompactionRecord

    _ = _run("checkpoint", stdin=_first_intent())
    current = store.read_record()
    assert current is not None
    intent = records.structure(cast(object, json.loads(_intent_json(orientation="Same words."))), CheckpointIntent)
    proof = CompactionRecord(
        rehydrated_from_revision_id=current.revision_id,
        rehydrated_record_digest=records.record_digest(current),
        reconciled_entry_ids=[e.entry_id for e in records.entries(current)],
    )
    without = wheypoint.request_identity_for(intent, None)
    with_proof = wheypoint.request_identity_for(intent, proof)
    assert without != with_proof
    assert without == wheypoint.request_identity_for(intent, None)


@pytest.mark.usefixtures("store")
def test_cure_pr_urls_with_a_trailing_route_satisfy_the_affinage_gate() -> None:
    status, payload = _run(
        "checkpoint",
        stdin=_first_intent(next="affinage", artifact="https://github.com/o/r/pull/12/files"),
    )
    assert status == 0, payload


def test_cure_turns_strips_host_wrappers_but_keeps_the_users_words(tmp_path: Path) -> None:
    transcript = tmp_path / "s.jsonl"
    entries = [
        {"type": "user", "timestamp": "t1", "message": {"content": "<system-reminder>ignored</system-reminder>Pull the ten turns in too."}},
        {"type": "user", "timestamp": "t2", "message": {"content": "Curdle.\n<task-notification><task-id>x</task-id></task-notification>"}},
        {"type": "user", "timestamp": "t3", "message": {"content": "<local-command-stdout></local-command-stdout>"}},
    ]
    _ = transcript.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")
    status, payload = _run("turns", "--transcript", str(transcript))
    assert status == 0
    assert cast(list[str], payload["lines"]) == ["t1\tPull the ten turns in too.", "t2\tCurdle."]


def test_cure_turns_refuses_a_session_id_that_escapes_the_projects_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    status, payload = _run("turns", "--session", "../../etc/passwd")
    assert (status, _error(payload)[0]) == (1, "invalid-session")


@pytest.mark.usefixtures("store")
def test_cure_artifact_digests_resolve_from_the_repository_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    checkout = tmp_path / "checkout"
    (checkout / "sub").mkdir(parents=True)
    _ = subprocess.run(["git", "init", "--quiet"], cwd=checkout, check=True)
    doc = checkout / "doc.md"
    _ = doc.write_text("root-relative\n", encoding="utf-8")
    monkeypatch.chdir(checkout / "sub")
    status, payload = _run("checkpoint", "--no-note", stdin=_first_intent(artifact_links=[{"path": "doc.md"}]))
    assert status == 0, payload
    links = cast(list[dict[str, object]], _get(payload, "record", "artifact_links"))
    assert links[0]["digest"] == storage.file_digest(doc)

# --- cure of the whole-diff review ------------------------------------------


def _tasks_intent(**fields: object) -> str:
    task = {"slug": "s", "intent": "cook", "repo": "r", "branch": "b", "branch_from": "main", "command": "/cook s"}
    return _first_intent(
        next="tasks",
        artifact=None,
        tasks=[task],
        parallel={"isolation": "wt", "worktree_strategy": "create", "worktree_root": "../wt"},
        **fields,
    )


@pytest.mark.usefixtures("store")
def test_cure_a_tasks_projection_parses_and_lints_clean() -> None:
    from easy_cheese.skills.wheypoint import lint, projection

    status, payload = _run("checkpoint", stdin=_tasks_intent())
    assert status == 0, payload
    markdown = cast(str, payload["markdown"])
    parsed = projection.parse(markdown)
    assert parsed.next_action.tasks is not None and parsed.next_action.tasks[0].command == "/cook s"
    assert parsed.next_action.parallel is not None and parsed.next_action.parallel.worktree_root == "../wt"
    assert lint.lint_projection_text(markdown).findings == ()


@pytest.mark.usefixtures("store")
def test_cure_validate_reports_next_action_and_delta_invariants() -> None:
    status, payload = _run("validate", stdin=_first_intent(next="tasks", artifact=None))
    assert status == 1
    assert any("tasks must be non-empty" in p for p in cast(list[str], _get(payload, "error", "problems")))
    status, payload = _run("validate", stdin=_first_intent(expected_revision_id="rev-000000000000"))
    problems = cast(list[str], _get(payload, "error", "problems"))
    assert status == 1 and len([p for p in problems if "expected_revision_id" in p]) == 1


@pytest.mark.usefixtures("store")
def test_cure_a_task_command_must_be_a_skill_dispatch() -> None:
    status, payload = _run(
        "checkpoint",
        stdin=_first_intent(next="tasks", artifact=None, tasks=[{"slug": "s", "intent": "cook", "repo": "r", "branch": "b", "branch_from": "main", "command": "rm -rf /"}]),
    )
    assert status == 1 and "tasks[0].command is not a skill dispatch" in _error(payload)[1]


@pytest.mark.usefixtures("store")
def test_cure_single_line_fields_refuse_newlines() -> None:
    status, payload = _run("checkpoint", stdin=_first_intent(artifact_links=[{"path": "a.md\n## Decision dossier"}]))
    assert status == 1 and "must be a single line" in _error(payload)[1]
    status, payload = _run("checkpoint", stdin=_first_intent(artifact="x.md\nmode: parallel"))
    assert status == 1 and "must be a single line" in _error(payload)[1]


@pytest.mark.usefixtures("store")
@pytest.mark.parametrize(
    ("label", "text"),
    [
        # Assembled at runtime so no literal in the repo looks like a live credential.
        ("Slack webhook", "https://hooks." + "slack.com/services/" + "T000/B000/" + "X" * 24),
        ("Google API key", "AIza" + "A" * 35),
        ("JWT or bearer token", ".".join(("eyJ" + "a" * 20, "eyJ" + "b" * 20, "c" * 40))),
        ("URL with basic-auth credentials", "https://user:hunter2hunter2@example.com/repo"),
        ("credential assignment", "api_key = abcdefghijklmnop"),
    ],
)
def test_cure_secret_patterns_cover_the_common_shapes(label: str, text: str) -> None:
    status, payload = _run("checkpoint", stdin=_first_intent(notes=f"pasted {text} here"))
    code, message = _error(payload)
    assert (status, code) == (1, "secret-pattern") and message.startswith(f"notes ({label})")


@pytest.mark.usefixtures("store")
def test_cure_validate_reports_every_secret_not_just_the_first() -> None:
    token = "ghp_" + "c" * 36
    status, payload = _run("validate", stdin=_first_intent(orientation=f"a {token}", notes=f"b {token}"))
    problems = cast(list[str], _get(payload, "error", "problems"))
    assert status == 1 and sum("looks like a credential" in p for p in problems) == 2


def test_cure_turns_counts_unreadable_lines(tmp_path: Path) -> None:
    transcript = tmp_path / "s.jsonl"
    _transcript(transcript)
    with transcript.open("a", encoding="utf-8") as handle:
        _ = handle.write('{"type": "user", "timestamp": "t9", "message": {"content": "truncated')
    status, payload = _run("turns", "--transcript", str(transcript))
    assert status == 0 and (payload["count"], payload["skipped_lines"]) == (2, 1)


def test_cure_enumerate_ignores_directories_that_are_not_work_ids(corpus_root: Path) -> None:
    _ = _run("checkpoint", stdin=_first_intent())
    rogue = corpus_root / storage.WORK_DIRNAME / "Not_A_Work-ID"
    rogue.mkdir(parents=True)
    _ = (rogue / storage.RECORD_FILENAME).write_text("{}", encoding="utf-8")
    status, payload = _run("list")
    assert status == 0
    assert [line.split("\t")[0] for line in cast(list[str], payload["lines"])] == [WORK_ID]


# --- cure of pr-621 review findings ----------------------------------------


@pytest.mark.usefixtures("store")
def test_cure_log_survives_a_corrupt_revision_and_names_it_unreadable(
    store: storage.WorkStore,
) -> None:
    first = _run("checkpoint", stdin=_first_intent())[1]
    _ = _run("checkpoint", stdin=_intent_json(orientation="Second."))
    corrupt_path = store.revision_path(1, cast(str, first["revision_id"]))
    _ = corrupt_path.write_text("not json", encoding="utf-8")

    status, payload = _run("log", "--work-id", WORK_ID)

    assert status == 0
    revisions = cast(list[dict[str, object]], payload["revisions"])
    assert [r["revision_number"] for r in revisions] == [2]
    unreadable = cast(list[dict[str, str]], payload["unreadable"])
    assert len(unreadable) == 1
    assert unreadable[0]["path"] == corrupt_path.name
    assert "malformed JSON" in unreadable[0]["reason"]


@pytest.mark.usefixtures("store")
def test_cure_log_survives_a_missing_projection_and_names_it_unreadable(
    store: storage.WorkStore,
) -> None:
    first = _run("checkpoint", stdin=_first_intent())[1]
    _ = _run("checkpoint", stdin=_intent_json(orientation="Second."))
    orphan_path = store.projection_path(1, cast(str, first["revision_id"]))
    orphan_path.unlink()

    status, payload = _run("log", "--work-id", WORK_ID)

    assert status == 0
    revisions = cast(list[dict[str, object]], payload["revisions"])
    assert [r["revision_number"] for r in revisions] == [2]
    unreadable = cast(list[dict[str, str]], payload["unreadable"])
    assert len(unreadable) == 1
    assert unreadable[0]["path"] == store.revision_path(1, cast(str, first["revision_id"])).name
    assert "projection file is missing" in unreadable[0]["reason"]


@pytest.mark.usefixtures("store")
def test_cure_log_refuses_store_inconsistent_when_every_revision_is_lost(
    store: storage.WorkStore,
) -> None:
    first = _run("checkpoint", stdin=_first_intent())[1]
    second = _run("checkpoint", stdin=_intent_json(orientation="Second."))[1]
    _ = store.revision_path(1, cast(str, first["revision_id"])).write_text("not json", encoding="utf-8")
    _ = store.revision_path(2, cast(str, second["revision_id"])).write_text("not json", encoding="utf-8")

    status, payload = _run("log", "--work-id", WORK_ID)

    assert status != 0
    assert _error(payload)[0] == "store-inconsistent"


@pytest.mark.usefixtures("store")
def test_cure_validate_reports_the_next_action_gate_and_the_task_command_together() -> None:
    task = {
        "slug": "s", "intent": "cook", "repo": "r", "branch": "b", "branch_from": "main",
        "command": "rm -rf /",
    }
    status, payload = _run(
        "validate",
        stdin=_first_intent(next="affinage", artifact="x", tasks=[task]),
    )

    assert status == 1
    problems = cast(list[str], _get(payload, "error", "problems"))
    assert any("PR#" in p for p in problems)
    assert any("tasks[0].command is not a skill dispatch" in p for p in problems)


@pytest.mark.usefixtures("store")
def test_cure_ac7_a_non_gating_question_with_a_dossier_renders_open_entries() -> None:
    status, payload = _run(
        "checkpoint",
        stdin=_first_intent(
            entries=[{"kind": "question", "summary": "Bump or migrate?", "blocks_continuation": False}],
            decision_dossier=[
                {"fork": "f", "options": [{"option": "o", "evidence": ["e"], "breaks": "x"}], "prior_leaning": None}
            ],
        ),
    )

    assert status == 0, payload
    assert payload["status"] == "ok"
    assert "## Open entries" in cast(str, payload["markdown"])


def test_cure_turns_lines_escape_a_multiline_user_turn(tmp_path: Path) -> None:
    transcript = tmp_path / "s.jsonl"
    entries = [
        {"type": "user", "timestamp": "t1", "message": {"content": [{"type": "text", "text": "Line one.\nLine two."}]}},
    ]
    _ = transcript.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")

    status, payload = _run("turns", "--transcript", str(transcript))

    assert status == 0
    assert cast(list[dict[str, str]], payload["turns"]) == [{"timestamp": "t1", "text": "Line one.\nLine two."}]
    assert cast(list[str], payload["lines"]) == ["t1\tLine one.\\nLine two."]


@pytest.mark.usefixtures("store")
def test_cure_list_and_log_lines_are_the_escaped_tab_join_of_typed_rows() -> None:
    _ = _run("checkpoint", stdin=_first_intent(orientation="Tab\ttest line.\nSecond line."))

    status, payload = _run("list")
    assert status == 0
    items = cast(list[dict[str, object]], payload["items"])
    lines = cast(list[str], payload["lines"])
    assert items[0]["orientation"] == "Tab\ttest line."
    assert lines[0].split("\t")[-1] == "Tab\\ttest line."

    status, payload = _run("log", "--work-id", WORK_ID)
    assert status == 0
    revisions = cast(list[dict[str, object]], payload["revisions"])
    lines = cast(list[str], payload["lines"])
    row = lines[0].split("\t")
    assert row[0] == str(revisions[0]["revision_number"])
    assert row[1] == revisions[0]["revision_id"]


def test_cure_turns_lists_a_candidate_even_when_stat_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    cwd = tmp_path / "Dev" / "easy.cheese_x"
    cwd.mkdir(parents=True)
    projects = home / ".claude" / "projects" / str(cwd).replace("/", "-").replace(".", "-").replace("_", "-")
    projects.mkdir(parents=True)
    _transcript(projects / "aaa.jsonl")
    _transcript(projects / "bbb.jsonl")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(cwd)

    real_stat = Path.stat

    def flaky_stat(self: Path, *args: object, **kwargs: object) -> object:
        if self.name == "aaa.jsonl":
            raise OSError("boom")
        return real_stat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", flaky_stat)

    status, payload = _run("turns")

    assert (status, _error(payload)[0]) == (1, "session-required")
    candidates = cast(list[dict[str, object]], _get(payload, "error", "candidates"))
    assert len(candidates) == 2
    by_session = {cast(str, c["session"]): c["modified"] for c in candidates}
    assert by_session["aaa"] is None
    assert by_session["bbb"] is not None


@pytest.mark.usefixtures("store")
def test_cure_a_resumed_promotion_never_reuses_a_prior_note_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    _ = subprocess.run(["git", "init", "--quiet"], cwd=checkout, check=True)
    monkeypatch.chdir(checkout)
    prior = tmp_path / "prior-notes"
    body = _first_intent()

    real_clear = wheypoint._clear_pending  # pyright: ignore[reportPrivateUsage]

    def crash_once(_store: storage.WorkStore, _request_identity: str) -> None:
        monkeypatch.setattr(wheypoint, "_clear_pending", real_clear)
        raise RuntimeError("simulated crash before the ledger entry is cleared")

    monkeypatch.setattr(wheypoint, "_clear_pending", crash_once)
    interrupted_status, _interrupted = _run("checkpoint", "--note-dir", str(prior), stdin=body)
    assert interrupted_status == wheypoint.EXIT_INTERNAL

    default_notes = checkout / ".cheese" / "notes" / f"{WORK_ID}.md"
    status, payload = _run("checkpoint", stdin=body)

    assert status == 0
    assert payload["note_path"] == str(default_notes)
    assert default_notes.read_text(encoding="utf-8") == payload["markdown"]
