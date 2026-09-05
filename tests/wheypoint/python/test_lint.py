"""Lint: a checkpoint is only dispatchable when the disk still proves it."""

from __future__ import annotations

from easy_cheese_schemas import SCHEMA_VERSION
import os
import re
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import cast
from typing import Protocol

import pytest
from attrs import evolve
from easy_cheese_schemas import (
    ArtifactLink,
    CompactionRecord,
    Durability,
    EntryKind,
    EntryState,
    ProtectedEntry,
    WheypointRecord,
    WheypointRevision,
)

from easy_cheese.skills.wheypoint import canonical, lint, projection, records, storage

from conftest import Promotion

PROJECT = "paulnsorensen-easy-cheese"


def all_objects_exist(_obj: str) -> bool:
    return True


def no_artifacts(_path: str) -> str | None:
    return None


class _PromotionLike(Protocol):
    record: WheypointRecord
    revision: WheypointRevision
    markdown: str


def make_store(corpus_root: Path) -> storage.WorkStore:
    return storage.WorkStore.open("work-0001", corpus_root=corpus_root)


def check(
    store: storage.WorkStore,
    *,
    project_key: str = PROJECT,
    git_object_exists: Callable[[str], bool] = all_objects_exist,
    artifact_digest: Callable[[str], str | None] = no_artifacts,
) -> lint.LintReport:
    return lint.lint_work(
        store,
        project_key=project_key,
        git_object_exists=git_object_exists,
        artifact_digest=artifact_digest,
    )


def test_a_consistent_promotion_lints_clean(
    corpus_root: Path, make_promotion: Callable[..., _PromotionLike]
) -> None:
    store = make_store(corpus_root)
    promotion = make_promotion()
    store.promote(promotion.record, promotion.revision, promotion.markdown)

    report = check(store)

    assert report.codes == ()
    assert report.ok
    assert report.record is not None
    assert report.projection is not None
    assert report.projection.revision_id == "rev-0001"


def test_an_empty_store_reports_the_missing_record_path(corpus_root: Path) -> None:
    store = make_store(corpus_root)

    report = check(store)

    assert report.codes == (lint.LintCode.RECORD_MISSING,)
    assert str(store.record_path) in report.findings[0].detail


def test_a_tampered_projection_fails_its_own_digest(
    corpus_root: Path, make_promotion: Callable[..., _PromotionLike]
) -> None:
    store = make_store(corpus_root)
    promotion = make_promotion()
    store.promote(promotion.record, promotion.revision, promotion.markdown)
    path = store.projection_path(1, "rev-0001")
    _ = path.write_text(
        promotion.markdown.replace("status: ok", "status: gated"), encoding="utf-8"
    )

    report = check(store)

    assert lint.LintCode.PROJECTION_DIGEST_MISMATCH in report.codes
    assert not report.ok


_DIGEST_LINE = re.compile(r"^projection_digest:.*$", re.MULTILINE)


def _repin(text: str) -> str:
    """Re-hash a hand-edited document so it passes its own digest check."""
    digest = projection.projection_digest_of_text(text)
    return _DIGEST_LINE.sub(f"projection_digest: {digest}", text, count=1)


def test_a_projection_written_gated_while_nothing_gates_is_reported(
    make_promotion: Callable[..., _PromotionLike],
) -> None:
    """A hand-authored note can hash itself, so the digest cannot catch a
    header that contradicts the gates the document actually lists."""
    lying = _repin(make_promotion().markdown.replace("status: ok", "status: gated"))

    report = lint.lint_projection_text(lying)

    assert report.codes == (lint.LintCode.PROJECTION_STATUS_MISMATCH,)
    assert "'gated'" in report.findings[0].detail
    assert "'ok'" in report.findings[0].detail


