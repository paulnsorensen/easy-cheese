"""Resolve durable and transient artifact paths for packaged skills.

Thin CLI wrapper over ``paths.py`` -- phase tables, the slug regex, and the
root-resolution math live there as the single source of truth. See
``paths.artifact_path`` / ``paths.project_corpus_root``.
"""

from __future__ import annotations

import sys
from typing import Annotated

from cyclopts import App, Parameter
from pathlib import Path
from easy_cheese.shared import cli

from easy_cheese.shared import paths


def artifact_path(phase: str, slug: str) -> Path:
    # paths.validate_slug reports an empty slug as "must be a non-empty
    # string"; this shim's long-standing CLI contract folds that case into
    # the same kebab-case message as every other invalid slug, so it is
    # special-cased here rather than delegated.
    if not isinstance(slug, str) or not slug:  # pyright: ignore[reportUnnecessaryIsInstance]
        raise ValueError(
            f"slug {slug!r} must be kebab-case, 1-64 chars, [a-z0-9-], "
            + "no leading/trailing hyphen, no double hyphens"
        )
    return paths.artifact_path(phase, slug)


def _command(
    phase: str | None = None,
    slug: str | None = None,
    *,
    named_phase: Annotated[str | None, Parameter(name="--phase")] = None,
    named_slug: Annotated[str | None, Parameter(name="--slug")] = None,
) -> int:
    if named_phase is not None and phase is not None:
        print("error: phase supplied more than once", file=sys.stderr)
        return 2
    if named_slug is not None and slug is not None:
        print("error: slug supplied more than once", file=sys.stderr)
        return 2
    resolved_phase = named_phase if named_phase is not None else phase
    resolved_slug = named_slug if named_slug is not None else slug
    if resolved_phase is None or resolved_slug is None:
        print("error: phase and slug are required", file=sys.stderr)
        return 2
    try:
        resolved = artifact_path(resolved_phase, resolved_slug)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(resolved)
    return 0


app = App(name="artifact-path")
_ = app.default(_command)


def main(argv: list[str]) -> int:
    return cli.run(app, argv=argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))