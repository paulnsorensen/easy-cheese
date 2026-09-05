"""The `checkpoint` command: an intent in, a bound revision out.

`checkpoint` exists to delete bookkeeping, so every test here is really one of
two questions: did the runtime bind something the caller used to have to write
down, and is the guarantee that used to depend on the caller writing it down
still enforced? The refusals matter as much as the successes -- a command that
quietly accepted a compaction claim or a stale base would be a simplification
that cost exactly what it was told not to.
"""

from __future__ import annotations

import io
import json
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import cast

import pytest
from easy_cheese_schemas import NextMove, WheypointRecord

from easy_cheese.skills.wheypoint import checkpoint, commit, storage, wheypoint

from conftest import WORK_ID

CAPTURED_AT = "2026-08-30T12:00:00Z"
DOSSIER = [
    {
        "fork": "Where the intent is bound",
        "options": [
            {
                "option": "runtime",
                "evidence": ["the caller cannot see the lock"],
                "breaks": "nothing: commit re-checks under it",
            }
        ],
        "prior_leaning": "runtime",
    }
]


def _run(command: str, *args: str, stdin: str = "") -> tuple[int, dict[str, object]]:
    out = io.StringIO()
    status = wheypoint.main([command, *args], stdin=io.StringIO(stdin), stdout=out)
    lines = out.getvalue().splitlines()
    assert len(lines) == 1, f"expected exactly one JSON line, got {lines!r}"
    return status, json.loads(lines[0])


def _intent(**overrides: object) -> str:
    payload: dict[str, object] = {"work_id": WORK_ID}
    payload.update(overrides)
    return json.dumps(payload)


def _first(**overrides: object) -> str:
    """A genesis intent: everything a first record cannot carry forward."""
    payload: dict[str, object] = {
        "orientation": "Bind the parent in the runtime.\nNot the title line.",
        "working_context": ["src/easy_cheese/skills/wheypoint/checkpoint.py"],
        "next": "cook",
        "artifact": ".cheese/cook/wheypoint-checkpoint.md",
        # AC-26: a first checkpoint must capture something beyond orientation.
        "notes": "First record.",
    }
    payload.update(overrides)
    return _intent(**payload)


def _get(container: object, *path: str) -> object:
    value = container
    for key in path:
        value = cast(dict[str, object], value)[key]
    return value


