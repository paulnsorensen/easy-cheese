"""Discovery: typed hits across worktrees, projects, and the machine.

Every test points HOME, XDG_DATA_HOME, and the machine search roots at a
tmp_path so the real `~` is never touched (G8/G9).
"""

from __future__ import annotations

import datetime as _dt
import os
import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Callable, Protocol, TypedDict

import pytest
from easy_cheese_schemas import NextAction, NextMove, WheypointRecord, WheypointRevision
from typing_extensions import Unpack

from easy_cheese.shared.wheypoint import discovery, legacy, storage

_GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.com",
}
HAS_RG = shutil.which("rg") is not None


class _PromotionLike(Protocol):
    record: WheypointRecord
    revision: WheypointRevision
    markdown: str


class _Filters(TypedDict, total=False):
    grep: str
    status: str
    next: str
    source: str
    projects: Sequence[str]
    since: str
    limit: int


@pytest.fixture  # noqa: V103 -- side-effect fixture, injected via usefixtures
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point HOME, XDG_DATA_HOME, and the machine search roots at tmp_path.

    Nothing in this module is allowed to see the real `~`.
    """
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.delenv("EASY_CHEESE_HOME", raising=False)
    monkeypatch.delenv("EASY_CHEESE_PROJECT", raising=False)
    monkeypatch.setenv("EASY_CHEESE_SEARCH_ROOTS", str(home))
    return home


def _seed_store(
    corpus_root: Path,
    make_record: Callable[..., WheypointRecord],
    make_promotion: Callable[..., _PromotionLike],
    *,
    work_id: str,
    slug: str,
    gating: bool = False,
    next_action: NextAction | None = None,
    orientation: str = "Wave 2 owns storage and projection.",
    updated: float | None = None,
) -> storage.WorkStore:
    fields: dict[str, object] = {
        "work_id": work_id,
        "slug": slug,
        "gating": gating,
        "orientation": orientation,
    }
    if next_action is not None:
        fields["next_action"] = next_action
    record = make_record(**fields)
    promotion = make_promotion(1, "rev-0001", record=record)
    store = storage.WorkStore.open(work_id, corpus_root=corpus_root)
    store.promote(promotion.record, promotion.revision, promotion.markdown)
    if updated is not None:
        os.utime(store.record_path, (updated, updated))
    return store


def _write_note(
    root: Path,
    slug: str,
    *,
    status: str = "ok",
    next_skill: str = "cook",
    orientation: str = "Legacy note body.",
) -> Path:
    body = f"status: {status}\nnext: {next_skill}\nartifact: .cheese/age/demo.md\n{orientation}\n"
    path = root.joinpath(*legacy.NOTES_DIR_PARTS, f"{slug}.md")
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(body, encoding="utf-8")
    return path


def _init_repo(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for args in (
        ["init", "-q", "-b", "main"],
        ["commit", "-q", "--allow-empty", "-m", "seed"],
    ):
        _ = subprocess.run(
            ["git", *args], cwd=root, env=_GIT_ENV, check=True, capture_output=True
        )


def _add_worktree(main: Path, side: Path, branch: str) -> None:
    _ = subprocess.run(
        ["git", "worktree", "add", "-q", "-b", branch, str(side)],
        cwd=main,
        env=_GIT_ENV,
        check=True,
        capture_output=True,
    )


@pytest.mark.usefixtures("isolated_home")
def test_machine_scope_finds_stores_across_two_projects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    make_record: Callable[..., WheypointRecord],
    make_promotion: Callable[..., _PromotionLike],
) -> None:
    """AC-5: two project corpora under corpus_home() both surface, each with
    its project key and an absolute resume path."""
    home = tmp_path / "cheese"
    monkeypatch.setenv("EASY_CHEESE_HOME", str(home))
    store_a = _seed_store(
        home / "proj-a", make_record, make_promotion, work_id="work-0001", slug="alpha"
    )
    _ = _seed_store(
        home / "proj-b", make_record, make_promotion, work_id="work-0002", slug="beta"
    )

    result = discovery.discover(scope="machine", start=tmp_path)

    by_project = {hit.project: hit for hit in result.hits}
    assert set(by_project) == {"proj-a", "proj-b"}
    assert by_project["proj-a"].ref == "work-0001"
    assert by_project["proj-a"].resume.is_absolute()
    assert (
        by_project["proj-a"].resume == store_a.projection_path(1, "rev-0001").resolve()
    )


@pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")
@pytest.mark.usefixtures("isolated_home")
def test_project_scope_finds_a_note_in_a_sibling_worktree(tmp_path: Path) -> None:
    """AC-6: a real repo with two worktrees; the note lives in the sibling."""
    main = tmp_path / "main"
    side = tmp_path / "side"
    _init_repo(main)
    _add_worktree(main, side, "side-branch")
    note = _write_note(side, "cold-start")

    result = discovery.discover(
        scope="project", start=main, corpus_root=tmp_path / "empty-corpus"
    )

    note_hits = [hit for hit in result.hits if hit.source == "note"]
    assert len(note_hits) == 1
    hit = note_hits[0]
    assert hit.ref == "cold-start"
    assert hit.path == note.resolve()
    assert hit.status == "ok"
    assert hit.next == "cook"


@pytest.mark.usefixtures("isolated_home")
def test_machine_root_flag_backends_agree_on_notes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC-5b: identical hits from the walk fallback and, when available, rg."""
    repo1 = tmp_path / "repo1"
    repo2 = tmp_path / "repo2"
    note1 = _write_note(repo1, "alpha-note")
    note2 = _write_note(repo2, "beta-note")
    # Caches, dependency trees, and build output hold copied or fixture notes;
    # both backends must skip them the same way.
    for pruned in (".cache/basetemp", "node_modules/pkg", ".venv/lib", "target/x"):
        _ = _write_note(repo1 / pruned, "pruned-note")
    monkeypatch.setenv("EASY_CHEESE_HOME", str(tmp_path / "empty-cheese"))
    original_path = os.environ.get("PATH", "")

    monkeypatch.setenv("PATH", "")
    walk_result = discovery.discover(
        scope="machine", start=tmp_path, roots=[repo1, repo2]
    )

    assert any(s.startswith("walk:") for s in walk_result.searched)
    walk_paths = {str(hit.path) for hit in walk_result.hits if hit.source == "note"}
    assert walk_paths == {str(note1.resolve()), str(note2.resolve())}

    if not HAS_RG:
        pytest.skip("rg is not installed; the walk fallback is already verified")
    monkeypatch.setenv("PATH", original_path)
    rg_result = discovery.discover(
        scope="machine", start=tmp_path, roots=[repo1, repo2]
    )

    assert any(s.startswith("rg:") for s in rg_result.searched)
    rg_paths = {str(hit.path) for hit in rg_result.hits if hit.source == "note"}
    assert rg_paths == walk_paths


