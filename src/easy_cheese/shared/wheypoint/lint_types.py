"""Lint vocabulary shared by `lint` and `lint_freshness`.

Kept apart so the freshness checks can build findings without importing the
composer that calls them (`lint -> lint_freshness -> lint` would be a cycle).
"""

from __future__ import annotations

from enum import Enum

from attrs import define


class LintCode(str, Enum):
    """Why a checkpoint cannot be acted on automatically."""

    RECORD_MISSING = "record-missing"
    STORE_INCONSISTENT = "store-inconsistent"
    RUNTIME_BEHIND = "runtime-behind"
    REVISION_INCOMPLETE = "revision-incomplete"
    PROJECTION_UNREADABLE = "projection-unreadable"
    PROJECTION_DIGEST_MISMATCH = "projection-digest-mismatch"
    PROJECTION_STATUS_MISMATCH = "projection-status-mismatch"
    PROJECTION_RECORD_MISMATCH = "projection-record-mismatch"
    PARENT_UNRESOLVED = "parent-unresolved"
    PARENT_DIGEST_MISMATCH = "parent-digest-mismatch"
    PARENT_NOT_CONTIGUOUS = "parent-not-contiguous"
    PROJECT_MISMATCH = "project-mismatch"
    GIT_OBJECT_MISSING = "git-object-missing"
    STALE_COMMIT = "stale-commit"
    ARTIFACT_COVERAGE_INVALID = "artifact-coverage-invalid"
    STALE_ARTIFACT_LINK = "stale-artifact-link"
    GROUNDED_PATH_MISSING = "grounded-path-missing"
    ENTRY_DROPPED = "entry-dropped"
    DURABILITY_LOCAL_ONLY = "durability-local-only"
    COMPACTION_PARENT_UNRESOLVED = "compaction-parent-unresolved"


# Findings that describe the store's surroundings rather than the authority of
# the record being resumed. An interrupted promotion leaves an orphan no reader
# can have quoted, and the retry overwrites it; blocking continuation on one
# would strand a valid current record in exactly the crash it survived. The
# spec gates automatic continuation on projection and record digests, the
# parent chain, project identity, referenced Git objects, and required artifact
# coverage -- an orphan is none of those, so it is reported, not enforced.
#
# A canonical-local checkpoint over an open gate is likewise not an authority
# problem: the record is exactly as valid as it says it is. What is at risk is
# the human-owed state it holds, which no commit or publish has carried
# anywhere. That is a choice for the operator, so it warns and does not block.
ADVISORY_CODES = frozenset(
    {
        LintCode.REVISION_INCOMPLETE,
        LintCode.DURABILITY_LOCAL_ONLY,
        LintCode.STALE_COMMIT,
        LintCode.GROUNDED_PATH_MISSING,
    }
)


def gates_continuation(finding: LintFinding) -> bool:
    """Whether this finding must stop automatic dispatch."""
    return finding.code not in ADVISORY_CODES


@define(frozen=True)
class LintFinding:
    code: LintCode
    detail: str
