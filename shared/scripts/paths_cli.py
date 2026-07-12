"""CLI wrapper around shared/scripts/paths.py — slugify, validate, existing, resolve, list.

Subcommands:

    paths_cli.py slugify --text "Tail trailing newline"
    -> tail-trailing-newline

    paths_cli.py validate --slug fix-auth-retry
    -> (exit 0)

    paths_cli.py existing --slug demo --phase age --json
    -> ["<root>/age/demo.md"]

    paths_cli.py existing --slug demo --phase specs --json
    -> ["<xdg-corpus>/specs/demo.md"]   (durable phases route to the XDG corpus)

    paths_cli.py resolve --slug demo
    -> {"matches": [...], "fallback_roots": [...]}

    paths_cli.py list --phase specs --json
    -> [{"slug": "demo", "path": "<xdg-corpus>/specs/demo.md"}, ...]

Stdlib-only; delegates all rules to paths.py so the regex + phase list stay
single-source.
"""
from __future__ import annotations

import argparse

import cli
import paths


def _cmd_slugify(args: argparse.Namespace) -> None:
    if not args.text:
        raise cli.CliError("slugify requires non-empty --text")
    slug = paths.slugify(args.text)
    if not slug:
        raise cli.CliError(f"slugify produced an empty slug from {args.text!r}")
    cli.emit(slug, json_mode=args.json_mode)


def _cmd_validate(args: argparse.Namespace) -> None:
    err = paths.validate_slug(args.slug)
    if err is not None:
        raise cli.CliError(err)


def _cmd_existing(args: argparse.Namespace) -> None:
    err = paths.validate_slug(args.slug)
    if err is not None:
        raise cli.CliError(err)
    if args.phase not in paths.PHASES:
        raise cli.CliError(
            f"unknown phase {args.phase!r}; expected one of {sorted(paths.PHASES)}"
        )
    found = paths.existing_artifacts(args.slug, root=args.root, phases=(args.phase,))
    items = [str(p) for p in found.values()]
    cli.emit(items, limit=args.limit, full=args.full, json_mode=args.json_mode)


def _cmd_list(args: argparse.Namespace) -> None:
    if args.phase not in paths.PHASES:
        raise cli.CliError(
            f"unknown phase {args.phase!r}; expected one of {sorted(paths.PHASES)}"
        )
    try:
        entries = paths.list_artifacts(args.phase, repo_root=args.repo_root)
    except ValueError as exc:
        raise cli.CliError(str(exc)) from exc
    if args.json_mode:
        shown = entries if (args.full or args.limit is None) else entries[: args.limit]
        cli.emit(shown, json_mode=True)
    else:
        cli.emit([e["slug"] for e in entries], limit=args.limit, full=args.full)


def _cmd_resolve(args: argparse.Namespace) -> None:
    err = paths.validate_slug(args.slug)
    if err is not None:
        raise cli.CliError(err)
    try:
        result = paths.resolve_slug(
            args.slug, phase_hint=args.phase, repo_root=args.repo_root
        )
    except ValueError as exc:
        raise cli.CliError(str(exc)) from exc
    cli.emit(result, json_mode=True)


def _setup(parser: argparse.ArgumentParser) -> None:
    sub = parser.add_subparsers(dest="cmd", required=True)

    slugify = sub.add_parser("slugify", help="kebab-slug arbitrary text")
    slugify.add_argument("--text", required=True, help="source text to slugify")
    slugify.set_defaults(func=_cmd_slugify)

    validate = sub.add_parser("validate", help="exit 0 if slug is valid kebab-case")
    validate.add_argument("--slug", required=True)
    validate.set_defaults(func=_cmd_validate)

    existing = sub.add_parser(
        "existing",
        help="list .cheese/<phase>/<slug>.md artifacts present on disk",
    )
    existing.add_argument("--slug", required=True)
    existing.add_argument("--phase", required=True, help=f"one of {sorted(paths.PHASES)}")
    existing.add_argument(
        "--root",
        default=None,
        help="artifact root override (default: phase-appropriate -- XDG corpus for durable phases, .cheese/ otherwise)",
    )
    existing.add_argument("--limit", type=int, default=None, help="cap list length")
    existing.set_defaults(func=_cmd_existing)

    resolve = sub.add_parser(
        "resolve",
        help="resolve a slug to absolute artifact path(s) across all phases",
    )
    resolve.add_argument("--slug", required=True)
    resolve.add_argument(
        "--phase", default=None, help="restrict the search to this phase/aux token"
    )
    resolve.add_argument(
        "--repo-root",
        dest="repo_root",
        default=None,
        help="repo root for .cheese/ (default: git toplevel or cwd)",
    )
    resolve.set_defaults(func=_cmd_resolve)

    list_cmd = sub.add_parser(
        "list",
        help="enumerate slugs (and paths) for a phase's artifacts on disk",
    )
    list_cmd.add_argument("--phase", required=True, help=f"one of {sorted(paths.PHASES)}")
    list_cmd.add_argument(
        "--repo-root",
        dest="repo_root",
        default=None,
        help="repo root for .cheese/ (default: git toplevel or cwd)",
    )
    list_cmd.add_argument("--limit", type=int, default=None, help="cap list length")
    list_cmd.set_defaults(func=_cmd_list)


if __name__ == "__main__":
    cli.run(_setup)
