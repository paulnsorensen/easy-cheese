"""Read the versioned handoff envelope from a .cheese artifact.

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
    text = artifact.read_text(encoding="utf-8")
    try:
        envelope = handoff.parse_handoff(text, artifact)
    except handoff.HandoffParseError as exc:
        if text.startswith("---\\n"):
            raise cli.CliError(f"malformed handoff preamble in {artifact}: {exc}") from exc
        try:
            slug = handoff.parse_handoff_slug(text)
        except handoff.HandoffParseError as legacy_exc:
            raise cli.CliError(f"malformed handoff preamble in {artifact}: {legacy_exc}") from legacy_exc
        cli.emit({"status": slug.status, "next": slug.next_skill, "artifact": slug.artifact,
                  "orientation": slug.orientation, "halt_reason": slug.halt_reason,
                  "taste_test": slug.taste_test, "durable_flags": slug.durable_flags,
                  "baseline": slug.baseline}, json_mode=True)
        return
    cli.emit(envelope.as_mapping(), json_mode=True)


def _setup(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--phase", required=True, choices=sorted(paths.PHASES))
    parser.add_argument("--slug", required=True)
    parser.set_defaults(func=_cmd)


if __name__ == "__main__":
    cli.run(_setup)
