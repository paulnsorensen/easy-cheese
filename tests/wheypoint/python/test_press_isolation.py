"""Regression tests for a project-scope note-discovery leak.

`list` (project scope) unions `legacy.repository_chain(cwd)` with
`legacy.worktree_roots(cwd)` and then sweeps the ancestor it finds for every
`**/.cheese/notes/*.md` file. `repository_chain` climbs from cwd to the
nearest ancestor holding a `.git` entry -- so a transient `.git` directory
anywhere above a test's tmp dir turns that ancestor into a sweep root, and
every sibling test directory's notes underneath it become "foreign" hits in
this test's own `list` output. These tests pin that mechanism down: one
reproduces the leak hermetically without touching the real filesystem above
`tmp_path`, and the other exercises the ancestor-detection helper the
autouse `_cwd_outside_a_repository` fixture in `test_cli.py` now uses to
refuse to run from underneath a stray `.git`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from test_cli import CAPTURED_AT

from conftest import WORK_ID, git_marker_ancestor, run_cli


@pytest.mark.usefixtures("corpus_root")
def test_list_project_scope_leaks_notes_from_beneath_a_shared_git_ancestor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pins the leak path: a `.git` above two unrelated tmp dirs makes
    project-scope `list` see the sibling's legacy note, while store-only
    `list --source store` stays correctly scoped to this test's own record.
    """
    shared = tmp_path / "shared"
    (shared / ".git").mkdir(parents=True)

    sibling_notes = shared / "sibling-test" / ".cheese" / "notes"
    sibling_notes.mkdir(parents=True)
    _ = (sibling_notes / "foreign.md").write_text(
        "# Foreign note\n\nbody\n", encoding="utf-8"
    )

    here = shared / "this-test"
    here.mkdir()
    monkeypatch.chdir(here)

    checkpoint_status, _ = run_cli(
        ["checkpoint"],
        stdin=json.dumps(
            {
                "work_id": WORK_ID,
                "orientation": "Genesis orientation.\nNot the title.",
                "working_context": [],
                "next": "cook",
                "artifact": ".cheese/cook/wheypoint-ergonomics.md",
                "notes": "First record.",
                "session": {"captured_at": CAPTURED_AT},
            }
        ),
    )
    assert checkpoint_status == 0

    status, payload = run_cli(["list"])
    assert status == 0
    lines = cast(list[str], payload["lines"])
    third_cells = {line.split("\t")[2] for line in lines}
    # The foreign legacy note under the shared .git ancestor leaks in
    # alongside this test's own store record.
    assert third_cells == {WORK_ID, "foreign"}

    status, payload = run_cli(["list", "--source", "store"])
    assert status == 0
    lines = cast(list[str], payload["lines"])
    assert [line.split("\t")[2] for line in lines] == [WORK_ID]


def test_git_marker_ancestor_finds_none_above_a_plain_tmp_dir(
    tmp_path: Path,
) -> None:
    leaf = tmp_path / "a" / "b"
    leaf.mkdir(parents=True)

    result = git_marker_ancestor(leaf)

    # The real filesystem above tmp_path may or may not hold a stray `.git`
    # (that is exactly the bug); either no ancestor was found, or the one
    # found lies outside this test's own tmp_path tree.
    assert result is None or not result.is_relative_to(tmp_path)


def test_git_marker_ancestor_finds_the_nearest_git_marker(tmp_path: Path) -> None:
    root = tmp_path / "root"
    (root / ".git").mkdir(parents=True)
    leaf = root / "x" / "y"
    leaf.mkdir(parents=True)

    assert git_marker_ancestor(leaf) == root
