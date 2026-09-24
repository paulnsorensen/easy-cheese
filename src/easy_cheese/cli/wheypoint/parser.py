"""The argv grammar for each of the nine wheypoint commands."""

from __future__ import annotations

from easy_cheese.cli.envelope import Parser
from easy_cheese.shared.wheypoint import legacy as legacy_mod


def parser_for(command: str) -> Parser:
    parser = Parser(prog=f"wheypoint.pyz {command}")
    if command == "checkpoint":
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
    elif command in ("list", "log"):
        _ = parser.add_argument(
            "--corpus-root",
            dest="corpus_root",
            default=None,
            help="the per-project corpus root (default: the project's own corpus)",
        )
        if command == "log":
            _ = parser.add_argument("--work-id", required=True, dest="work_id")
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
            "--ref",
            required=True,
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
    elif command == "show":
        _ = parser.add_argument("--work-id", required=True, dest="work_id")
    elif command == "lint":
        _ = parser.add_argument("path", help="path to a rendered projection document")
    return parser
