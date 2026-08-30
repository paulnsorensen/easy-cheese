"""CLI wrapper for shared/scripts/handoff.py.

Exposes render / parse / dispatch as subcommands so non-Python skills can
shell out for the canonical preamble logic without re-implementing it.

    python3 shared/scripts/handoff_cli.py render \\
        --status ok --next cure --artifact .cheese/age/demo.md \\
        --orientation "Reviewed the retry path."

    python3 shared/scripts/handoff_cli.py parse --file .cheese/age/demo.md
    python3 shared/scripts/handoff_cli.py dispatch "/age demo --hard"
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import TextIO, cast

from easy_cheese.shared import cli, handoff


def _parse_status_arg(raw: str) -> tuple[str, str | None]:
    if raw == "ok":
        return "ok", None
    if raw.startswith("halt:"):
        reason = raw[len("halt:"):].strip()
        if not reason:
            raise cli.CliError("halt status requires a reason after 'halt:'")
        return "halt", reason
    raise cli.CliError(f"status must be 'ok' or 'halt: <reason>', got {raw!r}")


def _cmd_render(args: argparse.Namespace) -> None:
    status, halt_reason = _parse_status_arg(cast(str, args.status))
    next_skill = cast(str, args.next_skill)
    artifact = cast(str, args.artifact)
    slug = handoff.HandoffSlug(
        status=status,
        halt_reason=halt_reason,
        next_skill=next_skill.lstrip("/"),
        artifact=artifact or None,
        orientation=cast(str, args.orientation),
        taste_test=cast("str | None", args.taste_test),
        durable_flags=cast("str | None", args.durable_flags),
    )
    try:
        print(handoff.render_handoff_slug(slug), file=cast("TextIO", args.stdout))
    except ValueError as exc:
        raise cli.CliError(str(exc)) from exc


def _cmd_parse(args: argparse.Namespace) -> None:
    file_arg = cast(str, args.file)
    path = Path(file_arg)
    if not path.is_file():
        raise cli.CliError(f"file not found: {file_arg}")
    try:
        slug = handoff.parse_handoff_slug(path.read_text(encoding="utf-8"))
    except handoff.HandoffParseError as exc:
        raise cli.CliError(str(exc)) from exc
    cli.emit(
        {
            "status": slug.status,
            "halt_reason": slug.halt_reason,
            "next_skill": slug.next_skill,
            "artifact": slug.artifact,
            "orientation": slug.orientation,
            "taste_test": slug.taste_test,
            "durable_flags": slug.durable_flags,
        },
        stdout=cast("TextIO", args.stdout),
    )


def _cmd_dispatch(args: argparse.Namespace) -> None:
    try:
        skill, dispatch_args = handoff.parse_skill_dispatch(cast(str, args.command))
    except ValueError as exc:
        raise cli.CliError(str(exc)) from exc
    cli.emit({"skill": skill, "args": dispatch_args}, stdout=cast("TextIO", args.stdout))


def _setup(parser: argparse.ArgumentParser) -> None:
    parser.description = "Render, parse, and dispatch handoff preambles."
    sub = parser.add_subparsers(dest="cmd", required=True)

    render = sub.add_parser("render", help="render a 4-line handoff preamble")
    _ = render.add_argument("--status", required=True, help="'ok' or 'halt: <reason>'")
    _ = render.add_argument("--next", dest="next_skill", required=True, help="next skill name (or 'done')")
    _ = render.add_argument("--artifact", default="", help="path to prior report; empty if none")
    _ = render.add_argument("--orientation", required=True, help="one-line orientation")
    _ = render.add_argument("--taste-test", default=None, help="optional taste_test: keyed line")
    _ = render.add_argument("--durable-flags", default=None, help="optional durable_flags: keyed line")
    render.set_defaults(func=_cmd_render)

    parse = sub.add_parser("parse", help="parse a handoff preamble from a file")
    _ = parse.add_argument("--file", required=True, help="path to file containing the preamble")
    parse.set_defaults(func=_cmd_parse)

    dispatch = sub.add_parser("dispatch", help="split a '/skill arg --flag' command")
    _ = dispatch.add_argument("command", help="full dispatch string, e.g. '/age slug --hard'")
    dispatch.set_defaults(func=_cmd_dispatch)


def main(argv: list[str]) -> int:
    return cli.run(_setup, argv=argv)


if __name__ == "__main__":
    raise SystemExit(cli.run(_setup))
