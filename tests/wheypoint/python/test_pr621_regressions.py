"""Regression contracts for the thirteen retained PR 621 findings."""

from __future__ import annotations

import hashlib
import io
import json
import tracemalloc
from pathlib import Path
from typing import cast

import pytest
from easy_cheese_schemas import EntryKind, ProposedEntry
from easy_cheese_schemas.compat import load
from easy_cheese.shared.handoff import HandoffSlug, parse_handoff_slug, render_handoff_slug
from easy_cheese.shared.wheypoint import projection, storage
from easy_cheese.skills.wheypoint import wheypoint


def _run(command: str, *args: str, **fields: object) -> tuple[int, dict[str, object]]:
    out = io.StringIO()
    status = wheypoint.main(
        [command, *args], stdin=io.StringIO(json.dumps(fields)), stdout=out
    )
    return status, cast(dict[str, object], json.loads(out.getvalue()))


def _intent(**fields: object) -> dict[str, object]:
    return {
        "work_id": "review-fixes",
        "orientation": "Continue the review.",
        "working_context": ["checkpoint.md"],
        "next": "hold",
        "notes": "Preserve the review.",
        **fields,
    }


def _task() -> dict[str, str]:
    return {
        "slug": "review",
        "intent": "Review the change. ",
        "repo": "/repo ",
        "worktree": "/worktree ",
        "branch": "review ",
        "branch_from": "main ",
        "command": "/age review ",
    }


def _error(reply: dict[str, object]) -> dict[str, object]:
    return cast(dict[str, object], reply["error"])


