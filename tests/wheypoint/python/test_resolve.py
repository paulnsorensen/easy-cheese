"""Resolution: fixed precedence, no recency, and nothing dispatches unverified."""

from __future__ import annotations

import os
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Protocol

import pytest
from easy_cheese_schemas import WheypointRecord, WheypointRevision

from easy_cheese.skills.wheypoint import canonical, lint, records, storage
from easy_cheese.skills.wheypoint import resolve as resolve_mod

PROJECT = "paulnsorensen-easy-cheese"
NOTE = "status: ok\nnext: cook\nartifact: {artifact}\nPick the loop back up.\n"


class _PromotionLike(Protocol):
    record: WheypointRecord
    revision: WheypointRevision
    markdown: str

def seed(
    corpus_root: Path,
    make_record: Callable[..., WheypointRecord],
    make_promotion: Callable[..., _PromotionLike],
    *,
    work_id: str,
    slug: str,
    gating: bool = False,
    revision_id: str = "rev-0001",
    number: int = 1,
) -> tuple[storage.WorkStore, _PromotionLike]:
    """Promote one revision and hand back the store plus that first promotion.

    The promotion comes back so a successor can name it as its real parent,
    which is what pins the ancestor digest into the child's receipt.
    """
    record = make_record(
        work_id=work_id,
        slug=slug,
        gating=gating,
        revision_id=revision_id,
        revision_number=number,
    )
    promotion = make_promotion(number, revision_id, record=record)
    store = storage.WorkStore.open(work_id, corpus_root=corpus_root)
    store.promote(promotion.record, promotion.revision, promotion.markdown)
    return store, promotion


def run(
    ref: str,
    corpus_root: Path,
    *,
    project_key: str = PROJECT,
    git_object_exists: Callable[[str], bool] = lambda obj: True,
    artifact_digest: Callable[[str], str | None] = lambda path: None,
) -> resolve_mod.Resolution:
    return resolve_mod.resolve(
        ref,
        corpus_root=corpus_root,
        project_key=project_key,
        git_object_exists=git_object_exists,
        artifact_digest=artifact_digest,
    )


def test_an_exact_work_id_beats_another_record_holding_that_slug(
    corpus_root: Path,
    make_record: Callable[..., WheypointRecord],
    make_promotion: Callable[..., _PromotionLike],
) -> None:
    _ = seed(corpus_root, make_record, make_promotion, work_id="alpha", slug="beta")
    _ = seed(corpus_root, make_record, make_promotion, work_id="gamma", slug="alpha")

    found = run("alpha", corpus_root)

    assert found.outcome is resolve_mod.ResolutionOutcome.AUTHORITATIVE
    assert found.source is resolve_mod.ResolutionSource.WORK_ID
    assert found.work_id == "alpha"



def test_a_work_id_ending_in_md_is_not_treated_as_a_path(
    corpus_root: Path,
    make_record: Callable[..., WheypointRecord],
    make_promotion: Callable[..., _PromotionLike],
) -> None:
    _ = seed(corpus_root, make_record, make_promotion, work_id="alpha.md", slug="beta")

    found = run("alpha.md", corpus_root)

    assert found.outcome is resolve_mod.ResolutionOutcome.AUTHORITATIVE
    assert found.source is resolve_mod.ResolutionSource.WORK_ID
    assert found.work_id == "alpha.md"

def test_an_explicit_path_beats_the_corpus_lookups(
    corpus_root: Path,
    make_record: Callable[..., WheypointRecord],
    make_promotion: Callable[..., _PromotionLike],
) -> None:
    store, _ = seed(
        corpus_root, make_record, make_promotion, work_id="alpha", slug="beta"
    )
    path = store.projection_path(1, "rev-0001")

    found = run(str(path), corpus_root)

    assert found.source is resolve_mod.ResolutionSource.PATH
    assert found.outcome is resolve_mod.ResolutionOutcome.AUTHORITATIVE
    assert found.work_id == "alpha"
    assert found.searched == (str(path),)


def test_a_unique_slug_resolves_when_no_work_id_matches(
    corpus_root: Path,
    make_record: Callable[..., WheypointRecord],
    make_promotion: Callable[..., _PromotionLike],
) -> None:
    _ = seed(corpus_root, make_record, make_promotion, work_id="work-0001", slug="kernel")

    found = run("kernel", corpus_root)

    assert found.outcome is resolve_mod.ResolutionOutcome.AUTHORITATIVE
    assert found.source is resolve_mod.ResolutionSource.SLUG
    assert found.work_id == "work-0001"
    assert found.record is not None
    assert found.projection is not None
    assert found.dispatchable