@pytest.mark.usefixtures("isolated_home")
def test_filters_combine_with_and(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    make_record: Callable[..., WheypointRecord],
    make_promotion: Callable[..., _PromotionLike],
) -> None:
    """AC-7: grep, status, next, source, since, limit, and project each
    filter, and combine with AND."""
    home = tmp_path / "cheese"
    monkeypatch.setenv("EASY_CHEESE_HOME", str(home))
    press = NextAction(
        move=NextMove.PRESS, orientation="Press it.", artifact=".cheese/press/demo.md"
    )
    old_ts = _dt.datetime(2020, 1, 1).timestamp()
    new_ts = _dt.datetime(2026, 9, 1).timestamp()

    _ = _seed_store(
        home / "proj-a",
        make_record,
        make_promotion,
        work_id="work-aaaa",
        slug="alpha",
        orientation="Cook the curd batch one.",
        updated=new_ts,
    )
    _ = _seed_store(
        home / "proj-a",
        make_record,
        make_promotion,
        work_id="work-bbbb",
        slug="beta",
        gating=True,
        orientation="Cook the curd batch two.",
        updated=old_ts,
    )
    _ = _seed_store(
        home / "proj-b",
        make_record,
        make_promotion,
        work_id="work-cccc",
        slug="gamma",
        next_action=press,
        orientation="Unrelated batch entirely.",
        updated=new_ts,
    )

    def refs(**filters: Unpack[_Filters]) -> set[str]:
        return {
            hit.ref
            for hit in discovery.discover(
                scope="machine", start=tmp_path, **filters
            ).hits
        }

    assert refs(grep="curd") == {"work-aaaa", "work-bbbb"}
    assert refs(status="gated") == {"work-bbbb"}
    assert refs(next="press") == {"work-cccc"}
    assert refs(source="store") == {"work-aaaa", "work-bbbb", "work-cccc"}
    assert refs(projects=["proj-b"]) == {"work-cccc"}
    assert refs(since="2025-01-01") == {"work-aaaa", "work-cccc"}
    assert len(discovery.discover(scope="machine", start=tmp_path, limit=1).hits) == 1
    assert refs(grep="curd", status="ok") == {"work-aaaa"}


