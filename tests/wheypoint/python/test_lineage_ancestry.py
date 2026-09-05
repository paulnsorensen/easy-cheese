"""A resolvable parent is not yet an ancestor.

The walk verifies the parent pin. These tests hold it to the two identity
rules the pin alone cannot carry: the parent belongs to the same work, and it
sits exactly one revision earlier.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from attrs import evolve

from easy_cheese.skills.wheypoint import lineage, lint, records, storage

from conftest import Promotion

PROJECT = "paulnsorensen-easy-cheese"


def _store(corpus_root: Path) -> storage.WorkStore:
    return storage.WorkStore.open("work-0001", corpus_root=corpus_root)


def _check(store: storage.WorkStore) -> lint.LintReport:
    return lint.lint_work(
        store,
        project_key=PROJECT,
        git_object_exists=lambda _obj: True,
        artifact_digest=lambda _path: None,
    )


def test_a_parent_from_another_work_is_not_an_ancestor(
    make_promotion: Callable[..., Promotion],
) -> None:
    foreign = make_promotion(1, "rev-0001")
    foreign_revision = evolve(foreign.revision, work_id="work-9999")
    child = make_promotion(2, "rev-0002", parent=foreign)
    child_revision = evolve(
        child.revision,
        parent_revision_digest=records.revision_digest(foreign_revision),
    )

    walked = lineage.walk([foreign_revision], child_revision)

    assert walked.revisions == (child_revision,)
    assert [issue.kind for issue in walked.issues] == [
        lineage.LineageIssueKind.PARENT_NOT_CONTIGUOUS
    ]


def test_a_revision_gap_is_not_an_ancestry(
    make_promotion: Callable[..., Promotion],
) -> None:
    first = make_promotion(1, "rev-0001")
    third = make_promotion(3, "rev-0003", parent=first)

    walked = lineage.walk([first.revision], third.revision)

    assert walked.revisions == (third.revision,)
    assert [issue.kind for issue in walked.issues] == [
        lineage.LineageIssueKind.PARENT_NOT_CONTIGUOUS
    ]


def test_lint_reports_a_revision_gap_and_stops_the_walk(
    corpus_root: Path, make_promotion: Callable[..., Promotion]
) -> None:
    store = _store(corpus_root)
    first = make_promotion(1, "rev-0001")
    store.promote(first.record, first.revision, first.markdown)
    skipped = make_promotion(3, "rev-0003", parent=first)
    store.promote(skipped.record, skipped.revision, skipped.markdown)

    report = _check(store)

    assert report.codes == (lint.LintCode.PARENT_NOT_CONTIGUOUS,)
    assert "revision number 1" in report.findings[0].detail
    assert lint.gates_continuation(report.findings[0])


def test_a_contiguous_chain_still_walks_clean(
    corpus_root: Path, make_promotion: Callable[..., Promotion]
) -> None:
    store = _store(corpus_root)
    first = make_promotion(1, "rev-0001")
    store.promote(first.record, first.revision, first.markdown)
    second = make_promotion(2, "rev-0002", parent=first)
    store.promote(second.record, second.revision, second.markdown)

    report = _check(store)

    assert report.codes == ()