def test_a_slug_ending_in_md_is_not_treated_as_a_path(
    corpus_root: Path,
    make_record: Callable[..., WheypointRecord],
    make_promotion: Callable[..., _PromotionLike],
) -> None:
    _ = seed(
        corpus_root,
        make_record,
        make_promotion,
        work_id="work-0001",
        slug="kernel.md",
    )

    found = run("kernel.md", corpus_root)

    assert found.outcome is resolve_mod.ResolutionOutcome.AUTHORITATIVE
    assert found.source is resolve_mod.ResolutionSource.SLUG
    assert found.work_id == "work-0001"


@pytest.mark.parametrize("newer", ["work-0001", "work-0002"])
def test_one_slug_on_two_records_is_ambiguous_whichever_is_newer(
    corpus_root: Path,
    make_record: Callable[..., WheypointRecord],
    make_promotion: Callable[..., _PromotionLike],
    newer: str,
) -> None:
    """A recency tiebreak would pick the newer record; ambiguity must not."""
    for work_id in ("work-0001", "work-0002"):
        store, _ = seed(
            corpus_root, make_record, make_promotion, work_id=work_id, slug="kernel"
        )
        stamp = 2_000_100_000 if work_id == newer else 2_000_000_000
        os.utime(store.record_path, (stamp, stamp))

    found = run("kernel", corpus_root)

    assert found.outcome is resolve_mod.ResolutionOutcome.AMBIGUOUS
    assert found.matches == ("work-0001", "work-0002")
    assert found.work_id is None
    assert not found.dispatchable
    assert found.detail == "slug 'kernel' names 2 work records: work-0001, work-0002"


def test_a_miss_lists_exactly_the_corpus_locations_searched(corpus_root: Path) -> None:
    work_root = corpus_root / "work"

    found = run("kernel", corpus_root)

    assert found.outcome is resolve_mod.ResolutionOutcome.NOT_FOUND
    assert found.searched == (
        str(work_root / "kernel" / "record.json"),
        str(work_root / "*" / "record.json"),
    )


def test_a_missing_explicit_path_reports_only_that_path(
    corpus_root: Path, tmp_path: Path
) -> None:
    missing = tmp_path / "nope.md"

    found = run(str(missing), corpus_root)

    assert found.outcome is resolve_mod.ResolutionOutcome.NOT_FOUND
    assert found.searched == (str(missing),)


def test_a_path_that_is_not_a_projection_is_an_error(
    corpus_root: Path, tmp_path: Path
) -> None:
    stray = tmp_path / "notes.md"
    _ = stray.write_text("# just markdown\n", encoding="utf-8")

    found = run(str(stray), corpus_root)

    assert found.outcome is resolve_mod.ResolutionOutcome.ERROR
    assert found.findings[0].code.value == "projection-unreadable"


def test_a_superseded_projection_path_does_not_dispatch(
    corpus_root: Path,
    make_record: Callable[..., WheypointRecord],
    make_promotion: Callable[..., _PromotionLike],
) -> None:
    store, first = seed(
        corpus_root, make_record, make_promotion, work_id="alpha", slug="beta"
    )
    stale = store.projection_path(1, "rev-0001")
    second = make_promotion(
        2,
        "rev-0002",
        parent=first,
        record=make_record(
            work_id="alpha", slug="beta", revision_id="rev-0002", revision_number=2
        ),
    )
    store.promote(second.record, second.revision, second.markdown)

    found = run(str(stale), corpus_root)

    assert found.outcome is resolve_mod.ResolutionOutcome.GATED
    assert not found.dispatchable
    assert found.detail == (
        "reference names revision 'rev-0001', but the current revision is 'rev-0002'"
    )


def test_an_active_gate_blocks_automatic_continuation(
    corpus_root: Path,
    make_record: Callable[..., WheypointRecord],
    make_promotion: Callable[..., _PromotionLike],
) -> None:
    _ = seed(
        corpus_root,
        make_record,
        make_promotion,
        work_id="work-0001",
        slug="kernel",
        gating=True,
    )

    found = run("kernel", corpus_root)

    assert found.outcome is resolve_mod.ResolutionOutcome.GATED
    assert found.detail == "active gating entries: q-durability"
    assert found.record is not None
    assert not found.dispatchable