def test_a_projection_written_ok_over_a_live_gate_is_reported(
    corpus_root: Path, make_promotion: Callable[..., _PromotionLike]
) -> None:
    store = make_store(corpus_root)
    promotion = make_promotion(gating=True)
    store.promote(promotion.record, promotion.revision, promotion.markdown)
    path = store.projection_path(1, "rev-0001")
    _ = path.write_text(
        _repin(promotion.markdown.replace("status: gated", "status: ok")),
        encoding="utf-8",
    )

    report = check(store)

    assert lint.LintCode.PROJECTION_STATUS_MISMATCH in report.codes
    assert lint.LintCode.PROJECTION_DIGEST_MISMATCH not in report.codes
    assert not report.ok


def test_an_honest_projection_status_is_not_reported(
    make_promotion: Callable[..., _PromotionLike],
) -> None:
    for gating in (False, True):
        report = lint.lint_projection_text(make_promotion(gating=gating).markdown)
        assert report.codes == (), gating


def test_a_tampered_record_fails_the_digest_its_receipt_quotes(
    corpus_root: Path, make_promotion: Callable[..., _PromotionLike]
) -> None:
    store = make_store(corpus_root)
    promotion = make_promotion()
    store.promote(promotion.record, promotion.revision, promotion.markdown)
    forged = records.unstructure(promotion.record)
    forged["orientation"] = "someone edited the authority directly"
    _ = store.record_path.write_bytes(canonical.canonical_bytes(forged))

    report = check(store)

    assert lint.LintCode.STORE_INCONSISTENT in report.codes


def test_a_missing_parent_revision_blocks(
    corpus_root: Path, make_promotion: Callable[..., _PromotionLike]
) -> None:
    store = make_store(corpus_root)
    promotion = make_promotion(parent="rev-0000")
    store.promote(promotion.record, promotion.revision, promotion.markdown)

    report = check(store)

    assert report.codes == (lint.LintCode.PARENT_UNRESOLVED,)
    assert "rev-0000" in report.findings[0].detail


def test_a_present_parent_chain_lints_clean(
    corpus_root: Path, make_promotion: Callable[..., _PromotionLike]
) -> None:
    store = make_store(corpus_root)
    first = make_promotion(1, "rev-0001")
    store.promote(first.record, first.revision, first.markdown)
    second = make_promotion(2, "rev-0002", parent=first)
    store.promote(second.record, second.revision, second.markdown)

    report = check(store)

    assert report.codes == ()
    assert report.record is not None
    assert report.record.revision_id == "rev-0002"


def test_a_tampered_ancestor_receipt_breaks_the_pin_and_stops_the_walk(
    corpus_root: Path, make_promotion: Callable[..., _PromotionLike]
) -> None:
    """Editing a receipt after the fact is exactly what the pin catches.

    `preserved_entry_ids` is covered by no record digest, so this edit was
    invisible before the pin. The forged carry-forward is also how the break is
    observed: had the walk continued past the tampered link, 'q-forged' would
    have been accounted for by lineage and lost by the record, and a second
    finding would stand beside this one.
    """
    store = make_store(corpus_root)
    first = make_promotion(1, "rev-0001")
    store.promote(first.record, first.revision, first.markdown)
    second = make_promotion(2, "rev-0002", parent=first)
    store.promote(second.record, second.revision, second.markdown)
    third = make_promotion(3, "rev-0003", parent=second)
    store.promote(third.record, third.revision, third.markdown)
    tampered = evolve(second.revision, preserved_entry_ids=["q-forged"])
    _ = store.revision_path(2, "rev-0002").write_bytes(
        records.canonical_payload(tampered)
    )

    report = check(store)

    assert report.codes == (lint.LintCode.PARENT_DIGEST_MISMATCH,)
    assert report.findings[0].detail.startswith(
        "revision 'rev-0003' pins parent 'rev-0002' at "
    )
    assert records.revision_digest(tampered) in report.findings[0].detail
    assert lint.gates_continuation(report.findings[0])


