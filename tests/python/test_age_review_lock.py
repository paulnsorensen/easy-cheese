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
from easy_cheese.shared import cli, git_utils
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


def test_different_clean_commits_have_different_lock_digests(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert review_lock.main(["--slug", "before", "--root", str(repo)]) == 0
    first_payload = cast(
        "dict[str, object]",
        json.loads(
            review_lock.lock_path(root=repo, slug="before").read_text(encoding="utf-8")
        ),
    )
    first_digest = first_payload["digest"]
    assert isinstance(first_digest, str)
    _ = capsys.readouterr()

    _ = (repo / "app.py").write_text(
        "def add(a, b):\n    return a + b + 1\n", encoding="utf-8"
    )
    _git(repo, "add", "app.py")
    _git(repo, "commit", "-m", "change")

    assert review_lock.main(["--slug", "after", "--root", str(repo)]) == 0
    second_payload = cast(
        "dict[str, object]",
        json.loads(
            review_lock.lock_path(root=repo, slug="after").read_text(encoding="utf-8")
        ),
    )
    second_digest = second_payload["digest"]
    assert isinstance(second_digest, str)
    assert first_digest != second_digest


def test_mutating_a_review_spec_changes_the_lock_digest(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    spec = repo / ".cheese" / "specs" / "demo.md"
    spec.parent.mkdir(parents=True)
    _ = spec.write_text("# Demo\n\nInitial requirements.\n", encoding="utf-8")
    assert review_lock.main(["--slug", "demo", "--root", str(repo)]) == 0
    first_payload = cast(
        "dict[str, object]",
        json.loads(
            review_lock.lock_path(root=repo, slug="demo").read_text(encoding="utf-8")
        ),
    )
    first_digest = first_payload["digest"]
    assert isinstance(first_digest, str)
    _ = capsys.readouterr()

    _ = spec.write_text("# Demo\n\nRevised requirements.\n", encoding="utf-8")
    assert review_lock.main(["--slug", "demo", "--root", str(repo)]) == 0
    second_payload = cast(
        "dict[str, object]",
        json.loads(
            review_lock.lock_path(root=repo, slug="demo").read_text(encoding="utf-8")
        ),
    )
    second_digest = second_payload["digest"]
    assert isinstance(second_digest, str)
    assert first_digest != second_digest


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
    assert review_lock.tree_digest(tmp_path, slug="demo") is None
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


def test_a_configured_textconv_filter_never_runs_during_the_lock(repo: Path) -> None:
    """A repository under review must not execute commands as the reviewer."""
    marker = repo / "textconv-ran"
    _ = (repo / ".gitattributes").write_text("*.py diff=probe\n", encoding="utf-8")
    _git(repo, "add", ".gitattributes")
    _git(repo, "commit", "-m", "attributes")
    _git(repo, "config", "diff.probe.textconv", f"touch {marker} && cat")
    _ = (repo / "app.py").write_text("def add(a, b):\n    return a\n", encoding="utf-8")

    assert review_lock.main(["--slug", "demo", "--root", str(repo)]) == 0
    assert not marker.exists()


def test_a_git_failure_fails_closed_instead_of_disabling_the_gate(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A probe that cannot answer must not read as "no repository"."""
    missing = repo / "gone"
    with pytest.raises(cli.CliError):
        _ = review_lock.tree_digest(missing, slug="demo")
    assert review_lock.gated_write_handoff_artifact(_write_args(missing, "demo")) == 2
    assert not (missing / ".cheese" / "age" / "demo.md").exists()
    _ = capsys.readouterr()


def test_staged_content_counts_before_the_first_commit(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """With no HEAD, plain `git diff` hides the index; the digest must not."""
    _git(tmp_path, "init", "--initial-branch=main", ".")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test")
    _ = (tmp_path / ".gitignore").write_text(".cheese/\n", encoding="utf-8")
    source = tmp_path / "app.py"
    _ = source.write_text("original\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")

    first = review_lock.tree_digest(tmp_path, slug="demo")
    _ = source.write_text("inline fix\n", encoding="utf-8")
    _git(tmp_path, "add", "app.py")

    assert review_lock.tree_digest(tmp_path, slug="demo") != first
    _ = capsys.readouterr()


def test_changing_the_fan_out_packet_after_the_lock_blocks_the_report(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The packet is review evidence, so it may not move under a live lock."""
    packet = repo / ".cheese" / "age" / "demo-packet.md"
    packet.parent.mkdir(parents=True, exist_ok=True)
    _ = packet.write_text("# packet\n\noriginal evidence\n", encoding="utf-8")
    assert review_lock.main(["--slug", "demo", "--root", str(repo)]) == 0
    _ = capsys.readouterr()

    _ = packet.write_text("# packet\n\nrewritten evidence\n", encoding="utf-8")

    assert review_lock.gated_write_handoff_artifact(_write_args(repo, "demo")) == 2
    assert "production tree changed" in capsys.readouterr().err
    assert not _report(repo, "demo").exists()


def test_another_slugs_report_still_counts_as_production_state(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    other = repo / ".cheese" / "age" / "other.md"
    other.parent.mkdir(parents=True, exist_ok=True)
    _ = other.write_text("# Age Report — other\n", encoding="utf-8")
    assert review_lock.main(["--slug", "demo", "--root", str(repo)]) == 0
    _ = capsys.readouterr()

    _ = other.write_text("# Age Report — other\n\nedited\n", encoding="utf-8")

    assert review_lock.gated_write_handoff_artifact(_write_args(repo, "demo")) == 2
    assert "production tree changed" in capsys.readouterr().err


def test_the_lock_resolves_the_repository_root_from_a_nested_directory(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    nested = repo / "src" / "deep"
    nested.mkdir(parents=True)
    _ = (nested / "mod.py").write_text("VALUE = 1\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "nested")

    assert review_lock.main(["--slug", "demo", "--root", str(nested)]) == 0
    assert review_lock.lock_path(root=repo, slug="demo").is_file()
    _ = capsys.readouterr()

    assert review_lock.gated_write_handoff_artifact(_write_args(repo, "demo")) == 0

    _ = (nested / "mod.py").write_text("VALUE = 2\n", encoding="utf-8")
    assert review_lock.gated_write_handoff_artifact(_write_args(repo, "demo")) == 2
    assert "production tree changed" in capsys.readouterr().err


def test_a_symlinked_lock_directory_is_refused(repo: Path, tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    scratch = repo / ".cheese"
    scratch.mkdir(exist_ok=True)
    (scratch / "age").symlink_to(outside, target_is_directory=True)

    with pytest.raises(cli.CliError, match="symlink"):
        _ = review_lock.lock_path(root=repo, slug="demo")
    assert review_lock.main(["--slug", "demo", "--root", str(repo)]) == 2
    assert not (outside / f"demo{review_lock.LOCK_SUFFIX}").exists()