def test_a_tampered_record_gates_instead_of_dispatching(
    corpus_root: Path,
    make_record: Callable[..., WheypointRecord],
    make_promotion: Callable[..., _PromotionLike],
) -> None:
    store, _ = seed(
        corpus_root, make_record, make_promotion, work_id="work-0001", slug="kernel"
    )
    forged = records.unstructure(store.read_record())
    forged["orientation"] = "edited behind the runtime's back"
    _ = store.record_path.write_bytes(canonical.canonical_bytes(forged))

    found = run("kernel", corpus_root)

    assert found.outcome is resolve_mod.ResolutionOutcome.GATED
    assert found.findings[0].code.value == "store-inconsistent"
    assert not found.dispatchable


def test_a_declared_commit_that_is_gone_gates(
    corpus_root: Path,
    make_record: Callable[..., WheypointRecord],
    make_promotion: Callable[..., _PromotionLike],
) -> None:
    _ = seed(
        corpus_root, make_record, make_promotion, work_id="work-0001", slug="kernel"
    )

    found = run("kernel", corpus_root, git_object_exists=lambda obj: False)

    assert found.outcome is resolve_mod.ResolutionOutcome.GATED
    assert found.findings[0].code.value == "git-object-missing"


def test_a_record_from_another_project_never_resolves_here(
    corpus_root: Path,
    make_record: Callable[..., WheypointRecord],
    make_promotion: Callable[..., _PromotionLike],
) -> None:
    _ = seed(
        corpus_root, make_record, make_promotion, work_id="work-0001", slug="kernel"
    )

    found = run("kernel", corpus_root, project_key="someone-else-other-repo")

    assert found.outcome is resolve_mod.ResolutionOutcome.GATED
    assert found.findings[0].code.value == "project-mismatch"


@pytest.mark.parametrize("ref", ["", "   ", "Not An Id", "UPPER"])
def test_a_reference_that_is_neither_path_nor_identifier_is_an_error(
    corpus_root: Path, ref: str
) -> None:
    found = run(ref, corpus_root)

    assert found.outcome is resolve_mod.ResolutionOutcome.ERROR
    assert found.detail is not None


# ----- legacy fallback -----------------------------------------------------


def porcelain(*roots: Path) -> str:
    return "\n".join(f"worktree {root}\nbranch refs/heads/wt\n" for root in roots)


def fake_runner(output: str) -> Callable[[Sequence[str], Path], str]:
    def run_git(_args: Sequence[str], _cwd: Path) -> str:
        return output

    return run_git


def write_note(root: Path, slug: str, *, artifact: str = "") -> Path:
    path = root / ".cheese" / "notes" / f"{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(NOTE.format(artifact=artifact), encoding="utf-8")
    return path


def test_a_unique_sibling_legacy_note_resolves_without_dispatching(
    tmp_path: Path,
) -> None:
    start, sibling = tmp_path / "start", tmp_path / "sibling"
    start.mkdir()
    sibling.mkdir()
    note = write_note(sibling, "cold-start")

    found = resolve_mod.resolve_legacy(
        "cold-start", start=start, run=fake_runner(porcelain(start, sibling))
    )

    assert found.outcome is resolve_mod.ResolutionOutcome.LEGACY
    assert found.legacy_note == note
    assert found.legacy_slug is not None
    assert found.legacy_slug.next_skill == "cook"
    assert not found.dispatchable


def test_two_legacy_notes_stay_ambiguous(tmp_path: Path) -> None:
    start, sibling = tmp_path / "start", tmp_path / "sibling"
    start.mkdir()
    sibling.mkdir()
    here = write_note(start, "cold-start")
    there = write_note(sibling, "cold-start")

    found = resolve_mod.resolve_legacy(
        "cold-start", start=start, run=fake_runner(porcelain(start, sibling))
    )

    assert found.outcome is resolve_mod.ResolutionOutcome.AMBIGUOUS
    assert found.matches == (str(here), str(there))
    assert found.legacy_note is None


def test_a_legacy_note_whose_artifact_is_gone_gates(tmp_path: Path) -> None:
    start = tmp_path / "start"
    start.mkdir()
    _ = write_note(start, "cold-start", artifact=".cheese/cook/cold-start.md")

    found = resolve_mod.resolve_legacy(
        "cold-start", start=start, run=fake_runner(porcelain(start))
    )

    assert found.outcome is resolve_mod.ResolutionOutcome.GATED
    assert found.detail is not None
    assert ".cheese/cook/cold-start.md" in found.detail


