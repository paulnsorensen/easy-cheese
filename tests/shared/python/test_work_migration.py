from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[3] / "shared" / "scripts"))
import work  # noqa: E402


@pytest.fixture(autouse=True)
def work_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("EASY_CHEESE_PROJECT", "test-project")


def test_export_and_local_import_preserve_identity(tmp_path: Path) -> None:
    record = work.ensure_work(subject="Ship cheese", worktree="wt_one")
    assert record
    snapshot = work.export_work_snapshot(record.work_id, 0, tmp_path)
    work.work_record_path(record.work_id).unlink()
    imported = work.load_work(record.work_id, repo_root=tmp_path)
    assert snapshot.exists()
    assert imported.work_id == record.work_id


def test_divergent_snapshot_requires_reconciliation(tmp_path: Path) -> None:
    record = work.ensure_work(subject="Ship cheese", worktree="wt_one")
    assert record
    snapshot = work.export_work_snapshot(record.work_id, 0, tmp_path)
    snapshot.write_text(snapshot.read_text().replace("Ship cheese", "Different"), encoding="utf-8")
    with pytest.raises(ValueError, match="divergent"):
        work.load_work(record.work_id, repo_root=tmp_path)


def test_malformed_legacy_file_is_untouched(tmp_path: Path) -> None:
    legacy = tmp_path / "legacy.json"
    legacy.write_text("{broken", encoding="utf-8")
    result = work.migrate_legacy([legacy])
    assert result == {"migrated": [], "skipped": [str(legacy)]}
    assert legacy.read_text(encoding="utf-8") == "{broken"
