from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[3] / "shared" / "scripts"))
import work  # noqa: E402
import handoff  # noqa: E402


@pytest.fixture(autouse=True)
def work_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("EASY_CHEESE_PROJECT", "test-project")


def test_empty_subject_creates_no_work() -> None:
    assert work.ensure_work(subject="  ", worktree="wt_one") is None


def test_join_reuses_blocked_attempt() -> None:
    record = work.ensure_work(subject="Ship cheese", worktree="wt_one")
    assert record is not None
    attempt = record.attempts[0]
    blocked = work.transition_attempt(
        record.work_id, 0, {"attempt_id": attempt.attempt_id, "target_status": "blocked", "reason": "waiting"}, "op_block"
    )
    joined = work.ensure_work(blocked.work_id, worktree="wt_one")
    assert len(joined.attempts) == 1
    assert joined.attempts[0].status == "blocked"


def test_stale_patch_does_not_mutate() -> None:
    record = work.ensure_work(subject="Ship cheese", worktree="wt_one")
    assert record is not None
    with pytest.raises(ValueError, match="stale"):
        work.patch_work(record.work_id, 1, "work", {"scope": "work", "changes": []}, operation_id="op_stale")
    assert work.load_work(record.work_id).revision == 0


def test_patch_scope_is_explicit_and_matches_api() -> None:
    record = work.ensure_work(subject="Scoped patch", worktree="wt_one")
    assert record is not None
    with pytest.raises(ValueError, match="invalid work patch"):
        work.patch_work(record.work_id, 0, "attempt", {"changes": []}, operation_id="op_omitted")
    with pytest.raises(ValueError, match="invalid work patch"):
        work.patch_work(
            record.work_id,
            0,
            "attempt",
            {"scope": "work", "changes": []},
            attempt_id=record.attempts[0].attempt_id,
            operation_id="op_mismatch",
        )
    assert work.load_work(record.work_id).revision == 0


def test_prepared_patch_reconciles_recorded_result_once(monkeypatch: pytest.MonkeyPatch) -> None:
    record = work.ensure_work(subject="Recover patch", worktree="wt_one")
    assert record is not None
    original = work._write_journal

    def fail_completion(path: Path, entry: dict) -> None:
        if entry.get("kind") == "work-mutation" and entry.get("complete"):
            raise OSError("journal completion failed")
        original(path, entry)

    monkeypatch.setattr(work, "_write_journal", fail_completion)
    with pytest.raises(OSError, match="journal completion failed"):
        work.patch_work(
            record.work_id,
            0,
            "work",
            {
                "scope": "work",
                "changes": [{"section": "working_context", "operation": "append", "value": "once"}],
            },
            operation_id="op_recover_patch",
        )
    monkeypatch.setattr(work, "_write_journal", original)

    result = work.reconcile_work(record.work_id)
    saved = work.load_work(record.work_id, include_local=False)
    assert len(result["reconciled"]) == 1
    assert saved.revision == 1
    assert saved.working_context == "once"


def test_continuation_is_deterministic() -> None:
    first = work.ensure_work(subject="Beta", worktree="wt_one")
    second = work.ensure_work(subject="Alpha", worktree="wt_one")
    assert first and second
    resolved = work.resolve_continue(worktree="wt_one")
    assert resolved["action"] == "picker"
    assert [item["title"] for item in resolved["records"]] == ["Alpha", "Beta"]


def test_abandon_and_reopen() -> None:
    record = work.ensure_work(subject="Ship cheese", worktree="wt_one")
    assert record
    abandoned = work.abandon_work(record.work_id, 0, "cancelled", "op_abandon")
    assert abandoned.status == "abandoned"
    reopened = work.reopen_work(record.work_id, 1, "wt_one", "op_reopen")
    assert reopened.status == "active"


def test_continue_imports_local_snapshot_and_rejects_divergence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    record = work.ensure_work(subject="Local work", worktree="wt_one")
    assert record
    snapshot = work.local_work_snapshot_path(record.work_id)
    work._save(record, snapshot)
    work.work_record_path(record.work_id).unlink()
    resolved = work.resolve_continue(worktree="wt_one")
    assert resolved["action"] == "continue"
    assert resolved["records"][0]["work_id"] == record.work_id
    assert work.work_record_path(record.work_id).is_file()

    durable = work.ensure_work(subject="Durable work", worktree="wt_two")
    assert durable
    divergent = work.local_work_snapshot_path(durable.work_id)
    changed = work.load_work(durable.work_id, include_local=False)
    changed.title = "Changed locally"
    work._save(changed, divergent)
    with pytest.raises(ValueError, match="divergent"):
        work.resolve_continue(worktree="wt_two")


def test_work_record_uses_json_frontmatter() -> None:
    record = work.ensure_work(subject="Readable JSON", worktree="wt_one")
    assert record is not None
    text = work.work_record_path(record.work_id).read_text(encoding="utf-8")
    frontmatter = text.removeprefix("---\n").split("\n---\n", 1)[0]
    assert json.loads(frontmatter) == record.to_mapping()


def test_legacy_handoff_migration_writes_validated_envelope(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "legacy-handoff.md"
    source.write_text("status: ok\nnext: [cook, press]\nartifact:\norientation\n# Body\n")
    monkeypatch.setattr(work, "worktree_key", lambda: "wt_test")
    result = work.migrate_legacy([source])
    assert result["migrated"] == [str(source)]
    index = next(work.work_record_path("placeholder").parents[1].glob("wk_*/index.md"))
    record = work.load_work(index.parent.name)
    artifact = Path(record.attempts[0].artifacts[0]["path"])
    envelope = handoff.parse_handoff(artifact.read_text(), artifact)
    assert envelope.next == "tasks"
    assert envelope.provenance["legacy"] == {
        "source_path": str(source.resolve()), "status": "status: ok", "next": "[cook, press]"
    }
    assert [task["phase"] for task in record.tasks] == ["cook", "press"]
    assert source.is_file()
