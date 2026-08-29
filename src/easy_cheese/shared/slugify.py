"""Derive a kebab-case slug + ``.cheese/specs/<slug>.md`` path from task text.

CLI:

    python3 shared/scripts/slugify.py from-task --task "Tail trailing newline"
    -> {"slug": "tail-trailing-newline", "path": ".cheese/specs/tail-trailing-newline.md"}

Slug rules match ``paths.slugify``: lowercase, kebab-case, stopwords dropped,
capped at 5 words. Collision with an existing ``.cheese/specs/<slug>.md``
exits 2 via ``cli.CliError``.
"""

from __future__ import annotations

import argparse
from typing import TextIO, cast

from easy_cheese.shared import cli, paths


def _from_task(args: argparse.Namespace) -> None:
    task = cast(str, args.task)
    slug = paths.slugify(task, max_words=5)
    if not slug:
        raise cli.CliError(
            f"task text {task!r} produced an empty slug; provide more words"
        )
    err = paths.validate_slug(slug)
    if err is not None:
        raise cli.CliError(err)
    artifact = paths.artifact_path("specs", slug, root=cast(str, args.root))
    if artifact.exists():
        raise cli.CliError(
            f"{artifact} already exists; rephrase --task for a distinct slug "
            + "or remove the existing spec"
        )
    cli.emit(
        {"slug": slug, "path": str(artifact)},
        json_mode=cast(bool, args.json_mode),
        stdout=cast(TextIO, args.stdout),
    )


def _setup(parser: argparse.ArgumentParser) -> None:
    parser.description = "Derive a slug + .cheese/specs/<slug>.md path from task text."
    sub = parser.add_subparsers(dest="cmd")
    from_task = sub.add_parser("from-task", help="derive slug+path from task text")
    _ = from_task.add_argument("--task", required=True, help="free-form task description")
    _ = from_task.add_argument(
        "--root",
        default=".cheese",
        help="root directory for artifact path (default: .cheese)",
    )
    from_task.set_defaults(func=_from_task)


def main(argv: list[str]) -> int:
    return cli.run(_setup, argv=argv)


if __name__ == "__main__":
    raise SystemExit(cli.run(_setup))