def test_a_current_receipt_that_names_a_parent_without_pinning_it_is_flagged(
    corpus_root: Path, make_promotion: Callable[..., _PromotionLike]
) -> None:
    store = make_store(corpus_root)
    first = make_promotion(1, "rev-0001")
    store.promote(first.record, first.revision, first.markdown)
    unpinned = make_promotion(2, "rev-0002", parent="rev-0001")
    store.promote(unpinned.record, unpinned.revision, unpinned.markdown)

    report = check(store)

    assert report.codes == (lint.LintCode.PARENT_DIGEST_MISMATCH,)
    assert report.findings[0].detail == (
        f"revision 'rev-0002' is stamped schema version {SCHEMA_VERSION} and names parent "
        "'rev-0001' without pinning its digest"
    )


def test_a_legacy_receipt_without_the_pin_is_left_alone(
    corpus_root: Path,
    make_record: Callable[..., WheypointRecord],
    make_promotion: Callable[..., _PromotionLike],
) -> None:
    """Schema version 1 predates the field, so its absence proves nothing."""
    store = make_store(corpus_root)
    first = make_promotion(1, "rev-0001", record=make_record(schema_version=1))
    store.promote(first.record, first.revision, first.markdown)
    second = make_promotion(
        2,
        "rev-0002",
        parent="rev-0001",
        record=make_record(schema_version=1, revision_id="rev-0002", revision_number=2),
    )
    legacy = evolve(second.revision, schema_version=1)
    store.promote(
        evolve(second.record, revision_digest=records.revision_digest(legacy)),
        legacy,
        second.markdown,
    )

    report = check(store)

    assert report.codes == ()


def _compacted(promotion: _PromotionLike, compaction: CompactionRecord) -> Promotion:
    """Re-seal a promotion around a compaction record.

    The receipt is what changes, so the record's pointer at it has to be
    restamped; the projection is untouched because the record digest it quotes
    deliberately excludes that pointer.
    """
    revision = evolve(promotion.revision, compaction=compaction)
    return Promotion(
        record=evolve(
            promotion.record, revision_digest=records.revision_digest(revision)
        ),
        revision=revision,
        markdown=promotion.markdown,
    )


def test_a_compaction_that_rehydrated_from_another_revision_blocks(
    corpus_root: Path, make_promotion: Callable[..., _PromotionLike]
) -> None:
    """Reconciling against one revision and committing onto another means the
    state that was reloaded is not the state that was extended."""
    store = make_store(corpus_root)
    first = make_promotion(1, "rev-0001")
    store.promote(first.record, first.revision, first.markdown)
    second = _compacted(
        make_promotion(2, "rev-0002", parent=first),
        CompactionRecord(
            rehydrated_from_revision_id="rev-0000",
            rehydrated_record_digest=records.record_digest(first.record),
            reconciled_entry_ids=[],
        ),
    )
    store.promote(second.record, second.revision, second.markdown)

    report = check(store)

    assert report.codes == (lint.LintCode.COMPACTION_PARENT_UNRESOLVED,)
    assert report.findings[0].detail == (
        "revision 'rev-0002' rehydrated from 'rev-0000' but was written onto "
        "parent 'rev-0001'"
    )
    assert lint.gates_continuation(report.findings[0])


def test_a_prior_compaction_outside_the_proven_ancestry_blocks(
    corpus_root: Path, make_promotion: Callable[..., _PromotionLike]
) -> None:
    store = make_store(corpus_root)
    first = make_promotion(1, "rev-0001")
    store.promote(first.record, first.revision, first.markdown)
    second = _compacted(
        make_promotion(2, "rev-0002", parent=first),
        CompactionRecord(
            rehydrated_from_revision_id="rev-0001",
            rehydrated_record_digest=records.record_digest(first.record),
            reconciled_entry_ids=[],
            prior_compaction_revision_id="rev-9999",
        ),
    )
    store.promote(second.record, second.revision, second.markdown)

    report = check(store)

    assert report.codes == (lint.LintCode.COMPACTION_PARENT_UNRESOLVED,)
    assert report.findings[0].detail == (
        "revision 'rev-0002' chains to prior compaction 'rev-9999', which is "
        "not in the proven ancestry of this revision"
    )


