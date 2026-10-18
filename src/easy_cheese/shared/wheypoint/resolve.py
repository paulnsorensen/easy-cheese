"""Turn a reference into something it is safe to continue from -- or a refusal.

Authoritative lookup has one fixed precedence, followed by phase artifacts and
then the legacy fallback:

1. an explicit path to a projection document;
2. an exact work id in the project's XDG corpus;
3. a *unique* slug in that corpus;
4. `.cheese/{cure,age,press,cook}/<slug>.md` in fixed order;
5. a safe legacy slug or exact `.cheese/notes/<slug>.md` path after an
   authoritative miss;
6. only when the caller asks for `fuzzy`, a unique slug prefix, then a unique
   slug substring, after every tier above misses.

A slug is an alias, not an identity, so two work ids answering to one slug is an
ambiguity that names both. Nothing here breaks a tie by modification time,
session, or which slug was written last, and a miss reports the exact locations
that were probed rather than a bare "not found".

Whatever the lookup finds is then re-validated from disk by `_check_work`, and
only a clean record with no active gate comes back `authoritative`. Everything else --
an inconsistent or incomplete store, a projection that describes another record,
another project's record, a commit that no longer exists, a stale coverage
claim or artifact link, an open question -- comes back `gated`
or `error`, which is the whole point: the caller has no branch that dispatches
on a checkpoint it could not verify.

Legacy notes use the private Wheypoint compatibility parser. They remain
non-authoritative context and never become dispatchable.
"""

from __future__ import annotations

import functools
import json
import re
import subprocess
import sys
from collections.abc import Callable, Generator
from contextlib import contextmanager
from enum import Enum
from pathlib import Path
from typing import cast

from attrs import define, evolve, field
from easy_cheese_schemas import (
    WheypointProjection,
    WheypointRecord,
    WheypointRevision,
    WheypointStatus,
)

from easy_cheese_schemas.compat import Provenance, classify_stamp
from easy_cheese_schemas.handback_status import PROCEED
from easy_cheese.shared import git_utils, handoff, paths

from . import checkpoint as checkpoint_mod
from . import commit as commit_mod
from . import legacy as legacy_mod
from . import grounded, lint_types, records, refs, storage
from . import projection as projection_mod

_IDENTIFIER_RE = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")
# A parent may live outside every worktree, but only as a reference someone can
# actually open: an absolute http(s) URL, never a bare host or a local path.
_PARENT_URL_RE = re.compile(r"https?://[^\s/]+(?:/\S*)?")


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
    PHASE_ARTIFACT = "phase-artifact"
    LEGACY = "legacy"


@define(frozen=True)
class Resolution:
    """What a reference resolved to, and what stops it being acted on."""

    outcome: ResolutionOutcome
    source: ResolutionSource | None = None
    work_id: str | None = None
    record: WheypointRecord | None = None
    projection: WheypointProjection | None = None
    findings: tuple[lint_types.LintFinding, ...] = field(default=())
    matches: tuple[str, ...] = field(default=())
    searched: tuple[str, ...] = field(default=())
    legacy_note: Path | None = None
    legacy_slug: legacy_mod.LegacyHandoffSlug | None = None
    phase_slug: handoff.HandoffSlug | None = None
    detail: str | None = None
    fuzzy_mode: str | None = None

    @property
    def matched_by(self) -> str | None:
        """How the reference matched: exact, prefix, or substring; None on a miss."""
        if self.outcome in {ResolutionOutcome.NOT_FOUND, ResolutionOutcome.ERROR}:
            return None
        return self.fuzzy_mode or "exact"

    @property
    def dispatchable(self) -> bool:
        """Only a validated, ungated current revision may dispatch by itself."""
        return self.outcome is ResolutionOutcome.AUTHORITATIVE


def _is_path_ref(ref: str) -> bool:
    return "/" in ref or ref.startswith("~")


def _corpus_address(ref: str) -> tuple[Path, str] | None:
    """Infer a project corpus only from its canonical projection layout."""
    path = Path(ref).expanduser().resolve()
    try:
        relative = path.relative_to(paths.corpus_home().resolve())
    except ValueError:
        return None
    parts = relative.parts
    if (
        len(parts) != 5
        or parts[1] != storage.WORK_DIRNAME
        or parts[3] != storage.PROJECTIONS_DIRNAME
        or not path.is_file()
    ):
        return None
    project = parts[0]
    work_id = parts[2]
    try:
        _ = storage.WorkStore.open(work_id, corpus_root=paths.corpus_home() / project)
    except storage.StorageError:
        return None
    projection = _read_projection(path)[0]
    if projection is None or projection.work_id != work_id:
        return None
    return paths.corpus_home() / project, project


