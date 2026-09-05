"""XDG work storage: layout, promotion ordering, recovery, coverage.

The promotion order is the crash-safety invariant, so it is asserted as an
exact event sequence rather than by its outcome, and every failure point is
forced: a crash before the record swap, a re-promoted revision, a truncated
receipt, a missing projection, and tampering with each of the three files.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import Protocol, cast

import pytest
from attrs import evolve
from easy_cheese_schemas import (
    ArtifactLink,
    EntryKind,
    EntryState,
    EntryTransition,
    ProtectedEntry,
    TransitionAction,
    WheypointRecord,
    WheypointRevision,
)

from easy_cheese.skills.wheypoint import projection, records, storage


class _Promotion(Protocol):
    record: WheypointRecord
    revision: WheypointRevision
    markdown: str


class _FcntlModule(Protocol):
    LOCK_EX: int
    LOCK_NB: int
    LOCK_UN: int

    def flock(self, fd: int, operation: int, /) -> None: ...


WORK_ID = "work-0001"


@pytest.fixture
def store(corpus_root: Path) -> storage.WorkStore:
    _ = corpus_root
    return storage.WorkStore.open(WORK_ID)


def _tree(root: Path) -> list[str]:
    return sorted(
        str(path.relative_to(root)) for path in root.rglob("*") if path.is_file()
    )


# ----- layout ---------------------------------------------------------------


def test_work_root_is_anchored_on_project_corpus_root(
    store: storage.WorkStore, corpus_root: Path
) -> None:
    assert store.root == corpus_root / "work" / WORK_ID
    assert store.record_path == store.root / "record.json"
    assert store.revisions_dir == store.root / "revisions"
    assert store.projections_dir == store.root / "projections"


def test_immutable_file_names_pair_number_with_revision_id(
    store: storage.WorkStore,
) -> None:
    assert store.revision_path(7, "rev-0007").name == "7-rev-0007.json"
    assert store.projection_path(7, "rev-0007").name == "7-rev-0007.md"


@pytest.mark.parametrize("request_identity", [".foo", ".", ".."])
def test_pending_path_rejects_dot_prefixed_stems(
    store: storage.WorkStore, request_identity: str
) -> None:
    with pytest.raises(storage.StorageError, match="safe path segment"):
        _ = store.pending_path(request_identity)


@pytest.mark.parametrize("work_id", ["../evil", "work/0001", "Work-0001", "", "."])
def test_a_work_id_that_could_escape_the_corpus_is_refused(
    corpus_root: Path, work_id: str
) -> None:
    _ = corpus_root
    with pytest.raises(storage.StorageError):
        _ = storage.WorkStore.open(work_id)


def test_an_explicit_corpus_root_overrides_the_environment(tmp_path: Path) -> None:
    store = storage.WorkStore.open(WORK_ID, corpus_root=tmp_path / "elsewhere")
    assert store.root == tmp_path / "elsewhere" / "work" / WORK_ID


# ----- promotion ------------------------------------------------------------


def test_promotion_writes_the_three_files_with_exact_bytes(
    store: storage.WorkStore, make_promotion: Callable[..., _Promotion]
) -> None:
    promotion = make_promotion()
    store.promote(promotion.record, promotion.revision, promotion.markdown)

    assert _tree(store.root) == [
        "projections/1-rev-0001.md",
        "record.json",
        "revisions/1-rev-0001.json",
    ]
    assert store.record_path.read_bytes() == records.canonical_payload(promotion.record)
    assert store.revision_path(1, "rev-0001").read_bytes() == records.canonical_payload(
        promotion.revision
    )
    assert store.projection_path(1, "rev-0001").read_text(
        encoding="utf-8"
    ) == promotion.markdown


def test_record_json_is_replaced_last_and_after_the_immutable_fsyncs(
    store: storage.WorkStore,
    make_promotion: Callable[..., _Promotion],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    real_replace, real_fsync = os.replace, os.fsync

    def spy_replace(src: str, dst: str) -> None:
        events.append(f"replace:{Path(dst).name}")
        real_replace(src, dst)

    def spy_fsync(fd: int) -> None:
        events.append("fsync")
        real_fsync(fd)

    monkeypatch.setattr(os, "replace", spy_replace)
    monkeypatch.setattr(os, "fsync", spy_fsync)

    promotion = make_promotion()
    store.promote(promotion.record, promotion.revision, promotion.markdown)

    assert events == [
        "fsync",
        "replace:1-rev-0001.json",
        "fsync",
        "fsync",
        "replace:1-rev-0001.md",
        "fsync",
        "fsync",
        "replace:record.json",
        "fsync",
    ]


def test_a_crash_before_the_record_swap_leaves_the_prior_record_standing(
    store: storage.WorkStore,
    make_promotion: Callable[..., _Promotion],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = make_promotion(1, "rev-0001")
    store.promote(first.record, first.revision, first.markdown)
    settled = store.record_path.read_bytes()

    real_replace = os.replace

    def crash_on_record(src: str, dst: str) -> None:
        if Path(dst).name == "record.json":
            raise OSError("power loss")
        real_replace(src, dst)

    monkeypatch.setattr(os, "replace", crash_on_record)
    second = make_promotion(2, "rev-0002", parent="rev-0001")
    with pytest.raises(OSError, match="power loss"):
        store.promote(second.record, second.revision, second.markdown)

    # The immutable half landed; the pointer did not move.
    assert store.revision_path(2, "rev-0002").is_file()
    assert store.projection_path(2, "rev-0002").is_file()
    assert store.record_path.read_bytes() == settled

    report = store.recover()
    assert report.record == first.record
    assert [file.revision.revision_id for file in report.complete] == [
        "rev-0001",
        "rev-0002",
    ]
    assert report.incomplete == ()


def test_a_crash_before_the_first_record_swap_leaves_no_record_at_all(
    store: storage.WorkStore,
    make_promotion: Callable[..., _Promotion],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_replace = os.replace

    def crash_on_record(src: str, dst: str) -> None:
        if Path(dst).name == "record.json":
            raise OSError("power loss")
        real_replace(src, dst)

    monkeypatch.setattr(os, "replace", crash_on_record)
    promotion = make_promotion()
    with pytest.raises(OSError):
        store.promote(promotion.record, promotion.revision, promotion.markdown)

    assert not store.record_path.exists()
    report = store.recover()
    assert report.record is None
    assert report.latest_complete is not None
    assert report.latest_complete.revision.revision_id == "rev-0001"


def test_a_crash_before_the_projection_lands_leaves_an_incomplete_pair(
    store: storage.WorkStore,
    make_promotion: Callable[..., _Promotion],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_replace = os.replace

    def crash_on_projection(src: str, dst: str) -> None:
        if Path(dst).suffix == ".md":
            raise OSError("power loss")
        real_replace(src, dst)

    monkeypatch.setattr(os, "replace", crash_on_projection)
    promotion = make_promotion()
    with pytest.raises(OSError):
        store.promote(promotion.record, promotion.revision, promotion.markdown)

    report = store.recover()
    assert report.complete == ()
    assert report.incomplete == ("1-rev-0001.json: projection file is missing",)
    assert report.latest_complete is None


def test_a_promoted_revision_is_immutable(
    store: storage.WorkStore, make_promotion: Callable[..., _Promotion]
) -> None:
    promotion = make_promotion()
    store.promote(promotion.record, promotion.revision, promotion.markdown)
    original = store.revision_path(1, "rev-0001").read_bytes()

    rewritten = evolve(promotion.revision, preserved_entry_ids=["d-one"])
    with pytest.raises(storage.StorageError, match="already exists"):
        store.promote(promotion.record, rewritten, promotion.markdown)
    assert store.revision_path(1, "rev-0001").read_bytes() == original


def test_an_interrupted_promotion_can_be_finished_by_the_identical_retry(
    store: storage.WorkStore,
    make_promotion: Callable[..., _Promotion],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nothing can have quoted an incomplete pair, so the retry that produces
    the same revision id completes it instead of being refused forever."""
    real_replace = os.replace

    def crash_on_projection(src: str, dst: str) -> None:
        if Path(dst).suffix == ".md":
            raise OSError("power loss")
        real_replace(src, dst)

    monkeypatch.setattr(os, "replace", crash_on_projection)
    promotion = make_promotion()
    with pytest.raises(OSError):
        store.promote(promotion.record, promotion.revision, promotion.markdown)
    assert store.recover().complete == ()

    monkeypatch.setattr(os, "replace", real_replace)
    store.promote(promotion.record, promotion.revision, promotion.markdown)

    report = store.recover()
    assert report.incomplete == ()
    assert [file.revision.revision_id for file in report.complete] == ["rev-0001"]
    assert report.consistent
    assert store.read_record() == promotion.record