def test_a_prior_compaction_naming_a_revision_that_never_compacted_blocks(
    corpus_root: Path, make_promotion: Callable[..., _PromotionLike]
) -> None:
    """Being an ancestor is not enough: the predecessor has to be a compaction."""
    store = make_store(corpus_root)
    first = make_promotion(1, "rev-0001")
    store.promote(first.record, first.revision, first.markdown)
    second = _compacted(
        make_promotion(2, "rev-0002", parent=first),
        CompactionRecord(
            rehydrated_from_revision_id="rev-0001",
            rehydrated_record_digest=records.record_digest(first.record),
            reconciled_entry_ids=[],
            prior_compaction_revision_id="rev-0001",
        ),
    )
    store.promote(second.record, second.revision, second.markdown)

    report = check(store)

    assert report.codes == (lint.LintCode.COMPACTION_PARENT_UNRESOLVED,)
    assert report.findings[0].detail == (
        "revision 'rev-0002' chains to prior compaction 'rev-0001', which "
        "records no compaction"
    )


def test_a_lineage_that_survived_two_compactions_lints_clean(
    corpus_root: Path, make_promotion: Callable[..., _PromotionLike]
) -> None:
    """The chain reads as a history: each compaction rehydrated from the parent
    it wrote onto, and named the compaction behind it."""
    store = make_store(corpus_root)
    first = make_promotion(1, "rev-0001")
    store.promote(first.record, first.revision, first.markdown)
    second = _compacted(
        make_promotion(2, "rev-0002", parent=first),
        CompactionRecord(
            rehydrated_from_revision_id="rev-0001",
            rehydrated_record_digest=records.record_digest(first.record),
            reconciled_entry_ids=[],
        ),
    )
    store.promote(second.record, second.revision, second.markdown)
    third = _compacted(
        make_promotion(3, "rev-0003", parent=second),
        CompactionRecord(
            rehydrated_from_revision_id="rev-0002",
            rehydrated_record_digest=records.record_digest(second.record),
            reconciled_entry_ids=[],
            prior_compaction_revision_id="rev-0002",
        ),
    )
    store.promote(third.record, third.revision, third.markdown)

    report = check(store)

    assert report.codes == ()


def test_a_gated_canonical_local_checkpoint_warns_without_blocking(
    corpus_root: Path, make_promotion: Callable[..., _PromotionLike]
) -> None:
    """The gates are human-owed state that lives nowhere but this corpus."""
    store = make_store(corpus_root)
    promotion = make_promotion(gating=True)
    store.promote(promotion.record, promotion.revision, promotion.markdown)

    report = check(store)

    assert report.codes == (lint.LintCode.DURABILITY_LOCAL_ONLY,)
    assert not lint.gates_continuation(report.findings[0])
    detail = report.findings[0].detail
    assert "q-durability" in detail
    assert "canonical-local" in detail
    assert "Preserve it" in detail and "publish it" in detail
    assert "never commits and never publishes" in detail


def test_a_settled_canonical_local_checkpoint_is_not_warned_about(
    corpus_root: Path, make_promotion: Callable[..., _PromotionLike]
) -> None:
    """Nothing is owed, so a local-only projection loses nothing: the record
    it was generated from is right there beside it."""
    store = make_store(corpus_root)
    promotion = make_promotion(gating=False)
    store.promote(promotion.record, promotion.revision, promotion.markdown)

    report = check(store)

    assert report.codes == ()