@pytest.fixture(autouse=True)
def _cwd_outside_a_repository(  # pyright: ignore[reportUnusedFunction]
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No git toplevel, so no note mirror is written into the checkout."""
    monkeypatch.chdir(tmp_path)


@pytest.fixture
def store(corpus_root: Path) -> storage.WorkStore:
    return storage.WorkStore.open(WORK_ID, corpus_root=corpus_root)


@pytest.fixture  # noqa: V103 -- side-effect fixture, injected via usefixtures
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    """A clock that never repeats, so a re-read is visible as a new request."""
    ticks = iter(f"2026-08-30T12:00:{second:02d}Z" for second in range(60))

    def _clock() -> str:
        return next(ticks)

    monkeypatch.setattr(checkpoint, "_utc_now", _clock)


@pytest.fixture
def genesis(store: storage.WorkStore) -> Iterator[dict[str, object]]:
    """One committed first record, and the payload that created it."""
    _ = store  # the corpus root must exist before the CLI runs
    status, payload = _run(
        "checkpoint", stdin=_first(session={"captured_at": CAPTURED_AT})
    )
    assert status == 0, payload
    yield payload


@pytest.mark.usefixtures("frozen_clock")
def test_checkpoint_creates_the_first_record_without_a_genesis_sentinel(
    store: storage.WorkStore,
) -> None:
    status, payload = _run("checkpoint", stdin=_first())

    assert status == 0, payload
    assert payload["ok"] is True
    assert payload["command"] == "checkpoint"
    assert payload["replayed"] is False
    assert payload["revision_number"] == 1
    # Genesis is inferred from the absent record, and the sentinel the caller
    # never wrote shows up as the receipt's null parent.
    assert payload["parent_revision_id"] is None
    assert _get(payload, "record", "next_action", "move") == "cook"
    assert (
        _get(payload, "record", "next_action", "artifact")
        == ".cheese/cook/wheypoint-checkpoint.md"
    )
    # The clock is read because genesis has no created time to carry forward.
    assert _get(payload, "record", "created") == "2026-08-30T12:00:00Z"
    assert _get(payload, "record", "title") == "Bind the parent in the runtime."
    assert store.read_record() is not None


def test_checkpoint_binds_the_current_revision_on_an_update(
    genesis: dict[str, object],
) -> None:
    status, payload = _run(
        "checkpoint", stdin=_intent(orientation="The kernel is unchanged.")
    )

    assert status == 0, payload
    assert payload["revision_number"] == 2
    assert payload["parent_revision_id"] == genesis["revision_id"]
    assert _get(payload, "record", "orientation") == "The kernel is unchanged."


@pytest.mark.usefixtures("frozen_clock")
def test_an_identical_update_replays_because_no_clock_was_read(
    genesis: dict[str, object],
) -> None:
    """A pinned base names no session, so its bytes do not move on a resubmit.

    The base has to be pinned for the request to stay the same request: an
    unpinned resubmission binds whatever revision is current by then, which is
    the one this call just wrote, and so describes a new checkpoint rather than
    the one already on disk.
    """
    intent = _intent(
        orientation="Resubmitted verbatim.",
        base_revision_id=cast(str, genesis["revision_id"]),
    )

    _, first = _run("checkpoint", stdin=intent)
    status, second = _run("checkpoint", stdin=intent)

    assert status == 0, second
    assert first["replayed"] is False
    assert second["replayed"] is True
    assert second["revision_id"] == first["revision_id"]
    assert second["revision_number"] == first["revision_number"]


@pytest.mark.usefixtures("frozen_clock", "genesis")
def test_a_named_session_reads_the_clock_and_so_does_not_replay() -> None:
    """Naming a harness makes the request session-specific on purpose."""
    intent = _intent(orientation="Stamped.", session={"harness": "claude"})

    _, first = _run("checkpoint", stdin=intent)
    status, second = _run("checkpoint", stdin=intent)

    assert status == 0, second
    assert second["replayed"] is False
    assert second["revision_number"] == 3
    assert _get(first, "revision", "session_provenance", "captured_at") != _get(
        second, "revision", "session_provenance", "captured_at"
    )


@pytest.mark.usefixtures("frozen_clock", "store")
def test_a_genesis_replay_needs_an_explicit_captured_at() -> None:
    """The documented cost of deriving genesis' created time from the clock."""
    unstamped = _first(base_revision_id=commit.GENESIS_PARENT)

    _, first = _run("checkpoint", stdin=unstamped)
    status, conflict = _run("checkpoint", stdin=unstamped)

    assert first["replayed"] is False
    assert status == 1
    assert _get(conflict, "error", "code") == "genesis-conflict"


@pytest.mark.usefixtures("frozen_clock", "store")
def test_a_genesis_carrying_captured_at_replays() -> None:
    stamped = _first(
        session={"captured_at": CAPTURED_AT},
        base_revision_id=commit.GENESIS_PARENT,
    )

    _, first = _run("checkpoint", stdin=stamped)
    status, second = _run("checkpoint", stdin=stamped)

    assert status == 0, second
    assert second["replayed"] is True
    assert second["revision_id"] == first["revision_id"]


@pytest.mark.usefixtures("genesis")
def test_a_concurrent_writer_still_loses_under_the_lock(
    store: storage.WorkStore,
) -> None:
    """Binding a parent outside the lock settles nothing, and must not.

    The delta is built against the record as it read a moment ago; another
    writer then moves the record on. `commit` re-checks the parent under the
    lock, so the bound delta is refused exactly as a hand-written one would be.
    """
    current = store.read_record()
    assert current is not None
    intent = checkpoint.CheckpointIntent(
        work_id=WORK_ID, orientation="Built against the record that was current."
    )
    delta = checkpoint.build_delta(intent, current)

    _, winner = _run("checkpoint", stdin=_intent(orientation="Got there first."))
    assert winner["revision_id"] != current.revision_id

    with pytest.raises(commit.StaleParentError) as raised:
        _ = commit.commit(delta, store=store)

    assert current.revision_id in str(raised.value)


def test_a_base_revision_id_that_is_not_current_refuses(
    genesis: dict[str, object],
) -> None:
    """A caller that did read the state can still be told it read a stale one."""
    _, _ = _run("checkpoint", stdin=_intent(orientation="Moves the record on."))

    status, payload = _run(
        "checkpoint",
        stdin=_intent(
            orientation="Built against the old one.",
            base_revision_id=cast(str, genesis["revision_id"]),
        ),
    )

    assert status == 1
    # The pinned base is passed through to the kernel, so the refusal is the
    # kernel's own -- checkpoint invents no second staleness check above it.
    assert _get(payload, "error", "code") == "stale-parent"
    assert cast(str, genesis["revision_id"]) in cast(
        str, _get(payload, "error", "message")
    )


def test_a_base_revision_id_that_is_current_is_accepted(
    genesis: dict[str, object],
) -> None:
    status, payload = _run(
        "checkpoint",
        stdin=_intent(
            orientation="Built against the current one.",
            base_revision_id=cast(str, genesis["revision_id"]),
        ),
    )

    assert status == 0, payload
    assert payload["parent_revision_id"] == genesis["revision_id"]


@pytest.mark.usefixtures("store")
def test_a_base_revision_id_on_work_with_no_record_refuses() -> None:
    status, payload = _run(
        "checkpoint", stdin=_first(base_revision_id="rev-000000000000")
    )

    assert status == 1
    # Pinning a revision that is not the genesis sentinel says the caller read
    # a record; there is none, so the kernel refuses rather than creating one.
    assert _get(payload, "error", "code") == "commit-refused"


@pytest.mark.parametrize(
    "field, value",
    [
        ("compacted", True),
        (
            "compaction",
            {
                "rehydrated_from_revision_id": "rev-000000000000",
                "rehydrated_record_digest": "sha256:" + "0" * 64,
                "reconciled_entry_ids": [],
                "reconciliation_source_session_ids": [],
            },
        ),
        ("expected_revision_id", "rev-000000000000"),
    ],
)
@pytest.mark.usefixtures("genesis")
def test_checkpoint_refuses_the_fields_that_belong_to_commit(
    field: str, value: object
) -> None:
    """Deriving a rehydration proof from the store would prove nothing.

    Unknown keys are dropped when an intent is structured, so a caller who
    reached for these would otherwise be told nothing at all while their proof
    was discarded.
    """
    status, payload = _run("checkpoint", stdin=_intent(**{field: value}))

    assert status == 1
    assert _get(payload, "error", "code") == "commit-only-field"
    message = cast(str, _get(payload, "error", "message"))
    assert field in message
    assert "commit" in message


@pytest.mark.usefixtures("store")
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("mode", "parallel"),
        ("tasks", [{"next": "cook", "artifact": "spec.md"}]),
        ("order", ["a", "b"]),
        ("baseline", {"suite": "pytest", "test_id": "t", "signature": "s"}),
        ("durable_flags", "--hard"),
    ],
)
def test_checkpoint_refuses_a_field_the_record_cannot_hold(
    field: str, value: object
) -> None:
    """Silence is the worst answer here.

    Structuring an intent drops an unknown key, so a caller who authored one of
    these would be told nothing while the data disappeared.
    """
    status, payload = _run("checkpoint", stdin=_first(**{field: value}))

    assert status == 1
    assert _get(payload, "error", "code") == "invalid-intent"
    message = cast(str, _get(payload, "error", "message"))
    assert field in message


