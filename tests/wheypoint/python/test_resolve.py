"""Resolution: fixed precedence, no recency, and nothing dispatches unverified."""

from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path

import pytest

import canonical
import records
import resolve as resolve_mod
import storage

PROJECT = "paulnsorensen-easy-cheese"
NOTE = "status: ok\nnext: cook\nartifact: {artifact}\nPick the loop back up.\n"


def seed(
    corpus_root: Path,
    make_record,
    make_promotion,
    *,
    work_id: str,
    slug: str,
    gating: bool = False,
    revision_id: str = "rev-0001",
    number: int = 1,
) -> storage.WorkStore:
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
    return store


def run(ref: str, corpus_root: Path, **kwargs) -> resolve_mod.Resolution:
    kwargs.setdefault("project_key", PROJECT)
    kwargs.setdefault("git_object_exists", lambda obj: True)
    kwargs.setdefault("artifact_digest", lambda path: None)
    return resolve_mod.resolve(ref, corpus_root=corpus_root, **kwargs)


def test_an_exact_work_id_beats_another_record_holding_that_slug(
    corpus_root, make_record, make_promotion
) -> None:
    seed(corpus_root, make_record, make_promotion, work_id="alpha", slug="beta")
    seed(corpus_root, make_record, make_promotion, work_id="gamma", slug="alpha")

    found = run("alpha", corpus_root)

    assert found.outcome is resolve_mod.ResolutionOutcome.AUTHORITATIVE
    assert found.source is resolve_mod.ResolutionSource.WORK_ID
    assert found.work_id == "alpha"


def test_an_explicit_path_beats_the_corpus_lookups(
    corpus_root, make_record, make_promotion
) -> None:
    store = seed(corpus_root, make_record, make_promotion, work_id="alpha", slug="beta")
    path = store.projection_path(1, "rev-0001")

    found = run(str(path), corpus_root)

    assert found.source is resolve_mod.ResolutionSource.PATH
    assert found.outcome is resolve_mod.ResolutionOutcome.AUTHORITATIVE
    assert found.work_id == "alpha"
    assert found.searched == (str(path),)


def test_a_unique_slug_resolves_when_no_work_id_matches(
    corpus_root, make_record, make_promotion
) -> None:
    seed(corpus_root, make_record, make_promotion, work_id="work-0001", slug="kernel")

    found = run("kernel", corpus_root)

    assert found.outcome is resolve_mod.ResolutionOutcome.AUTHORITATIVE
    assert found.source is resolve_mod.ResolutionSource.SLUG
    assert found.work_id == "work-0001"
    assert found.record is not None
    assert found.projection is not None
    assert found.dispatchable