@pytest.mark.parametrize(
    "durability", [Durability.REPO_SNAPSHOT, Durability.PUBLISHED]
)
def test_a_gated_checkpoint_that_has_travelled_is_not_warned_about(
    corpus_root: Path,
    make_promotion: Callable[..., _PromotionLike],
    durability: Durability,
) -> None:
    store = make_store(corpus_root)
    promotion = make_promotion(gating=True)
    # Durability is part of the projection document, so travelling it re-hashes
    # the projection and the receipt that quotes it.
    projected, markdown = projection.build_projection(
        promotion.record, durability=durability
    )
    revision = evolve(
        promotion.revision, projection_digest=projected.projection_digest
    )
    store.promote(
        evolve(promotion.record, revision_digest=records.revision_digest(revision)),
        revision,
        markdown,
    )

    report = check(store)

    assert report.codes == ()


def test_a_record_from_another_project_never_dispatches_here(
    corpus_root: Path, make_promotion: Callable[..., _PromotionLike]
) -> None:
    store = make_store(corpus_root)
    promotion = make_promotion()
    store.promote(promotion.record, promotion.revision, promotion.markdown)

    report = check(store, project_key="someone-else-other-repo")

    assert report.codes == (lint.LintCode.PROJECT_MISMATCH,)
    assert "someone-else-other-repo" in report.findings[0].detail


def test_a_declared_commit_that_no_longer_resolves_blocks(
    corpus_root: Path, make_promotion: Callable[..., _PromotionLike]
) -> None:
    store = make_store(corpus_root)
    promotion = make_promotion()
    store.promote(promotion.record, promotion.revision, promotion.markdown)
    asked: list[str] = []

    def missing(obj: str) -> bool:
        asked.append(obj)
        return False

    report = check(store, git_object_exists=missing)

    assert asked == ["abc1234"]
    assert report.codes == (lint.LintCode.GIT_OBJECT_MISSING,)


# ----- same-slug replacement (issue #371) -----------------------------------


def decision(entry_id: str, summary: str) -> ProtectedEntry:
    return ProtectedEntry(
        entry_id=entry_id,
        kind=EntryKind.DECISION,
        summary=summary,
        state=EntryState.ACTIVE,
        blocks_continuation=False,
    )


def test_a_narrowed_rewrite_that_drops_a_prior_decision_is_reported(
    corpus_root: Path,
    make_record: Callable[..., WheypointRecord],
    make_promotion: Callable[..., _PromotionLike],
) -> None:
    """The incident: a full checkpoint is resumed, the topic is narrowed, and
    the next revision for the same work carries fewer decisions than its own
    lineage accounts for. Every digest agrees, so only the reconciliation pass
    against the chain can see the loss."""
    store = make_store(corpus_root)
    kept = decision("d-authority", "The record is the authority.")
    dropped = decision("d-projection", "The note is a projection.")
    full = make_promotion(
        1,
        "rev-0001",
        record=make_record(decisions=[kept, dropped]),
        additions=[kept, dropped],
    )
    store.promote(full.record, full.revision, full.markdown)
    narrowed = make_promotion(
        2,
        "rev-0002",
        parent=full,
        record=make_record(
            revision_id="rev-0002", revision_number=2, decisions=[kept]
        ),
        preserved=["d-authority"],
    )
    store.promote(narrowed.record, narrowed.revision, narrowed.markdown)

    report = check(store)

    assert report.codes == (lint.LintCode.ENTRY_DROPPED,)
    assert report.findings[0].detail == (
        "revision 'rev-0001' accounts for entry 'd-projection', which record "
        "'rev-0002' no longer carries"
    )


def test_a_rewrite_that_carries_every_accounted_entry_lints_clean(
    corpus_root: Path,
    make_record: Callable[..., WheypointRecord],
    make_promotion: Callable[..., _PromotionLike],
) -> None:
    store = make_store(corpus_root)
    kept = decision("d-authority", "The record is the authority.")
    carried = decision("d-projection", "The note is a projection.")
    full = make_promotion(
        1,
        "rev-0001",
        record=make_record(decisions=[kept, carried]),
        additions=[kept, carried],
    )
    store.promote(full.record, full.revision, full.markdown)
    later = make_promotion(
        2,
        "rev-0002",
        parent=full,
        record=make_record(
            revision_id="rev-0002", revision_number=2, decisions=[kept, carried]
        ),
        preserved=["d-authority", "d-projection"],
    )
    store.promote(later.record, later.revision, later.markdown)

    assert check(store).codes == ()


