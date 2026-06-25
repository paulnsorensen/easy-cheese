"""CLI wrapper around shared/scripts/findings.py.

Two subcommands:

    python3 shared/scripts/findings_cli.py render-table --report <path>
    python3 shared/scripts/findings_cli.py parse-selection --report <path> --selection "<verb>"

Both honor `--full` / `--json` injected by cli.run.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import cli
import findings


def _load_findings(report_path: str) -> list:
    path = Path(report_path)
    if not path.is_file():
        raise cli.CliError(f"report not found: {report_path}")
    return findings.parse_findings_report(path.read_text(encoding="utf-8"))


def _cmd_render_table(args: argparse.Namespace) -> None:
    items = _load_findings(args.report)
    table = findings.render_selection_table(items)
    cli.emit(table, full=args.full, json_mode=args.json_mode)


def _cmd_parse_selection(args: argparse.Namespace) -> None:
    items = _load_findings(args.report)
    try:
        ids = findings.parse_selection(args.selection, items)
    except findings.SelectionError as exc:
        raise cli.CliError(str(exc))
    cli.emit(ids, full=args.full, json_mode=args.json_mode)


def _setup(parser: argparse.ArgumentParser) -> None:
    sub = parser.add_subparsers(dest="cmd", required=True)

    render = sub.add_parser("render-table", help="render selection table from an /age report")
    render.add_argument("--report", required=True, help="path to /age findings report")
    render.set_defaults(func=_cmd_render_table)

    select = sub.add_parser("parse-selection", help="resolve a selection verb to finding ids")
    select.add_argument("--report", required=True, help="path to /age findings report")
    select.add_argument("--selection", required=True, help="selection verb (e.g. 'all-high', '1,3', 'skip 2')")
    select.set_defaults(func=_cmd_parse_selection)


if __name__ == "__main__":
    cli.run(_setup)