@pytest.fixture
def store(corpus_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> storage.WorkStore:
    _ = (tmp_path / "checkpoint.md").write_text("Review the checkpoint contract.\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    return storage.WorkStore.open("review-fixes", corpus_root=corpus_root)


@pytest.mark.parametrize("mode", [None, "parallel"])
@pytest.mark.parametrize("body", ["", "\n\n# Report\nBody"])
def test_b1_shared_mode_does_not_consume_orientation(mode: str | None, body: str) -> None:
    slug = HandoffSlug(
        status="ok", next_skill="hold", artifact=None, orientation="mode: parallel", mode=mode
    )
    rendered = render_handoff_slug(slug)
    expected = ["status: ok", "next: hold"]
    if mode is not None:
        expected.append("mode: parallel")
    expected.extend(["artifact: ", "mode: parallel"])
    assert rendered.splitlines() == expected
    assert parse_handoff_slug(rendered + body) == slug


@pytest.mark.parametrize("orientation", ["mode: parallel", "mode: parallel\nActual orientation", "mode: linear"])
@pytest.mark.parametrize("tasks", [False, True])
def test_b1_projection_preserves_mode_shaped_orientation(
    store: storage.WorkStore, orientation: str, tasks: bool
) -> None:
    fields = _intent(orientation=orientation)
    if tasks:
        fields.update(next="tasks", tasks=[_task()])
    status, reply = _run("checkpoint", "--no-note", **fields)
    assert status == 0, reply
    record = store.read_record()
    assert record is not None
    parsed = projection.parse(cast(str, reply["markdown"]))
    assert parsed.next_action == record.next_action
    assert store.recover().consistent


@pytest.mark.parametrize("prefix", ["sk-ant-api03-", "sk-proj-", "sk-svcacct-"])
def test_b2_credentials_refuse_validate_and_checkpoint(store: storage.WorkStore, prefix: str) -> None:
    value = prefix + "aB_9-" * 20
    for command in ("validate", "checkpoint"):
        status, reply = _run(command, **_intent(notes=value))
        assert status == 1, reply
        assert "credential" in cast(str, _error(reply)["message"])
        assert value not in json.dumps(reply)
    assert store.read_record() is None


@pytest.mark.parametrize("field", ["tasks", "parallel", "both"])
def test_b3_task_fields_without_next_refuse_without_a_revision(
    store: storage.WorkStore, field: str
) -> None:
    assert _run("checkpoint", "--no-note", **_intent())[0] == 0
    before = store.read_record()
    fields: dict[str, object] = {"work_id": store.work_id, "notes": "New instructions."}
    if field in {"tasks", "both"}:
        fields["tasks"] = [_task()]
    if field in {"parallel", "both"}:
        fields["parallel"] = {"isolation": "worktree", "worktree_strategy": "existing"}
    for command in ("validate", "checkpoint"):
        status, reply = _run(command, **fields)
        assert status == 1, reply
        assert "explicit next" in cast(str, _error(reply)["message"])
    assert store.read_record() == before
    assert len(store.revisions().files) == 1


@pytest.mark.parametrize("separator", ["\r", "\r\n", "\u0085", "\u2028", "\u2029", "\v", "\f", "\x1c", "\x1d", "\x1e"])
def test_b4_dossier_separators_survive_checkpoint_and_resolve(
    store: storage.WorkStore, separator: str
) -> None:
    text = f"A{separator}B"
    fork = {"fork": text, "options": [{"option": text, "evidence": [text], "breaks": text}], "prior_leaning": text}
    fields = _intent(decision_dossier=[fork])
    assert _run("validate", **fields)[0] == 0
    status, reply = _run("checkpoint", "--no-note", **fields)
    assert status == 0, reply
    record = store.read_record()
    assert record is not None
    revision = store.revisions().files[0]
    parsed = projection.parse(revision.projection_path.read_text(encoding="utf-8"))
    assert parsed.decision_dossier == record.decision_dossier
    assert store.recover().consistent
    status, resolved = _run("resolve", "--ref", store.work_id)
    assert status == 0, resolved
    assert resolved["outcome"] == "authoritative"
    assert resolved["findings"] == []


def test_b5_task_values_survive_exactly(store: storage.WorkStore) -> None:
    status, reply = _run(
        "checkpoint", "--no-note", **_intent(
            next="tasks", tasks=[_task()],
            parallel={"isolation": "worktree ", "worktree_strategy": "create", "worktree_root": "/root "},
        )
    )
    assert status == 0, reply
    record = store.read_record()
    assert record is not None
    assert projection.parse(cast(str, reply["markdown"])).next_action == record.next_action


def test_b6_phrase_mentions_remain_user_turns(tmp_path: Path) -> None:
    ordinary = [
        "Explain the phrase Base directory for this skill before you continue.",
        "Base directory for this skill needs clearer wording.",
        "Base directory for this skill: relative-path",
        "Base directory for this skill: /skills/review\nPlease preserve this user instruction.",
        "Base directory for this skill: /skills/review\n\nPlease preserve this user instruction.",
    ]
    texts = [
        "Base directory for this skill: /skills/review",
        "Base directory for this skill: /skills/review\n\n# Review",
        *ordinary,
    ]
    transcript = tmp_path / "synthetic.jsonl"
    _ = transcript.write_text("\n".join(
        json.dumps({"type": "user", "message": {"content": text}}) for text in texts
    ), encoding="utf-8")
    status, reply = _run("turns", "--transcript", str(transcript))
    assert status == 0, reply
    assert reply["count"] == len(ordinary)
    assert [turn["text"] for turn in cast(list[dict[str, str]], reply["turns"])] == ordinary


@pytest.mark.parametrize("fields", [{}, {"base_revision_id": "rev-0001"}, {"next": "hold"}])
def test_h1_validation_accepts_narrowed_updates_without_store(
    store: storage.WorkStore, fields: dict[str, object]
) -> None:
    status, reply = _run("validate", work_id=store.work_id, notes="Continue.", **fields)
    assert (status, reply.get("valid")) == (0, True), reply
    assert not store.root.exists()


@pytest.mark.parametrize("quote", [None, "", " "])
def test_h2_directives_require_quote_at_each_boundary(store: storage.WorkStore, quote: str | None) -> None:
    with pytest.raises(ValueError, match="quote"):
        _ = ProposedEntry(kind=EntryKind.DIRECTIVE, summary="Keep it simple.", quote=quote)
    entry = {"kind": "directive", "summary": "Keep it simple.", "quote": quote}
    loaded = load(entry, ProposedEntry, strict=True, forbid_unknown=True)
    assert loaded.value is None
    assert any("quote" in problem for problem in loaded.problems)
    status, reply = _run("checkpoint", **_intent(entries=[entry]))
    assert status == 1, reply
    assert "quote" in cast(str, _error(reply)["message"])
    assert store.read_record() is None


def test_h2_directive_quote_is_preserved(store: storage.WorkStore) -> None:
    quote = "Keep it simple."
    status, reply = _run("checkpoint", "--no-note", **_intent(
        entries=[{"kind": "directive", "summary": "Use simple code.", "quote": quote}]
    ))
    assert status == 0, reply
    record = store.read_record()
    assert record is not None
    assert record.directives[0].quote == quote
    assert quote in cast(str, reply["markdown"])


def test_m1_file_digest_uses_bounded_memory(tmp_path: Path) -> None:
    path = tmp_path / "large.bin"
    block = b"bounded-digest\x00" * 4096
    digest = hashlib.sha256()
    with path.open("wb") as stream:
        for _ in range(256):
            _ = stream.write(block)
            digest.update(block)
    tracemalloc.start()
    try:
        actual = storage.file_digest(path)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert actual == f"sha256:{digest.hexdigest()}"
    assert peak < 1024 * 1024
    assert storage.file_digest(tmp_path / "missing") is None
    assert storage.file_digest(tmp_path) is None


@pytest.mark.parametrize("extra", [{"bogus": 1}, {"bogus": 1, "entries": "invalid"}])
def test_m2_validation_keeps_independent_diagnostics(
    store: storage.WorkStore, extra: dict[str, object]
) -> None:
    status, reply = _run("validate", **_intent(
        next="affinage", artifact="not a PR", notes="sk-ant-api03-" + "a" * 40, **extra
    ))
    assert status == 1
    problems = cast(list[str], _error(reply)["problems"])
    assert any("bogus" in problem for problem in problems)
    assert any("PR#" in problem for problem in problems)
    assert any("credential" in problem for problem in problems)
    if "entries" in extra:
        assert any("entries" in problem for problem in problems)
    assert not store.root.exists()


def test_m3_log_refuses_missing_immutable_history(store: storage.WorkStore, corpus_root: Path) -> None:
    assert _run("checkpoint", "--no-note", **_intent())[0] == 0
    for revision in store.revisions().files:
        revision.path.unlink()
        revision.projection_path.unlink()
    status, reply = _run("log", "--work-id", store.work_id, "--corpus-root", str(corpus_root))
    assert (status, _error(reply)["code"]) == (1, "store-inconsistent")


@pytest.mark.parametrize("problem", ["json", "directory"])
def test_m3_log_maps_unreadable_record_without_history(
    store: storage.WorkStore, corpus_root: Path, capsys: pytest.CaptureFixture[str], problem: str
) -> None:
    store.record_path.parent.mkdir(parents=True)
    if problem == "json":
        _ = store.record_path.write_text("{", encoding="utf-8")
    else:
        store.record_path.mkdir()
    assert store.revisions().files == ()
    status, reply = _run("log", "--work-id", store.work_id, "--corpus-root", str(corpus_root))
    assert (status, _error(reply)["code"]) == (1, "record-unreadable")
    assert "Traceback" not in capsys.readouterr().err


@pytest.mark.parametrize("problem", ["json", "directory"])
def test_m4_show_maps_expected_read_failures(
    store: storage.WorkStore, capsys: pytest.CaptureFixture[str], problem: str
) -> None:
    store.record_path.parent.mkdir(parents=True)
    if problem == "json":
        _ = store.record_path.write_text("{", encoding="utf-8")
    else:
        store.record_path.mkdir()
    status, reply = _run("show", "--work-id", store.work_id)
    assert (status, _error(reply)["code"]) == (1, "record-unreadable")
    assert "Traceback" not in capsys.readouterr().err


def test_l1_reserved_field_guidance_names_current_checkpoint_options(store: storage.WorkStore) -> None:
    status, reply = _run("checkpoint", **_intent(expected_revision_id="rev-0001"))
    assert (status, _error(reply)["code"]) == (1, "commit-only-field")
    message = cast(str, _error(reply)["message"])
    assert "base_revision_id" in message
    assert "checkpoint --compacted" in message
    assert "with commit" not in message
    assert store.read_record() is None
