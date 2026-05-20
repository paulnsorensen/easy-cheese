"""Write a handoff artifact (4-line preamble + optional body) atomically.

CLI:

    python3 shared/scripts/write_handoff_artifact.py \\
        --slug my-task --status ok --next age \\
        --artifact .cheese/press/my-task.md \\
        --orientation "implemented X" \\
        [--body-file path/to/body.md]

Writes ``.cheese/<next>/<slug>.md`` containing the canonical four-line
preamble (status / next / artifact / orientation) followed by an optional
body separated by a blank line. The write is atomic: contents land in a tmp
file inside the target directory and are then ``os.rename``'d into place, so
readers never observe a half-written file.

When ``shared/scripts/handoff.py`` exposes ``render_handoff_slug`` with a
matching ``(status, next, artifact, orientation) -> str`` signature, the
preamble is delegated. The current ``handoff.py`` exposes a different shape
(``render_handoff_slug(HandoffSlug)``), so this module renders inline by
default — kept simple per the spec quality gate.
"""

from __future__ import annotations

import argparse
import inspect
import os
from pathlib import Path

import cli
import handoff


def _render_preamble(*, status: str, next_skill: str, artifact: str, orientation: str) -> str:
    """Render the 4-line preamble; delegate to handoff if a matching helper exists."""
    fn = getattr(handoff, "render_handoff_slug", None)
    if fn is not None:
        try:
            params = list(inspect.signature(fn).parameters)
        except (TypeError, ValueError):
            params = []
        if params[:4] == ["status", "next", "artifact", "orientation"]:
            return fn(status, next_skill, artifact, orientation)  # type: ignore[misc]

    return "\n".join(
        [
            f"status: {status}",
            f"next: {next_skill}",
            f"artifact: {artifact}",
            orientation,
        ]
    )


def _build_contents(*, preamble: str, body: str | None) -> str:
    if body is None:
        return preamble + "\n"
    return preamble + "\n\n" + body


def write_artifact(
    *,
    slug: str,
    status: str,
    next_skill: str,
    artifact: str,
    orientation: str,
    body: str | None,
    root: Path,
) -> Path:
    """Write the artifact atomically; return the final path."""
    if not slug:
        raise cli.CliError("--slug must be non-empty")
    if not next_skill:
        raise cli.CliError("--next must be non-empty")
    if not orientation:
        raise cli.CliError("--orientation must be non-empty")

    target_dir = root / ".cheese" / next_skill
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{slug}.md"

    preamble = _render_preamble(
        status=status, next_skill=next_skill, artifact=artifact, orientation=orientation
    )
    contents = _build_contents(preamble=preamble, body=body)

    tmp = target.with_name(target.name + ".tmp")
    try:
        tmp.write_text(contents, encoding="utf-8")
        os.rename(tmp, target)
    except BaseException:
        # Atomic-rename contract: clean up the tmp on failure so callers never
        # see a half-written sibling. swallow tmp-cleanup errors — the real
        # failure is the one we're propagating.
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass
        raise
    return target


def _cmd_write(args: argparse.Namespace) -> None:
    body: str | None = None
    if args.body_file is not None:
        body_path = Path(args.body_file)
        if not body_path.is_file():
            raise cli.CliError(f"--body-file not found: {body_path}")
        body = body_path.read_text(encoding="utf-8")

    root = Path(args.root) if args.root else Path.cwd()
    target = write_artifact(
        slug=args.slug,
        status=args.status,
        next_skill=args.next,
        artifact=args.artifact,
        orientation=args.orientation,
        body=body,
        root=root,
    )
    cli.emit(str(target))


def _setup(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--slug", required=True, help="artifact slug (filename stem)")
    parser.add_argument("--status", required=True, help="'ok' or 'halt: <reason>'")
    parser.add_argument("--next", required=True, help="next skill name or 'done'")
    parser.add_argument("--artifact", required=True, help="path to prior artifact (may be empty)")
    parser.add_argument("--orientation", required=True, help="one-line orientation")
    parser.add_argument("--body-file", default=None, help="optional path to body content")
    parser.add_argument(
        "--root",
        default=None,
        help="repo root (default: cwd); .cheese/<next>/<slug>.md is written under this",
    )
    parser.set_defaults(func=_cmd_write)


if __name__ == "__main__":
    cli.run(_setup)
