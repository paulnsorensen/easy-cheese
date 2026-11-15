"""Read the handoff preamble from a .cheese/<phase>/<slug>.md artifact.

Emits JSON with keys: status, next, artifact, orientation, halt_reason,
taste_test, durable_flags, baseline.

    python3 shared/scripts/read_handoff_slug.py --phase age --slug foo
    -> {"status": "ok", "next": "cure", ...}
"""
from __future__ import annotations

import fromargs

from easy_cheese.shared import handoff, paths


def read_handoff_slug(*, phase: str, slug: str) -> dict[str, object]:
    """Read the handoff preamble from a .cheese/<phase>/<slug>.md artifact.

    Parameters
    ----------
    phase
        Pipeline phase directory name.
    slug
        Artifact slug.
    """
    if phase not in paths.PHASES:
        raise fromargs.CliError(
            f"unknown phase {phase!r}; expected one of {sorted(paths.PHASES)}"
        )
    artifact = paths.artifact_path(phase, slug)
    if not artifact.is_file():
        raise fromargs.CliError(f"artifact not found: {artifact}")
    try:
        parsed = handoff.parse_handoff_slug(artifact.read_text(encoding="utf-8"))
    except handoff.HandoffParseError as exc:
        raise fromargs.CliError(f"malformed handoff preamble in {artifact}: {exc}") from exc
    return handoff.slug_payload(parsed)


def build_app() -> fromargs.App:
    return fromargs.App(
        "read-handoff-slug",
        help="Read the handoff preamble from a .cheese/<phase>/<slug>.md artifact.",
        help_formatter="plain",
        default_command=read_handoff_slug,
    )


def main(argv: list[str] | None = None) -> int:
    return build_app().run(argv)


if __name__ == "__main__":
    raise SystemExit(main())