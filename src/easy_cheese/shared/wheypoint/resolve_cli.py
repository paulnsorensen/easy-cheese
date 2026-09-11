"""JSON command adapter for the shared Wheypoint resolver.

Phase bundles expose this adapter as ``wheypoint-resolve`` so each phase can
resolve its own entry reference without importing the Wheypoint skill bundle.
The resolver remains the single source of truth; this module is also the
single owner of the resolve payload's JSON projection, the refusal/usage
exception types, the argv parser, and the exit codes. The skill bundle's own
``wheypoint.py::_run_resolve`` imports them rather than keeping a second copy,
adding only its own ``--legacy`` branch.
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from collections.abc import Sequence
from typing import NoReturn, TextIO, cast, override

from attrs import AttrsInstance
from easy_cheese.shared import handoff
from easy_cheese.shared.wheypoint import lint as lint_mod
from easy_cheese.shared.wheypoint import records
from easy_cheese.shared.wheypoint import resolve as resolve_mod

COMMAND = "wheypoint-resolve"
EXIT_OK = 0
EXIT_REFUSED = 1
EXIT_USAGE = 2
EXIT_INTERNAL = 3


class BadUsage(Exception):
    """argparse's complaint, raised instead of printed so it can be JSON."""


class Refusal(Exception):
    """A reference that could not be interpreted; carries the full JSON payload.

    The ``error`` outcome is still an answer about the corpus, not a bare
    refusal envelope, so the caller emits ``payload`` with ``ok: false``
    rather than the ``{code, message}`` shape usage and internal errors use.
    """

    def __init__(self, payload: dict[str, object]) -> None:
        super().__init__(
            str(payload.get("detail") or "reference could not be interpreted")
        )
        self.payload: dict[str, object] = payload


class Parser(argparse.ArgumentParser):
    @override
    def error(self, message: str) -> NoReturn:
        raise BadUsage(message)


def _parser() -> Parser:
    parser = Parser(prog=COMMAND)
    _ = parser.add_argument(
        "--ref",
        required=True,
        help="an absolute projection path, a work id, or a slug",
    )
    return parser


def _findings(findings: tuple[lint_mod.LintFinding, ...]) -> list[dict[str, str]]:
    return [
        {"code": finding.code.value, "detail": finding.detail} for finding in findings
    ]


def _maybe(obj: object) -> dict[str, object] | None:
    return None if obj is None else records.unstructure(cast(AttrsInstance, obj))


def resolve_payload(resolution: resolve_mod.Resolution, ref: str) -> dict[str, object]:
    """Project a ``Resolution`` into the native Wheypoint JSON shape.

    Raises `Refusal` carrying the full payload when the reference could not
    be interpreted at all, so both adapters emit the same ``outcome: "error"``
    answer instead of a bare refusal envelope.
    """
    payload: dict[str, object] = {
        "ref": ref,
        "outcome": resolution.outcome.value,
        "dispatchable": resolution.dispatchable,
        "source": None if resolution.source is None else resolution.source.value,
        "work_id": resolution.work_id,
        "record": _maybe(resolution.record),
        "projection": _maybe(resolution.projection),
        "findings": _findings(resolution.findings),
        "matches": list(resolution.matches),
        "searched": list(resolution.searched),
        "legacy_note": (
            None if resolution.legacy_note is None else str(resolution.legacy_note)
        ),
        "legacy_slug": _maybe(resolution.legacy_slug),
        "phase_slug": (
            None
            if resolution.phase_slug is None
            else handoff.slug_payload(resolution.phase_slug)
        ),
        "detail": resolution.detail,
    }
    if resolution.outcome is resolve_mod.ResolutionOutcome.ERROR:
        raise Refusal(payload)
    return payload


def _emit(stdout: TextIO, payload: dict[str, object]) -> None:
    _ = stdout.write(json.dumps(payload, sort_keys=True) + "\n")


def _refuse(
    stdout: TextIO,
    code: str,
    message: str,
    status: int,
) -> int:
    _emit(
        stdout,
        {
            "ok": False,
            "command": COMMAND,
            "error": {"code": code, "message": message},
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
        args = _parser().parse_args(argv2)
    except BadUsage as exc:
        return _refuse(stdout2, "usage", str(exc), EXIT_USAGE)
    try:
        ref = cast(str, args.ref)
        payload = resolve_payload(resolve_mod.resolve(ref), ref)
    except Refusal as exc:
        _emit(stdout2, {"ok": False, "command": COMMAND, **exc.payload})
        return EXIT_REFUSED
    except Exception as exc:  # noqa: BLE001 - a traceback is not a reply
        traceback.print_exc(file=sys.stderr)
        return _refuse(
            stdout2,
            "internal-error",
            f"{type(exc).__name__}: {exc}",
            EXIT_INTERNAL,
        )
    _emit(stdout2, {"ok": True, "command": COMMAND, **payload})
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