def _git_project_key(root: Path) -> str | None:
    """Read the Git-derived project key without ambient corpus overrides."""
    try:
        return paths.git_project_key(root)
    except (OSError, subprocess.SubprocessError):
        return None


def _is_git_checkout(root: Path) -> bool:
    """Require an explicit foreign workspace to be a real checkout."""
    try:
        result = git_utils.run_git(
            ["rev-parse", "--show-toplevel"], cwd=root, timeout=5
        )
    except (OSError, subprocess.SubprocessError):
        return False
    if result.returncode != 0 or not result.stdout.strip():
        return False
    try:
        return Path(result.stdout.strip()).resolve() == root
    except OSError:
        return False


def resolve(
    ref: str,
    *,
    corpus_root: Path | str | None = None,
    project_key: str | None = None,
    workspace_root: Path | str | None = None,
    git_object_exists: Callable[[str], bool] | None = None,
    require_workspace: bool = False,
    artifact_digest: Callable[[str], str | None] | None = None,
    fuzzy: bool = False,
) -> Resolution:
    """Resolve an authoritative reference, then fall back to one legacy note.

    `fuzzy` adds slug prefix, then substring, matching as the last tier, after
    the exact slug, phase-artifact, and legacy lookups all miss.
    """
    if not ref.strip():
        return Resolution(ResolutionOutcome.ERROR, detail="reference is empty")

    root = paths.resolve_repo_root(workspace_root)
    resolved_project_key = (
        project_key if project_key is not None else paths.project_key(root)
    )
    resolved_corpus_root = (
        Path(corpus_root)
        if corpus_root is not None
        else paths.project_corpus_root(resolved_project_key)
    )
    if _is_path_ref(ref) and corpus_root is None and project_key is None:
        addressed = _corpus_address(ref)
        if addressed is not None:
            resolved_corpus_root, resolved_project_key = addressed
            require_workspace = True

    context_findings: tuple[lint_types.LintFinding, ...] = ()
    git_workspace_key = _git_project_key(root)
    workspace_project_key = git_workspace_key or paths.project_key(root)
    missing_checkout = (
        require_workspace and workspace_root is not None and not _is_git_checkout(root)
    )
    alias_binding = (
        require_workspace
        and workspace_root is not None
        and project_key is not None
        and paths.project_key(root) == resolved_project_key
        and not missing_checkout
        and git_workspace_key != resolved_project_key
    )
    workspace_mismatch = require_workspace and (
        (git_workspace_key is None or resolved_project_key != git_workspace_key)
        and not alias_binding
    )
    if workspace_mismatch or missing_checkout:
        code = (
            lint_types.LintCode.WORKSPACE_MISMATCH
            if workspace_root is not None
            else lint_types.LintCode.WORKSPACE_REQUIRED
        )
        if missing_checkout:
            detail = f"workspace {root} is not an owning Git checkout"
        else:
            detail = (
                f"record belongs to project {resolved_project_key!r}, but workspace "
                + f"{root} identifies as {workspace_project_key!r}"
            )
        if workspace_root is None:
            detail += "; pass --workspace-root PATH for the owning checkout"
        context_findings = (lint_types.LintFinding(code, detail),)

    checks = _Checks(
        workspace_root=root,
        corpus_root=resolved_corpus_root,
        project_key=resolved_project_key,
        git_object_exists=git_object_exists or _git_object_exists_in(root),
        artifact_digest=artifact_digest or _artifact_digest_in(root),
        alias_binding=alias_binding,
        context_findings=context_findings,
    )
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

    if authoritative.outcome is ResolutionOutcome.NOT_FOUND and not _is_path_ref(ref):
        phase = _resolve_phase_artifact(ref, checks, searched=authoritative.searched)
        if phase is not None:
            return phase
    if authoritative.outcome is ResolutionOutcome.NOT_FOUND or _is_legacy_path_ref(ref):
        legacy = resolve_legacy(ref, start=root)
        if legacy.outcome is not ResolutionOutcome.NOT_FOUND:
            return legacy
    if (
        fuzzy
        and not _is_path_ref(ref)
        and authoritative.outcome is ResolutionOutcome.NOT_FOUND
    ):
        # Only a user-facing lookup guesses, and only after every exact tier missed.
        guessed = _resolve_fuzzy_slug(ref, checks)
        if guessed.outcome is not ResolutionOutcome.NOT_FOUND:
            return guessed
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

    workspace_root: Path
    corpus_root: Path
    project_key: str
    git_object_exists: Callable[[str], bool]
    artifact_digest: Callable[[str], str | None]
    alias_binding: bool = False
    context_findings: tuple[lint_types.LintFinding, ...] = ()

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
    parsed, document_findings = _read_projection(path)
    try:
        path = path.resolve()
        inside_corpus = path.is_relative_to(checks.corpus_root.resolve())
    except OSError:
        inside_corpus = False
    if not inside_corpus and parsed is not None:
        return Resolution(
            ResolutionOutcome.NOT_FOUND,
            source=ResolutionSource.PATH,
            searched=(str(path),),
        )
    if parsed is None:
        return Resolution(
            ResolutionOutcome.ERROR,
            source=ResolutionSource.PATH,
            searched=(str(path),),
            findings=document_findings,
            detail=f"{path} is not a Wheypoint projection",
        )
    return _validate(
        parsed.work_id,
        ResolutionSource.PATH,
        checks,
        searched=(str(path),),
        document_findings=document_findings,
        expected_revision_id=parsed.revision_id,
    )


