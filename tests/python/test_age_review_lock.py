"""The age review lock refuses a report written over inline fixes (#552).

`/age` reviews and `/cure` applies. These tests drive the real seam — the
`review-lock` capture and the `write-handoff-artifact` command the age bundle
exposes — against real git work trees, so the assertions are about the
artifact that does or does not land on disk.
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import pytest
from easy_cheese.shared import cli, git_utils
from easy_cheese.skills.age import review_lock


def _git(repo: Path, *args: str) -> None:
    result = git_utils.run_git(list(args), cwd=repo)
    assert result.returncode == 0, result.stderr


@pytest.fixture(autouse=True)
def isolated_corpus_home(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep wheypoint revisions out of the shared durable store; parallel tests race on one slug there."""
    monkeypatch.setenv("EASY_CHEESE_HOME", str(tmp_path_factory.mktemp("corpus-home")))


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "--initial-branch=main", ".")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test")
    _ = (tmp_path / ".gitignore").write_text(".cheese/\n", encoding="utf-8")
    _ = (tmp_path / "app.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-m", "seed")
    grounded = tmp_path / ".cheese" / "grounded.md"
    grounded.parent.mkdir(parents=True)
    _ = grounded.write_text("grounded context\n", encoding="utf-8")
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
        "--grounded", ".cheese/grounded.md#1-1",
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


def _write_late_packet(repo: Path) -> None:
    packet = repo / ".cheese" / "age" / "demo-packet.md"
    packet.parent.mkdir(parents=True, exist_ok=True)
    _ = packet.write_text("# packet written after the lock\n", encoding="utf-8")


