"""Discovery: typed hits across worktrees, projects, and the machine.

Every test points HOME, XDG_DATA_HOME, and the machine search roots at a
tmp_path so the real `~` is never touched (G8/G9).
"""

from __future__ import annotations

import datetime as _dt
import functools
import os
import shutil
import subprocess
import time
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Callable, Protocol, TypedDict

import pytest
from easy_cheese_schemas import (
    ArtifactLink,
    EntryKind,
    EntryState,
    NextAction,
    NextMove,
    ProtectedEntry,
    WheypointRecord,
    WheypointRevision,
)
from easy_cheese_schemas.contracts import EdgeKind, WorkEdge
from typing_extensions import Unpack

from easy_cheese.shared.wheypoint import discovery, discovery_notes, legacy, storage

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
    grep: Sequence[str]
    status: Sequence[str]
    next: Sequence[str]
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


@pytest.mark.usefixtures("isolated_home")
def test_unreadable_store_record_reports_path(
    tmp_path: Path,
) -> None:
    """An unreadable enumerated record remains visible as a discovery error."""
    corpus = tmp_path / "corpus"
    store = storage.WorkStore.open("work-0001", corpus_root=corpus)
    store.root.mkdir(parents=True)
    _ = store.record_path.write_bytes(b"not-json")

    result = discovery.discover(scope="project", start=tmp_path, corpus_root=corpus)

    assert result.hits == ()
    assert any(str(store.record_path) in error for error in result.errors)


@pytest.mark.usefixtures("isolated_home")
def test_missing_machine_corpus_home_is_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A first-run machine search treats a missing corpus home as empty."""
    home = tmp_path / "missing-cheese"
    monkeypatch.setenv("EASY_CHEESE_HOME", str(home))

    result = discovery.discover(scope="machine", start=tmp_path)

    assert result.hits == ()
    assert result.errors == ()


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
    rg_entries = [
        entry
        for entry in original_path.split(os.pathsep)
        if Path(entry).name != "shims"
    ]
    if not any((Path(entry) / "rg").is_file() for entry in rg_entries):
        pytest.skip("rg is only available through a shim")
    monkeypatch.setenv("PATH", os.pathsep.join(rg_entries))
    rg_result = discovery.discover(
        scope="machine", start=tmp_path, roots=[repo1, repo2]
    )

    assert any(s.startswith("rg:") for s in rg_result.searched)
    rg_paths = {str(hit.path) for hit in rg_result.hits if hit.source == "note"}
    assert rg_paths == walk_paths


@pytest.mark.usefixtures("isolated_home")
def test_fallback_walk_discards_partial_results_on_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An interrupted fallback walk reports no partial hits as complete."""
    root = tmp_path / "repo"
    notes = root / ".cheese" / "notes"
    first = notes / "first.md"
    root.mkdir()
    clock = iter((0.0, 0.0, 1.0))

    def fake_walk(_root: Path) -> Iterator[tuple[str, list[str], list[str]]]:
        yield str(notes), [], [first.name]
        yield str(root), [], []

    monkeypatch.setenv("EASY_CHEESE_HOME", str(tmp_path / "empty-cheese"))
    monkeypatch.setenv("PATH", "")
    monkeypatch.setattr(os, "walk", fake_walk)
    monkeypatch.setattr(discovery_notes, "_WALK_TIMEOUT_SECONDS", 1.0)
    monkeypatch.setattr(time, "monotonic", lambda: next(clock))

    result = discovery.discover(scope="machine", start=tmp_path, roots=[root])

    assert result.hits == ()
    assert any("directory walk timed out" in error for error in result.errors)


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

    assert refs(grep=["curd"]) == {"work-aaaa", "work-bbbb"}
    assert refs(grep=["CURD"]) == {"work-aaaa", "work-bbbb"}
    assert refs(status=["gated"]) == {"work-bbbb"}
    assert refs(next=["press"]) == {"work-cccc"}
    assert refs(source="store") == {"work-aaaa", "work-bbbb", "work-cccc"}
    assert refs(projects=["proj-b"]) == {"work-cccc"}
    assert refs(since="2025-01-01") == {"work-aaaa", "work-cccc"}
    assert len(discovery.discover(scope="machine", start=tmp_path, limit=1).hits) == 1
    assert refs(grep=["curd"], status=["ok"]) == {"work-aaaa"}
    # The terms of one repeatable filter combine with OR.
    assert refs(grep=["batch one", "unrelated"]) == {"work-aaaa", "work-cccc"}
    assert refs(grep=["no-such-term", "batch two"]) == {"work-bbbb"}
    assert refs(status=["ok", "gated"]) == {"work-aaaa", "work-bbbb", "work-cccc"}
    assert refs(next=["press", "no-such-move"]) == {"work-cccc"}
    # Distinct filters still combine with AND.
    assert refs(grep=["batch one", "unrelated"], next=["press"]) == {"work-cccc"}


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


def _seed_fields(
    corpus_root: Path,
    make_record: Callable[..., WheypointRecord],
    make_promotion: Callable[..., _PromotionLike],
    work_id: str,
    **fields: object,
) -> None:
    record = make_record(work_id=work_id, slug=work_id, **fields)
    promotion = make_promotion(1, "rev-0001", record=record)
    storage.WorkStore.open(work_id, corpus_root=corpus_root).promote(
        promotion.record, promotion.revision, promotion.markdown
    )


def _keys(hits: Sequence[discovery.Hit]) -> set[tuple[str, str]]:
    return {(hit.project, hit.ref) for hit in hits}