def _raw_slug(record_path: Path) -> str | None:
    try:
        raw = cast(object, json.loads(record_path.read_text(encoding="utf-8")))
    except (ValueError, OSError):
        return None
    if not isinstance(raw, dict):
        return None
    claimed = cast(dict[str, object], raw).get("slug")
    return claimed if isinstance(claimed, str) else None


def _slug_records(checks: _Checks) -> Generator[tuple[str, str], None, None]:
    """Each readable record's (work id, claimed slug), in work-id order.

    Work-id order is reporting order for an ambiguity, never a preference.
    """
    if not checks.work_root.is_dir():
        return
    for directory in sorted(checks.work_root.iterdir(), key=lambda p: p.name):
        record_path = directory / storage.RECORD_FILENAME
        if not record_path.is_file():
            continue
        try:
            # The same guard `_validate` re-opens with: a directory whose name is
            # not a safe work id is not a store, whatever record it holds.
            record = storage.WorkStore.open(
                directory.name, corpus_root=checks.corpus_root
            ).read_record()
            claimed = None if record is None else record.slug
        except storage.SchemaVersionFutureError:
            # A newer runtime's record keeps its slug: it must still resolve,
            # so that `_check_work` can report it as ahead of this runtime.
            claimed = _raw_slug(record_path)
        except (storage.StorageError, ValueError, OSError):
            continue
        if claimed is not None:
            yield directory.name, claimed


def _exact_slug_matches(slug: str, checks: _Checks) -> tuple[str, ...]:
    """Work ids whose slug equals `slug`; the walk stops at the second match."""
    matched: list[str] = []
    for work_id, claimed in _slug_records(checks):
        if claimed == slug:
            matched.append(work_id)
            if len(matched) > 1:
                break
    return tuple(matched)


def _fuzzy_slug_matches(
    text: str, checks: _Checks
) -> tuple[str, tuple[tuple[str, str], ...]]:
    """One corpus read, classified in memory.

    Returns the first of prefix then substring with any hit, as
    `(mode, ((work_id, slug), ...))`, or `("", ())` on a miss.
    """
    records_ = tuple(_slug_records(checks))
    prefix = tuple(item for item in records_ if item[1].startswith(text))
    if prefix:
        return "prefix", prefix
    substring = tuple(item for item in records_ if text in item[1])
    if substring:
        return "substring", substring
    return "", ()


def _resolve_slug(slug: str, checks: _Checks) -> Resolution:
    work_ids = _exact_slug_matches(slug, checks)
    searched = _corpus_locations(slug, checks)
    if not work_ids:
        return Resolution(
            ResolutionOutcome.NOT_FOUND,
            source=ResolutionSource.SLUG,
            searched=searched,
        )
    if len(work_ids) > 1:
        return Resolution(
            ResolutionOutcome.AMBIGUOUS,
            source=ResolutionSource.SLUG,
            matches=work_ids,
            searched=searched,
            detail=(
                f"slug {slug!r} names {len(work_ids)} work records: "
                + ", ".join(work_ids)
            ),
        )
    return _validate(
        next(iter(work_ids)),
        ResolutionSource.SLUG,
        checks,
        searched=searched,
    )


