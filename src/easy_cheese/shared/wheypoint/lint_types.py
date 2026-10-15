"""Finding vocabulary for resolution: why a checkpoint cannot be acted on.

The `lint` command is gone; `resolve` reports these findings itself.
"""

from __future__ import annotations

from enum import Enum

from attrs import define


class LintCode(str, Enum):
    """Why a checkpoint cannot be acted on automatically."""

    RECORD_MISSING = "record-missing"
    STORE_INCONSISTENT = "store-inconsistent"
    SCHEMA_VERSION_FUTURE = "schema-version-future"
    REVISION_INCOMPLETE = "revision-incomplete"
    PROJECTION_UNREADABLE = "projection-unreadable"
    PROJECTION_RECORD_MISMATCH = "projection-record-mismatch"
    PROJECT_MISMATCH = "project-mismatch"
    WORKSPACE_REQUIRED = "workspace-required"
    WORKSPACE_MISMATCH = "workspace-mismatch"
    GIT_OBJECT_MISSING = "git-object-missing"
    STALE_COMMIT = "stale-commit"
    ARTIFACT_COVERAGE_INVALID = "artifact-coverage-invalid"
    STALE_ARTIFACT_LINK = "stale-artifact-link"
    GROUNDED_PATH_MISSING = "grounded-path-missing"


# Findings that describe the store's surroundings rather than the authority of
# the record being resumed. An interrupted promotion leaves an orphan no reader
# can have quoted, and the retry overwrites it; blocking continuation on one
# would strand a valid current record in exactly the crash it survived.
ADVISORY_CODES = frozenset(
    {
        LintCode.REVISION_INCOMPLETE,
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