@pytest.mark.parametrize("newer", ["work-0001", "work-0002"])
def test_one_slug_on_two_records_is_ambiguous_whichever_is_newer(
    corpus_root, make_record, make_promotion, newer: str
) -> None:
    """A recency tiebreak would pick the newer record; ambiguity must not."""
    for work_id in ("work-0001", "work-0002"):
        store = seed(
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


def test_a_miss_lists_exactly_the_corpus_locations_searched(corpus_root) -> None:
    work_root = corpus_root / "work"

    found = run("kernel", corpus_root)

    assert found.outcome is resolve_mod.ResolutionOutcome.NOT_FOUND
    assert found.searched == (
        str(work_root / "kernel" / "record.json"),
        str(work_root / "*" / "record.json"),
    )


def test_a_missing_explicit_path_reports_only_that_path(
    corpus_root, tmp_path: Path
) -> None:
    missing = tmp_path / "nope.md"

    found = run(str(missing), corpus_root)

    assert found.outcome is resolve_mod.ResolutionOutcome.NOT_FOUND
    assert found.searched == (str(missing),)


def test_a_path_that_is_not_a_projection_is_an_error(
    corpus_root, tmp_path: Path
) -> None:
    stray = tmp_path / "notes.md"
    stray.write_text("# just markdown\n", encoding="utf-8")

    found = run(str(stray), corpus_root)

    assert found.outcome is resolve_mod.ResolutionOutcome.ERROR
    assert found.findings[0].code.value == "projection-unreadable"


def test_a_superseded_projection_path_does_not_dispatch(
    corpus_root, make_record, make_promotion
) -> None:
    store = seed(corpus_root, make_record, make_promotion, work_id="alpha", slug="beta")
    stale = store.projection_path(1, "rev-0001")
    second = make_promotion(
        2,
        "rev-0002",
        parent="rev-0001",
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
    corpus_root, make_record, make_promotion
) -> None:
    seed(
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
    corpus_root, make_record, make_promotion
) -> None:
    store = seed(
        corpus_root, make_record, make_promotion, work_id="work-0001", slug="kernel"
    )
    forged = records.unstructure(store.read_record())
    forged["orientation"] = "edited behind the runtime's back"
    store.record_path.write_bytes(canonical.canonical_bytes(forged))

    found = run("kernel", corpus_root)

    assert found.outcome is resolve_mod.ResolutionOutcome.GATED
    assert found.findings[0].code.value == "store-inconsistent"
    assert not found.dispatchable


def test_a_declared_commit_that_is_gone_gates(
    corpus_root, make_record, make_promotion
) -> None:
    seed(
        corpus_root, make_record, make_promotion, work_id="work-0001", slug="kernel"
    )

    found = run("kernel", corpus_root, git_object_exists=lambda obj: False)

    assert found.outcome is resolve_mod.ResolutionOutcome.GATED
    assert found.findings[0].code.value == "git-object-missing"


def test_a_record_from_another_project_never_resolves_here(
    corpus_root, make_record, make_promotion
) -> None:
    seed(
        corpus_root, make_record, make_promotion, work_id="work-0001", slug="kernel"
    )

    found = run("kernel", corpus_root, project_key="someone-else-other-repo")

    assert found.outcome is resolve_mod.ResolutionOutcome.GATED
    assert found.findings[0].code.value == "project-mismatch"


@pytest.mark.parametrize("ref", ["", "   ", "Not An Id", "UPPER"])
def test_a_reference_that_is_neither_path_nor_identifier_is_an_error(
    corpus_root, ref: str
) -> None:
    found = run(ref, corpus_root)

    assert found.outcome is resolve_mod.ResolutionOutcome.ERROR
    assert found.detail is not None


# ----- legacy fallback -----------------------------------------------------


def porcelain(*roots: Path) -> str:
    return "\n".join(f"worktree {root}\nbranch refs/heads/wt\n" for root in roots)


def fake_runner(output: str):
    def run_git(args: Sequence[str], cwd: Path) -> str:
        return output

    return run_git


def write_note(root: Path, slug: str, *, artifact: str = "") -> Path:
    path = root / ".cheese" / "notes" / f"{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(NOTE.format(artifact=artifact), encoding="utf-8")
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
    write_note(start, "cold-start", artifact=".cheese/cook/cold-start.md")

    found = resolve_mod.resolve_legacy(
        "cold-start", start=start, run=fake_runner(porcelain(start))
    )

    assert found.outcome is resolve_mod.ResolutionOutcome.GATED
    assert found.detail is not None
    assert ".cheese/cook/cold-start.md" in found.detail


def test_a_legacy_note_whose_artifact_resolves_is_returned(tmp_path: Path) -> None:
    start = tmp_path / "start"
    start.mkdir()
    write_note(start, "cold-start", artifact=".cheese/cook/cold-start.md")
    report = start / ".cheese" / "cook" / "cold-start.md"
    report.parent.mkdir(parents=True)
    report.write_text("prior report\n", encoding="utf-8")

    found = resolve_mod.resolve_legacy(
        "cold-start", start=start, run=fake_runner(porcelain(start))
    )

    assert found.outcome is resolve_mod.ResolutionOutcome.LEGACY


def test_an_unparsable_legacy_note_is_an_error(tmp_path: Path) -> None:
    start = tmp_path / "start"
    start.mkdir()
    path = start / ".cheese" / "notes" / "cold-start.md"
    path.parent.mkdir(parents=True)
    path.write_text("# not a handoff note\n\nbody\n", encoding="utf-8")

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