@pytest.mark.usefixtures("isolated_home")
def test_mirror_note_hidden_by_default_and_shown_with_flag(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    make_record: Callable[..., WheypointRecord],
    make_promotion: Callable[..., _PromotionLike],
) -> None:
    """AC-8: a note sharing a store's slug is hidden by default and counted."""
    home = tmp_path / "cheese"
    monkeypatch.setenv("EASY_CHEESE_HOME", str(home))
    monkeypatch.setenv("EASY_CHEESE_PROJECT", "proj-a")
    _ = _seed_store(
        home / "proj-a",
        make_record,
        make_promotion,
        work_id="work-dddd",
        slug="mirror-slug",
    )
    note_root = tmp_path / "worktree"
    note_root.mkdir()
    _ = _write_note(note_root, "mirror-slug")

    default_result = discovery.discover(
        scope="machine", start=tmp_path, roots=[note_root]
    )
    assert default_result.hidden_mirrors == 1
    assert {hit.source for hit in default_result.hits} == {"store"}

    shown_result = discovery.discover(
        scope="machine", start=tmp_path, roots=[note_root], show_mirrors=True
    )
    assert shown_result.hidden_mirrors == 0
    assert {hit.source for hit in shown_result.hits} == {"store", "note"}


@pytest.mark.usefixtures("isolated_home")
def test_unparseable_note_becomes_a_problem_hit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "worktree"
    root.mkdir()
    monkeypatch.setenv("EASY_CHEESE_HOME", str(tmp_path / "empty-cheese"))
    path = root.joinpath(*legacy.NOTES_DIR_PARTS, "broken.md")
    path.parent.mkdir(parents=True)
    _ = path.write_text("\n# Resume brief — broken\n\nbody\n", encoding="utf-8")

    result = discovery.discover(scope="machine", start=tmp_path, roots=[root])

    note_hits = [hit for hit in result.hits if hit.source == "note"]
    assert len(note_hits) == 1
    assert note_hits[0].ref == "broken"
    assert note_hits[0].problem is not None
    assert note_hits[0].orientation == "Resume brief — broken"
    assert note_hits[0].status is None


@pytest.mark.usefixtures("isolated_home")
def test_suggestions_offers_close_matches_and_never_picks_one(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    make_record: Callable[..., WheypointRecord],
    make_promotion: Callable[..., _PromotionLike],
) -> None:
    """Suggestion part of AC-10: a near-miss id surfaces as a suggestion."""
    home = tmp_path / "cheese"
    monkeypatch.setenv("EASY_CHEESE_HOME", str(home))
    _ = _seed_store(
        home / "proj-a",
        make_record,
        make_promotion,
        work_id="work-0001",
        slug="wheypoint-cli",
    )

    result = discovery.suggestions("wrk-0001", start=tmp_path, scope="machine")

    assert result == ("work-0001",)
