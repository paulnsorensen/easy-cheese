"""Turn a reference into something it is safe to continue from -- or a refusal.

Authoritative lookup has one fixed precedence, followed only by the legacy
fallback:

1. an explicit path to a projection document;
2. an exact work id in the project's XDG corpus;
3. a *unique* slug in that corpus;
4. a safe legacy slug or exact `.cheese/notes/<slug>.md` path after an
   authoritative miss.

A slug is an alias, not an identity, so two work ids answering to one slug is an
ambiguity that names both. Nothing here breaks a tie by modification time,
session, or which slug was written last, and a miss reports the exact locations
that were probed rather than a bare "not found".

Whatever the lookup finds is then re-validated from disk by `lint`, and only a
clean record with no active gate comes back `authoritative`. Everything else --
tampering, an unresolved parent, another project's record, a commit that no
longer exists, a stale coverage claim, an open question -- comes back `gated`
or `error`, which is the whole point: the caller has no branch that dispatches
on a checkpoint it could not verify.

Legacy notes use the private Wheypoint compatibility parser. They remain
non-authoritative context and never become dispatchable.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from enum import Enum
from pathlib import Path

from attrs import define, evolve, field
from easy_cheese_schemas import (
    WheypointProjection,
    WheypointRecord,
    WheypointStatus,
)

from easy_cheese.shared import paths

from . import legacy as legacy_mod
from . import lint, records, storage

_IDENTIFIER_RE = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")


class ResolutionOutcome(str, Enum):
    AUTHORITATIVE = "authoritative"
    GATED = "gated"
    AMBIGUOUS = "ambiguous"
    NOT_FOUND = "not-found"
    LEGACY = "legacy"
    ERROR = "error"


class ResolutionSource(str, Enum):
    PATH = "path"
    WORK_ID = "work-id"
    SLUG = "slug"
    LEGACY = "legacy"


@define(frozen=True)
class Resolution:
    """What a reference resolved to, and what stops it being acted on."""

    outcome: ResolutionOutcome
    source: ResolutionSource | None = None
    work_id: str | None = None
    record: WheypointRecord | None = None
    projection: WheypointProjection | None = None
    findings: tuple[lint.LintFinding, ...] = field(default=())
    matches: tuple[str, ...] = field(default=())
    searched: tuple[str, ...] = field(default=())
    legacy_note: Path | None = None
    legacy_slug: legacy_mod.LegacyHandoffSlug | None = None
    detail: str | None = None

    @property
    def dispatchable(self) -> bool:
        """Only a validated, ungated current revision may dispatch by itself."""
        return self.outcome is ResolutionOutcome.AUTHORITATIVE


def _is_path_ref(ref: str) -> bool:
    return "/" in ref or ref.startswith("~")


def resolve(
    ref: str,
    *,
    corpus_root: Path | str | None = None,
    project_key: str | None = None,
    workspace_root: Path | str | None = None,
    git_object_exists: Callable[[str], bool] | None = None,
    artifact_digest: Callable[[str], str | None] | None = None,
) -> Resolution:
    """Resolve an authoritative reference, then fall back to one legacy note."""
    root = Path(workspace_root) if workspace_root is not None else Path.cwd()
    checks = _Checks(
        corpus_root=(
            Path(corpus_root)
            if corpus_root is not None
            else paths.project_corpus_root()
        ),
        project_key=project_key if project_key is not None else paths.project_key(),
        git_object_exists=git_object_exists or lint.git_object_exists_in(root),
        artifact_digest=artifact_digest or lint.artifact_digest_in(root),
    )

    if not ref.strip():
        return Resolution(ResolutionOutcome.ERROR, detail="reference is empty")
    if _is_path_ref(ref):
        authoritative = _resolve_path(ref, checks)
        if authoritative.outcome not in {
            ResolutionOutcome.NOT_FOUND,
            ResolutionOutcome.ERROR,
        } or not _is_legacy_path_ref(ref):
            return authoritative
    else:
        if _IDENTIFIER_RE.fullmatch(ref) is None:
            return Resolution(
                ResolutionOutcome.ERROR,
                detail=(
                    f"reference {ref!r} is neither a path nor an identifier matching "
                    f"{_IDENTIFIER_RE.pattern}"
                ),
            )
        if (checks.work_root / ref / storage.RECORD_FILENAME).is_file():
            return _validate(ref, ResolutionSource.WORK_ID, checks)
        authoritative = _resolve_slug(ref, checks)

    if authoritative.outcome is ResolutionOutcome.NOT_FOUND or _is_legacy_path_ref(ref):
        legacy = resolve_legacy(ref, start=root)
        if legacy.outcome is not ResolutionOutcome.NOT_FOUND:
            return legacy
    return authoritative


def _is_legacy_path_ref(ref: str) -> bool:
    path = Path(ref).expanduser()
    return (
        path.is_absolute()
        and path.parent.name == legacy_mod.NOTES_DIR_PARTS[1]
        and path.parent.parent.name == legacy_mod.NOTES_DIR_PARTS[0]
        and path.suffix == ".md"
    )


@define(frozen=True)
class _Checks:
    """The corpus and the validators every resolution runs against."""

    corpus_root: Path
    project_key: str
    git_object_exists: Callable[[str], bool]
    artifact_digest: Callable[[str], str | None]

    @property
    def work_root(self) -> Path:
        return self.corpus_root / storage.WORK_DIRNAME


def _corpus_locations(ref: str, checks: _Checks) -> tuple[str, ...]:
    """Exactly the two places an id-or-slug reference is looked for."""
    return (
        str(checks.work_root / ref / storage.RECORD_FILENAME),
        str(checks.work_root / "*" / storage.RECORD_FILENAME),
    )


def _resolve_path(ref: str, checks: _Checks) -> Resolution:
    path = Path(ref).expanduser()
    if not path.is_file():
        return Resolution(
            ResolutionOutcome.NOT_FOUND,
            source=ResolutionSource.PATH,
            searched=(str(path),),
        )
    report = lint.lint_projection_file(path)
    if report.projection is None:
        return Resolution(
            ResolutionOutcome.ERROR,
            source=ResolutionSource.PATH,
            searched=(str(path),),
            findings=report.findings,
            detail=f"{path} is not a Wheypoint projection",
        )
    return _validate(
        report.projection.work_id,
        ResolutionSource.PATH,
        checks,
        searched=(str(path),),
        document_findings=report.findings,
        expected_revision_id=report.projection.revision_id,
    )


def _slug_matches(slug: str, checks: _Checks) -> tuple[str, ...]:
    """Every work id whose record claims `slug`, in work-id order.

    Work-id order is reporting order for an ambiguity, never a preference: a
    second match is refused, not ranked.
    """
    if not checks.work_root.is_dir():
        return ()
    matched: list[str] = []
    for directory in sorted(checks.work_root.iterdir(), key=lambda p: p.name):
        record_path = directory / storage.RECORD_FILENAME
        if not record_path.is_file():
            continue
        try:
            record = storage.WorkStore(
                work_id=directory.name, root=directory
            ).read_record()
        except (ValueError, OSError):
            continue
        if record is not None and record.slug == slug:
            matched.append(directory.name)
    return tuple(matched)


def _resolve_slug(slug: str, checks: _Checks) -> Resolution:
    matches = _slug_matches(slug, checks)
    searched = _corpus_locations(slug, checks)
    if not matches:
        return Resolution(
            ResolutionOutcome.NOT_FOUND,
            source=ResolutionSource.SLUG,
            searched=searched,
        )
    if len(matches) > 1:
        return Resolution(
            ResolutionOutcome.AMBIGUOUS,
            source=ResolutionSource.SLUG,
            matches=matches,
            searched=searched,
            detail=(
                f"slug {slug!r} names {len(matches)} work records: "
                + ", ".join(matches)
            ),
        )
    only_match = next(iter(matches))
    return _validate(only_match, ResolutionSource.SLUG, checks, searched=searched)


def _validate(
    work_id: str,
    source: ResolutionSource,
    checks: _Checks,
    *,
    searched: tuple[str, ...] = (),
    document_findings: tuple[lint.LintFinding, ...] = (),
    expected_revision_id: str | None = None,
) -> Resolution:
    try:
        store = storage.WorkStore.open(work_id, corpus_root=checks.corpus_root)
    except storage.StorageError as exc:
        return Resolution(
            ResolutionOutcome.ERROR, source=source, searched=searched, detail=str(exc)
        )
    try:
        report = lint.lint_work(
            store,
            project_key=checks.project_key,
            git_object_exists=checks.git_object_exists,
            artifact_digest=checks.artifact_digest,
        )
    except (records.RecordError, ValueError, OSError) as exc:
        return Resolution(
            ResolutionOutcome.ERROR, source=source, work_id=work_id, detail=str(exc)
        )

    findings = (*document_findings, *report.findings)
    if report.record is None:
        return Resolution(
            ResolutionOutcome.ERROR,
            source=source,
            work_id=work_id,
            findings=findings,
            searched=searched,
            detail=f"work {work_id!r} has no readable record",
        )

    resolution = Resolution(
        ResolutionOutcome.AUTHORITATIVE,
        source=source,
        work_id=work_id,
        record=report.record,
        projection=report.projection,
        findings=findings,
        searched=searched,
    )
    gating = tuple(f for f in findings if lint.gates_continuation(f))
    if gating:
        return _gate(resolution, f"{len(gating)} validation failure(s)")
    if (
        expected_revision_id is not None
        and expected_revision_id != report.record.revision_id
    ):
        return _gate(
            resolution,
            f"reference names revision {expected_revision_id!r}, but the current "
            + f"revision is {report.record.revision_id!r}",
        )
    if report.record.status is WheypointStatus.GATED:
        return _gate(
            resolution,
            "active gating entries: "
            + ", ".join(report.record.gating_entry_ids),
        )
    return resolution


def _gate(resolution: Resolution, detail: str) -> Resolution:
    return evolve(resolution, outcome=ResolutionOutcome.GATED, detail=detail)


def resolve_legacy(
    slug: str,
    *,
    start: Path | str,
    run: legacy_mod.Runner | None = None,
) -> Resolution:
    """Resolve a legacy note as untrusted, non-dispatchable context."""
    try:
        lookup = legacy_mod.find_legacy_note(slug, start=start, run=run)
    except legacy_mod.LegacyLookupError as exc:
        return Resolution(
            ResolutionOutcome.ERROR, source=ResolutionSource.LEGACY, detail=str(exc)
        )
    if lookup.outcome is legacy_mod.LegacyOutcome.AMBIGUOUS:
        return Resolution(
            ResolutionOutcome.AMBIGUOUS,
            source=ResolutionSource.LEGACY,
            matches=lookup.match_paths,
            searched=lookup.searched,
            detail=(
                f"slug {slug!r} names {len(lookup.matches)} legacy notes: "
                + ", ".join(lookup.match_paths)
            ),
        )
    note = lookup.note
    if note is None:
        return Resolution(
            ResolutionOutcome.NOT_FOUND,
            source=ResolutionSource.LEGACY,
            searched=lookup.searched,
            detail=lookup.error,
        )
    try:
        slug_block = legacy_mod.parse_legacy_note(
            note.path.read_text(encoding="utf-8")
        )
    except (legacy_mod.LegacyDecodeError, OSError) as exc:
        return Resolution(
            ResolutionOutcome.ERROR,
            source=ResolutionSource.LEGACY,
            legacy_note=note.path,
            searched=lookup.searched,
            detail=f"{note.path} is not a readable handoff note: {exc}",
        )
    found = Resolution(
        ResolutionOutcome.LEGACY,
        source=ResolutionSource.LEGACY,
        legacy_note=note.path,
        legacy_slug=slug_block,
        searched=lookup.searched,
    )
    if slug_block.artifact:
        artifact = Path(slug_block.artifact)
        worktree = note.worktree.resolve()
        if artifact.is_absolute():
            return _gate(
                found,
                f"declared artifact {slug_block.artifact!r} must be a "
                + f"repo-relative regular file under {worktree}",
            )
        candidate = worktree / artifact
        try:
            resolved_artifact = candidate.resolve(strict=True)
        except (OSError, RuntimeError, ValueError):
            return _gate(
                found,
                f"declared artifact {slug_block.artifact!r} does not resolve to "
                + f"an existing regular file under {worktree}",
            )
        try:
            _ = resolved_artifact.relative_to(worktree)
        except ValueError:
            return _gate(
                found,
                f"declared artifact {slug_block.artifact!r} resolves outside "
                + f"legacy worktree {worktree}",
            )
        if not resolved_artifact.is_file():
            return _gate(
                found,
                f"declared artifact {slug_block.artifact!r} must be an existing "
                + "regular file",
            )
    if slug_block.is_halt():
        reason = slug_block.halt_reason or "halt status"
        return _gate(found, f"legacy note halts: {reason}")
    if slug_block.is_gated():
        reason = slug_block.halt_reason or "gated status"
        return _gate(found, f"legacy note is gated: {reason}")
    return found