@pytest.mark.usefixtures("isolated_home")
def test_ac12_linked_to_and_backlinks_return_the_same_records(
    tmp_path: Path,
    make_record: Callable[..., WheypointRecord],
    make_promotion: Callable[..., _PromotionLike],
) -> None:
    corpus = tmp_path / "cheese" / "proj-a"
    target = "wheypoint:proj-a/target"
    seed = functools.partial(_seed_fields, corpus, make_record, make_promotion)
    seed("target")
    seed("by-edge", edges=[WorkEdge(to=f"{target}@rev-0001", kind=EdgeKind.INFORMS)])
    seed(
        "by-link",
        artifact_links=[
            ArtifactLink(path="docs/target.md", ref="wheypoint:proj-a/target")
        ],
    )
    seed(
        "elsewhere",
        edges=[WorkEdge(to="wheypoint:proj-a/other", kind=EdgeKind.INFORMS)],
    )

    listed = discovery.discover(
        start=tmp_path, corpus_root=corpus, linked_to=[target]
    ).hits
    back = discovery.backlinks(target, start=tmp_path, corpus_root=corpus)

    assert _keys(listed) == {("proj-a", "by-edge"), ("proj-a", "by-link")}
    assert _keys(back) == _keys(listed)
    by_ref = {
        hit.ref: hit
        for hit in discovery.discover(start=tmp_path, corpus_root=corpus).hits
    }
    assert by_ref["by-edge"].edges_out == (("informs", f"{target}@rev-0001"),)
    assert by_ref["target"].edges_in == (("informs", "wheypoint:proj-a/by-edge"),)
    pinned = discovery.discover(
        start=tmp_path, corpus_root=corpus, linked_to=[f"{target}@rev-0002"]
    ).hits
    assert pinned == ()
    by_path = discovery.discover(
        start=tmp_path, corpus_root=corpus, linked_to=["repo:docs/target.md"]
    ).hits
    assert by_path == ()


@pytest.mark.usefixtures("isolated_home")
def test_ac12_linked_to_matches_a_repo_link_by_its_path(
    tmp_path: Path,
    make_record: Callable[..., WheypointRecord],
    make_promotion: Callable[..., _PromotionLike],
) -> None:
    corpus = tmp_path / "cheese" / "proj-a"
    _seed_fields(
        corpus,
        make_record,
        make_promotion,
        "with-spec",
        artifact_links=[ArtifactLink(path="docs/spec.md")],
    )
    _seed_fields(corpus, make_record, make_promotion, "without")

    hits = discovery.backlinks(
        "repo:./docs/spec.md", start=tmp_path, corpus_root=corpus
    )

    assert _keys(hits) == {("proj-a", "with-spec")}


def _question(entry_id: str, state: EntryState) -> ProtectedEntry:
    return ProtectedEntry(
        entry_id=entry_id,
        kind=EntryKind.QUESTION,
        summary=f"Question {entry_id}?",
        state=state,
        blocks_continuation=False,
        rationale=None if state is EntryState.ACTIVE else "Settled.",
    )


@pytest.mark.usefixtures("isolated_home")
def test_ac13_entry_filters_and_gated_return_only_gated_records(
    tmp_path: Path,
    make_record: Callable[..., WheypointRecord],
    make_promotion: Callable[..., _PromotionLike],
) -> None:
    corpus = tmp_path / "cheese" / "proj-a"
    seed = functools.partial(_seed_fields, corpus, make_record, make_promotion)
    seed("gated", gating=True)
    seed("open", questions=[_question("q-open", EntryState.ACTIVE)])
    seed(
        "settled",
        questions=[_question("q-done", EntryState.RESOLVED)],
        blockers=[
            ProtectedEntry(
                entry_id="b-live",
                kind=EntryKind.BLOCKER,
                summary="Waiting on CI.",
                state=EntryState.ACTIVE,
                blocks_continuation=False,
            )
        ],
    )
    seed("empty")

    def keys(**filters: object) -> set[tuple[str, str]]:
        return _keys(
            discovery.discover(
                start=tmp_path,
                corpus_root=corpus,
                **filters,  # pyright: ignore[reportArgumentType]
            ).hits
        )

    gated = discovery.discover(
        start=tmp_path,
        corpus_root=corpus,
        entry_kind=["question"],
        entry_state=["active"],
        gated=True,
    ).hits

    assert _keys(gated) == {("proj-a", "gated")}
    assert gated[0].gates == ("q-durability",)
    assert keys(entry_kind=["question"], entry_state=["active"]) == {
        ("proj-a", "gated"),
        ("proj-a", "open"),
    }
    assert keys(gated=False) == {
        ("proj-a", "open"),
        ("proj-a", "settled"),
        ("proj-a", "empty"),
    }


@pytest.mark.usefixtures("isolated_home")
def test_forked_from_and_edge_kind_filters_find_the_child(
    tmp_path: Path,
    make_record: Callable[..., WheypointRecord],
    make_promotion: Callable[..., _PromotionLike],
) -> None:
    corpus = tmp_path / "cheese" / "proj-a"
    seed = functools.partial(_seed_fields, corpus, make_record, make_promotion)
    seed("parent")
    seed(
        "child",
        edges=[
            WorkEdge(to="wheypoint:proj-a/parent@rev-0001", kind=EdgeKind.FORKED_FROM)
        ],
    )
    seed("peer", edges=[WorkEdge(to="wheypoint:proj-a/parent", kind=EdgeKind.INFORMS)])

    forked = discovery.discover(
        start=tmp_path, corpus_root=corpus, forked_from=["parent"]
    ).hits
    by_kind = discovery.discover(
        start=tmp_path, corpus_root=corpus, edge_kind=["forked_from"]
    ).hits

    assert _keys(forked) == {("proj-a", "child")}
    assert forked[0].forked_from == "parent"
    assert _keys(by_kind) == {("proj-a", "child")}