def test_a_legacy_note_whose_artifact_resolves_is_returned(tmp_path: Path) -> None:
    start = tmp_path / "start"
    start.mkdir()
    _ = write_note(start, "cold-start", artifact=".cheese/cook/cold-start.md")
    report = start / ".cheese" / "cook" / "cold-start.md"
    report.parent.mkdir(parents=True)
    _ = report.write_text("prior report\n", encoding="utf-8")

    found = resolve_mod.resolve_legacy(
        "cold-start", start=start, run=fake_runner(porcelain(start))
    )

    assert found.outcome is resolve_mod.ResolutionOutcome.LEGACY


def write_note_with_parents(root: Path, slug: str, parents: str) -> Path:
    path = root / ".cheese" / "notes" / f"{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(
        "status: ok\nnext: cook\nartifact: \n"
        + f"parents: {parents}\nPick the loop back up.\n",
        encoding="utf-8",
    )
    return path


def test_a_legacy_note_whose_parent_names_no_note_gates(tmp_path: Path) -> None:
    """Lineage is followed off the note, so a dangling parent is a dangling
    pointer dressed as provenance -- the same failure as a dangling artifact."""
    start = tmp_path / "start"
    start.mkdir()
    _ = write_note_with_parents(start, "child", "[gone-forever]")

    found = resolve_mod.resolve_legacy(
        "child", start=start, run=fake_runner(porcelain(start))
    )

    assert found.outcome is resolve_mod.ResolutionOutcome.GATED
    assert found.detail is not None
    assert "'gone-forever'" in found.detail


def test_a_legacy_parent_in_a_sibling_worktree_resolves(tmp_path: Path) -> None:
    start, sibling = tmp_path / "start", tmp_path / "sibling"
    start.mkdir()
    sibling.mkdir()
    _ = write_note(sibling, "elder")
    _ = write_note_with_parents(start, "child", '["elder"]')

    found = resolve_mod.resolve_legacy(
        "child", start=start, run=fake_runner(porcelain(start, sibling))
    )

    assert found.outcome is resolve_mod.ResolutionOutcome.LEGACY
    assert found.legacy_slug is not None
    assert found.legacy_slug.parents == '["elder"]'


@pytest.mark.parametrize(
    "parents",
    ["[elder, other]", "elder,other", "['elder', \"other\"]", "[ elder , other ]"],
)
def test_parent_lists_are_read_tolerantly(tmp_path: Path, parents: str) -> None:
    """The field is hand-written Markdown, not JSON: brackets, quotes, and
    stray whitespace all describe the same lineage."""
    start = tmp_path / "start"
    start.mkdir()
    _ = write_note(start, "elder")
    _ = write_note(start, "other")
    _ = write_note_with_parents(start, "child", parents)

    found = resolve_mod.resolve_legacy(
        "child", start=start, run=fake_runner(porcelain(start))
    )

    assert found.outcome is resolve_mod.ResolutionOutcome.LEGACY, found.detail


def test_a_join_gates_on_the_one_parent_that_is_missing(tmp_path: Path) -> None:
    start = tmp_path / "start"
    start.mkdir()
    _ = write_note(start, "elder")
    _ = write_note_with_parents(start, "child", "[elder, vanished]")

    found = resolve_mod.resolve_legacy(
        "child", start=start, run=fake_runner(porcelain(start))
    )

    assert found.outcome is resolve_mod.ResolutionOutcome.GATED
    assert found.detail is not None
    assert "'vanished'" in found.detail
    assert "'elder'" not in found.detail


def test_an_absolute_http_parent_is_accepted_and_a_bare_path_is_not(
    tmp_path: Path,
) -> None:
    start = tmp_path / "start"
    start.mkdir()
    _ = write_note_with_parents(
        start, "child", "[https://github.com/o/r/pull/1]"
    )
    linked = resolve_mod.resolve_legacy(
        "child", start=start, run=fake_runner(porcelain(start))
    )
    assert linked.outcome is resolve_mod.ResolutionOutcome.LEGACY

    _ = write_note_with_parents(start, "child", "[.cheese/notes/elder.md]")
    pathy = resolve_mod.resolve_legacy(
        "child", start=start, run=fake_runner(porcelain(start))
    )
    assert pathy.outcome is resolve_mod.ResolutionOutcome.GATED