def _resolve_fuzzy_slug(slug: str, checks: _Checks) -> Resolution:
    """A unique prefix, then a unique substring; several matches are ambiguous."""
    mode, hits = _fuzzy_slug_matches(slug, checks)
    searched = _corpus_locations(slug, checks)
    if not hits:
        return Resolution(
            ResolutionOutcome.NOT_FOUND,
            source=ResolutionSource.SLUG,
            searched=searched,
        )
    if len(hits) > 1:
        return Resolution(
            ResolutionOutcome.AMBIGUOUS,
            source=ResolutionSource.SLUG,
            matches=tuple(work_id for work_id, _ in hits),
            searched=searched,
            fuzzy_mode=mode,
            detail=(
                f"slug {slug!r} is a {mode} of {len(hits)} work records: "
                + ", ".join(f"{work_id} ({claimed})" for work_id, claimed in hits)
            ),
        )
    work_id, claimed = next(iter(hits))
    resolution = _validate(work_id, ResolutionSource.SLUG, checks, searched=searched)
    note = f"matched by {mode}: {slug!r} -> slug {claimed!r}"
    detail = note if resolution.detail is None else f"{resolution.detail}; {note}"
    return evolve(resolution, detail=detail, fuzzy_mode=mode)


def _resolve_phase_artifact(
    slug: str, checks: _Checks, *, searched: tuple[str, ...]
) -> Resolution | None:
    """Resolve the first matching phase artifact before legacy notes."""
    if paths.validate_slug(slug) is not None:
        # An identifier the artifact grammar rejects names no artifact path;
        # that is a miss, not a failure to look.
        return None
    root = checks.workspace_root / ".cheese"
    phase_paths: list[str] = []
    for phase in reversed(paths.CHAIN_PHASES):
        path = paths.artifact_path(phase, slug, root=root)
        phase_paths.append(str(path))
        if not path.is_file():
            continue
        try:
            phase_slug = handoff.parse_handoff_slug(path.read_text(encoding="utf-8"))
        except (handoff.HandoffParseError, OSError) as exc:
            return Resolution(
                ResolutionOutcome.ERROR,
                source=ResolutionSource.PHASE_ARTIFACT,
                searched=(*searched, *phase_paths),
                detail=f"{path} is not a readable handoff artifact: {exc}",
            )
        return Resolution(
            ResolutionOutcome.LEGACY,
            source=ResolutionSource.PHASE_ARTIFACT,
            phase_slug=phase_slug,
            searched=(*searched, *phase_paths),
        )
    return None


