"""JSON command adapter for the shared Wheypoint resolver.

Phase bundles expose this adapter as ``wheypoint-resolve`` so each phase can
resolve its own entry reference without importing the Wheypoint skill bundle.
The resolver remains the single source of truth; this module is also the
single owner of the resolve payload's JSON projection. The skill bundle's
``wheypoint`` package imports ``resolve_payload``, ``findings_payload``, and
``maybe_payload`` rather than keeping a second copy, adding only its own
``--legacy`` branch.

Every reply here is one JSON document on stdout under the fromargs contract:
success prints the payload, and a refusal is one JSON line on stderr,
``{"error": ..., "exit_code": ...}``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TextIO, cast

import fromargs
from attrs import AttrsInstance

from easy_cheese.shared import handoff, paths
from easy_cheese.shared.wheypoint import edges, fork_reconcile, milknado_bridge
from easy_cheese.shared.wheypoint import lint as lint_mod
from easy_cheese.shared.wheypoint import records
from easy_cheese.shared.wheypoint import resolve as resolve_mod

COMMAND = "wheypoint-resolve"


def findings_payload(
    findings: tuple[lint_mod.LintFinding, ...],
) -> list[dict[str, str]]:
    return [
        {"code": finding.code.value, "detail": finding.detail} for finding in findings
    ]


def maybe_payload(obj: object) -> dict[str, object] | None:
    return None if obj is None else records.unstructure(cast(AttrsInstance, obj))


def resolve_payload(
    resolution: resolve_mod.Resolution,
    ref: str,
    *,
    workspace_root: Path | str | None = None,
) -> dict[str, object]:
    """Project a ``Resolution`` into the native Wheypoint JSON shape.

    Every outcome projects the same way, including ``error``: a reference that
    could not be interpreted is still an answer about the corpus, so the caller
    emits this payload with ``ok: false`` rather than the ``{code, message}``
    shape usage and internal errors use. ``raise_if_error`` picks the code.

    ``bridge`` reports the milknado binding of a resolved record, checked
    against ``workspace_root`` -- the same owning checkout `resolve` used, or
    the working directory when the caller resolved with none; it is ``None``
    when no record resolved. It never changes ``dispatchable``.
    """
    record = resolution.record
    bridge = (
        None
        if record is None
        else milknado_bridge.payload(
            milknado_bridge.bind(
                record, repo_root=paths.resolve_repo_root(workspace_root)
            )
        )
    )
    return {
        "ref": ref,
        "outcome": resolution.outcome.value,
        "dispatchable": resolution.dispatchable,
        "source": None if resolution.source is None else resolution.source.value,
        "work_id": resolution.work_id,
        "record": maybe_payload(resolution.record),
        "projection": maybe_payload(resolution.projection),
        "findings": findings_payload(resolution.findings),
        "matches": list(resolution.matches),
        "searched": list(resolution.searched),
        "legacy_note": (
            None if resolution.legacy_note is None else str(resolution.legacy_note)
        ),
        "legacy_slug": maybe_payload(resolution.legacy_slug),
        "phase_slug": (
            None
            if resolution.phase_slug is None
            else handoff.slug_payload(resolution.phase_slug)
        ),
        "detail": resolution.detail,
        # Link entries carry their edge kind; fork entries carry `"fork"`.
        "pending": [
            *edges.pending_payload(resolution.pending),
            *fork_reconcile.fork_payload(resolution.pending_forks),
        ],
        "bridge": bridge,
    }


def raise_if_error(payload: Mapping[str, object]) -> None:
    """Raise a `CliError` when `payload`'s outcome is `error`; the only refusing outcome."""
    if payload.get("outcome") == resolve_mod.ResolutionOutcome.ERROR.value:
        raise fromargs.CliError(f"error: {payload.get('detail')}", exit_code=1)


def resolve(
    *,
    ref: str,
    corpus_root: str | None = None,
    project: str | None = None,
    workspace_root: str | None = None,
) -> dict[str, object]:
    """Resolve `--ref` and return the native Wheypoint JSON shape.

    Parameters
    ----------
    ref
        an absolute projection path, a work id, or a slug
    corpus_root
        the corpus to resolve in; defaults to this project's XDG corpus
    project
        resolve another project's corpus (corpus_home()/KEY)
    workspace_root
        the owning repository checkout for cross-project continuation
    """
    payload = resolve_payload(
        resolve_mod.resolve(
            ref,
            corpus_root=corpus_root,
            project_key=project,
            workspace_root=workspace_root,
            require_workspace=project is not None,
        ),
        ref,
        workspace_root=workspace_root,
    )
    raise_if_error(payload)
    return {"ok": True, "command": COMMAND, **payload}


def build_app() -> fromargs.App:
    return fromargs.App(
        COMMAND,
        help="Resolve a slug, work id, or path to the current record.",
        help_formatter="plain",
        default_command=resolve,
    )


def main(
    argv: Sequence[str] | None = None,
    *,
    stdout: TextIO | None = None,
) -> int:
    """Resolve `--ref` and print the native Wheypoint JSON shape."""
    return build_app().run(argv, stdout=stdout)


if __name__ == "__main__":
    import sys

    sys.exit(main())