@pytest.mark.usefixtures("store")
def test_omitted_protected_state_carries_forward() -> None:
    status, _ = _run(
        "checkpoint",
        stdin=_first(
            session={"captured_at": CAPTURED_AT},
            entries=[
                {"kind": "decision", "summary": "The kernel keeps every check."}
            ],
        ),
    )
    assert status == 0

    status, payload = _run("checkpoint", stdin=_intent(orientation="Says nothing else."))

    assert status == 0, payload
    decisions = cast(list[dict[str, object]], _get(payload, "record", "decisions"))
    assert [entry["summary"] for entry in decisions] == [
        "The kernel keeps every check."
    ]
    assert [entry["state"] for entry in decisions] == ["active"]
    # The working context and next action were not restated and were not lost.
    assert _get(payload, "record", "working_context") == [
        "src/easy_cheese/skills/wheypoint/checkpoint.py"
    ]
    assert _get(payload, "record", "next_action", "move") == "cook"
    assert (
        _get(payload, "record", "next_action", "artifact")
        == ".cheese/cook/wheypoint-checkpoint.md"
    )
    assert cast(list[str], _get(payload, "revision", "preserved_entry_ids"))


@pytest.mark.usefixtures("store")
def test_retirement_still_needs_a_caller_authored_transition() -> None:
    status, first = _run(
        "checkpoint",
        stdin=_first(
            session={"captured_at": CAPTURED_AT},
            entries=[
                {
                    "kind": "question",
                    "summary": "Does binding weaken the stale-writer check?",
                    "blocks_continuation": True,
                }
            ],
            decision_dossier=DOSSIER,
        ),
    )
    assert status == 0, first
    questions = cast(list[dict[str, object]], _get(first, "record", "questions"))
    entry_id = cast(str, questions[0]["entry_id"])
    assert first["status"] == "gated"

    status, payload = _run(
        "checkpoint",
        stdin=_intent(
            transitions=[
                {
                    "entry_id": entry_id,
                    "action": "resolve",
                    "rationale": "commit re-checks the parent under the lock.",
                }
            ],
            decision_dossier=[],
        ),
    )

    assert status == 0, payload
    resolved = cast(list[dict[str, object]], _get(payload, "record", "questions"))
    assert [entry["state"] for entry in resolved] == ["resolved"]
    assert [entry["rationale"] for entry in resolved] == [
        "commit re-checks the parent under the lock."
    ]
    # The gate is gone only because the transition said so, and the status is
    # derived from the entries rather than written by the caller.
    assert payload["status"] == "ok"


