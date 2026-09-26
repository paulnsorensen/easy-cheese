"""JSON command adapter for the shared Wheypoint resolver.

Phase bundles expose this adapter as ``wheypoint-resolve`` so each phase can
resolve its own entry reference without importing the Wheypoint skill bundle.
The resolver remains the single source of truth; this module is also the
single owner of the resolve payload's JSON projection, the usage exception
type, the argv parser, the JSON emitters, and the exit codes. The skill
bundle's ``wheypoint.py`` imports them rather than keeping a second copy,
adding only its own ``--legacy`` branch.

The parser is not routed through ``cli.run``: every reply here is one JSON
line on stdout under a four-code exit ladder (``ok``/``refused``/``usage``/
``internal``), which is not the envelope or the status contract ``cli.run``
emits.
"""

from __future__ import annotations

import sys
import traceback
from collections.abc import Mapping, Sequence
from typing import TextIO, cast

from attrs import AttrsInstance
from easy_cheese.cli import (
    EXIT_OK,
    EXIT_REFUSED,
    EXIT_USAGE,
    BadUsage,
    Parser,
    emit,
    refuse,
)
from easy_cheese.cli import EXIT_INTERNAL as EXIT_INTERNAL
from easy_cheese.shared import handoff
from easy_cheese.shared.wheypoint import lint as lint_mod
from easy_cheese.shared.wheypoint import records
from easy_cheese.shared.wheypoint import resolve as resolve_mod

COMMAND = "wheypoint-resolve"


def _parser() -> Parser:
    parser = Parser(prog=COMMAND)
    _ = parser.add_argument(
        "--ref",
        required=True,
        help="an absolute projection path, a work id, or a slug",
    )
    _ = parser.add_argument(
        "--corpus-root",
        dest="corpus_root",
        default=None,
        help="the corpus to resolve in; defaults to this project's XDG corpus",
    )
    _ = parser.add_argument(
        "--project",
        dest="project",
        default=None,
        help="resolve another project's corpus (corpus_home()/KEY)",
    )
    _ = parser.add_argument(
        "--workspace-root",
        dest="workspace_root",
        default=None,
        help="the owning repository checkout for cross-project continuation",
    )
    return parser


def findings_payload(
    findings: tuple[lint_mod.LintFinding, ...],
) -> list[dict[str, str]]:
    return [
        {"code": finding.code.value, "detail": finding.detail} for finding in findings
    ]


def maybe_payload(obj: object) -> dict[str, object] | None:
    return None if obj is None else records.unstructure(cast(AttrsInstance, obj))


def resolve_payload(resolution: resolve_mod.Resolution, ref: str) -> dict[str, object]:
    """Project a ``Resolution`` into the native Wheypoint JSON shape.

    Every outcome projects the same way, including ``error``: a reference that
    could not be interpreted is still an answer about the corpus, so the caller
    emits this payload with ``ok: false`` rather than the ``{code, message}``
    shape usage and internal errors use. ``resolve_status`` picks the code.
    """
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
    }


def resolve_status(payload: Mapping[str, object]) -> int:
    """The exit status a resolve payload carries: only ``error`` refuses."""
    if payload.get("outcome") == resolve_mod.ResolutionOutcome.ERROR.value:
        return EXIT_REFUSED
    return EXIT_OK


def main(
    argv: Sequence[str] | None = None,
    *,
    stdout: TextIO | None = None,
) -> int:
    """Resolve ``--ref`` and emit the native Wheypoint JSON shape."""
    argv2 = list(sys.argv[1:] if argv is None else argv)
    stdout2 = sys.stdout if stdout is None else stdout
    try:
        args = _parser().parse_args(argv2)
    except BadUsage as exc:
        return refuse(stdout2, COMMAND, "usage", str(exc), EXIT_USAGE)
    try:
        ref = cast(str, args.ref)
        corpus_root = cast("str | None", args.corpus_root)
        project_key = cast("str | None", args.project)
        workspace_root = cast("str | None", args.workspace_root)
        payload = resolve_payload(
            resolve_mod.resolve(
                ref,
                corpus_root=corpus_root,
                project_key=project_key,
                workspace_root=workspace_root,
                require_workspace=project_key is not None,
            ),
            ref,
        )
    except Exception as exc:  # noqa: BLE001 - a traceback is not a reply
        traceback.print_exc(file=sys.stderr)
        return refuse(
            stdout2,
            COMMAND,
            "internal-error",
            f"{type(exc).__name__}: {exc}",
            EXIT_INTERNAL,
        )
    status = resolve_status(payload)
    emit(stdout2, {"ok": status == EXIT_OK, "command": COMMAND, **payload})
    return status


if __name__ == "__main__":
    sys.exit(main())
