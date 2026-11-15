"""The `export` and `import` commands: thin mouths over `shared.wheypoint.transfer`."""

from __future__ import annotations

import datetime as _dt
from pathlib import Path

import fromargs

from easy_cheese_schemas import Durability, SessionProvenance

from easy_cheese.shared import paths
from easy_cheese.shared.wheypoint import checkpoint as checkpoint_mod
from easy_cheese.shared.wheypoint import commit as commit_mod
from easy_cheese.shared.wheypoint import canonical, records, storage
from easy_cheese.shared.wheypoint import resolve as resolve_mod
from easy_cheese.shared.wheypoint import transfer as transfer_mod

from easy_cheese.cli.wheypoint.checkpoint import (
    MirrorError,
    mirror_finalizer,
    note_dir_for,
    refusal_for,
    result_payload,
)

_EXPORTABLE = (
    resolve_mod.ResolutionOutcome.AUTHORITATIVE,
    resolve_mod.ResolutionOutcome.GATED,
)


def run_export(
    ref: str,
    *,
    out: str | None = None,
    include_operator: bool = False,
    include_local: bool = False,
    workspace_root: str | None = None,
) -> dict[str, object]:
    """The bundle for the record `ref` resolves to; written to `out` when given.

    The checkout that classifies local paths is `workspace_root`, else the Git
    toplevel; it is passed on explicitly and never read again downstream.
    """
    resolution = resolve_mod.resolve(ref, workspace_root=workspace_root)
    if resolution.record is None or resolution.outcome not in _EXPORTABLE:
        raise fromargs.CliError(
            f"export-unresolved: {ref!r} resolved to {resolution.outcome.value}, "
            + f"not to one current record ({resolution.detail or 'no detail'})",
            exit_code=2,
        )
    checkout = paths.git_toplevel() if workspace_root is None else Path(workspace_root).resolve()
    try:
        bundle = transfer_mod.export_bundle(
            resolution.record,
            checkout=checkout,
            include_operator=include_operator,
            include_local=include_local,
        )
    except transfer_mod.TransferError as exc:
        raise fromargs.CliError(str(exc), exit_code=2) from exc
    summary: dict[str, object] = {
        "work_id": resolution.record.work_id,
        "revision_id": resolution.record.revision_id,
        "record_digest": bundle["record_digest"],
        "bundle_digest": bundle["bundle_digest"],
    }
    if out is None:
        return {**summary, "out": None, "bundle": bundle}
    target = Path(out).expanduser()
    try:
        storage.write_atomic(target, canonical.canonical_bytes(bundle) + b"\n")
    except OSError as exc:
        raise fromargs.CliError(
            f"bundle-unwritable: {target} cannot be written: {exc}", exit_code=2
        ) from exc
    return {**summary, "out": str(target)}


def _read_bundle(path: str) -> bytes:
    source = Path(path).expanduser()
    try:
        with source.open("rb") as handle:
            return handle.read(transfer_mod.MAX_BUNDLE_BYTES + 1)
    except OSError as exc:
        raise fromargs.CliError(
            f"bundle-unreadable: {source} cannot be read: {exc}", exit_code=2
        ) from exc


def run_import(
    bundle: str,
    *,
    slug: str | None = None,
    note_dir: str | None = None,
    no_note: bool = False,
    workspace_root: str | None = None,
) -> dict[str, object]:
    """Verify `bundle`, then write it as the genesis of a fork child.

    `workspace_root`, else the Git toplevel, is the checkout that digests links.
    """
    raw = _read_bundle(bundle)
    try:
        parsed = transfer_mod.parse_bundle(raw)
        _ = transfer_mod.target_store(parsed[0], slug, paths.project_corpus_root())
    except transfer_mod.TransferError as exc:
        raise fromargs.CliError(str(exc), exit_code=2) from exc
    record = parsed[0]
    name = record.work_id if slug is None else slug
    directory = note_dir_for(note_dir=note_dir, no_note=no_note)
    target = None if directory is None else directory / f"{name}.md"
    if directory is not None:
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise fromargs.CliError(
                f"note-unwritable: note directory {directory} cannot be created: {exc}",
                exit_code=2,
            ) from exc
    captured_at = _dt.datetime.now(_dt.timezone.utc).strftime(
        checkpoint_mod.TIMESTAMP_FORMAT
    )
    checkout = paths.resolve_repo_root(workspace_root)
    try:
        outcome = transfer_mod.import_bundle(
            parsed,
            slug=slug,
            corpus_root=paths.project_corpus_root(),
            checkout=checkout,
            session_provenance=SessionProvenance(
                harness=None, session_id=None, captured_at=captured_at
            ),
            durability=(
                Durability.CANONICAL_LOCAL if target is None else Durability.REPO_SNAPSHOT
            ),
            finalize=None if target is None else mirror_finalizer(target),
        )
    except MirrorError as exc:
        raise fromargs.CliError(f"note-unwritable: {exc}", exit_code=2) from exc
    except transfer_mod.TransferError as exc:
        raise fromargs.CliError(str(exc), exit_code=2) from exc
    except (commit_mod.CommitError, storage.StorageError) as exc:
        raise refusal_for(exc) from exc
    warnings = [
        f"skipped-local-link: {text} needs the author's machine" for text in outcome.skipped_local
    ] + [
        f"skipped-unresolvable-link: {text} cannot be digested on this machine"
        for text in outcome.skipped_unresolvable
    ]
    return {
        **result_payload(
            outcome.result, None if target is None else str(target), warnings=warnings
        ),
        "edges": [records.unstructure(edge) for edge in outcome.result.record.edges],
    }
