"""Lint: a checkpoint is only dispatchable when the disk still proves it."""

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest
from easy_cheese_schemas import (
    ArtifactLink,
    EntryKind,
    EntryState,
    ProtectedEntry,
    WheypointRecord,
)

import canonical
import lint
import records
import storage

PROJECT = "paulnsorensen-easy-cheese"


def all_objects_exist(obj: str) -> bool:
    return True


def no_artifacts(path: str) -> str | None:
    return None


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


def test_a_consistent_promotion_lints_clean(corpus_root, make_promotion) -> None:
    store = make_store(corpus_root)
    promotion = make_promotion()
    store.promote(promotion.record, promotion.revision, promotion.markdown)

    report = check(store)

    assert report.codes == ()
    assert report.ok
    assert report.record is not None
    assert report.projection is not None
    assert report.projection.revision_id == "rev-0001"


def test_an_empty_store_reports_the_missing_record_path(corpus_root) -> None:
    store = make_store(corpus_root)

    report = check(store)

    assert report.codes == (lint.LintCode.RECORD_MISSING,)
    assert str(store.record_path) in report.findings[0].detail


def test_a_tampered_projection_fails_its_own_digest(
    corpus_root, make_promotion
) -> None:
    store = make_store(corpus_root)
    promotion = make_promotion()
    store.promote(promotion.record, promotion.revision, promotion.markdown)
    path = store.projection_path(1, "rev-0001")
    path.write_text(
        promotion.markdown.replace("status: ok", "status: gated"), encoding="utf-8"
    )

    report = check(store)

    assert lint.LintCode.PROJECTION_DIGEST_MISMATCH in report.codes
    assert not report.ok


def test_a_tampered_record_fails_the_digest_its_receipt_quotes(
    corpus_root, make_promotion
) -> None:
    store = make_store(corpus_root)
    promotion = make_promotion()
    store.promote(promotion.record, promotion.revision, promotion.markdown)
    forged = records.unstructure(promotion.record)
    forged["orientation"] = "someone edited the authority directly"
    store.record_path.write_bytes(canonical.canonical_bytes(forged))

    report = check(store)

    assert lint.LintCode.STORE_INCONSISTENT in report.codes


def test_a_missing_parent_revision_blocks(corpus_root, make_promotion) -> None:
    store = make_store(corpus_root)
    promotion = make_promotion(parent="rev-0000")
    store.promote(promotion.record, promotion.revision, promotion.markdown)

    report = check(store)

    assert report.codes == (lint.LintCode.PARENT_UNRESOLVED,)
    assert "rev-0000" in report.findings[0].detail


def test_a_present_parent_chain_lints_clean(corpus_root, make_promotion) -> None:
    store = make_store(corpus_root)
    first = make_promotion(1, "rev-0001")
    store.promote(first.record, first.revision, first.markdown)
    second = make_promotion(2, "rev-0002", parent="rev-0001")
    store.promote(second.record, second.revision, second.markdown)

    report = check(store)

    assert report.codes == ()
    assert report.record is not None
    assert report.record.revision_id == "rev-0002"


def test_a_record_from_another_project_never_dispatches_here(
    corpus_root, make_promotion
) -> None:
    store = make_store(corpus_root)
    promotion = make_promotion()
    store.promote(promotion.record, promotion.revision, promotion.markdown)

    report = check(store, project_key="someone-else-other-repo")

    assert report.codes == (lint.LintCode.PROJECT_MISMATCH,)
    assert "someone-else-other-repo" in report.findings[0].detail


def test_a_declared_commit_that_no_longer_resolves_blocks(
    corpus_root, make_promotion
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


def covered_record(make_record, digest: str) -> WheypointRecord:
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
    corpus_root, make_record, make_promotion
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
    corpus_root, make_record, make_promotion
) -> None:
    store = make_store(corpus_root)
    pinned = canonical.digest_text("as written")
    promotion = make_promotion(record=covered_record(make_record, pinned))
    store.promote(promotion.record, promotion.revision, promotion.markdown)

    report = check(store, artifact_digest=lambda path: pinned)

    assert report.codes == ()


def test_an_interrupted_promotion_is_named_rather_than_reported_clean(
    corpus_root, make_promotion
) -> None:
    """A half-written pair is invisible to the record checks, so lint reports
    it directly: the operator has to be told the retry was interrupted."""
    store = make_store(corpus_root)
    promotion = make_promotion(1, "rev-0001")
    store.promote(promotion.record, promotion.revision, promotion.markdown)
    orphan = make_promotion(2, "rev-0002", parent="rev-0001")
    store.revision_path(2, "rev-0002").write_bytes(
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
    (tmp_path / "cook" / "report.md").write_text("body", encoding="utf-8")
    digest = lint.artifact_digest_in(tmp_path)

    assert digest("cook/report.md") == canonical.digest_text("body")
    assert digest("cook/absent.md") is None


def test_artifact_digest_in_rejects_absolute_paths(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text("body", encoding="utf-8")

    assert lint.artifact_digest_in(root)(str(outside)) is None


def test_artifact_digest_in_rejects_parent_traversal(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (tmp_path / "outside.md").write_text("body", encoding="utf-8")

    assert lint.artifact_digest_in(root)("../outside.md") is None


def test_artifact_digest_in_rejects_symlink_escapes(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text("body", encoding="utf-8")
    (root / "link.md").symlink_to(outside)

    assert lint.artifact_digest_in(root)("link.md") is None


def test_artifact_digest_in_rejects_non_regular_paths(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "reports").mkdir()

    assert lint.artifact_digest_in(root)("reports") is None


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
        subprocess.run(
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