def test_an_empty_parent_list_is_not_a_gate(tmp_path: Path) -> None:
    start = tmp_path / "start"
    start.mkdir()
    _ = write_note_with_parents(start, "child", "[]")

    found = resolve_mod.resolve_legacy(
        "child", start=start, run=fake_runner(porcelain(start))
    )

    assert found.outcome is resolve_mod.ResolutionOutcome.LEGACY


def test_an_unparsable_legacy_note_is_an_error(tmp_path: Path) -> None:
    start = tmp_path / "start"
    start.mkdir()
    path = start / ".cheese" / "notes" / "cold-start.md"
    path.parent.mkdir(parents=True)
    _ = path.write_text("# not a handoff note\n\nbody\n", encoding="utf-8")

    found = resolve_mod.resolve_legacy(
        "cold-start", start=start, run=fake_runner(porcelain(start))
    )

    assert found.outcome is resolve_mod.ResolutionOutcome.ERROR
    assert found.legacy_note == path


def test_a_legacy_miss_reports_every_worktree_probed(tmp_path: Path) -> None:
    start, sibling = tmp_path / "start", tmp_path / "sibling"
    start.mkdir()
    sibling.mkdir()

    found = resolve_mod.resolve_legacy(
        "cold-start", start=start, run=fake_runner(porcelain(start, sibling))
    )

    assert found.outcome is resolve_mod.ResolutionOutcome.NOT_FOUND
    assert found.searched == (
        str(start.resolve() / ".cheese" / "notes" / "cold-start.md"),
        str(sibling.resolve() / ".cheese" / "notes" / "cold-start.md"),
    )


def test_an_orphaned_revision_is_reported_but_does_not_block_continuation(
    corpus_root: Path,
    make_record: Callable[..., WheypointRecord],
    make_promotion: Callable[..., _PromotionLike],
) -> None:
    """An interrupted promotion leaves a revision file with no projection. No
    reader can have quoted it and the identical retry overwrites it, so it is
    surroundings, not authority: gating on it would strand a valid current
    record in exactly the crash it just survived."""
    store, _ = seed(
        corpus_root, make_record, make_promotion, work_id="alpha", slug="alpha"
    )
    orphan = store.revision_path(2, "rev-0002")
    _ = orphan.write_text(store.revision_path(1, "rev-0001").read_text(), encoding="utf-8")

    found = run("alpha", corpus_root)

    codes = tuple(f.code for f in found.findings)
    assert lint.LintCode.REVISION_INCOMPLETE in codes, codes
    assert found.outcome is resolve_mod.ResolutionOutcome.AUTHORITATIVE
    assert found.dispatchable is True


def test_a_real_integrity_failure_still_blocks_continuation(
    corpus_root: Path,
    make_record: Callable[..., WheypointRecord],
    make_promotion: Callable[..., _PromotionLike],
) -> None:
    """The advisory carve-out must not leak: tampering still gates."""
    store, _ = seed(
        corpus_root, make_record, make_promotion, work_id="alpha", slug="alpha"
    )
    path = store.projection_path(1, "rev-0001")
    _ = path.write_text(path.read_text(encoding="utf-8").replace("cook", "press"), encoding="utf-8")

    found = run("alpha", corpus_root)

    assert found.dispatchable is False
    assert found.outcome is resolve_mod.ResolutionOutcome.GATED

WRAPPED_NOTE = """## Handoff slug

~~~text
status: ok
next: mold
mode: single
artifact: .cheese/notes/context.md
session: codex:test-session
git: branch@deadbeef
created: 2026-08-02T00:00:00Z
parents: [context]
baseline: none
Resume the parent protocol.
~~~

## Document
body
"""


def test_real_wrapped_legacy_note_decodes_additive_header(tmp_path: Path) -> None:
    start = tmp_path / "start"
    start.mkdir()
    note = start / ".cheese" / "notes" / "wrapped.md"
    note.parent.mkdir(parents=True)
    _ = note.write_text(WRAPPED_NOTE, encoding="utf-8")
    _ = (start / ".cheese" / "notes" / "context.md").write_text("context\n", encoding="utf-8")

    found = resolve_mod.resolve_legacy(
        "wrapped", start=start, run=fake_runner(porcelain(start))
    )

    assert found.outcome is resolve_mod.ResolutionOutcome.LEGACY
    assert found.legacy_slug is not None
    assert found.legacy_slug.next_skill == "mold"
    assert found.legacy_slug.mode == "single"
    assert found.legacy_slug.session == "codex:test-session"
    assert found.legacy_slug.parents == "[context]"


