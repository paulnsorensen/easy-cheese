"""The age review lock refuses a report written over inline fixes (#552).

`/age` reviews and `/cure` applies. These tests drive the real seam — the
`review-lock` capture and the `write-handoff-artifact` command the age bundle
exposes — against real git work trees, so the assertions are about the
artifact that does or does not land on disk.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import cast

import pytest
from easy_cheese.shared import git_utils
from easy_cheese.skills.age import review_lock


def _git(repo: Path, *args: str) -> None:
    result = git_utils.run_git(list(args), cwd=repo)
    assert result.returncode == 0, result.stderr


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "--initial-branch=main", ".")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test")
    _ = (tmp_path / ".gitignore").write_text(".cheese/\n", encoding="utf-8")
    _ = (tmp_path / "app.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-m", "seed")
    return tmp_path


def _write_args(repo: Path, slug: str) -> list[str]:
    return [
        "--slug", slug,
        "--status", "ok",
        "--phase", "age",
        "--next", "cure",
        "--artifact", "",
        "--orientation", "reviewed the diff",
        "--root", str(repo),
    ]


def _report(repo: Path, slug: str) -> Path:
    return repo / ".cheese" / "age" / f"{slug}.md"


def test_lock_capture_records_digest_and_write_succeeds_on_an_untouched_tree(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert review_lock.main(["--slug", "demo", "--root", str(repo)]) == 0
    lock = review_lock.lock_path(root=repo, slug="demo")
    assert lock.read_text(encoding="utf-8").strip().startswith("{")
    payload = cast("dict[str, object]", json.loads(lock.read_text(encoding="utf-8")))
    assert payload["slug"] == "demo"
    digest = payload["digest"]
    assert isinstance(digest, str) and len(digest) == 64

    _ = capsys.readouterr()
    assert review_lock.gated_write_handoff_artifact(_write_args(repo, "demo")) == 0
    assert "next: cure" in _report(repo, "demo").read_text(encoding="utf-8")


def test_editing_a_tracked_file_after_the_lock_blocks_the_report_and_names_cure(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert review_lock.main(["--slug", "demo", "--root", str(repo)]) == 0
    _ = capsys.readouterr()

    # The exact defect: age "fixes" the reviewed file instead of routing to /cure.
    _ = (repo / "app.py").write_text("def add(a, b):\n    return int(a) + int(b)\n", encoding="utf-8")

    assert review_lock.gated_write_handoff_artifact(_write_args(repo, "demo")) == 2
    stderr = capsys.readouterr().err
    assert "production tree changed" in stderr
    assert "/cure" in stderr
    assert not _report(repo, "demo").exists()


def test_a_new_untracked_production_file_after_the_lock_blocks_the_report(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert review_lock.main(["--slug", "demo", "--root", str(repo)]) == 0
    _ = capsys.readouterr()
    _ = (repo / "patch.py").write_text("# applied inline\n", encoding="utf-8")

    assert review_lock.gated_write_handoff_artifact(_write_args(repo, "demo")) == 2
    assert "production tree changed" in capsys.readouterr().err
    assert not _report(repo, "demo").exists()


def test_editing_an_existing_untracked_file_after_the_lock_blocks_the_report(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    patch = repo / "patch.py"
    _ = patch.write_text("# pending review\n", encoding="utf-8")
    assert review_lock.main(["--slug", "demo", "--root", str(repo)]) == 0
    _ = capsys.readouterr()

    _ = patch.write_text("# applied inline\n", encoding="utf-8")

    assert review_lock.gated_write_handoff_artifact(_write_args(repo, "demo")) == 2
    assert "production tree changed" in capsys.readouterr().err
    assert not _report(repo, "demo").exists()


def test_writing_the_phases_own_scratch_directory_never_trips_the_lock(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert review_lock.main(["--slug", "demo", "--root", str(repo)]) == 0
    _ = capsys.readouterr()
    body = repo / ".cheese" / "age" / "demo-body.md"
    _ = body.write_text("# Age Report — demo\n", encoding="utf-8")

    args = [*_write_args(repo, "demo"), "--body-file", str(body)]
    assert review_lock.gated_write_handoff_artifact(args) == 0
    assert "# Age Report — demo" in _report(repo, "demo").read_text(encoding="utf-8")


def test_a_missing_lock_blocks_the_report_and_prints_the_capture_command(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert review_lock.gated_write_handoff_artifact(_write_args(repo, "demo")) == 2
    stderr = capsys.readouterr().err
    assert "no review lock for 'demo'" in stderr
    assert "review-lock --slug demo" in stderr
    assert not _report(repo, "demo").exists()


def test_another_slugs_lock_does_not_satisfy_this_report(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert review_lock.main(["--slug", "other", "--root", str(repo)]) == 0
    _ = capsys.readouterr()
    assert review_lock.gated_write_handoff_artifact(_write_args(repo, "demo")) == 2
    assert "no review lock for 'demo'" in capsys.readouterr().err


def test_reviewing_a_dirty_working_tree_locks_that_diff_not_head(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # The common case: age reviews uncommitted work. The lock must accept the
    # pre-existing diff and still reject a further edit to the same file.
    _ = (repo / "app.py").write_text("def add(a, b):\n    return a + b + 0\n", encoding="utf-8")
    assert review_lock.main(["--slug", "demo", "--root", str(repo)]) == 0
    _ = capsys.readouterr()
    assert review_lock.gated_write_handoff_artifact(_write_args(repo, "demo")) == 0

    _ = (repo / "app.py").write_text("def add(a, b):\n    return a + b + 1\n", encoding="utf-8")
    assert review_lock.gated_write_handoff_artifact(_write_args(repo, "demo")) == 2
    assert "production tree changed" in capsys.readouterr().err


def test_staging_a_fix_without_changing_the_worktree_still_trips_the_lock(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _ = (repo / "app.py").write_text("def add(a, b):\n    return a + b + 0\n", encoding="utf-8")
    _git(repo, "add", "app.py")
    assert review_lock.main(["--slug", "demo", "--root", str(repo)]) == 0
    _ = capsys.readouterr()
    _git(repo, "commit", "-m", "inline fix")

    assert review_lock.gated_write_handoff_artifact(_write_args(repo, "demo")) == 2
    assert "production tree changed" in capsys.readouterr().err


def test_a_malformed_lock_blocks_rather_than_silently_passing(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    lock = review_lock.lock_path(root=repo, slug="demo")
    lock.parent.mkdir(parents=True, exist_ok=True)
    _ = lock.write_text("{not json", encoding="utf-8")
    assert review_lock.gated_write_handoff_artifact(_write_args(repo, "demo")) == 2
    assert "unreadable review lock" in capsys.readouterr().err

    _ = lock.write_text(json.dumps({"slug": "demo", "digest": None}) + "\n", encoding="utf-8")
    assert review_lock.gated_write_handoff_artifact(_write_args(repo, "demo")) == 2
    assert "recorded no digest" in capsys.readouterr().err


def test_outside_a_git_work_tree_the_gate_degrades_to_a_no_op(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert review_lock.tree_digest(tmp_path) is None
    assert review_lock.gated_write_handoff_artifact(_write_args(tmp_path, "demo")) == 0
    assert _report(tmp_path, "demo").is_file()
    _ = capsys.readouterr()


def test_non_age_phases_are_not_gated(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    args = [
        "--slug", "demo", "--status", "ok", "--phase", "press", "--next", "age",
        "--artifact", "", "--orientation", "hardened", "--root", str(repo),
    ]
    assert review_lock.gated_write_handoff_artifact(args) == 0
    assert (repo / ".cheese" / "press" / "demo.md").is_file()
    _ = capsys.readouterr()


def test_lock_slug_rejects_path_traversal(repo: Path) -> None:
    assert review_lock.main(["--slug", "../escape", "--root", str(repo)]) == 2


def test_committed_age_bundle_exposes_the_review_lock_gate(repo: Path) -> None:
    bundle = Path(__file__).resolve().parents[2] / "skills" / "age" / "scripts" / "age.pyz"
    capture = subprocess.run(
        ["python3", str(bundle), "review-lock", "--slug", "demo", "--root", str(repo)],
        capture_output=True, text=True, cwd=str(repo),
    )
    assert capture.returncode == 0, capture.stderr
    assert review_lock.lock_path(root=repo, slug="demo").is_file()

    _ = (repo / "app.py").write_text("# inline fix\n", encoding="utf-8")
    blocked = subprocess.run(
        ["python3", str(bundle), "write-handoff-artifact", *_write_args(repo, "demo")],
        capture_output=True, text=True, cwd=str(repo),
    )
    assert blocked.returncode == 2, blocked.stdout
    assert "/cure" in blocked.stderr
    assert not _report(repo, "demo").exists()
