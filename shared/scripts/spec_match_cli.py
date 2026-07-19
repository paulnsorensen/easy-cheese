"""CLI wrapper around shared/scripts/spec_match.py -- rank markdown candidates.

Subcommand:

    spec_match_cli.py rank --request "add retry" --dir .cheese/specs
    -> [{"path": "...", "score": 0.62, "tier": "high"}, ...]

Builds candidates from every ``*.md`` file directly under --dir: slug from the
YAML front matter's ``slug:`` field (falling back to the file stem), title
from the first ``# `` (H1) heading, and first_heading from the first line of
content under the first ``## `` (H2) heading -- for a rejection record that
line is the one-line description under ``## Direction``; for a spec it is the
opening line of its first section. Missing --dir (or no *.md files in it)
emits an empty JSON list -- the call sites skip silently in that case.

Stdlib-only; delegates scoring to spec_match.py so the ranking rule stays
single-source.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import cli
import spec_match

_FRONT_MATTER = re.compile(r"\A---\n(.*?\n)---\n", re.DOTALL)
_SLUG_FIELD = re.compile(r"^slug:\s*(.+?)\s*$", re.MULTILINE)
_H1 = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
_H2_BODY = re.compile(r"^##\s+.+?\s*\n+(.+?)\s*$", re.MULTILINE)


def _strip_front_matter(text: str) -> str:
    match = _FRONT_MATTER.match(text)
    return text[match.end():] if match else text


def _build_candidate(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    front_matter_match = _FRONT_MATTER.match(text)
    slug_match = _SLUG_FIELD.search(front_matter_match.group(1)) if front_matter_match else None
    slug = slug_match.group(1) if slug_match else path.stem

    body = _strip_front_matter(text)
    title_match = _H1.search(body)
    h2_match = _H2_BODY.search(body)
    return {
        "slug": slug,
        "title": title_match.group(1) if title_match else "",
        "first_heading": h2_match.group(1) if h2_match else "",
        "path": str(path),
    }


def _cmd_rank(args: argparse.Namespace) -> None:
    if not args.request:
        raise cli.CliError("rank requires non-empty --request")
    directory = Path(args.dir)
    if not directory.is_dir():
        cli.emit([], json_mode=True)
        return
    candidates = []
    for p in sorted(directory.glob("*.md")):
        try:
            candidates.append(_build_candidate(p))
        except OSError:
            continue
    results = spec_match.score_candidates(args.request, candidates)
    cli.emit(results, json_mode=True)


def _setup(parser: argparse.ArgumentParser) -> None:
    sub = parser.add_subparsers(dest="cmd", required=True)

    rank = sub.add_parser(
        "rank", help="rank *.md candidates in --dir against --request"
    )
    rank.add_argument("--request", required=True, help="incoming request text to match")
    rank.add_argument("--dir", required=True, help="directory to glob *.md candidates from")
    rank.set_defaults(func=_cmd_rank)


if __name__ == "__main__":
    cli.run(_setup)
