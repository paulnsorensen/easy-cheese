"""Legacy-note lookup: every worktree, no recency, exact searched locations."""

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

from easy_cheese.skills.wheypoint import legacy


def write_note(root: Path, slug: str, body: str = "legacy body\n") -> Path:
    path = root.joinpath(*legacy.NOTES_DIR_PARTS, f"{slug}.md")
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(body, encoding="utf-8")
    return path


def porcelain(*roots: Path, bare: Path | None = None) -> str:
    blocks: list[str] = []
    if bare is not None:
        blocks.append(f"worktree {bare}\nbare\n")
    blocks.extend(
        f"worktree {root}\nHEAD 0123456789abcdef0123456789abcdef01234567\n"
        + f"branch refs/heads/wt-{index}\n"
        for index, root in enumerate(roots)
    )
    return "\n".join(blocks)


class _FakeRunner:
    calls: list[tuple[tuple[str, ...], Path]]
    _output: str | None

    def __init__(self, output: str | None) -> None:
        self.calls = []
        self._output = output

    def __call__(self, args: Sequence[str], cwd: Path) -> str | None:
        self.calls.append((tuple(args), cwd))
        return self._output


def fake_runner(output: str | None) -> _FakeRunner:
    return _FakeRunner(output)


def test_parse_worktree_list_keeps_working_trees_and_drops_bare(tmp_path: Path) -> None:
    main = tmp_path / "main"
    linked = tmp_path / "wt"
    text = porcelain(main, linked, bare=tmp_path / "bare.git")

    assert legacy.parse_worktree_list(text) == (main, linked)


def test_worktree_roots_puts_start_first_then_sorted_siblings(tmp_path: Path) -> None:
    start = tmp_path / "b-start"
    for name in ("b-start", "a-sib", "c-sib"):
        (tmp_path / name).mkdir()
    run = fake_runner(
        porcelain(tmp_path / "c-sib", tmp_path / "b-start", tmp_path / "a-sib")
    )

    scan = legacy.worktree_roots(start, run=run)

    assert scan.roots == (
        start.resolve(),
        (tmp_path / "a-sib").resolve(),
        (tmp_path / "c-sib").resolve(),
    )
    assert scan.error is None
    assert run.calls == [(legacy.WORKTREE_LIST_ARGS, start.resolve())]


def test_unique_sibling_note_is_found_when_resuming_elsewhere(tmp_path: Path) -> None:
    start, sibling = tmp_path / "start", tmp_path / "sibling"
    start.mkdir()
    sibling.mkdir()
    expected = write_note(sibling, "cold-start")

    found = legacy.find_legacy_note(
        "cold-start", start=start, run=fake_runner(porcelain(start, sibling))
    )

    assert found.outcome is legacy.LegacyOutcome.FOUND
    assert found.note is not None
    assert found.note.path == expected
    assert found.note.worktree == sibling.resolve()


@pytest.mark.parametrize("newer", ["start", "sibling"])
def test_two_candidates_are_ambiguous_whichever_one_is_newer(
    tmp_path: Path, newer: str
) -> None:
    """The only tiebreak a recency rule could use is mtime -- so vary it."""
    start, sibling = tmp_path / "start", tmp_path / "sibling"
    start.mkdir()
    sibling.mkdir()
    in_start = write_note(start, "cold-start", "from start\n")
    in_sibling = write_note(sibling, "cold-start", "from sibling\n")
    old, new = (2_000_000_000, 2_000_100_000)
    os.utime(in_start, (old, new if newer == "start" else old))
    os.utime(in_sibling, (old, new if newer == "sibling" else old))

    found = legacy.find_legacy_note(
        "cold-start", start=start, run=fake_runner(porcelain(start, sibling))
    )

    assert found.outcome is legacy.LegacyOutcome.AMBIGUOUS
    assert found.note is None
    assert found.match_paths == (str(in_start), str(in_sibling))


def test_miss_lists_exactly_the_candidate_paths_probed(tmp_path: Path) -> None:
    start, sibling = tmp_path / "start", tmp_path / "sibling"
    start.mkdir()
    sibling.mkdir()

    found = legacy.find_legacy_note(
        "absent", start=start, run=fake_runner(porcelain(start, sibling))
    )

    assert found.outcome is legacy.LegacyOutcome.NOT_FOUND
    assert found.matches == ()
    assert found.searched == (
        str(start.resolve() / ".cheese" / "notes" / "absent.md"),
        str(sibling.resolve() / ".cheese" / "notes" / "absent.md"),
    )
    assert found.error is None


def test_unlistable_git_degrades_to_start_and_says_so(tmp_path: Path) -> None:
    start = tmp_path / "start"
    start.mkdir()

    found = legacy.find_legacy_note("absent", start=start, run=fake_runner(None))

    assert found.searched == (
        str(start.resolve() / ".cheese" / "notes" / "absent.md"),
    )
    assert found.error == (
        f"git worktree list --porcelain could not be run in {start.resolve()}"
    )


@pytest.mark.parametrize("slug", ["../escape", "a/b", "Upper", ""])
def test_a_slug_that_is_not_one_path_segment_is_refused(
    tmp_path: Path, slug: str
) -> None:
    with pytest.raises(legacy.LegacyLookupError, match="single path segment"):
        _ = legacy.find_legacy_note(slug, start=tmp_path, run=fake_runner(""))


@pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")
def test_real_git_worktrees_are_searched_through_the_default_runner(
    tmp_path: Path,
) -> None:
    main = tmp_path / "main"
    main.mkdir()
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.com",
    }
    for args in (
        ["init", "-q", "-b", "main"],
        ["commit", "-q", "--allow-empty", "-m", "seed"],
        ["worktree", "add", "-q", "-b", "side", str(tmp_path / "side")],
    ):
        _ = subprocess.run(
            ["git", *args], cwd=main, env=env, check=True, capture_output=True
        )
    expected = write_note(tmp_path / "side", "cold-start")

    found = legacy.find_legacy_note("cold-start", start=main)

    assert found.outcome is legacy.LegacyOutcome.FOUND
    assert found.note is not None
    assert found.note.path == expected
