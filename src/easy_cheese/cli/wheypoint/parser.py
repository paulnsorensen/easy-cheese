"""The argv grammar for each of the nine wheypoint commands."""

from __future__ import annotations

import argparse
import datetime as _dt
from typing import cast

from easy_cheese.cli.envelope import BadUsage, Parser
from easy_cheese.shared.wheypoint import legacy as legacy_mod

_POSITIONAL_REF = {
    "show": ("work_id_pos", "work_id"),
    "log": ("work_id_pos", "work_id"),
    "resolve": ("ref_pos", "ref"),
}


def _project_key(value: str) -> str:
    """Reject anything that is not one filesystem path segment (G9, G10)."""
    if not value or value in (".", "..") or "/" in value or "\\" in value:
        raise argparse.ArgumentTypeError(
            f"--project must be one path segment, not {value!r}"
        )
    return value


def _iso_date(value: str) -> str:
    """Accept only a `YYYY-MM-DD` date, so a bad `--since` is a usage error."""
    try:
        _ = _dt.date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"--since must be a YYYY-MM-DD date, not {value!r}"
        ) from exc
    return value


def _positive_int(value: str) -> int:
    """Accept only a whole number of at least 1 for `--limit`."""
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"--limit must be a whole number, not {value!r}"
        ) from exc
    if number < 1:
        raise argparse.ArgumentTypeError(f"--limit must be at least 1, not {number}")
    return number


def normalize_positional_ref(command: str, args: argparse.Namespace) -> None:
    """Merge a G5 positional ref with its aliasing flag; refuse a conflict.

    Raised as `BadUsage` so the caller's parse-phase `try` reports it the same
    way argparse itself does -- exit 2, `code: usage` (AC-1).
    """
    spec = _POSITIONAL_REF.get(command)
    if spec is None:
        return
    positional_name, flag_name = spec
    pos_val = cast("str | None", getattr(args, positional_name, None))
    flag_val = cast("str | None", getattr(args, flag_name, None))
    if pos_val is not None and flag_val is not None and pos_val != flag_val:
        raise BadUsage(
            f"{command}: {flag_name} was given as both a positional argument "
            + f"({pos_val!r}) and --{flag_name.replace('_', '-')} ({flag_val!r})"
        )
    value = pos_val if pos_val is not None else flag_val
    if value is None:
        raise BadUsage(f"{command}: a {flag_name.replace('_', '-')} is required")
    setattr(args, flag_name, value)


def parser_for(command: str) -> Parser:
    parser = Parser(prog=f"wheypoint.pyz {command}")
    if command == "checkpoint":
        _ = parser.add_argument(
            "intent",
            nargs="?",
            default=None,
            metavar="INTENT",
            help="path to a JSON intent file, or - for stdin (default: stdin)",
        )
        _ = parser.add_argument(
            "--compacted",
            dest="compacted",
            default=None,
            metavar="PROOF_JSON",
            help=(
                "path to a caller-authored CompactionRecord proving the session "
                + "rehydrated from the current revision before writing"
            ),
        )
        _ = parser.add_argument(
            "--note-dir",
            dest="note_dir",
            default=None,
            help=(
                "directory the readable projection is mirrored into "
                + f"(default: <git toplevel>/{'/'.join(legacy_mod.NOTES_DIR_PARTS)})"
            ),
        )
        _ = parser.add_argument(
            "--no-note",
            dest="no_note",
            action="store_true",
            help="write no mirror; the checkpoint stays canonical-local",
        )
    elif command == "schema":
        _ = parser.add_argument(
            "slug", help="a registered contract slug, e.g. checkpoint-intent"
        )
    elif command == "validate":
        _ = parser.add_argument(
            "intent",
            nargs="?",
            default=None,
            metavar="INTENT",
            help="path to a JSON intent file, or - for stdin (default: stdin)",
        )
    elif command == "list":
        _ = parser.add_argument(
            "--corpus-root",
            dest="corpus_root",
            default=None,
            help="the per-project corpus root (default: the project's own corpus)",
        )
        _ = parser.add_argument(
            "--scope",
            choices=("project", "machine"),
            default="project",
            help="this project's worktrees (default), or the whole machine",
        )
        _ = parser.add_argument(
            "--project",
            dest="project",
            action="append",
            default=None,
            type=_project_key,
            help="limit hits to this project key (repeatable; implies --scope machine)",
        )
        _ = parser.add_argument(
            "--root",
            dest="root",
            action="append",
            default=None,
            help="an extra machine search root (repeatable)",
        )
        _ = parser.add_argument(
            "--grep", default=None, help="case-insensitive substring filter"
        )
        _ = parser.add_argument("--status", default=None, help="filter by status")
        _ = parser.add_argument(
            "--next", dest="next", default=None, help="filter by next move"
        )
        _ = parser.add_argument(
            "--source",
            choices=("store", "note"),
            default=None,
            help="filter by hit source",
        )
        _ = parser.add_argument(
            "--since",
            type=_iso_date,
            default=None,
            help="filter to YYYY-MM-DD or later",
        )
        _ = parser.add_argument(
            "--limit", type=_positive_int, default=None, help="cap the hit count"
        )
        _ = parser.add_argument(
            "--mirrors", action="store_true", help="show notes that mirror a store hit"
        )
    elif command == "log":
        _ = parser.add_argument(
            "--corpus-root",
            dest="corpus_root",
            default=None,
            help="the per-project corpus root (default: the project's own corpus)",
        )
        _ = parser.add_argument(
            "work_id_pos",
            nargs="?",
            metavar="WORK_ID",
            help="the work id (positional form of --work-id)",
        )
        _ = parser.add_argument("--work-id", dest="work_id", default=None)
        _ = parser.add_argument(
            "--project",
            dest="project",
            default=None,
            type=_project_key,
            help="read another project's corpus (corpus_home()/KEY)",
        )
    elif command == "turns":
        _ = parser.add_argument(
            "--transcript", default=None, help="path to a session .jsonl transcript"
        )
        _ = parser.add_argument(
            "--session",
            default=None,
            help="session id under the derived projects directory",
        )
    elif command == "resolve":
        _ = parser.add_argument(
            "ref_pos",
            nargs="?",
            metavar="REF",
            help="an absolute projection path, a work id, or a slug (positional form of --ref)",
        )
        _ = parser.add_argument(
            "--ref",
            default=None,
            help="an absolute projection path, a work id, or a slug",
        )
        # A legacy note lives beside the repository, not in a corpus, so a
        # corpus root given with --legacy would be silently dropped.
        where = parser.add_mutually_exclusive_group()
        _ = where.add_argument(
            "--legacy",
            action="store_true",
            help="resolve a pre-kernel .cheese/notes/<slug>.md instead",
        )
        _ = where.add_argument(
            "--corpus-root",
            dest="corpus_root",
            default=None,
            help="the corpus to resolve in; defaults to this project's XDG corpus",
        )
        _ = where.add_argument(
            "--project",
            dest="project",
            default=None,
            type=_project_key,
            help="resolve in another project's corpus (corpus_home()/KEY)",
        )
    elif command == "show":
        _ = parser.add_argument(
            "work_id_pos",
            nargs="?",
            metavar="WORK_ID",
            help="the work id (positional form of --work-id)",
        )
        _ = parser.add_argument("--work-id", dest="work_id", default=None)
        _ = parser.add_argument(
            "--project",
            dest="project",
            default=None,
            type=_project_key,
            help="read another project's corpus (corpus_home()/KEY)",
        )
    elif command == "lint":
        _ = parser.add_argument("path", help="path to a rendered projection document")
    return parser
