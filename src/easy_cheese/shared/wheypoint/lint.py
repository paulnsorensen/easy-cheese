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

import functools
from collections.abc import Callable
from pathlib import Path

from attrs import define, field
from easy_cheese_schemas import (
    SCHEMA_VERSION,
    CompactionRecord,
    Durability,
    WheypointProjection,
    WheypointRecord,
    WheypointRevision,
    WheypointStatus,
)

from easy_cheese.shared import paths

from . import lineage
from . import lint_freshness
from .lint_types import ADVISORY_CODES, LintCode, LintFinding, gates_continuation
from . import projection as projection_mod
from . import records, storage
from .lineage import Lineage

__all__ = ["ADVISORY_CODES", "LintCode", "LintFinding", "gates_continuation"]


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
    """Read-only git reachability probe in `root` (see `lint_freshness`)."""
    return lint_freshness.git_object_exists_in(root)


def artifact_digest_in(root: Path | str) -> Callable[[str], str | None]:
    """Digest a regular artifact file contained by `root` (see `lint_freshness`)."""
    return lint_freshness.artifact_digest_in(root)


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
    repository_root: Path | str | None = None,
) -> LintReport:
    """Validate the whole current checkpoint of one work store.

    Lineage is walked over receipts alone, and the only projection read is
    the one the record points at -- the single revision whose projection a
    caller is about to act on. Every other projection's bytes are a question
    for `recover()`, not for a dispatch gate.
    """
    root = paths.resolve_repo_root(repository_root)
    digest_of = _memoized(artifact_digest)
    survey = store.survey_receipts()
    record = survey.record
    stamped_schema_version = survey.stamped_schema_version
    if stamped_schema_version is not None and stamped_schema_version > SCHEMA_VERSION:
        # A newer runtime wrote this store. Its bytes may not round-trip through
        # this reader's canonical form, so a digest disagreement here says
        # nothing about the store (ADR wheypoint-ergonomics-004). The stamp is
        # read from the raw bytes, not the structured record, because a future
        # record this reader cannot structure must still be reported as
        # runtime-behind rather than misattributed to store corruption.
        return LintReport(
            findings=(
                LintFinding(
                    LintCode.RUNTIME_BEHIND,
                    f"record is stamped schema version {stamped_schema_version} but "
                    + f"this runtime reads up to {SCHEMA_VERSION}: upgrade the "
                    + "wheypoint bundle before trusting any integrity verdict",
                ),
            ),
            record=record,
        )
    findings = [
        LintFinding(LintCode.STORE_INCONSISTENT, problem) for problem in survey.problems
    ]
    if record is None:
        if not findings:
            findings.append(
                LintFinding(
                    LintCode.RECORD_MISSING,
                    f"no record at {store.record_path}",
                )
            )
        findings.extend(_incomplete_findings(survey.incomplete))
        return LintReport(findings=tuple(findings))

    findings.extend(_incomplete_findings(survey.incomplete))

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
        chain = lineage.walk(survey.revisions, current)
        ancestry = chain.revision_ids
        findings.extend(_lineage_finding(issue) for issue in chain.issues)
        findings.extend(_compaction_findings(chain))
        findings.extend(_conservation_findings(chain, record))
        findings.extend(_git_findings(current, git_object_exists, repository_root=root))

    findings.extend(lint_freshness.artifact_link_findings(record, digest_of))
    findings.extend(_coverage_findings(ancestry, record, digest_of))
    if projection is not None:
        findings.extend(_durability_findings(projection, record))
    findings.extend(lint_freshness.grounded_path_findings(record, root))
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


def _memoized(digest: Callable[[str], str | None]) -> Callable[[str], str | None]:
    """One digest per path for the life of one lint.

    Artifact links and coverage claims ask about the same files, so an
    unmemoized digest hashes a linked-and-covering artifact twice.
    """
    return functools.cache(digest)


def _incomplete_findings(incomplete: tuple[str, ...]) -> list[LintFinding]:
    """Name every half-written pair: an interrupted promotion is not clean."""
    return [LintFinding(LintCode.REVISION_INCOMPLETE, detail) for detail in incomplete]


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
        mismatches.append(f"record_digest {parsed.record_digest} != {expected_digest}")
    if not mismatches:
        return report
    return LintReport(
        findings=(
            *report.findings,
            LintFinding(
                LintCode.PROJECTION_RECORD_MISMATCH,
                f"{path.name} describes a different record: " + "; ".join(mismatches),
            ),
        ),
        projection=parsed,
    )


