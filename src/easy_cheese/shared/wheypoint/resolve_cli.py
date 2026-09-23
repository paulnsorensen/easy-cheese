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

import json
from typing import Annotated

from cyclopts import App, Parameter
import sys
import traceback
from collections.abc import Mapping, Sequence
from typing import TextIO, cast

from attrs import AttrsInstance
from easy_cheese.shared import cli, handoff
from easy_cheese.shared.wheypoint import lint as lint_mod
from easy_cheese.shared.wheypoint import records
from easy_cheese.shared.wheypoint import resolve as resolve_mod

COMMAND = "wheypoint-resolve"
EXIT_OK = 0
EXIT_REFUSED = 1
EXIT_USAGE = 2
EXIT_INTERNAL = 3


def _resolve_app() -> App:
    app = App(name=COMMAND)

    def command(
        ref: Annotated[str, Parameter(name="--ref", help="an absolute projection path, a work id, or a slug")],
        corpus_root: Annotated[str | None, Parameter(name="--corpus-root")] = None,
    ) -> tuple[str, str | None]:
        return ref, corpus_root

    _ = app.default(command)
    return app


resolve_app = _resolve_app()


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


def emit(stdout: TextIO, payload: dict[str, object]) -> None:
    _ = stdout.write(json.dumps(payload, sort_keys=True) + "\n")


def refuse(
    stdout: TextIO,
    command: str,
    code: str,
    message: str,
    status: int,
    extra: dict[str, object] | None = None,
) -> int:
    emit(
        stdout,
        {
            "ok": False,
            "command": command,
            "error": {"code": code, "message": message, **(extra or {})},
        },
    )
    return status


def main(
    argv: Sequence[str] | None = None,
    *,
    stdout: TextIO | None = None,
) -> int:
    """Resolve ``--ref`` and emit the native Wheypoint JSON shape."""
    argv2 = list(sys.argv[1:] if argv is None else argv)
    stdout2 = sys.stdout if stdout is None else stdout
    try:
        canonical = cli.repair_argv(resolve_app, argv2)
        raw_result: object = cast(
            object,
            resolve_app(
                canonical,
                print_error=False,
                exit_on_error=False,
                help_on_error=False,
                result_action="return_value",
            ),
        )
        if raw_result is None:
            return EXIT_OK
        ref, corpus_root = cast(tuple[str, str | None], raw_result)
    except Exception as exc:
        return refuse(stdout2, COMMAND, "usage", str(exc), EXIT_USAGE)
    try:
        payload = resolve_payload(
            resolve_mod.resolve(ref, corpus_root=corpus_root), ref
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
