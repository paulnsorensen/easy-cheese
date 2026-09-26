"""Resolve durable and transient artifact paths for packaged skills.

Thin CLI wrapper over ``paths.py`` -- phase tables, the slug regex, and the
root-resolution math live there as the single source of truth. See
``paths.artifact_path`` / ``paths.project_corpus_root``.
"""

from __future__ import annotations

from pathlib import Path

import fromargs

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


def resolve(phase: str, slug: str) -> dict[str, str]:
    """Resolve the artifact path for a phase and slug.

    Parameters
    ----------
    phase
        Phase name that owns the artifact.
    slug
        Kebab-case slug that identifies the artifact.
    """
    try:
        resolved = artifact_path(phase, slug)
    except ValueError as exc:
        raise fromargs.CliError(str(exc), exit_code=1) from exc
    return {"path": str(resolved)}


def build_app() -> fromargs.App:
    return fromargs.App(
        "artifact-path", help_formatter="plain", default_command=resolve
    )


def main(argv: list[str] | None = None) -> int:
    return build_app().run(argv)


if __name__ == "__main__":
    raise SystemExit(main())