def test_an_entry_an_unreachable_sibling_added_is_not_accounted_for(
    corpus_root: Path,
    make_record: Callable[..., WheypointRecord],
    make_promotion: Callable[..., _PromotionLike],
) -> None:
    """Only the walked chain accounts for entries. A receipt that sits in the
    work directory without being an ancestor of the current revision never
    obliges the record to carry what it added."""
    store = make_store(corpus_root)
    kept = decision("d-authority", "The record is the authority.")
    sibling_only = decision("d-sibling", "Written down an abandoned branch.")
    sibling = make_promotion(
        1,
        "rev-0009",
        record=make_record(revision_id="rev-0009", decisions=[sibling_only]),
        additions=[sibling_only],
    )
    store.promote(sibling.record, sibling.revision, sibling.markdown)
    current = make_promotion(
        1, "rev-0001", record=make_record(decisions=[kept]), additions=[kept]
    )
    store.promote(current.record, current.revision, current.markdown)

    assert check(store).codes == ()


def covered_record(
    make_record: Callable[..., WheypointRecord], digest: str
) -> WheypointRecord:
    return make_record(
        decisions=[
            ProtectedEntry(
                entry_id="d-shape",
                kind=EntryKind.DECISION,
                summary="The record is the authority.",
                state=EntryState.ACTIVE,
                blocks_continuation=False,
            )
        ],
        artifact_links=[
            ArtifactLink(
                path="cook/report.md",
                digest=digest,
                covers_entry_ids=["d-shape"],
            )
        ],
    )


def test_a_stale_artifact_invalidates_its_claim_and_keeps_the_entry(
    corpus_root: Path,
    make_record: Callable[..., WheypointRecord],
    make_promotion: Callable[..., _PromotionLike],
) -> None:
    store = make_store(corpus_root)
    promotion = make_promotion(
        record=covered_record(make_record, canonical.digest_text("as written"))
    )
    store.promote(promotion.record, promotion.revision, promotion.markdown)

    report = check(
        store, artifact_digest=lambda path: canonical.digest_text("edited since")
    )

    assert report.codes == (lint.LintCode.ARTIFACT_COVERAGE_INVALID,)
    assert report.findings[0].detail == "cook/report.md: artifact digest mismatch"
    assert report.record is not None
    assert [entry.entry_id for entry in report.record.decisions] == ["d-shape"]


def test_a_pinned_artifact_that_still_matches_lints_clean(
    corpus_root: Path,
    make_record: Callable[..., WheypointRecord],
    make_promotion: Callable[..., _PromotionLike],
) -> None:
    store = make_store(corpus_root)
    pinned = canonical.digest_text("as written")
    promotion = make_promotion(record=covered_record(make_record, pinned))
    store.promote(promotion.record, promotion.revision, promotion.markdown)

    report = check(store, artifact_digest=lambda path: pinned)

    assert report.codes == ()


def revision_pinned_record(
    make_record: Callable[..., WheypointRecord],
    pinned_revision_id: str,
    **overrides: object,
) -> WheypointRecord:
    return make_record(
        decisions=[
            ProtectedEntry(
                entry_id="d-shape",
                kind=EntryKind.DECISION,
                summary="The record is the authority.",
                state=EntryState.ACTIVE,
                blocks_continuation=False,
            )
        ],
        artifact_links=[
            ArtifactLink(
                path="cook/report.md",
                revision_id=pinned_revision_id,
                covers_entry_ids=["d-shape"],
            )
        ],
        **overrides,
    )


