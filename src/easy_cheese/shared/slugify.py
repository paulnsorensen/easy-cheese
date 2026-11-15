"""Derive a kebab-case slug + ``.cheese/specs/<slug>.md`` path from task text.

CLI:

    python3 shared/scripts/slugify.py from-task --task "Tail trailing newline"
    -> {"slug": "tail-trailing-newline", "path": ".cheese/specs/tail-trailing-newline.md"}

Slug rules match ``paths.slugify``: lowercase, kebab-case, stopwords dropped,
capped at 5 words. Collision with an existing ``.cheese/specs/<slug>.md``
exits 2 via ``fromargs.CliError``.
"""

from __future__ import annotations

import fromargs

from easy_cheese.shared import paths

LEAVES = ("from-task",)


def from_task(*, task: str, root: str = ".cheese") -> dict[str, str]:
    """Derive slug+path from task text.

    Parameters
    ----------
    task
        Free-form task description.
    root
        Root directory for the artifact path.
    """
    slug = paths.slugify(task, max_words=5)
    if not slug:
        raise fromargs.CliError(
            f"task text {task!r} produced an empty slug; provide more words"
        )
    err = paths.validate_slug(slug)
    if err is not None:
        raise fromargs.CliError(err)
    artifact = paths.artifact_path("specs", slug, root=root)
    if artifact.exists():
        raise fromargs.CliError(
            f"{artifact} already exists; rephrase --task for a distinct slug "
            + "or remove the existing spec"
        )
    return {"slug": slug, "path": str(artifact)}


def build_app() -> fromargs.App:
    app = fromargs.App(
        "slugify",
        help="Derive a slug + .cheese/specs/<slug>.md path from task text.",
        help_formatter="plain",
    )
    _ = app.command(from_task, name="from-task")
    return app


def main(argv: list[str] | None = None) -> int:
    return build_app().run(argv)


if __name__ == "__main__":
    raise SystemExit(main())