def test_the_identical_retry_over_a_complete_pair_moves_only_the_record(
    store: storage.WorkStore,
    make_promotion: Callable[..., _Promotion],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The window between the projection rename and the record rename: the
    immutable pair landed and the pointer did not. The retry finishes it by
    writing record.json alone -- the immutable half is compared, not rewritten."""
    real_replace = os.replace

    def crash_on_record(src: str, dst: str) -> None:
        if Path(dst).name == "record.json":
            raise OSError("power loss")
        real_replace(src, dst)

    monkeypatch.setattr(os, "replace", crash_on_record)
    promotion = make_promotion()
    with pytest.raises(OSError):
        store.promote(promotion.record, promotion.revision, promotion.markdown)
    monkeypatch.setattr(os, "replace", real_replace)
    assert not store.record_path.exists()
    assert store.recover().latest_complete is not None
    untouched = [
        (path, path.read_bytes(), path.stat().st_mtime_ns)
        for path in (
            store.revision_path(1, "rev-0001"),
            store.projection_path(1, "rev-0001"),
        )
    ]

    store.promote(promotion.record, promotion.revision, promotion.markdown)

    assert store.read_record() == promotion.record
    assert store.recover().consistent
    assert [
        (path, path.read_bytes(), path.stat().st_mtime_ns)
        for path, _, _ in untouched
    ] == untouched


def test_an_incomplete_pair_may_be_replaced_by_any_agreeing_triple_at_its_name(
    store: storage.WorkStore, make_promotion: Callable[..., _Promotion]
) -> None:
    """What the overwrite is permitted to replace: a pair no reader can have
    quoted. The abandoned receipt's own bytes are not binding -- an incomplete
    pair carries no claim -- so the retry lands whatever agrees with itself."""
    promotion = make_promotion()
    store.revisions_dir.mkdir(parents=True, exist_ok=True)
    _ = store.revision_path(1, "rev-0001").write_bytes(
        records.canonical_payload(
            evolve(promotion.revision, preserved_entry_ids=["injected"])
        )
    )
    assert store.recover().complete == ()

    store.promote(promotion.record, promotion.revision, promotion.markdown)

    assert store.read_revision(1, "rev-0001") == promotion.revision
    assert store.read_record() == promotion.record
    assert store.recover().consistent


def test_a_complete_pair_is_refused_when_the_projection_is_what_changed(
    store: storage.WorkStore, make_promotion: Callable[..., _Promotion]
) -> None:
    """The projection digest lives in the receipt, so different markdown is a
    different receipt: re-promoting it at a settled name is a rewrite, and both
    files stay exactly as the first promotion left them."""
    promotion = make_promotion()
    store.promote(promotion.record, promotion.revision, promotion.markdown)
    before_receipt = store.revision_path(1, "rev-0001").read_bytes()
    before_projection = store.projection_path(1, "rev-0001").read_text(
        encoding="utf-8"
    )

    rewritten = promotion.markdown.replace(
        "Implement the canonical record runtime.", "Ship it, no gates."
    )
    assert rewritten != promotion.markdown
    reprojected = evolve(
        promotion.revision,
        projection_digest=projection.projection_digest_of_text(rewritten),
    )

    with pytest.raises(storage.StorageError, match="already exists"):
        store.promote(promotion.record, reprojected, rewritten)

    assert store.revision_path(1, "rev-0001").read_bytes() == before_receipt
    assert store.projection_path(1, "rev-0001").read_text(
        encoding="utf-8"
    ) == before_projection


def test_a_projection_no_receipt_names_is_reported_rather_than_unseen(
    store: storage.WorkStore, make_promotion: Callable[..., _Promotion]
) -> None:
    """Half a store is still a store: a corpus salvaged into its readable half
    alone holds real history, and scanning only receipts would report it clean."""
    promotion = make_promotion()
    store.promote(promotion.record, promotion.revision, promotion.markdown)
    store.revision_path(1, "rev-0001").unlink()

    report = store.recover()

    assert report.complete == ()
    assert report.incomplete == (
        "1-rev-0001.md: no revision receipt names this projection",
    )


@pytest.mark.parametrize(
    "field",
    ["revision_id", "revision_number", "work_id", "record_digest", "projection_digest"],
)
def test_promotion_refuses_a_triple_that_does_not_agree(
    store: storage.WorkStore, make_promotion: Callable[..., _Promotion], field: str
) -> None:
    promotion = make_promotion()
    broken = {
        "revision_id": "rev-9999",
        "revision_number": 9,
        "work_id": "work-9999",
        "record_digest": "sha256:" + "9" * 64,
        "projection_digest": "sha256:" + "9" * 64,
    }[field]
    with pytest.raises(storage.StorageError):
        store.promote(
            promotion.record,
            evolve(promotion.revision, **{field: broken}),
            promotion.markdown,
        )
    assert not store.record_path.exists()
    assert _tree(store.root) == []


def test_promotion_refuses_a_record_that_does_not_point_at_its_receipt(
    store: storage.WorkStore, make_promotion: Callable[..., _Promotion]
) -> None:
    promotion = make_promotion()
    detached = evolve(promotion.record, revision_digest="sha256:" + "9" * 64)
    with pytest.raises(storage.StorageError, match="revision_digest"):
        store.promote(detached, promotion.revision, promotion.markdown)


# ----- reading and recovery -------------------------------------------------


def test_reading_a_missing_record_is_absence_not_an_error(
    store: storage.WorkStore,
) -> None:
    assert store.read_record() is None
    assert store.revision_ids() == frozenset()


def test_a_promoted_record_reads_back_identically(
    store: storage.WorkStore, make_promotion: Callable[..., _Promotion]
) -> None:
    promotion = make_promotion(gating=True)
    store.promote(promotion.record, promotion.revision, promotion.markdown)
    restored = store.read_record()
    assert restored == promotion.record
    assert store.revision_ids() == frozenset({"rev-0001"})


def test_recovery_never_writes_anything(
    store: storage.WorkStore, make_promotion: Callable[..., _Promotion]
) -> None:
    promotion = make_promotion()
    store.promote(promotion.record, promotion.revision, promotion.markdown)
    before = {path: path.read_bytes() for path in store.root.rglob("*") if path.is_file()}

    _ = store.recover()

    after = {path: path.read_bytes() for path in store.root.rglob("*") if path.is_file()}
    assert after == before


def test_a_truncated_receipt_is_incomplete_rather_than_half_trusted(
    store: storage.WorkStore, make_promotion: Callable[..., _Promotion]
) -> None:
    promotion = make_promotion()
    store.promote(promotion.record, promotion.revision, promotion.markdown)
    path = store.revision_path(1, "rev-0001")
    _ = path.write_bytes(path.read_bytes()[:40])

    report = store.recover()
    assert report.complete == ()
    assert report.incomplete == ("1-rev-0001.json: malformed JSON",)
    assert not report.consistent
    assert any("rev-0001" in problem for problem in report.problems)


def test_a_receipt_whose_filename_lies_about_its_identity_is_incomplete(
    store: storage.WorkStore, make_promotion: Callable[..., _Promotion]
) -> None:
    promotion = make_promotion()
    store.promote(promotion.record, promotion.revision, promotion.markdown)
    _ = store.revision_path(1, "rev-0001").rename(
        store.revisions_dir / "1-rev-9999.json"
    )

    report = store.recover()
    assert report.incomplete == (
        "1-rev-9999.json: filename does not match the revision identity inside it",
        "1-rev-0001.md: no revision receipt names this projection",
    )


def test_a_tampered_projection_breaks_its_pair(
    store: storage.WorkStore, make_promotion: Callable[..., _Promotion]
) -> None:
    promotion = make_promotion()
    store.promote(promotion.record, promotion.revision, promotion.markdown)
    path = store.projection_path(1, "rev-0001")
    tampered = promotion.markdown.replace(
        "Implement the canonical record runtime.", "Ship it, no gates."
    )
    assert tampered != promotion.markdown
    _ = path.write_text(tampered, encoding="utf-8")

    report = store.recover()
    assert report.complete == ()
    assert report.incomplete == ("1-rev-0001.json: projection digest mismatch",)


def test_recovery_reads_each_projection_once(
    store: storage.WorkStore,
    make_promotion: Callable[..., _Promotion],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    promotion = make_promotion()
    store.promote(promotion.record, promotion.revision, promotion.markdown)
    projection_path = store.projection_path(1, "rev-0001")
    real_read_bytes = Path.read_bytes
    real_read_text = Path.read_text
    reads = 0

    def count_read_bytes(path: Path) -> bytes:
        nonlocal reads
        if path == projection_path:
            reads += 1
        return real_read_bytes(path)

    def count_read_text(
        path: Path, encoding: str | None = None, errors: str | None = None
    ) -> str:
        nonlocal reads
        if path == projection_path:
            reads += 1
        return real_read_text(path, encoding, errors)

    monkeypatch.setattr(Path, "read_bytes", count_read_bytes)
    monkeypatch.setattr(Path, "read_text", count_read_text)

    assert store.recover().latest_complete is not None
    assert reads == 1


def test_an_unreadable_projection_is_incomplete(
    store: storage.WorkStore, make_promotion: Callable[..., _Promotion]
) -> None:
    promotion = make_promotion()
    store.promote(promotion.record, promotion.revision, promotion.markdown)
    path = store.projection_path(1, "rev-0001")
    path.unlink()
    path.mkdir()

    report = store.recover()

    assert report.complete == ()
    assert report.incomplete == ("1-rev-0001.json: projection file is missing",)


def test_a_tampered_record_is_reported_against_its_receipt(
    store: storage.WorkStore, make_promotion: Callable[..., _Promotion]
) -> None:
    promotion = make_promotion()
    store.promote(promotion.record, promotion.revision, promotion.markdown)
    forged = evolve(promotion.record, orientation="nothing to see here")
    _ = store.record_path.write_bytes(records.canonical_payload(forged))

    report = store.recover()
    assert not report.consistent
    assert report.problems == (
        "record.json does not match the record digest in revision 'rev-0001'",
    )


def test_a_record_pointing_at_an_absent_revision_invents_nothing(
    store: storage.WorkStore, make_promotion: Callable[..., _Promotion]
) -> None:
    promotion = make_promotion()
    store.promote(promotion.record, promotion.revision, promotion.markdown)
    store.revision_path(1, "rev-0001").unlink()

    report = store.recover()
    assert report.record is not None
    assert report.complete == ()
    assert report.latest_complete is None
    assert report.problems == (
        "record.json points at revision 'rev-0001', which is not a complete "
        + "immutable revision",
    )


def test_malformed_record_json_is_reported_not_raised(
    store: storage.WorkStore,
) -> None:
    store.record_path.parent.mkdir(parents=True, exist_ok=True)
    _ = store.record_path.write_bytes(b"{ not json")
    report = store.recover()
    assert report.record is None
    assert report.problems == ("record.json is malformed JSON",)


# ----- locking --------------------------------------------------------------


def test_the_record_lock_excludes_a_second_holder(store: storage.WorkStore) -> None:
    fcntl = cast(_FcntlModule, pytest.importorskip("fcntl"))
    with store.lock():
        assert store.lock_path.is_file()
        assert store.lock_path.stat().st_mode & 0o777 == 0o600
        rival = os.open(str(store.lock_path), os.O_RDWR)
        try:
            with pytest.raises(BlockingIOError):
                fcntl.flock(rival, fcntl.LOCK_EX | fcntl.LOCK_NB)
        finally:
            os.close(rival)

    freed = os.open(str(store.lock_path), os.O_RDWR)
    try:
        fcntl.flock(freed, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(freed, fcntl.LOCK_UN)
    finally:
        os.close(freed)


# ----- artifact coverage ----------------------------------------------------


def _covered_record(
    make_record: Callable[..., WheypointRecord], link: ArtifactLink
) -> WheypointRecord:
    return make_record(
        decisions=[
            ProtectedEntry(
                entry_id="d-store",
                kind=EntryKind.DECISION,
                summary="Write the record last.",
                state=EntryState.ACTIVE,
                blocks_continuation=False,
            )
        ],
        artifact_links=[link],
    )


def _report(
    record: WheypointRecord, base: Path, store: storage.WorkStore
) -> records.CoverageReport:
    return records.coverage_report(
        record,
        artifact_digest=lambda path: storage.file_digest(base / path),
        ancestor_revision_ids=store.revision_ids(),
    )


def test_a_pinned_artifact_that_still_matches_covers_its_entries(
    tmp_path: Path, store: storage.WorkStore, make_record: Callable[..., WheypointRecord]
) -> None:
    artifact = tmp_path / "cook.md"
    _ = artifact.write_text("the cook report", encoding="utf-8")
    link = ArtifactLink(
        path="cook.md",
        digest=storage.file_digest(artifact),
        covers_entry_ids=["d-store"],
    )
    record = _covered_record(make_record, link)

    report = _report(record, tmp_path, store)
    assert report.failures == ()
    assert report.covered_entry_ids == ("d-store",)
    assert report.valid


def test_a_missing_artifact_invalidates_the_claim_and_keeps_the_entry(
    tmp_path: Path, store: storage.WorkStore, make_record: Callable[..., WheypointRecord]
) -> None:
    link = ArtifactLink(
        path="gone.md", digest="sha256:" + "a" * 64, covers_entry_ids=["d-store"]
    )
    record = _covered_record(make_record, link)

    report = _report(record, tmp_path, store)
    assert report.covered_entry_ids == ()
    assert report.failures == (
        records.CoverageFailure(path="gone.md", reason="artifact is missing"),
    )
    # The inline decision is untouched: coverage is a claim about it, not a
    # replacement for it.
    assert [entry.entry_id for entry in record.decisions] == ["d-store"]
    assert record.decisions[0].state is EntryState.ACTIVE


def test_a_stale_artifact_digest_invalidates_the_claim(
    tmp_path: Path, store: storage.WorkStore, make_record: Callable[..., WheypointRecord]
) -> None:
    artifact = tmp_path / "cook.md"
    _ = artifact.write_text("the cook report", encoding="utf-8")
    link = ArtifactLink(
        path="cook.md",
        digest=storage.file_digest(artifact),
        covers_entry_ids=["d-store"],
    )
    record = _covered_record(make_record, link)
    _ = artifact.write_text("edited after the claim", encoding="utf-8")

    report = _report(record, tmp_path, store)
    assert report.covered_entry_ids == ()
    assert report.failures == (
        records.CoverageFailure(path="cook.md", reason="artifact digest mismatch"),
    )
    assert record.artifact_links == [link]


def test_an_unpinned_coverage_claim_is_refused(
    tmp_path: Path, store: storage.WorkStore, make_record: Callable[..., WheypointRecord]
) -> None:
    _ = (tmp_path / "cook.md").write_text("the cook report", encoding="utf-8")
    record = _covered_record(
        make_record, ArtifactLink(path="cook.md", covers_entry_ids=["d-store"])
    )

    report = _report(record, tmp_path, store)
    assert report.failures == (
        records.CoverageFailure(
            path="cook.md",
            reason="coverage claim has neither a digest nor a revision to pin it",
        ),
    )


def test_a_claim_naming_an_unknown_entry_is_refused(
    tmp_path: Path, store: storage.WorkStore, make_record: Callable[..., WheypointRecord]
) -> None:
    artifact = tmp_path / "cook.md"
    _ = artifact.write_text("the cook report", encoding="utf-8")
    record = _covered_record(
        make_record,
        ArtifactLink(
            path="cook.md",
            digest=storage.file_digest(artifact),
            covers_entry_ids=["d-store", "d-ghost"],
        ),
    )

    report = _report(record, tmp_path, store)
    assert report.failures == (
        records.CoverageFailure(
            path="cook.md", reason="coverage names unknown entry 'd-ghost'"
        ),
    )
    assert report.covered_entry_ids == ()


def test_a_revision_pinned_claim_needs_that_revision_to_exist(
    tmp_path: Path,
    store: storage.WorkStore,
    make_record: Callable[..., WheypointRecord],
    make_promotion: Callable[..., _Promotion],
) -> None:
    promotion = make_promotion()
    store.promote(promotion.record, promotion.revision, promotion.markdown)
    _ = (tmp_path / "cook.md").write_text("the cook report", encoding="utf-8")

    known = _covered_record(
        make_record,
        ArtifactLink(path="cook.md", revision_id="rev-0001", covers_entry_ids=["d-store"]),
    )
    assert _report(known, tmp_path, store).failures == ()

    unknown = _covered_record(
        make_record,
        ArtifactLink(path="cook.md", revision_id="rev-9999", covers_entry_ids=["d-store"]),
    )
    assert _report(unknown, tmp_path, store).failures == (
        records.CoverageFailure(
            path="cook.md", reason="coverage pins unknown revision 'rev-9999'"
        ),
    )


def test_a_revision_pinned_claim_needs_the_artifact_to_still_be_there(
    tmp_path: Path,
    store: storage.WorkStore,
    make_record: Callable[..., WheypointRecord],
    make_promotion: Callable[..., _Promotion],
) -> None:
    """A revision pin says what the file was at a revision, which says nothing
    at all once the file is gone -- the digest branch already refused that, and
    the revision branch used to wave it through."""
    promotion = make_promotion()
    store.promote(promotion.record, promotion.revision, promotion.markdown)

    record = _covered_record(
        make_record,
        ArtifactLink(path="gone.md", revision_id="rev-0001", covers_entry_ids=["d-store"]),
    )

    report = _report(record, tmp_path, store)
    assert report.covered_entry_ids == ()
    assert report.failures == (
        records.CoverageFailure(path="gone.md", reason="artifact is missing"),
    )
    assert [entry.entry_id for entry in record.decisions] == ["d-store"]


def test_a_link_without_a_coverage_claim_is_not_a_failure(
    tmp_path: Path, store: storage.WorkStore, make_record: Callable[..., WheypointRecord]
) -> None:
    record = _covered_record(make_record, ArtifactLink(path="never-written.md"))
    report = _report(record, tmp_path, store)
    assert report.failures == ()
    assert report.covered_entry_ids == ()


# ----- protected-entry validation -------------------------------------------


def test_transitions_are_checked_against_the_entries_that_exist(
    make_record: Callable[..., WheypointRecord],
) -> None:
    record = make_record(
        decisions=[
            ProtectedEntry(
                entry_id="d-open",
                kind=EntryKind.DECISION,
                summary="open",
                state=EntryState.ACTIVE,
                blocks_continuation=False,
            ),
            ProtectedEntry(
                entry_id="d-settled",
                kind=EntryKind.DECISION,
                summary="settled",
                state=EntryState.RESOLVED,
                blocks_continuation=False,
                rationale="done",
            ),
        ]
    )
    problems = records.validate_transitions(
        record,
        [
            EntryTransition(
                entry_id="d-open", action=TransitionAction.RESOLVE, rationale="ok"
            ),
            EntryTransition(
                entry_id="d-ghost", action=TransitionAction.WITHDRAW, rationale="ok"
            ),
            EntryTransition(
                entry_id="d-settled", action=TransitionAction.RESOLVE, rationale="ok"
            ),
        ],
    )
    assert problems == (
        "transition names unknown entry 'd-ghost'",
        "entry 'd-settled' is already resolved",
    )


def test_a_supersede_transition_must_name_an_existing_successor(
    make_record: Callable[..., WheypointRecord],
) -> None:
    record = make_record(
        decisions=[
            ProtectedEntry(
                entry_id="d-open",
                kind=EntryKind.DECISION,
                summary="open",
                state=EntryState.ACTIVE,
                blocks_continuation=False,
            )
        ]
    )
    assert records.validate_transitions(
        record,
        [
            EntryTransition(
                entry_id="d-open",
                action=TransitionAction.SUPERSEDE,
                rationale="replaced",
                target_entry_id="d-ghost",
            )
        ],
    ) == ("transition targets unknown entry 'd-ghost'",)


def test_find_entry_spans_all_three_protected_lists(
    make_record: Callable[..., WheypointRecord],
) -> None:
    record = make_record(gating=True)
    assert records.find_entry(record, "q-durability") is record.questions[0]
    assert records.find_entry(record, "missing") is None
    assert [entry.entry_id for entry in records.entries(record)] == ["q-durability"]
