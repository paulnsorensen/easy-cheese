"""Read the handoff preamble from a .cheese/<phase>/<slug>.md artifact.

Emits JSON with keys: status, next, artifact, orientation, halt_reason,
taste_test, durable_flags, baseline.
"""
from __future__ import annotations

from typing import Annotated
import sys

from cyclopts import App, Parameter

from easy_cheese.shared import cli, handoff, paths


def _command(
    *,
    phase: Annotated[str | None, Parameter(name="--phase")] = None,
    slug: Annotated[str | None, Parameter(name="--slug")] = None,
) -> int:
    if phase is None or slug is None:
        print("error: --phase and --slug are required", file=sys.stderr)
        return 2
    if phase not in paths.PHASES:
        print(f"error: invalid phase: {phase}", file=sys.stderr)
        return 2
    artifact = paths.artifact_path(phase, slug)
    if not artifact.is_file():
        raise cli.CliError(f"artifact not found: {artifact}")
    try:
        payload = handoff.parse_handoff_slug(artifact.read_text(encoding="utf-8"))
    except handoff.HandoffParseError as exc:
        raise cli.CliError(f"malformed handoff preamble in {artifact}: {exc}") from exc
    cli.emit(handoff.slug_payload(payload), json_mode=True)
    return 0


app = App(name="read-handoff-slug")
_ = app.default(_command)


def main(argv: list[str]) -> int:
    return cli.run(app, argv=argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
