"""Read the 4-line handoff preamble from a .cheese/<phase>/<slug>.md artifact.

Emits JSON with keys: status, next, artifact, orientation, halt_reason.

    python3 shared/scripts/read_handoff_slug.py --phase age --slug foo
    -> {"status": "ok", "next": "cure", ...}
"""
from __future__ import annotations

import argparse

import cli
import handoff
import paths


def _cmd(args: argparse.Namespace) -> None:
    artifact = paths.artifact_path(args.phase, args.slug)
    if not artifact.is_file():
        raise cli.CliError(f"artifact not found: {artifact}")
    slug = handoff.parse_handoff_slug(artifact.read_text())
    cli.emit(
        {
            "status": slug.status,
            "next": slug.next_skill,
            "artifact": slug.artifact,
            "orientation": slug.orientation,
            "halt_reason": slug.halt_reason,
        },
        json_mode=True,
    )


def _setup(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--phase", required=True, choices=sorted(paths.PHASES))
    parser.add_argument("--slug", required=True)
    parser.set_defaults(func=_cmd)


if __name__ == "__main__":
    cli.run(_setup)