@pytest.mark.usefixtures("genesis")
def test_a_transition_without_a_rationale_is_not_a_retirement() -> None:
    status, payload = _run(
        "checkpoint",
        stdin=_intent(
            transitions=[{"entry_id": "q-nothing", "action": "resolve"}]
        ),
    )

    assert status == 1
    assert _get(payload, "error", "code") == "invalid-intent"


def test_a_gating_addition_derives_gated_status_and_a_projection(
    store: storage.WorkStore, tmp_path: Path
) -> None:
    notes = tmp_path / "notes"

    status, payload = _run(
        "checkpoint",
        "--note-dir",
        str(notes),
        stdin=_first(
            session={"captured_at": CAPTURED_AT},
            entries=[
                {
                    "kind": "blocker",
                    "summary": "The bundle manifest has not been regenerated.",
                    "blocks_continuation": True,
                }
            ],
            decision_dossier=DOSSIER,
        ),
    )

    assert status == 0, payload
    assert payload["status"] == "gated"
    gating = cast(list[dict[str, object]], _get(payload, "record", "blockers"))
    assert [entry["state"] for entry in gating] == ["active"]
    assert payload["durability"] == "repo-snapshot"
    revision_id = cast(str, payload["revision_id"])
    assert payload["projection_path"] == f"projections/1-{revision_id}.md"
    # The projection is generated, written to the store, and mirrored -- the
    # caller wrote no markdown and no status word.
    generated = cast(str, payload["markdown"])
    assert "status: gated" in generated
    assert "next: cook" in generated
    mirror = notes / f"{WORK_ID}.md"
    assert payload["note_path"] == str(mirror)
    assert mirror.read_text(encoding="utf-8") == generated
    assert (store.root / cast(str, payload["projection_path"])).read_text(
        encoding="utf-8"
    ) == generated
