"""CLI wrapper for shared/scripts/gates.py.

Subcommands:
    classify  — call gates.classify_readiness with the 5 scoreboard booleans
                 and emit {press_status, readiness}.
"""
from __future__ import annotations

import argparse

import cli
import gates


def _cmd_classify(args: argparse.Namespace) -> None:
    try:
        verdict = gates.classify_readiness(
            hard_floor_met=args.hard_floor_met,
            has_open_level_1_or_2=args.has_open_level_1_or_2,
            has_open_level_3=args.has_open_level_3,
            has_open_level_4_or_5=args.has_open_level_4_or_5,
            any_spinning=args.any_spinning,
        )
    except (ValueError, TypeError) as exc:
        raise cli.CliError(str(exc)) from exc
    cli.emit(
        {"press_status": args.press_status, "readiness": verdict.value},
        json_mode=args.json_mode,
    )


def _setup(parser: argparse.ArgumentParser) -> None:
    sub = parser.add_subparsers(dest="cmd", required=True)

    classify = sub.add_parser("classify", help="map scoreboard booleans to a readiness verdict")
    classify.add_argument("--press-status", required=True, help="press-status label (echoed in output)")
    classify.add_argument("--hard-floor-met", action="store_true")
    classify.add_argument("--has-open-level-1-or-2", action="store_true")
    classify.add_argument("--has-open-level-3", action="store_true")
    classify.add_argument("--has-open-level-4-or-5", action="store_true")
    classify.add_argument("--any-spinning", action="store_true")
    classify.set_defaults(func=_cmd_classify)


if __name__ == "__main__":
    cli.run(_setup)