def test_normal_resolve_falls_back_to_a_legacy_slug(tmp_path: Path) -> None:
    start = tmp_path / "start"
    start.mkdir()
    note = start / ".cheese" / "notes" / "wrapped.md"
    note.parent.mkdir(parents=True)
    _ = note.write_text(WRAPPED_NOTE, encoding="utf-8")

    _ = (start / ".cheese" / "notes" / "context.md").write_text("context\n", encoding="utf-8")
    found = resolve_mod.resolve("wrapped", workspace_root=start)

    assert found.outcome is resolve_mod.ResolutionOutcome.LEGACY
    assert found.legacy_note == note
    assert not found.dispatchable


def test_absolute_legacy_path_resolves_exact_note_without_worktree_scan(tmp_path: Path) -> None:
    start = tmp_path / "start"
    start.mkdir()
    note = start / ".cheese" / "notes" / "wrapped.md"
    note.parent.mkdir(parents=True)
    _ = note.write_text(WRAPPED_NOTE, encoding="utf-8")

    _ = (start / ".cheese" / "notes" / "context.md").write_text("context\n", encoding="utf-8")
    found = resolve_mod.resolve(str(note), workspace_root=tmp_path / "elsewhere")

    assert found.outcome is resolve_mod.ResolutionOutcome.LEGACY
    assert found.legacy_note == note
    assert found.searched == (str(note),)


def test_wrapped_needs_context_status_gates_and_carries_the_gap(tmp_path: Path) -> None:
    """#16: a `needs-context` legacy note gates (retry disposition), and the
    gap it names survives into the gating detail."""
    start = tmp_path / "start"
    start.mkdir()
    note = start / ".cheese" / "notes" / "needs-context.md"
    note.parent.mkdir(parents=True)
    _ = (start / ".cheese" / "notes" / "context.md").write_text("context\n", encoding="utf-8")
    _ = note.write_text(
        WRAPPED_NOTE.replace(
            "status: ok", "status: needs-context: missing the migration plan"
        ),
        encoding="utf-8",
    )

    found = resolve_mod.resolve_legacy(
        "needs-context", start=start, run=fake_runner(porcelain(start))
    )

    assert found.outcome is resolve_mod.ResolutionOutcome.GATED
    assert "missing the migration plan" in (found.detail or "")
    assert not found.dispatchable


def test_wrapped_ok_with_concerns_resolves_without_gating_and_keeps_its_reason(
    tmp_path: Path,
) -> None:
    """#16: a proceed status that still carries a concern must not gate, and
    the concern must survive onto the resolved legacy slug."""
    start = tmp_path / "start"
    start.mkdir()
    note = start / ".cheese" / "notes" / "ok-with-concerns.md"
    note.parent.mkdir(parents=True)
    _ = (start / ".cheese" / "notes" / "context.md").write_text("context\n", encoding="utf-8")
    _ = note.write_text(
        WRAPPED_NOTE.replace(
            "status: ok", "status: ok-with-concerns: double-check the migration"
        ),
        encoding="utf-8",
    )

    found = resolve_mod.resolve_legacy(
        "ok-with-concerns", start=start, run=fake_runner(porcelain(start))
    )

    assert found.outcome is resolve_mod.ResolutionOutcome.LEGACY
    assert found.legacy_slug is not None
    assert found.legacy_slug.status == "ok-with-concerns"
    assert found.legacy_slug.reason == "double-check the migration"


def test_wrapped_gated_status_blocks_legacy_resume(tmp_path: Path) -> None:
    start = tmp_path / "start"
    start.mkdir()
    note = start / ".cheese" / "notes" / "gated.md"
    note.parent.mkdir(parents=True)
    _ = note.write_text(WRAPPED_NOTE.replace("status: ok", "status: gated: decide"), encoding="utf-8")

    found = resolve_mod.resolve_legacy(
        "gated", start=start, run=fake_runner(porcelain(start))
    )

    assert found.outcome is resolve_mod.ResolutionOutcome.GATED
    assert "gated" in (found.detail or "")
    assert not found.dispatchable


