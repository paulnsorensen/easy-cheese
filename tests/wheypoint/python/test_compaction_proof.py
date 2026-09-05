"""Lint re-derives the whole compaction proof, not one third of it.

Commit checks the quoted record digest and the reconciled entry ledger before
it writes. Lint reads the same receipt back from disk, so it has to check both
again, and it has to place each prior compaction behind the revision that
chains to it.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from attrs import evolve
from easy_cheese_schemas import CompactionRecord, EntryKind, EntryState, ProtectedEntry

from easy_cheese.skills.wheypoint import lint, records, storage

from conftest import Promotion

PROJECT = "paulnsorensen-easy-cheese"
FALSE_DIGEST = "sha256:" + "9" * 64


def _store(corpus_root: Path) -> storage.WorkStore:
    return storage.WorkStore.open("work-0001", corpus_root=corpus_root)


def _check(store: storage.WorkStore) -> lint.LintReport:
    return lint.lint_work(
        store,
        project_key=PROJECT,
        git_object_exists=lambda _obj: True,
        artifact_digest=lambda _path: None,
    )


def _compacted(promotion: Promotion, compaction: CompactionRecord) -> Promotion:
    revision = evolve(promotion.revision, compaction=compaction)
    return Promotion(
        record=evolve(
            promotion.record, revision_digest=records.revision_digest(revision)
        ),
        revision=revision,
        markdown=promotion.markdown,
    )


GATE_ID = "q-durability"


def _gate() -> ProtectedEntry:
    """The entry the gating fixture record carries."""
    return ProtectedEntry(
        entry_id=GATE_ID,
        kind=EntryKind.QUESTION,
        state=EntryState.ACTIVE,
        summary="Should durability default to repo-snapshot?",
        blocks_continuation=True,
    )


def test_a_false_rehydrated_record_digest_blocks(
    corpus_root: Path, make_promotion: Callable[..., Promotion]
) -> None:
    store = _store(corpus_root)
    first = make_promotion(1, "rev-0001")
    store.promote(first.record, first.revision, first.markdown)
    second = _compacted(
        make_promotion(2, "rev-0002", parent=first),
        CompactionRecord(
            rehydrated_from_revision_id="rev-0001",
            rehydrated_record_digest=FALSE_DIGEST,
            reconciled_entry_ids=[],
        ),
    )
    store.promote(second.record, second.revision, second.markdown)

    report = _check(store)

    assert report.codes == (lint.LintCode.COMPACTION_PARENT_UNRESOLVED,)
    assert report.findings[0].detail == (
        f"revision 'rev-0002' quotes rehydrated record digest {FALSE_DIGEST}, "
        f"but revision 'rev-0001' recorded {first.revision.record_digest}"
    )
    assert lint.gates_continuation(report.findings[0])


def test_an_empty_ledger_over_a_protected_entry_blocks(
    corpus_root: Path, make_promotion: Callable[..., Promotion]
) -> None:
    """A compaction that reconciles nothing cannot have reloaded a live gate."""
    store = _store(corpus_root)
    gate = _gate()
    first = make_promotion(1, "rev-0001", gating=True, additions=[gate])
    store.promote(first.record, first.revision, first.markdown)
    second = _compacted(
        make_promotion(2, "rev-0002", parent=first, gating=True, preserved=[GATE_ID]),
        CompactionRecord(
            rehydrated_from_revision_id="rev-0001",
            rehydrated_record_digest=first.revision.record_digest,
            reconciled_entry_ids=[],
        ),
    )
    store.promote(second.record, second.revision, second.markdown)

    report = _check(store)

    assert lint.LintCode.COMPACTION_PARENT_UNRESOLVED in report.codes
    assert (
        f"revision 'rev-0002' reconciled no entry {GATE_ID!r} that revision "
        "'rev-0001' still carried"
    ) in [finding.detail for finding in report.findings]


def test_a_compaction_that_chains_to_itself_blocks(
    corpus_root: Path, make_promotion: Callable[..., Promotion]
) -> None:
    store = _store(corpus_root)
    first = make_promotion(1, "rev-0001")
    store.promote(first.record, first.revision, first.markdown)
    second = _compacted(
        make_promotion(2, "rev-0002", parent=first),
        CompactionRecord(
            rehydrated_from_revision_id="rev-0001",
            rehydrated_record_digest=first.revision.record_digest,
            reconciled_entry_ids=[],
            prior_compaction_revision_id="rev-0002",
        ),
    )
    store.promote(second.record, second.revision, second.markdown)

    report = _check(store)

    assert report.codes == (lint.LintCode.COMPACTION_PARENT_UNRESOLVED,)
    assert report.findings[0].detail == (
        "revision 'rev-0002' chains to prior compaction 'rev-0002', which is "
        "not behind it in the proven ancestry of this revision"
    )


def test_a_compaction_that_chains_to_a_descendant_blocks(
    corpus_root: Path, make_promotion: Callable[..., Promotion]
) -> None:
    """The chain runs current-first, so a descendant sits at a lower position."""
    store = _store(corpus_root)
    first = make_promotion(1, "rev-0001")
    store.promote(first.record, first.revision, first.markdown)
    second = _compacted(
        make_promotion(2, "rev-0002", parent=first),
        CompactionRecord(
            rehydrated_from_revision_id="rev-0001",
            rehydrated_record_digest=first.revision.record_digest,
            reconciled_entry_ids=[],
            prior_compaction_revision_id="rev-0003",
        ),
    )
    store.promote(second.record, second.revision, second.markdown)
    third = _compacted(
        make_promotion(3, "rev-0003", parent=second),
        CompactionRecord(
            rehydrated_from_revision_id="rev-0002",
            rehydrated_record_digest=second.revision.record_digest,
            reconciled_entry_ids=[],
            prior_compaction_revision_id="rev-0002",
        ),
    )
    store.promote(third.record, third.revision, third.markdown)

    report = _check(store)

    assert report.codes == (lint.LintCode.COMPACTION_PARENT_UNRESOLVED,)
    assert report.findings[0].detail == (
        "revision 'rev-0002' chains to prior compaction 'rev-0003', which is "
        "not behind it in the proven ancestry of this revision"
    )


def test_a_complete_compaction_proof_lints_clean(
    corpus_root: Path, make_promotion: Callable[..., Promotion]
) -> None:
    store = _store(corpus_root)
    gate = _gate()
    first = make_promotion(1, "rev-0001", gating=True, additions=[gate])
    store.promote(first.record, first.revision, first.markdown)
    second = _compacted(
        make_promotion(2, "rev-0002", parent=first, gating=True, preserved=[GATE_ID]),
        CompactionRecord(
            rehydrated_from_revision_id="rev-0001",
            rehydrated_record_digest=first.revision.record_digest,
            reconciled_entry_ids=[GATE_ID],
        ),
    )
    store.promote(second.record, second.revision, second.markdown)

    report = _check(store)

    # The gated checkpoint is canonical-local, so only the durability advisory
    # remains. No compaction finding survives a complete proof.
    assert report.codes == (lint.LintCode.DURABILITY_LOCAL_ONLY,)
    assert not lint.gates_continuation(report.findings[0])