def _not_contiguous_detail(issue: lineage.LineageIssue) -> str:
    """Why a resolvable parent is still not this revision's ancestor."""
    parent = issue.parent
    assert parent is not None
    return (
        f"revision {issue.revision.revision_id!r} of work "
        + f"{issue.revision.work_id!r} names parent {issue.parent_revision_id!r} "
        + f"of work {parent.work_id!r} at revision number "
        + f"{parent.revision_number}, but its own revision number is "
        + f"{issue.revision.revision_number}"
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
    if issue.kind is lineage.LineageIssueKind.PARENT_NOT_CONTIGUOUS:
        return LintFinding(
            LintCode.PARENT_NOT_CONTIGUOUS, _not_contiguous_detail(issue)
        )
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


def _held_entry_ids(revision: WheypointRevision) -> set[str]:
    """The protected entries the record held after `revision` was written."""
    return {addition.entry_id for addition in revision.applied_additions} | set(
        revision.preserved_entry_ids
    )


def _compaction_proof_findings(
    revision: WheypointRevision,
    compaction: CompactionRecord,
    parent: WheypointRevision | None,
) -> list[LintFinding]:
    """Re-derive the reconciliation report against the receipt it names."""
    if compaction.rehydrated_from_revision_id != revision.parent_revision_id:
        return [
            LintFinding(
                LintCode.COMPACTION_PARENT_UNRESOLVED,
                f"revision {revision.revision_id!r} rehydrated from "
                + f"{compaction.rehydrated_from_revision_id!r} but was "
                + f"written onto parent {revision.parent_revision_id!r}",
            )
        ]
    if parent is None:
        return []
    findings: list[LintFinding] = []
    if compaction.rehydrated_record_digest != parent.record_digest:
        findings.append(
            LintFinding(
                LintCode.COMPACTION_PARENT_UNRESOLVED,
                f"revision {revision.revision_id!r} quotes rehydrated record "
                + f"digest {compaction.rehydrated_record_digest}, but revision "
                + f"{parent.revision_id!r} recorded {parent.record_digest}",
            )
        )
    unreconciled = sorted(
        _held_entry_ids(parent) - set(compaction.reconciled_entry_ids)
    )
    if unreconciled:
        findings.append(
            LintFinding(
                LintCode.COMPACTION_PARENT_UNRESOLVED,
                f"revision {revision.revision_id!r} reconciled no entry "
                + f"{', '.join(repr(entry_id) for entry_id in unreconciled)} "
                + f"that revision {parent.revision_id!r} still carried",
            )
        )
    return findings


def _compaction_findings(chain: Lineage) -> list[LintFinding]:
    """Re-derive every compaction claim against the chain it was written into.

    A compaction record is a reconciliation report, and every link in it is
    checkable from the receipts alone.

    The revision it says it rehydrated from must be the parent it then wrote
    onto. The digest it quotes must be the digest that parent receipt recorded.
    The entries it reconciled must cover every protected entry that parent
    still carried. A session that skips any of the three reconciled against
    state that is not the state it extended.

    The predecessor it chains to must be a compaction that is genuinely behind
    it. The chain runs current-first, so a prior compaction must sit at a later
    position. An id outside the walked ancestry names a compaction this lineage
    never passed through. An id at the same position or an earlier one names
    itself or a descendant.

    None of this is repairable here, because the lost context is lost. Each
    finding gates continuation, because resuming on a checkpoint whose
    compaction claim does not hold is resuming on state nobody reconciled.
    """
    revisions = chain.revisions
    position = {revision.revision_id: index for index, revision in enumerate(revisions)}
    findings: list[LintFinding] = []
    for index, revision in enumerate(revisions):
        compaction = revision.compaction
        if compaction is None:
            continue
        parent = revisions[index + 1] if index + 1 < len(revisions) else None
        findings.extend(_compaction_proof_findings(revision, compaction, parent))
        prior_id = compaction.prior_compaction_revision_id
        if prior_id is None:
            continue
        prior_index = position.get(prior_id)
        if prior_index is None:
            findings.append(
                LintFinding(
                    LintCode.COMPACTION_PARENT_UNRESOLVED,
                    f"revision {revision.revision_id!r} chains to prior "
                    + f"compaction {prior_id!r}, which is not in the proven "
                    + "ancestry of this revision",
                )
            )
        elif prior_index <= index:
            findings.append(
                LintFinding(
                    LintCode.COMPACTION_PARENT_UNRESOLVED,
                    f"revision {revision.revision_id!r} chains to prior "
                    + f"compaction {prior_id!r}, which is not behind it in the "
                    + "proven ancestry of this revision",
                )
            )
        elif revisions[prior_index].compaction is None:
            findings.append(
                LintFinding(
                    LintCode.COMPACTION_PARENT_UNRESOLVED,
                    f"revision {revision.revision_id!r} chains to prior "
                    + f"compaction {prior_id!r}, which records no compaction",
                )
            )
    return findings


def _conservation_findings(
    chain: Lineage, record: WheypointRecord
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
    revision: WheypointRevision,
    git_object_exists: Callable[[str], bool],
    *,
    repository_root: Path,
) -> list[LintFinding]:
    commit = revision.repository.commit
    if commit is None:
        return []
    if not git_object_exists(commit):
        return [
            LintFinding(
                LintCode.GIT_OBJECT_MISSING,
                f"revision {revision.revision_id!r} cites commit {commit}, which "
                + "does not resolve in this repository",
            )
        ]
    return lint_freshness.stale_commit_findings(commit, repository_root=repository_root)


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