@pytest.mark.usefixtures("genesis")
def test_mirror_failure_then_retry_resumes_the_committed_revision(
    store: storage.WorkStore, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    notes = tmp_path / "notes"
    real_write_atomic = storage.write_atomic
    failed = False

    def fail_mirror_once(path: Path, payload: bytes) -> None:
        nonlocal failed
        if path.parent == notes and not failed:
            failed = True
            raise OSError("mirror is temporarily unavailable")
        real_write_atomic(path, payload)

    monkeypatch.setattr(storage, "write_atomic", fail_mirror_once)
    intent = _intent(
        entries=[
            {
                "kind": "question",
                "summary": "Can the mirror be retried?",
                "blocks_continuation": False,
            }
        ]
    )

    status, first = _run("checkpoint", "--note-dir", str(notes), stdin=intent)

    assert status == 1
    assert _get(first, "error", "code") == "note-unwritable"
    # The projection claims repo-snapshot durability, so a failed mirror must
    # leave no promoted record behind to carry that claim.
    committed = store.read_record()
    assert committed is not None
    assert committed.revision_number == 1
    assert committed.questions == []
    assert sorted(path.name for path in store.revisions_dir.glob("*.json")) == [
        f"1-{committed.revision_id}.json"
    ]
    assert not (notes / f"{WORK_ID}.md").exists()

    status, second = _run("checkpoint", "--note-dir", str(notes), stdin=intent)

    assert status == 0, second
    assert second["revision_number"] == 2
    assert second["replayed"] is False
    assert len(cast(list[dict[str, object]], _get(second, "record", "questions"))) == 1
    assert (notes / f"{WORK_ID}.md").read_text(encoding="utf-8") == second["markdown"]
    retried = store.read_record()
    assert retried is not None
    revision_files = sorted(path.name for path in store.revisions_dir.glob("*.json"))
    assert len(revision_files) == 2
    assert f"2-{retried.revision_id}.json" in revision_files

@pytest.mark.usefixtures("genesis")
def test_an_artifact_without_a_next_move_refuses() -> None:
    status, payload = _run("checkpoint", stdin=_intent(artifact=".cheese/x.md"))

    assert status == 1
    assert _get(payload, "error", "code") == "invalid-intent"
    assert "next" in cast(str, _get(payload, "error", "message"))


@pytest.mark.usefixtures("store")
def test_a_first_checkpoint_must_say_what_comes_next() -> None:
    status, payload = _run(
        "checkpoint", stdin=_intent(orientation="No next move.", working_context=[])
    )

    assert status == 1
    assert _get(payload, "error", "code") == "invalid-intent"


@pytest.mark.usefixtures("genesis")
def test_an_unknown_next_move_is_refused_as_an_intent() -> None:
    status, payload = _run("checkpoint", stdin=_intent(next="deploy"))

    assert status == 1
    assert _get(payload, "error", "code") == "invalid-intent"


def test_checkpoint_reports_a_work_id_that_is_not_a_path_segment() -> None:
    status, payload = _run("checkpoint", stdin=json.dumps({"work_id": "../escape"}))

    assert status == 1
    assert _get(payload, "error", "code") == "invalid-intent"


@pytest.mark.usefixtures("genesis")
def test_a_new_next_move_keeps_the_orientation_it_was_given() -> None:
    status, payload = _run(
        "checkpoint", stdin=_intent(next="age", orientation="Review the binding.")
    )

    assert status == 0, payload
    assert _get(payload, "record", "next_action", "move") == "age"
    assert _get(payload, "record", "next_action", "orientation") == (
        "Review the binding."
    )
    # No artifact was named, so the move now points at nothing rather than at
    # the artifact the previous move happened to be working on.
    assert _get(payload, "record", "next_action", "artifact") is None


def test_build_delta_carries_the_next_action_when_next_is_omitted(
    make_record: Callable[..., WheypointRecord],
) -> None:
    """The unit seam: an omitted move sends None, which the kernel reads as
    "unchanged" -- checkpoint invents no NextAction to restate it with."""
    delta = checkpoint.build_delta(
        checkpoint.CheckpointIntent(work_id=WORK_ID, orientation="Only this."),
        make_record(),
    )

    assert delta.next_action is None
    assert delta.expected_revision_id == "rev-0001"
    assert delta.session_provenance is None


def test_build_delta_names_the_genesis_sentinel_itself() -> None:
    delta = checkpoint.build_delta(
        checkpoint.CheckpointIntent(
            work_id=WORK_ID, orientation="First.", next=NextMove.MOLD
        ),
        None,
        now=lambda: CAPTURED_AT,
    )

    assert delta.expected_revision_id == commit.GENESIS_PARENT
    assert delta.session_provenance is not None
    assert delta.session_provenance.captured_at == CAPTURED_AT


def test_commit_only_fields_reports_them_in_a_stable_order() -> None:
    assert checkpoint.commit_only_fields(
        {"compaction": {}, "expected_revision_id": "rev-1", "work_id": WORK_ID}
    ) == ("expected_revision_id", "compaction")
    assert checkpoint.commit_only_fields(["not", "a", "mapping"]) == ()


def test_the_checkpoint_command_is_registered_for_the_bundle() -> None:
    """The dispatcher reads the subcommand from argv[0]; both lists must agree."""
    from easy_cheese.skills.wheypoint import commands

    assert "checkpoint" in wheypoint.COMMANDS
    # The bundle also registers the shared `handoff` command, which is not a runner here.
    assert [command.name for command in commands.COMMANDS] == [*wheypoint.COMMANDS, "handoff"]