def _validate(
    work_id: str,
    source: ResolutionSource,
    checks: _Checks,
    *,
    searched: tuple[str, ...] = (),
    document_findings: tuple[lint_types.LintFinding, ...] = (),
    expected_revision_id: str | None = None,
) -> Resolution:
    try:
        store = storage.WorkStore.open(work_id, corpus_root=checks.corpus_root)
    except storage.StorageError as exc:
        return Resolution(
            ResolutionOutcome.ERROR, source=source, searched=searched, detail=str(exc)
        )
    if checks.context_findings:
        try:
            record = store.read_record()
        except storage.SchemaVersionFutureError as exc:
            return _future_error(source, work_id, exc)
        except (records.RecordError, storage.StorageError, ValueError, OSError) as exc:
            return Resolution(
                ResolutionOutcome.ERROR, source=source, work_id=work_id, detail=str(exc)
            )
        if record is None:
            return Resolution(
                ResolutionOutcome.ERROR,
                source=source,
                work_id=work_id,
                findings=(*document_findings, *checks.context_findings),
                searched=searched,
                detail=f"work {work_id!r} has no readable record",
            )
        findings = [*document_findings]
        if record.project_key != checks.project_key:
            findings.append(
                lint_types.LintFinding(
                    lint_types.LintCode.PROJECT_MISMATCH,
                    f"record belongs to project {record.project_key!r}, not "
                    + f"{checks.project_key!r}",
                )
            )
        findings.extend(checks.context_findings)
        return _gate(
            Resolution(
                ResolutionOutcome.AUTHORITATIVE,
                source=source,
                work_id=work_id,
                record=record,
                findings=tuple(findings),
                searched=searched,
            ),
            "workspace binding is required before repository validation",
        )
    if checks.alias_binding:
        try:
            record = store.read_record()
            revision = (
                None
                if record is None
                else store.read_revision(record.revision_number, record.revision_id)
            )
        except storage.SchemaVersionFutureError as exc:
            return _future_error(source, work_id, exc)
        except (records.RecordError, storage.StorageError, ValueError, OSError) as exc:
            return Resolution(
                ResolutionOutcome.ERROR, source=source, work_id=work_id, detail=str(exc)
            )
        commit = None if revision is None else revision.repository.commit
        if record is not None and not commit:
            return _gate(
                Resolution(
                    ResolutionOutcome.AUTHORITATIVE,
                    source=source,
                    work_id=work_id,
                    record=record,
                    findings=(
                        *document_findings,
                        lint_types.LintFinding(
                            lint_types.LintCode.GIT_OBJECT_MISSING,
                            "alias project binding requires a pinned repository commit",
                        ),
                    ),
                    searched=searched,
                ),
                "alias project binding requires a pinned repository commit",
            )
        if (
            record is not None
            and revision is not None
            and commit is not None
            and not checks.git_object_exists(commit)
        ):
            return _gate(
                Resolution(
                    ResolutionOutcome.AUTHORITATIVE,
                    source=source,
                    work_id=work_id,
                    record=record,
                    findings=(
                        *document_findings,
                        lint_types.LintFinding(
                            lint_types.LintCode.GIT_OBJECT_MISSING,
                            f"revision {revision.revision_id!r} cites commit {commit}, "
                            + "which does not resolve in this repository",
                        ),
                    ),
                    searched=searched,
                ),
                "alias project binding requires the pinned commit in this checkout",
            )
    try:
        with _git_warnings_once():
            report = _check_work(store, checks)
    except (records.RecordError, storage.StorageError, ValueError, OSError) as exc:
        return Resolution(
            ResolutionOutcome.ERROR, source=source, work_id=work_id, detail=str(exc)
        )

    findings = (*document_findings, *report.findings, *checks.context_findings)
    future = next(
        (
            f
            for f in report.findings
            if f.code is lint_types.LintCode.SCHEMA_VERSION_FUTURE
        ),
        None,
    )
    if future is not None:
        return Resolution(
            ResolutionOutcome.ERROR,
            source=source,
            work_id=work_id,
            findings=findings,
            searched=searched,
            detail=f"{storage.FUTURE_STAMP_CODE}: {future.detail}",
        )
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
    gating = tuple(f for f in findings if lint_types.gates_continuation(f))
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
            "active gating entries: " + ", ".join(report.record.gating_entry_ids),
        )
    return resolution


def _future_error(
    source: ResolutionSource, work_id: str, exc: storage.SchemaVersionFutureError
) -> Resolution:
    return Resolution(
        ResolutionOutcome.ERROR,
        source=source,
        work_id=work_id,
        detail=f"{storage.FUTURE_STAMP_CODE}: {exc}",
    )


def _gate(resolution: Resolution, detail: str) -> Resolution:
    return evolve(resolution, outcome=ResolutionOutcome.GATED, detail=detail)


@define(frozen=True)
class _WorkReport:
    """What reading one work store found: findings plus what was readable."""

    findings: tuple[lint_types.LintFinding, ...] = field(default=())
    record: WheypointRecord | None = None
    projection: WheypointProjection | None = None


def _read_projection(
    path: Path | str,
) -> tuple[WheypointProjection | None, tuple[lint_types.LintFinding, ...]]:
    """Parse one projection document, or name why it cannot be read."""
    try:
        return projection_mod.parse(Path(path).read_text(encoding="utf-8")), ()
    except (OSError, projection_mod.ProjectionParseError) as exc:
        return None, (
            lint_types.LintFinding(lint_types.LintCode.PROJECTION_UNREADABLE, str(exc)),
        )


