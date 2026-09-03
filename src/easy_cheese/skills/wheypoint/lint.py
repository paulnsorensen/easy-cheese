"""Deterministic validation of a projection and of the work behind it.

Everything a caller would have to trust before acting on a checkpoint is
re-derived here from the bytes on disk: the projection hashes to the digest it
carries, the record hashes to the digest its receipt quotes, every parent in
the chain is present as an immutable local revision, every protected entry that
chain accounts for is still in the record, the record belongs to this project,
the commit it cites still exists, and every artifact coverage claim still
resolves.

A lint finding is a *reason not to dispatch*, never a repair. Nothing in this
module writes, and nothing removes protected inline state -- an artifact whose
coverage claim has gone stale invalidates the claim, and the entries it claimed
to cover stay exactly where they were.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from enum import Enum
from pathlib import Path

from attrs import define, field
from easy_cheese_schemas import (
    Durability,
    WheypointProjection,
    WheypointRecord,
    WheypointRevision,
    WheypointStatus,
)

from . import lineage
from . import projection as projection_mod
from . import records, storage

_GIT_TIMEOUT_SECONDS = 5



class LintCode(str, Enum):
    """Why a checkpoint cannot be acted on automatically."""

    RECORD_MISSING = "record-missing"
    STORE_INCONSISTENT = "store-inconsistent"
    REVISION_INCOMPLETE = "revision-incomplete"
    PROJECTION_UNREADABLE = "projection-unreadable"
    PROJECTION_DIGEST_MISMATCH = "projection-digest-mismatch"
    PROJECTION_STATUS_MISMATCH = "projection-status-mismatch"
    PROJECTION_RECORD_MISMATCH = "projection-record-mismatch"
    PARENT_UNRESOLVED = "parent-unresolved"
    PARENT_DIGEST_MISMATCH = "parent-digest-mismatch"
    PROJECT_MISMATCH = "project-mismatch"
    GIT_OBJECT_MISSING = "git-object-missing"
    ARTIFACT_COVERAGE_INVALID = "artifact-coverage-invalid"
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
    {LintCode.REVISION_INCOMPLETE, LintCode.DURABILITY_LOCAL_ONLY}
)


def gates_continuation(finding: LintFinding) -> bool:
    """Whether this finding must stop automatic dispatch."""
    return finding.code not in ADVISORY_CODES


@define(frozen=True)
class LintFinding:
    code: LintCode
    detail: str


@define(frozen=True)
class LintReport:
    """Everything that is wrong, plus what was readable while checking."""

    findings: tuple[LintFinding, ...] = field(default=())
    record: WheypointRecord | None = None
    projection: WheypointProjection | None = None

    @property
    def ok(self) -> bool:
        return not self.findings

    @property
    def codes(self) -> tuple[LintCode, ...]:
        return tuple(finding.code for finding in self.findings)


def git_object_exists_in(root: Path | str) -> Callable[[str], bool]:
    """Read-only `git cat-file -e <object>^{object}` in `root`.

    Inspection only: the runtime never commits, never publishes, and treats an
    unrunnable git as an unresolved reference rather than a pass.
    """

    def exists(obj: str) -> bool:
        try:
            completed = subprocess.run(
                ["git", "cat-file", "-e", f"{obj}^{{object}}"],
                cwd=str(root),
                capture_output=True,
                text=True,
                timeout=_GIT_TIMEOUT_SECONDS,
            )
        except (OSError, subprocess.SubprocessError):
            return False
        return completed.returncode == 0

    return exists


def artifact_digest_in(root: Path | str) -> Callable[[str], str | None]:
    """Digest a regular artifact file contained by `root`."""
    resolved_root = Path(root).resolve()

    def digest(path: str) -> str | None:
        candidate = Path(path)
        if candidate.is_absolute() or ".." in candidate.parts:
            return None
        try:
            resolved = (resolved_root / candidate).resolve()
            if not resolved.is_relative_to(resolved_root) or not resolved.is_file():
                return None
            return storage.file_digest(resolved)
        except (OSError, RuntimeError):
            return None

    return digest


def lint_projection_text(text: str) -> LintReport:
    """Parse a projection document and check it against its own digest."""
    try:
        parsed = projection_mod.parse(text)
    except projection_mod.ProjectionParseError as exc:
        return LintReport(
            findings=(LintFinding(LintCode.PROJECTION_UNREADABLE, str(exc)),)
        )
    actual = projection_mod.projection_digest_of_text(text)
    if actual != parsed.projection_digest:
        return LintReport(
            findings=(
                LintFinding(
                    LintCode.PROJECTION_DIGEST_MISMATCH,
                    f"document hashes to {actual}, but claims "
                    + f"{parsed.projection_digest}",
                ),
            ),
            projection=parsed,
        )
    written = projection_mod.declared_status(text)
    if written != parsed.status.value:
        return LintReport(
            findings=(
                LintFinding(
                    LintCode.PROJECTION_STATUS_MISMATCH,
                    f"document is written {written!r} but its gating entries "
                    + f"derive {parsed.status.value!r}",
                ),
            ),
            projection=parsed,
        )
    return LintReport(projection=parsed)


def lint_projection_file(path: Path | str) -> LintReport:
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        return LintReport(
            findings=(LintFinding(LintCode.PROJECTION_UNREADABLE, str(exc)),)
        )
    return lint_projection_text(text)


def lint_work(
    store: storage.WorkStore,
    *,
    project_key: str,
    git_object_exists: Callable[[str], bool],
    artifact_digest: Callable[[str], str | None],
) -> LintReport:
    """Validate the whole current checkpoint of one work store."""
    recovery = store.recover()
    findings = [
        LintFinding(LintCode.STORE_INCONSISTENT, problem)
        for problem in recovery.problems
    ]
    record = recovery.record
    if record is None:
        if not findings:
            findings.append(
                LintFinding(
                    LintCode.RECORD_MISSING,
                    f"no record at {store.record_path}",
                )
            )
        findings.extend(_incomplete_findings(recovery))
        return LintReport(findings=tuple(findings))

    findings.extend(_incomplete_findings(recovery))

    if record.project_key != project_key:
        findings.append(
            LintFinding(
                LintCode.PROJECT_MISMATCH,
                f"record belongs to project {record.project_key!r}, not "
                + f"{project_key!r}",
            )
        )

    current = store.read_revision(record.revision_number, record.revision_id)
    projection = None
    # No receipt for the current revision means no proven ancestry, so every
    # revision pin is unresolved rather than resolved against the whole store.
    ancestry: frozenset[str] = frozenset()
    if current is None:
        findings.append(
            LintFinding(
                LintCode.PARENT_UNRESOLVED,
                f"record names revision {record.revision_id!r}, which has no "
                + "immutable revision file",
            )
        )
    else:
        projection_report = _lint_current_projection(store, record, current)
        findings.extend(projection_report.findings)
        projection = projection_report.projection
        chain = _walk_chain(recovery, current)
        ancestry = chain.revision_ids
        findings.extend(chain.findings)
        findings.extend(_compaction_findings(chain))
        findings.extend(_conservation_findings(chain, record))
        findings.extend(_git_findings(current, git_object_exists))

    findings.extend(_coverage_findings(ancestry, record, artifact_digest))
    if projection is not None:
        findings.extend(_durability_findings(projection, record))
    return LintReport(findings=tuple(findings), record=record, projection=projection)


def _durability_findings(
    projection: WheypointProjection, record: WheypointRecord
) -> list[LintFinding]:
    """Warn when human-owed gating state has never left the local corpus.

    `canonical-local` means the projection exists only in this corpus. That is
    fine for a settled checkpoint -- it can be regenerated from the record. It
    is not fine for a gated one: the gates are questions and decisions a person
    still owes an answer to, and losing the corpus loses them. The runtime
    cannot fix that itself, because it never commits and never publishes, so
    this hands the operator the choice rather than making it.
    """
    if projection.durability is not Durability.CANONICAL_LOCAL:
        return []
    if record.status is not WheypointStatus.GATED:
        return []
    gates = ", ".join(record.gating_entry_ids)
    return [
        LintFinding(
            LintCode.DURABILITY_LOCAL_ONLY,
            f"revision {record.revision_id!r} still gates on {gates} and is "
            + "canonical-local: that state exists nowhere but this corpus. "
            + "Preserve it (snapshot the corpus into the repository) or "
            + "publish it -- this runtime never commits and never publishes, "
            + "so the choice is yours.",
        )
    ]


def _incomplete_findings(
    recovery: storage.RecoveryReport,
) -> list[LintFinding]:
    """Name every half-written pair: an interrupted promotion is not clean."""
    return [
        LintFinding(LintCode.REVISION_INCOMPLETE, detail)
        for detail in recovery.incomplete
    ]


def _lint_current_projection(
    store: storage.WorkStore,
    record: WheypointRecord,
    revision: WheypointRevision,
) -> LintReport:
    path = store.projection_path(revision.revision_number, revision.revision_id)
    report = lint_projection_file(path)
    parsed = report.projection
    if parsed is None:
        return report
    mismatches: list[str] = []
    if parsed.work_id != record.work_id:
        mismatches.append(f"work_id {parsed.work_id!r} != {record.work_id!r}")
    if parsed.revision_id != record.revision_id:
        mismatches.append(
            f"revision_id {parsed.revision_id!r} != {record.revision_id!r}"
        )
    expected_digest = records.record_digest(record)
    if parsed.record_digest != expected_digest:
        mismatches.append(
            f"record_digest {parsed.record_digest} != {expected_digest}"
        )
    if not mismatches:
        return report
    return LintReport(
        findings=(
            *report.findings,
            LintFinding(
                LintCode.PROJECTION_RECORD_MISMATCH,
                f"{path.name} describes a different record: "
                + "; ".join(mismatches),
            ),
        ),
        projection=parsed,
    )


@define(frozen=True)
class _Chain:
    """The ancestry of one revision, and why it stops where it does.

    `revisions` runs current-first and holds only the steps that were actually
    walked, so a chain that breaks reports the prefix it could prove rather
    than the whole store: a revision the walk never reached is not an ancestor
    of the current one, whatever else is on disk.
    """

    revisions: tuple[WheypointRevision, ...]
    findings: tuple[LintFinding, ...]

    @property
    def revision_ids(self) -> frozenset[str]:
        return frozenset(revision.revision_id for revision in self.revisions)


def _walk_chain(
    recovery: storage.RecoveryReport, current: WheypointRevision
) -> _Chain:
    """Adapt the shared provenance walk into lint findings."""
    checked = lineage.walk(
        (file.revision for file in recovery.complete),
        current,
    )
    return _Chain(
        revisions=checked.revisions,
        findings=tuple(_lineage_finding(issue) for issue in checked.issues),
    )


def _lineage_finding(issue: lineage.LineageIssue) -> LintFinding:
    if issue.kind is lineage.LineageIssueKind.PARENT_UNRESOLVED:
        if issue.cycle:
            detail = (
                f"revision {issue.revision.revision_id!r} re-enters the chain at "
                + f"{issue.parent_revision_id!r}"
            )
        else:
            detail = (
                f"revision {issue.revision.revision_id!r} names parent "
                + f"{issue.parent_revision_id!r}, which is not a complete "
                + "immutable revision"
            )
        return LintFinding(LintCode.PARENT_UNRESOLVED, detail)
    pinned = issue.expected_digest
    if pinned is None:
        detail = (
            f"revision {issue.revision.revision_id!r} is stamped schema version "
            + f"{issue.revision.schema_version} and names parent "
            + f"{issue.parent_revision_id!r} without pinning its digest"
        )
    else:
        detail = (
            f"revision {issue.revision.revision_id!r} pins parent "
            + f"{issue.parent_revision_id!r} at {pinned}, but that receipt now "
            + f"hashes to {issue.actual_digest}"
        )
    return LintFinding(LintCode.PARENT_DIGEST_MISMATCH, detail)




def _compaction_findings(chain: _Chain) -> list[LintFinding]:
    """Re-derive every compaction claim against the chain it was written into.

    A compaction record is a reconciliation report, and both of its links are
    checkable from the receipts alone. The revision it says it rehydrated from
    must be the parent it then wrote onto -- a session that re-read one revision
    and committed against another reconciled against state that is not the state
    it extended. And the predecessor it chains to must be a compaction that is
    genuinely behind it: an id outside the walked ancestry names a compaction
    this lineage never passed through, and an id inside it that carries no
    compaction of its own names an event that never happened.

    Neither is repairable here -- the lost context is lost -- so both are
    reported, and both gate continuation: resuming on a checkpoint whose
    compaction claim does not hold is resuming on state nobody reconciled.
    """
    compacted = {
        revision.revision_id: revision.compaction for revision in chain.revisions
    }
    findings: list[LintFinding] = []
    for revision in chain.revisions:
        compaction = revision.compaction
        if compaction is None:
            continue
        if compaction.rehydrated_from_revision_id != revision.parent_revision_id:
            findings.append(
                LintFinding(
                    LintCode.COMPACTION_PARENT_UNRESOLVED,
                    f"revision {revision.revision_id!r} rehydrated from "
                    + f"{compaction.rehydrated_from_revision_id!r} but was "
                    + f"written onto parent {revision.parent_revision_id!r}",
                )
            )
        prior_id = compaction.prior_compaction_revision_id
        if prior_id is None:
            continue
        if prior_id not in compacted:
            findings.append(
                LintFinding(
                    LintCode.COMPACTION_PARENT_UNRESOLVED,
                    f"revision {revision.revision_id!r} chains to prior "
                    + f"compaction {prior_id!r}, which is not in the proven "
                    + "ancestry of this revision",
                )
            )
        elif compacted[prior_id] is None:
            findings.append(
                LintFinding(
                    LintCode.COMPACTION_PARENT_UNRESOLVED,
                    f"revision {revision.revision_id!r} chains to prior "
                    + f"compaction {prior_id!r}, which records no compaction",
                )
            )
    return findings


def _conservation_findings(
    chain: _Chain, record: WheypointRecord
) -> list[LintFinding]:
    """Reconcile the record against every entry its own lineage accounts for.

    A receipt says what one revision added and what it carried forward
    untouched; together the chain therefore names every protected entry the
    work has ever held. An entry that lineage accounts for and the record no
    longer carries was not transitioned out -- there is no transition that
    removes one -- so it was replaced away, which is the one loss the
    carry-forward rules cannot catch from a single revision. It is reported
    against the record, never repaired: nothing here can know what the dropped
    entry said.
    """
    accounted: dict[str, str] = {}
    for revision in chain.revisions:
        for entry_id in (
            *(addition.entry_id for addition in revision.applied_additions),
            *revision.preserved_entry_ids,
        ):
            if entry_id not in accounted:
                accounted[entry_id] = revision.revision_id
    held = {entry.entry_id for entry in records.entries(record)}
    return [
        LintFinding(
            LintCode.ENTRY_DROPPED,
            f"revision {revision_id!r} accounts for entry {entry_id!r}, which "
            + f"record {record.revision_id!r} no longer carries",
        )
        for entry_id, revision_id in sorted(accounted.items())
        if entry_id not in held
    ]


def _git_findings(
    revision: WheypointRevision, git_object_exists: Callable[[str], bool]
) -> list[LintFinding]:
    commit = revision.repository.commit
    if commit is None or git_object_exists(commit):
        return []
    return [
        LintFinding(
            LintCode.GIT_OBJECT_MISSING,
            f"revision {revision.revision_id!r} cites commit {commit}, which "
            + "does not resolve in this repository",
        )
    ]


def _coverage_findings(
    ancestry: frozenset[str],
    record: WheypointRecord,
    artifact_digest: Callable[[str], str | None],
) -> list[LintFinding]:
    report = records.coverage_report(
        record,
        artifact_digest=artifact_digest,
        ancestor_revision_ids=ancestry,
    )
    return [
        LintFinding(
            LintCode.ARTIFACT_COVERAGE_INVALID,
            f"{failure.path}: {failure.reason}",
        )
        for failure in report.failures
    ]