def test_a_late_packet_is_named_as_evidence_and_not_as_a_production_change(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert review_lock.main(["--slug", "demo", "--root", str(repo)]) == 0
    _ = capsys.readouterr()
    _write_late_packet(repo)

    assert review_lock.gated_write_handoff_artifact(_write_args(repo, "demo")) == 2
    stderr = capsys.readouterr().err
    assert "review evidence changed" in stderr
    assert ".cheese/age/demo-packet.md" in stderr
    assert "--refresh-evidence" in stderr
    assert "production tree changed" not in stderr
    assert not _report(repo, "demo").exists()


def test_refresh_evidence_lets_the_report_write_after_a_late_packet(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert review_lock.main(["--slug", "demo", "--root", str(repo)]) == 0
    _write_late_packet(repo)

    refresh = ["--slug", "demo", "--root", str(repo), "--refresh-evidence"]
    assert review_lock.main(refresh) == 0
    _ = capsys.readouterr()
    assert review_lock.gated_write_handoff_artifact(_write_args(repo, "demo")) == 0
    assert _report(repo, "demo").is_file()


def test_refresh_evidence_refuses_when_a_source_file_also_moved(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    lock = review_lock.lock_path(root=repo, slug="demo")
    assert review_lock.main(["--slug", "demo", "--root", str(repo)]) == 0
    locked = lock.read_text(encoding="utf-8")
    _write_late_packet(repo)
    _ = (repo / "app.py").write_text("def add(a, b):\n    return 0\n", encoding="utf-8")
    _ = capsys.readouterr()

    refresh = ["--slug", "demo", "--root", str(repo), "--refresh-evidence"]
    assert review_lock.main(refresh) == 2
    stderr = capsys.readouterr().err
    assert "refresh is refused" in stderr
    assert "/cure" in stderr
    assert lock.read_text(encoding="utf-8") == locked
    assert review_lock.gated_write_handoff_artifact(_write_args(repo, "demo")) == 2
    assert "production tree changed" in capsys.readouterr().err


def test_refresh_evidence_needs_an_existing_lock_with_a_source_digest(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    refresh = ["--slug", "demo", "--root", str(repo), "--refresh-evidence"]
    assert review_lock.main(refresh) == 2
    assert "no review lock" in capsys.readouterr().err

    lock = review_lock.lock_path(root=repo, slug="demo")
    lock.parent.mkdir(parents=True, exist_ok=True)
    _ = lock.write_text(json.dumps({"slug": "demo", "digest": "0" * 64}), encoding="utf-8")
    assert review_lock.main(refresh) == 2
    assert "recorded no source digest" in capsys.readouterr().err


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
    grounded = tmp_path / ".cheese" / "grounded.md"
    grounded.parent.mkdir(parents=True)
    _ = grounded.write_text("grounded context\n", encoding="utf-8")
    assert review_lock.tree_digest(tmp_path, slug="demo") is None
    assert review_lock.gated_write_handoff_artifact(_write_args(tmp_path, "demo")) == 0
    assert _report(tmp_path, "demo").is_file()
    _ = capsys.readouterr()


def test_non_age_phases_are_not_gated(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    args = [
        "--slug", "demo", "--status", "ok", "--phase", "press", "--next", "age",
        "--artifact", "", "--orientation", "hardened", "--root", str(repo),
        "--grounded", ".cheese/grounded.md#1-1",
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
    stderr = capsys.readouterr().err
    assert "review evidence changed" in stderr
    assert ".cheese/age/demo-packet.md" in stderr
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
    stderr = capsys.readouterr().err
    assert "review evidence changed" in stderr
    assert ".cheese/age/other.md" in stderr


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


def test_a_slug_inside_quoted_free_text_never_reaches_the_writer(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # The gate and the writer read one argv. Free text is never split, so a slug
    # inside `--orientation` cannot name a report that the gate did not check.
    args = [
        token
        for token in _write_args(repo, "demo")
        if token not in ("--slug", "demo", "reviewed the diff")
    ]
    args.insert(args.index("--orientation") + 1, "done --slug demo")
    with pytest.raises(SystemExit) as raised:
        _ = review_lock.gated_write_handoff_artifact(args)
    assert raised.value.code == 2
    assert "--slug" in capsys.readouterr().err
    assert not _report(repo, "demo").exists()


def test_refresh_rejects_changed_prior_evidence(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    packet = repo / ".cheese" / "age" / "demo-packet.md"
    packet.parent.mkdir(parents=True, exist_ok=True)
    _ = packet.write_text("original\n", encoding="utf-8")
    assert review_lock.main(["--slug", "demo", "--root", str(repo)]) == 0
    locked = review_lock.lock_path(root=repo, slug="demo").read_text(encoding="utf-8")

    _ = packet.write_text("changed\n", encoding="utf-8")
    refresh = ["--slug", "demo", "--root", str(repo), "--refresh-evidence"]
    assert review_lock.main(refresh) == 2
    assert "refresh is refused" in capsys.readouterr().err
    assert review_lock.lock_path(root=repo, slug="demo").read_text(encoding="utf-8") == locked


def test_refresh_rejects_an_unexpected_new_evidence_file(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert review_lock.main(["--slug", "demo", "--root", str(repo)]) == 0
    unexpected = repo / ".cheese" / "age" / "other-packet.md"
    unexpected.parent.mkdir(parents=True, exist_ok=True)
    _ = unexpected.write_text("not the current packet\n", encoding="utf-8")
    refresh = ["--slug", "demo", "--root", str(repo), "--refresh-evidence"]
    assert review_lock.main(refresh) == 2
    assert ".cheese/age/other-packet.md" in capsys.readouterr().err


def test_source_digest_ignores_evidence_only_commit(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert review_lock.main(["--slug", "demo", "--root", str(repo)]) == 0
    before = review_lock.tree_digest(repo, slug="demo", evidence=False)
    evidence = repo / ".cheese" / "age" / "committed.md"
    _ = evidence.write_text("committed evidence\n", encoding="utf-8")
    _git(repo, "add", "-f", str(evidence.relative_to(repo)))
    _git(repo, "commit", "-m", "evidence")
    assert review_lock.tree_digest(repo, slug="demo", evidence=False) == before
    _ = capsys.readouterr()


def test_lock_parser_rejects_invalid_optional_fields(repo: Path) -> None:
    lock = review_lock.lock_path(root=repo, slug="demo")
    lock.parent.mkdir(parents=True, exist_ok=True)
    _ = lock.write_text(json.dumps({"slug": "demo", "digest": "0" * 64, "source_digest": 3}), encoding="utf-8")
    with pytest.raises(cli.CliError, match="invalid source_digest"):
        review_lock.verify(root=repo, slug="demo")


def test_evidence_mode_change_is_named(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    packet = repo / ".cheese" / "age" / "demo-packet.md"
    packet.parent.mkdir(parents=True, exist_ok=True)
    _ = packet.write_text("packet\n", encoding="utf-8")
    assert review_lock.main(["--slug", "demo", "--root", str(repo)]) == 0
    _ = capsys.readouterr()
    packet.chmod(0o755)
    assert review_lock.gated_write_handoff_artifact(_write_args(repo, "demo")) == 2
    stderr = capsys.readouterr().err
    assert "review evidence changed" in stderr
    assert ".cheese/age/demo-packet.md" in stderr


def test_non_utf8_evidence_path_is_named_without_loss(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    packet = repo / ".cheese" / "age"
    packet.mkdir(parents=True, exist_ok=True)
    raw_name = os.fsdecode(b"demo-\xff-packet.md")
    evidence = packet / raw_name
    try:
        _ = evidence.write_text("packet\n", encoding="utf-8")
    except OSError as exc:
        pytest.skip(f"filesystem rejects non-UTF-8 names: {exc}")
    assert review_lock.main(["--slug", "demo", "--root", str(repo)]) == 0
    _ = capsys.readouterr()
    _ = evidence.write_text("changed\n", encoding="utf-8")
    assert review_lock.gated_write_handoff_artifact(_write_args(repo, "demo")) == 2
    assert "\\xff" in capsys.readouterr().err


def test_surrogate_path_diagnostic_is_safe_for_strict_utf8(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw_name = os.fsdecode(b".cheese/age/demo-\xff-packet.md")
    @dataclass(frozen=True)
    class StubLock:
        digest: str
        source_digest: str
        evidence_files: dict[str, str]

    lock = StubLock("locked", "source", {raw_name: "old"})

    def read_lock(_target: Path, _slug: str) -> StubLock:
        return lock

    def tree_digest(_root: Path, slug: str, evidence: bool = True) -> str:
        _ = slug
        return "current" if evidence else "source"

    def evidence_files(_root: Path, _slug: str) -> dict[str, str]:
        return {raw_name: "new"}

    monkeypatch.setattr(review_lock, "_read_lock", read_lock)
    monkeypatch.setattr(review_lock, "tree_digest", tree_digest)
    monkeypatch.setattr(review_lock, "_evidence_files", evidence_files)
    output = io.BytesIO()
    stderr = io.TextIOWrapper(output, encoding="utf-8", errors="strict")
    monkeypatch.setattr(sys, "stderr", stderr)

    assert review_lock.gated_write_handoff_artifact(_write_args(repo, "demo")) == 2
    stderr.flush()
    assert b"\\xff" in output.getvalue()