def _projection_mismatch(
    record: WheypointRecord,
    current: WheypointRevision,
    projection: WheypointProjection | None,
) -> tuple[lint_types.LintFinding, ...]:
    """Name a current projection that describes a different record.

    The digest is the one the current receipt stored, which the survey already
    checked against the raw record: a recomputed digest would differ for a
    pre-v5 record once it is normalized.
    """
    if projection is None:
        return ()
    mismatches: list[str] = []
    if projection.work_id != record.work_id:
        mismatches.append(f"work_id {projection.work_id!r} != {record.work_id!r}")
    if projection.revision_id != record.revision_id:
        mismatches.append(
            f"revision_id {projection.revision_id!r} != {record.revision_id!r}"
        )
    if projection.record_digest != current.record_digest:
        mismatches.append(
            f"record_digest {projection.record_digest} != {current.record_digest}"
        )
    if not mismatches:
        return ()
    return (
        lint_types.LintFinding(
            lint_types.LintCode.PROJECTION_RECORD_MISMATCH,
            "the current projection describes a different record: "
            + "; ".join(mismatches),
        ),
    )


def _check_work(store: storage.WorkStore, checks: _Checks) -> _WorkReport:
    """Everything a caller must trust before acting on one work's checkpoint.

    Nothing here writes. A finding is a reason not to dispatch, never a repair.
    """
    survey = store.survey_receipts()
    record = survey.record
    stamped = survey.stamped_schema_version
    if stamped is not None and classify_stamp(stamped) is Provenance.FUTURE:
        # The stamp is read from the raw bytes: a future record this reader
        # cannot structure is still reported as ahead of the runtime, not as
        # store corruption (ADR wheypoint-ergonomics-004).
        detail = storage.future_stamp_detail(stamped, f"record for work {store.work_id!r}")
        return _WorkReport(
            findings=(
                lint_types.LintFinding(lint_types.LintCode.SCHEMA_VERSION_FUTURE, detail),
            )
        )
    findings = [
        lint_types.LintFinding(lint_types.LintCode.STORE_INCONSISTENT, problem)
        for problem in survey.problems
    ]
    incomplete = [
        lint_types.LintFinding(lint_types.LintCode.REVISION_INCOMPLETE, detail)
        for detail in survey.incomplete
    ]
    if record is None:
        if not findings:
            findings.append(
                lint_types.LintFinding(
                    lint_types.LintCode.RECORD_MISSING,
                    f"no record at {store.record_path}",
                )
            )
        return _WorkReport(findings=(*findings, *incomplete))
    findings.extend(incomplete)

    if record.project_key != checks.project_key:
        findings.append(
            lint_types.LintFinding(
                lint_types.LintCode.PROJECT_MISMATCH,
                f"record belongs to project {record.project_key!r}, not "
                + f"{checks.project_key!r}",
            )
        )
    # A missing current receipt is already a store problem in the survey.
    current = next(
        (
            revision
            for revision in survey.revisions
            if revision.revision_number == record.revision_number
            and revision.revision_id == record.revision_id
        ),
        None,
    )
    projection = None
    if current is not None:
        projection, projection_findings = _read_projection(
            store.projection_path(current.revision_number, current.revision_id)
        )
        findings.extend(projection_findings)
        findings.extend(_projection_mismatch(record, current, projection))
        findings.extend(_git_findings(current, checks))
    digest_of = functools.cache(checks.artifact_digest)
    findings.extend(_artifact_link_findings(record, digest_of))
    # Only the receipts the parent pointers reach count as ancestry.
    chain = commit_mod.ancestry(survey.revisions, current) if current else ()
    coverage = records.coverage_report(
        record,
        artifact_digest=digest_of,
        ancestor_revision_ids=frozenset(revision.revision_id for revision in chain),
    )
    findings.extend(
        lint_types.LintFinding(
            lint_types.LintCode.ARTIFACT_COVERAGE_INVALID,
            f"{failure.path}: {failure.reason}",
        )
        for failure in coverage.failures
    )
    findings.extend(_grounded_path_findings(record, checks.workspace_root))
    return _WorkReport(
        findings=tuple(findings), record=record, projection=projection
    )


_GIT_TIMEOUT_SECONDS = 5
# None outside a check: every failure is named. Inside one, the first failure
# flips it and the rest of that check stays quiet -- a single unrunnable git
# otherwise reports itself once per probe.
_warned_within_run: bool | None = None
# A `PR#<n>` or URL pointer in working_context references something outside the
# checkout, so the grounded path grammar has nothing local to check it against.
_EXTERNAL_POINTER_RE = re.compile(r"PR#[0-9]+|[a-z][a-z0-9+.-]*://.*")


@contextmanager
def _git_warnings_once() -> Generator[None]:
    """Name an unrunnable git at most once for the enclosing check."""
    global _warned_within_run
    previous = _warned_within_run
    _warned_within_run = False
    try:
        yield
    finally:
        _warned_within_run = previous