@pytest.mark.parametrize(
    ("body", "detail"),
    [
        (
            "## Handoff slug\n\n~~~text\nstatus: ok\nnext: mold\nartifact: \n",
            "handoff wrapper fence is not closed",
        ),
        (WRAPPED_NOTE + "\n## Handoff slug\n", "multiple handoff wrappers"),
    ],
)
def test_malformed_or_ambiguous_wrappers_are_rejected(
    tmp_path: Path, body: str, detail: str
) -> None:
    start = tmp_path / "start"
    start.mkdir()
    note = start / ".cheese" / "notes" / "bad.md"
    note.parent.mkdir(parents=True)
    _ = note.write_text(body, encoding="utf-8")

    found = resolve_mod.resolve_legacy(
        "bad", start=start, run=fake_runner(porcelain(start))
    )

    assert found.outcome is resolve_mod.ResolutionOutcome.ERROR
    assert found.legacy_note == note
    assert detail in (found.detail or "")


def test_unresolvable_absolute_legacy_path_is_an_error(tmp_path: Path) -> None:
    loop = tmp_path / "loop"
    loop.symlink_to(loop)

    found = resolve_mod.resolve_legacy(
        str(loop / ".cheese" / "notes" / "wrapped.md"), start=tmp_path
    )

    assert found.outcome is resolve_mod.ResolutionOutcome.ERROR
    assert "could not be resolved" in (found.detail or "")


def _resolve_legacy_artifact(tmp_path: Path, artifact: str) -> resolve_mod.Resolution:
    start = tmp_path / "start"
    start.mkdir()
    note = start / ".cheese" / "notes" / "artifact.md"
    note.parent.mkdir(parents=True)
    _ = note.write_text(
        WRAPPED_NOTE.replace(
            "artifact: .cheese/notes/context.md", f"artifact: {artifact}"
        ),
        encoding="utf-8",
    )
    return resolve_mod.resolve_legacy(
        "artifact", start=start, run=fake_runner(porcelain(start))
    )


def test_legacy_artifact_absolute_path_is_gated(tmp_path: Path) -> None:
    external = tmp_path / "outside.txt"
    _ = external.write_text("outside\n", encoding="utf-8")

    found = _resolve_legacy_artifact(tmp_path, str(external))

    assert found.outcome is resolve_mod.ResolutionOutcome.GATED
    assert "repo-relative" in (found.detail or "")


def test_legacy_artifact_traversal_escape_is_gated(tmp_path: Path) -> None:
    _ = (tmp_path / "outside.txt").write_text("outside\n", encoding="utf-8")

    found = _resolve_legacy_artifact(tmp_path, "../outside.txt")

    assert found.outcome is resolve_mod.ResolutionOutcome.GATED
    assert "outside" in (found.detail or "")


def test_legacy_artifact_symlink_escape_is_gated(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    _ = (outside / "secret.txt").write_text("secret\n", encoding="utf-8")
    start = tmp_path / "start"
    start.mkdir()
    (start / "link").symlink_to(outside, target_is_directory=True)

    note = start / ".cheese" / "notes" / "artifact.md"
    note.parent.mkdir(parents=True)
    _ = note.write_text(
        WRAPPED_NOTE.replace(
            "artifact: .cheese/notes/context.md", "artifact: link/secret.txt"
        ),
        encoding="utf-8",
    )
    found = resolve_mod.resolve_legacy(
        "artifact", start=start, run=fake_runner(porcelain(start))
    )

    assert found.outcome is resolve_mod.ResolutionOutcome.GATED
    assert "outside" in (found.detail or "")


def test_legacy_artifact_directory_is_gated(tmp_path: Path) -> None:
    found = _resolve_legacy_artifact(tmp_path, ".cheese/notes")

    assert found.outcome is resolve_mod.ResolutionOutcome.GATED
    assert "regular file" in (found.detail or "")


def test_repo_relative_regular_legacy_artifact_is_accepted(tmp_path: Path) -> None:
    start = tmp_path / "start"
    start.mkdir()
    context = start / ".cheese" / "notes" / "context.md"
    context.parent.mkdir(parents=True)
    _ = context.write_text("context\n", encoding="utf-8")
    note = context.parent / "artifact.md"
    _ = note.write_text(WRAPPED_NOTE, encoding="utf-8")

    found = resolve_mod.resolve_legacy(
        "artifact", start=start, run=fake_runner(porcelain(start))
    )

    assert found.outcome is resolve_mod.ResolutionOutcome.LEGACY
    assert found.detail is None
    assert not found.dispatchable