def test_a_revision_pin_resolves_against_the_ancestry_not_the_directory(
    corpus_root: Path,
    make_record: Callable[..., WheypointRecord],
    make_promotion: Callable[..., _PromotionLike],
) -> None:
    """An abandoned sibling is still a file on disk. A claim pinned to one
    describes work this record never took, so it must not read as fresh."""
    store = make_store(corpus_root)
    sibling = make_promotion(
        1, "rev-0009", record=make_record(revision_id="rev-0009")
    )
    store.promote(sibling.record, sibling.revision, sibling.markdown)
    current = make_promotion(
        1, "rev-0001", record=revision_pinned_record(make_record, "rev-0009")
    )
    store.promote(current.record, current.revision, current.markdown)

    report = check(store, artifact_digest=lambda path: canonical.digest_text("here"))

    assert report.codes == (lint.LintCode.ARTIFACT_COVERAGE_INVALID,)
    assert report.findings[0].detail == (
        "cook/report.md: coverage pins unknown revision 'rev-0009'"
    )


def test_a_revision_pin_on_a_walked_ancestor_lints_clean(
    corpus_root: Path,
    make_record: Callable[..., WheypointRecord],
    make_promotion: Callable[..., _PromotionLike],
) -> None:
    store = make_store(corpus_root)
    first = make_promotion(1, "rev-0001")
    store.promote(first.record, first.revision, first.markdown)
    second = make_promotion(
        2,
        "rev-0002",
        parent=first,
        record=revision_pinned_record(
            make_record, "rev-0001", revision_id="rev-0002", revision_number=2
        ),
    )
    store.promote(second.record, second.revision, second.markdown)

    report = check(store, artifact_digest=lambda path: canonical.digest_text("here"))

    assert report.codes == ()


def test_a_revision_pinned_artifact_that_is_gone_invalidates_its_claim(
    corpus_root: Path,
    make_record: Callable[..., WheypointRecord],
    make_promotion: Callable[..., _PromotionLike],
) -> None:
    store = make_store(corpus_root)
    promotion = make_promotion(
        record=revision_pinned_record(make_record, "rev-0001")
    )
    store.promote(promotion.record, promotion.revision, promotion.markdown)

    report = check(store)

    assert report.codes == (lint.LintCode.ARTIFACT_COVERAGE_INVALID,)
    assert report.findings[0].detail == "cook/report.md: artifact is missing"


def test_an_interrupted_promotion_is_named_rather_than_reported_clean(
    corpus_root: Path, make_promotion: Callable[..., _PromotionLike]
) -> None:
    """A half-written pair is invisible to the record checks, so lint reports
    it directly: the operator has to be told the retry was interrupted."""
    store = make_store(corpus_root)
    promotion = make_promotion(1, "rev-0001")
    store.promote(promotion.record, promotion.revision, promotion.markdown)
    orphan = make_promotion(2, "rev-0002", parent="rev-0001")
    _ = store.revision_path(2, "rev-0002").write_bytes(
        records.canonical_payload(orphan.revision)
    )

    report = check(store)

    assert report.codes == (lint.LintCode.REVISION_INCOMPLETE,)
    assert report.findings[0].detail == "2-rev-0002.json: projection file is missing"
    assert report.record is not None
    assert report.record.revision_id == "rev-0001"


@pytest.mark.parametrize(
    "text",
    [
        "",
        "status: ok\nnext: cook\nartifact: x\nnot a preamble key\n",
        "# just a markdown file\n\nbody\n",
    ],
)
def test_text_that_is_not_a_projection_is_unreadable(text: str) -> None:
    report = lint.lint_projection_text(text)

    assert report.codes == (lint.LintCode.PROJECTION_UNREADABLE,)
    assert report.projection is None


def test_lint_projection_file_reports_a_missing_file(tmp_path: Path) -> None:
    report = lint.lint_projection_file(tmp_path / "absent.md")

    assert report.codes == (lint.LintCode.PROJECTION_UNREADABLE,)