def _run_git_ok(
    args: list[str], *, cwd: Path | str
) -> subprocess.CompletedProcess[str] | None:
    """Run one advisory git command, or None when it could not run at all.

    Advisory checks degrade to silence, but a silence with no cause is
    indistinguishable from a pass, so the first failure names the command,
    where it ran, and what stopped it.
    """
    global _warned_within_run
    try:
        return git_utils.run_git(args, cwd=cwd, timeout=_GIT_TIMEOUT_SECONDS)
    except (OSError, subprocess.SubprocessError) as exc:
        if not _warned_within_run:
            if _warned_within_run is not None:
                _warned_within_run = True
            print(
                f"wheypoint: git-unavailable command={args[0]} cwd={cwd} "
                + f"error={type(exc).__name__}",
                file=sys.stderr,
            )
        return None


def _git_object_exists_in(root: Path | str) -> Callable[[str], bool]:
    """Read-only `git cat-file -e <object>^{object}` in `root`."""

    def exists(obj: str) -> bool:
        completed = _run_git_ok(["cat-file", "-e", f"{obj}^{{object}}"], cwd=root)
        return completed is not None and completed.returncode == 0

    return exists


def _artifact_digest_in(root: Path | str) -> Callable[[str], str | None]:
    """Digest a reference, with `repo:` paths contained by `root`."""
    return refs.digester(Path(root), paths.corpus_home())


def _git_findings(
    revision: WheypointRevision, checks: _Checks
) -> list[lint_types.LintFinding]:
    commit = revision.repository.commit
    if commit is None:
        return []
    if not checks.git_object_exists(commit):
        return [
            lint_types.LintFinding(
                lint_types.LintCode.GIT_OBJECT_MISSING,
                f"revision {revision.revision_id!r} cites commit {commit}, which "
                + "does not resolve in this repository",
            )
        ]
    ancestor = _run_git_ok(
        ["merge-base", "--is-ancestor", commit, "HEAD"], cwd=checks.workspace_root
    )
    if ancestor is None or ancestor.returncode != 1:
        return []
    distance_result = _run_git_ok(
        ["rev-list", "--count", f"{commit}..HEAD"], cwd=checks.workspace_root
    )
    if distance_result is None or distance_result.returncode != 0:
        return []
    try:
        distance = int(distance_result.stdout.strip())
    except ValueError:
        return []
    return [
        lint_types.LintFinding(
            lint_types.LintCode.STALE_COMMIT,
            f"HEAD does not descend from repository commit {commit}; "
            + f"distance is {distance}",
        )
    ]


def _artifact_link_findings(
    record: WheypointRecord,
    artifact_digest: Callable[[str], str | None],
) -> list[lint_types.LintFinding]:
    """Re-check each digest-bearing artifact link against its current target."""
    findings: list[lint_types.LintFinding] = []
    for link in record.artifact_links:
        if link.digest is None:
            continue
        ref = records.effective_ref(link)
        try:
            pinnable = refs.is_pinnable(refs.parse_ref(ref).scheme)
        except ValueError:
            pinnable = True
        if not pinnable:
            continue
        actual = artifact_digest(ref)
        if actual == link.digest:
            continue
        current = "missing" if actual is None else repr(actual)
        findings.append(
            lint_types.LintFinding(
                lint_types.LintCode.STALE_ARTIFACT_LINK,
                f"{link.path}: linked digest {link.digest!r}, current file "
                + f"digest is {current}",
            )
        )
    return findings


def _grounded_path_findings(
    record: WheypointRecord, repository_root: Path
) -> list[lint_types.LintFinding]:
    """Warn when a grounded entry violates the writer's own path grammar.

    Parses with `grounded.parse_grounded_entry` (the same grammar
    `validate_grounded` enforces at write time). A `PR#<n>` or URL pointer is
    exempt: it names something outside the checkout, so no local file can
    confirm or deny it.
    """
    findings: list[lint_types.LintFinding] = []
    resolved_root = repository_root.resolve()
    for entry in record.working_context:
        if _EXTERNAL_POINTER_RE.fullmatch(entry):
            continue
        try:
            path_text, _range = grounded.parse_grounded_entry(entry)
        except grounded.GroundedEntryError:
            findings.append(
                lint_types.LintFinding(
                    lint_types.LintCode.GROUNDED_PATH_MISSING,
                    f"working_context entry {entry!r} does not satisfy the "
                    + "grounded path grammar",
                )
            )
            continue
        issue = grounded.resolve_within(path_text, resolved_root)
        if issue is not None:
            findings.append(
                lint_types.LintFinding(
                    lint_types.LintCode.GROUNDED_PATH_MISSING,
                    f"working_context path {entry!r} {issue.value}",
                )
            )
    return findings


