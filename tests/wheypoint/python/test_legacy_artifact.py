"""A legacy artifact is validated against the destination that reads it.

Both skill documents publish `PR#<n>` or a pull request URL for
`next: affinage`. That value is not a file in the worktree, so the repository
file rule must not gate it. Every other move still reads a repository file.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

import pytest

from easy_cheese.skills.wheypoint import resolve as resolve_mod

_NOTE = "status: ok\nnext: {move}\nartifact: {artifact}\nPick the loop back up.\n"


def _runner(root: Path) -> Callable[[Sequence[str], Path], str]:
    output = f"worktree {root}\nbranch refs/heads/wt\n"

    def run_git(_args: Sequence[str], _cwd: Path) -> str:
        return output

    return run_git


def _resolve(root: Path, slug: str, *, move: str, artifact: str):
    path = root / ".cheese" / "notes" / f"{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(
        _NOTE.format(move=move, artifact=artifact), encoding="utf-8"
    )
    return resolve_mod.resolve_legacy(slug, start=root, run=_runner(root))


@pytest.mark.parametrize("artifact", ["PR#614", "https://github.com/o/r/pull/614"])
def test_a_documented_affinage_reference_is_not_gated(
    tmp_path: Path, artifact: str
) -> None:
    root = tmp_path / "start"
    root.mkdir()

    found = _resolve(root, "review", move="affinage", artifact=artifact)

    assert found.outcome is resolve_mod.ResolutionOutcome.LEGACY
    assert found.legacy_slug is not None
    assert found.legacy_slug.artifact == artifact


def test_an_affinage_artifact_that_is_neither_form_is_gated(tmp_path: Path) -> None:
    root = tmp_path / "start"
    root.mkdir()

    found = _resolve(root, "review", move="affinage", artifact="notes/review.md")

    assert found.outcome is resolve_mod.ResolutionOutcome.GATED
    assert found.detail is not None
    assert "must be 'PR#<n>' or a pull request URL" in found.detail


def test_a_file_move_still_needs_a_file_in_the_worktree(tmp_path: Path) -> None:
    root = tmp_path / "start"
    root.mkdir()

    found = _resolve(root, "build", move="cook", artifact="PR#614")

    assert found.outcome is resolve_mod.ResolutionOutcome.GATED
    assert found.detail is not None
    assert "does not resolve to an existing regular file" in found.detail


def test_a_file_move_accepts_a_present_repository_file(tmp_path: Path) -> None:
    root = tmp_path / "start"
    (root / ".cheese" / "notes").mkdir(parents=True)
    _ = (root / ".cheese" / "notes" / "context.md").write_text(
        "context\n", encoding="utf-8"
    )

    found = _resolve(
        root, "build", move="cook", artifact=".cheese/notes/context.md"
    )

    assert found.outcome is resolve_mod.ResolutionOutcome.LEGACY
