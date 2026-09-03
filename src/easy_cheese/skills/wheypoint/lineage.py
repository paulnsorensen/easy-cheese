"""Walk immutable Wheypoint ancestry and verify its provenance pins."""

from __future__ import annotations

from collections.abc import Iterable
from enum import Enum

from attrs import define
from easy_cheese_schemas import WheypointRevision

from . import records


class LineageIssueKind(str, Enum):
    """Why an immutable ancestry walk could not continue."""

    PARENT_UNRESOLVED = "parent-unresolved"
    PARENT_DIGEST_MISMATCH = "parent-digest-mismatch"


@define(frozen=True)
class LineageIssue:
    """One failed provenance check at the edge of a revision chain."""

    kind: LineageIssueKind
    revision: WheypointRevision
    parent_revision_id: str
    parent: WheypointRevision | None = None
    expected_digest: str | None = None
    actual_digest: str | None = None
    cycle: bool = False


@define(frozen=True)
class Lineage:
    """The current-first revisions that were proven, plus any failed edge."""

    revisions: tuple[WheypointRevision, ...]
    issues: tuple[LineageIssue, ...]

    @property
    def revision_ids(self) -> frozenset[str]:
        return frozenset(revision.revision_id for revision in self.revisions)

    @property
    def prior_compaction_revision_id(self) -> str | None:
        """The nearest proven receipt that recorded a compaction."""
        return next(
            (
                revision.revision_id
                for revision in self.revisions
                if revision.compaction is not None
            ),
            None,
        )


def walk(
    revisions: Iterable[WheypointRevision], current: WheypointRevision
) -> Lineage:
    """Walk from ``current`` to genesis and verify every parent provenance pin.

    The caller supplies only complete immutable revisions. A missing parent, a
    cycle, or a changed parent receipt stops the walk at that edge. The proven
    prefix remains useful to callers such as lint, but it never licenses a
    write past the failed edge.
    """
    known = {revision.revision_id: revision for revision in revisions}
    walked = [current]
    seen = {current.revision_id}
    issues: list[LineageIssue] = []
    revision = current
    while revision.parent_revision_id is not None:
        parent_id = revision.parent_revision_id
        if parent_id in seen:
            issues.append(
                LineageIssue(
                    kind=LineageIssueKind.PARENT_UNRESOLVED,
                    revision=revision,
                    parent_revision_id=parent_id,
                    cycle=True,
                )
            )
            break
        parent = known.get(parent_id)
        if parent is None:
            issues.append(
                LineageIssue(
                    kind=LineageIssueKind.PARENT_UNRESOLVED,
                    revision=revision,
                    parent_revision_id=parent_id,
                )
            )
            break
        pinned = revision.parent_revision_digest
        if pinned is None:
            if revision.schema_version >= 2:
                issues.append(
                    LineageIssue(
                        kind=LineageIssueKind.PARENT_DIGEST_MISMATCH,
                        revision=revision,
                        parent_revision_id=parent_id,
                        parent=parent,
                    )
                )
                break
        else:
            actual = records.revision_digest(parent)
            if pinned != actual:
                issues.append(
                    LineageIssue(
                        kind=LineageIssueKind.PARENT_DIGEST_MISMATCH,
                        revision=revision,
                        parent_revision_id=parent_id,
                        parent=parent,
                        expected_digest=pinned,
                        actual_digest=actual,
                    )
                )
                break
        seen.add(parent_id)
        walked.append(parent)
        revision = parent
    return Lineage(revisions=tuple(walked), issues=tuple(issues))