def _parent_tokens(raw: str) -> tuple[str, ...]:
    """The slugs a `parents:` line names, read tolerantly.

    The field is hand-written Markdown, not JSON: `[a, b]`, `a, b`, and
    `["a"]` all mean the same lineage, so the brackets and quotes are stripped
    rather than being made to parse.
    """
    tokens = (
        token.strip().strip("'\"").strip()
        for token in raw.strip().strip("[]").split(",")
    )
    return tuple(token for token in tokens if token)


def _parent_resolves(token: str, roots: tuple[Path, ...]) -> bool:
    if _PARENT_URL_RE.fullmatch(token) is not None:
        return True
    if "/" in token or token in {".", ".."}:
        return False
    return any(
        (
            root
            / legacy_mod.NOTES_DIR_PARTS[0]
            / legacy_mod.NOTES_DIR_PARTS[1]
            / f"{token}.md"
        ).is_file()
        for root in roots
    )


def _unresolved_parents(
    raw: str, *, note_worktree: Path, roots: tuple[Path, ...]
) -> tuple[str, ...]:
    """Every declared parent that names nothing a reader could go and read.

    Lineage is the one part of a legacy note a resumed session follows off the
    note itself, so a parent that resolves to nothing is a dangling pointer
    dressed as provenance -- reported here, exactly like a dangling artifact.
    """
    tokens = _parent_tokens(raw)
    if not tokens:
        return ()
    roots = (note_worktree, *(root for root in roots if root != note_worktree))
    return tuple(token for token in tokens if not _parent_resolves(token, roots))


def _legacy_artifact_gate(
    slug_block: legacy_mod.LegacyHandoffSlug, worktree: Path
) -> str | None:
    """Validate a declared legacy artifact against the destination that reads it.

    `next: affinage` reads a pull request, which is not a file in this
    worktree. Both skill documents publish `PR#<n>` or the pull request URL for
    that move. Every other move reads a repository file, so the file rule holds
    there.
    """
    value = slug_block.artifact
    assert value is not None
    if slug_block.next_skill == "affinage":
        if checkpoint_mod.PR_REFERENCE_RE.fullmatch(
            value.strip()
        ) or _PARENT_URL_RE.fullmatch(value):
            return None
        return (
            f"declared artifact {value!r} must be 'PR#<n>' or a pull request "
            + "URL for next: affinage"
        )
    artifact = Path(value)
    if artifact.is_absolute():
        return (
            f"declared artifact {value!r} must be a repo-relative regular file "
            + f"under {worktree}"
        )
    candidate = worktree / artifact
    try:
        resolved_artifact = candidate.resolve(strict=True)
    except (OSError, RuntimeError, ValueError):
        return (
            f"declared artifact {value!r} does not resolve to an existing "
            + f"regular file under {worktree}"
        )
    try:
        _ = resolved_artifact.relative_to(worktree)
    except ValueError:
        return (
            f"declared artifact {value!r} resolves outside legacy worktree {worktree}"
        )
    if not resolved_artifact.is_file():
        return f"declared artifact {value!r} must be an existing regular file"
    return None


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
        slug_block = legacy_mod.parse_legacy_note(note.path.read_text(encoding="utf-8"))
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
        artifact_gate = _legacy_artifact_gate(slug_block, note.worktree.resolve())
        if artifact_gate is not None:
            return _gate(found, artifact_gate)
    if slug_block.parents:
        unresolved = _unresolved_parents(
            slug_block.parents,
            note_worktree=note.worktree.resolve(),
            roots=lookup.roots,
        )
        if unresolved:
            return _gate(
                found,
                f"declared parent(s) {', '.join(repr(p) for p in unresolved)} "
                + "name no legacy note in any worktree and are not absolute "
                + "http(s) URLs",
            )
    if slug_block.disposition != PROCEED:
        reason = slug_block.reason or f"{slug_block.status} status"
        return _gate(found, f"legacy note {slug_block.status}: {reason}")
    return found