def test_artifact_digest_in_hashes_relative_paths(tmp_path: Path) -> None:
    (tmp_path / "cook").mkdir()
    _ = (tmp_path / "cook" / "report.md").write_text("body", encoding="utf-8")
    digest = lint.artifact_digest_in(tmp_path)

    assert digest("cook/report.md") == canonical.digest_text("body")
    assert digest("cook/absent.md") is None


def test_artifact_digest_in_rejects_absolute_paths(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside.md"
    _ = outside.write_text("body", encoding="utf-8")

    assert lint.artifact_digest_in(root)(str(outside)) is None


def test_artifact_digest_in_rejects_parent_traversal(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    _ = (tmp_path / "outside.md").write_text("body", encoding="utf-8")

    assert lint.artifact_digest_in(root)("../outside.md") is None


def test_artifact_digest_in_rejects_symlink_escapes(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside.md"
    _ = outside.write_text("body", encoding="utf-8")
    (root / "link.md").symlink_to(outside)

    assert lint.artifact_digest_in(root)("link.md") is None


def test_artifact_digest_in_rejects_non_regular_paths(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "reports").mkdir()

    assert lint.artifact_digest_in(root)("reports") is None


def test_ac16_a_future_record_this_reader_cannot_structure_reports_runtime_behind_only(
    corpus_root: Path, make_promotion: Callable[..., _PromotionLike]
) -> None:
    import json

    from easy_cheese_schemas import SCHEMA_VERSION

    store = make_store(corpus_root)
    promotion = make_promotion()
    store.promote(promotion.record, promotion.revision, promotion.markdown)
    raw = cast(dict[str, object], json.loads(store.record_path.read_text(encoding="utf-8")))
    raw["schema_version"] = SCHEMA_VERSION + 1
    # An identifier the schema's own validator refuses: the reader cannot
    # structure this record at all, so `record` stays None below.
    raw["work_id"] = "NOT A VALID WORK ID"
    _ = store.record_path.write_text(json.dumps(raw, sort_keys=True), encoding="utf-8")

    report = check(store)

    assert report.codes == (lint.LintCode.RUNTIME_BEHIND,)
    assert lint.LintCode.STORE_INCONSISTENT not in report.codes
    assert lint.LintCode.RECORD_MISSING not in report.codes
    assert f"schema version {SCHEMA_VERSION + 1}" in report.findings[0].detail
    assert report.record is None
    assert lint.gates_continuation(report.findings[0])


@pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")
def test_git_object_exists_in_answers_from_a_real_repository(tmp_path: Path) -> None:
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.com",
    }
    for args in (["init", "-q", "-b", "main"], ["commit", "-q", "--allow-empty", "-m", "s"]):
        _ = subprocess.run(
            ["git", *args], cwd=tmp_path, env=env, check=True, capture_output=True
        )
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=tmp_path,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    exists = lint.git_object_exists_in(tmp_path)

    assert exists(head) is True
    assert exists("0" * 40) is False

def test_ac16_a_store_from_a_newer_runtime_reports_runtime_behind_only(
    corpus_root: Path, make_promotion: Callable[..., _PromotionLike]
) -> None:
    import json

    from easy_cheese_schemas import SCHEMA_VERSION

    store = make_store(corpus_root)
    promotion = make_promotion()
    store.promote(promotion.record, promotion.revision, promotion.markdown)
    raw = cast(dict[str, object], json.loads(store.record_path.read_text(encoding="utf-8")))
    raw["schema_version"] = SCHEMA_VERSION + 1
    raw["field_from_the_future"] = {"still": "ignored on read"}
    _ = store.record_path.write_text(json.dumps(raw, sort_keys=True), encoding="utf-8")

    report = check(store)

    assert report.codes == (lint.LintCode.RUNTIME_BEHIND,)
    assert lint.LintCode.STORE_INCONSISTENT not in report.codes
    assert f"schema version {SCHEMA_VERSION + 1}" in report.findings[0].detail
    assert lint.gates_continuation(report.findings[0])
