"""Derive a kebab-case slug + ``.cheese/specs/<slug>.md`` path from task text.

CLI:

    python3 shared/scripts/slugify.py from-task --task "Tail trailing newline"
    -> {"slug": "tail-trailing-newline", "path": ".cheese/specs/tail-trailing-newline.md"}

Slug rules match ``paths.slugify``: lowercase, kebab-case, stopwords dropped,
capped at 5 words. Collision with an existing ``.cheese/specs/<slug>.md``
exits 2 via ``cli.CliError``.
"""

from __future__ import annotations

from typing import Annotated
import sys

from cyclopts import App, Parameter


from easy_cheese.shared import cli, paths


LEAVES = ("from-task",)

def _from_task(*, task: str, root: str = ".cheese", json_mode: Annotated[bool, Parameter(name="--json")] = False) -> int:
    slug = paths.slugify(task, max_words=5)
    if not slug:
        raise cli.CliError(f"task text {task!r} produced an empty slug; provide more words")
    err = paths.validate_slug(slug)
    if err is not None:
        raise cli.CliError(err)
    artifact = paths.artifact_path("specs", slug, root=root)
    if artifact.exists():
        raise cli.CliError(f"{artifact} already exists; rephrase --task for a distinct slug or remove the existing spec")
    cli.emit({"slug": slug, "path": str(artifact)}, json_mode=json_mode)
    return 0

app = App(name="slugify")
_ = app.command(_from_task, name="from-task")

def main(argv: list[str]) -> int:
    return cli.run(app, argv=argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
