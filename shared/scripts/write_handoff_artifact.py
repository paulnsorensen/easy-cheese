"""Write a handoff artifact (handoff preamble + optional body) atomically.

CLI:

    python3 shared/scripts/write_handoff_artifact.py \\
        --slug my-task --status ok --phase press --next age \\
        --artifact .cheese/cook/my-task.md \\
        --orientation "press hardened X" \\
        [--body-file path/to/body.md]

Writes ``.cheese/<phase>/<slug>.md`` containing the canonical preamble
(status / next / artifact / optional ``taste_test:`` and ``durable_flags:``
keyed lines / orientation) followed by an optional
body separated by a blank line. The write is atomic: contents land in a tmp
file inside the target directory and are then ``os.replace``'d into place
(atomic overwrite on POSIX and Windows alike), so readers never observe a
half-written file.

``--phase`` names *this* phase's own directory and is the on-disk path
authority. ``--next`` is preamble-content only — it tells the *next* phase
where the chain should go, but does not influence where this artifact lands.
For backward compatibility, ``--phase`` is optional: when omitted, the path
falls back to ``.cheese/<next>/<slug>.md`` (the legacy "write the next phase's
input" shape, kept so existing tests and callers do not break mid-rollout).
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import cli
import handoff


def _render_preamble(
    *,
    status: str,
    next_skill: str,
    artifact: str,
    orientation: str,
    taste_test: str | None = None,
    durable_flags: str | None = None,
) -> str:
    """Render the preamble via handoff.render_handoff_slug (single SSOT)."""
    # Parse status into (status_kind, halt_reason).
    if status.startswith("halt:"):
        halt_reason = status[len("halt:"):].strip()
        status_kind = "halt"
    else:
        halt_reason = None
        status_kind = status

    slug = handoff.HandoffSlug(
        status=status_kind,
        halt_reason=halt_reason,
        next_skill=next_skill,
        artifact=artifact or None,
        orientation=orientation,
        taste_test=taste_test,
        durable_flags=durable_flags,
    )
    return handoff.render_handoff_slug(slug)


def _reject_traversal(field: str, value: str) -> None:
    """Reject path-traversal segments in values used to build the on-disk path."""
    if ".." in value or "/" in value or "\\" in value:
        raise cli.CliError(f"{field} rejects path traversal: {value!r}")


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
    phase: str | None = None,
    taste_test: str | None = None,
    durable_flags: str | None = None,
) -> Path:
    """Write the artifact atomically; return the final path.

    The on-disk path is ``.cheese/<phase>/<slug>.md`` when ``phase`` is given;
    otherwise it falls back to ``.cheese/<next_skill>/<slug>.md`` (legacy).
    ``next_skill`` always lands in the preamble's ``next:`` field regardless,
    so callers can decouple "where this report lives" from "what runs next".
    """
    if not slug:
        raise cli.CliError("--slug must be non-empty")
    if not next_skill:
        raise cli.CliError("--next must be non-empty")
    if not orientation:
        raise cli.CliError("--orientation must be non-empty")
    _reject_traversal("--slug", slug)

    path_dir = phase if phase else next_skill
    cheese_root = (root / ".cheese").resolve()
    target = cheese_root / path_dir / f"{slug}.md"
    # Nested path_dir subdirs are allowed (factory chains write to subdirs); a
    # `..` or absolute escape out of .cheese/ is not.
    if cheese_root not in target.resolve().parents:
        raise cli.CliError(f"--phase/--next must stay under .cheese/: {path_dir!r}")
    target_dir = target.parent
    target_dir.mkdir(parents=True, exist_ok=True)

    preamble = _render_preamble(
        status=status,
        next_skill=next_skill,
        artifact=artifact,
        orientation=orientation,
        taste_test=taste_test,
        durable_flags=durable_flags,
    )
    contents = _build_contents(preamble=preamble, body=body)

    tmp = target.with_name(target.name + ".tmp")
    try:
        tmp.write_text(contents, encoding="utf-8")
        os.replace(tmp, target)
    except BaseException:
        # Atomic-rename contract: clean up the tmp on failure so callers never
        # see a half-written sibling. swallow tmp-cleanup errors — the real
        # failure is the one we're propagating.
        try:
            tmp.unlink()
        except FileNotFoundError:
            # tmp was never created or has already been cleaned up; nothing
            # to undo. Swallow so the original write error propagates uncovered.
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
        phase=args.phase,
        taste_test=args.taste_test,
        durable_flags=args.durable_flags,
    )
    cli.emit(str(target))


def _setup(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--slug", required=True, help="artifact slug (filename stem)")
    parser.add_argument("--status", required=True, help="'ok' or 'halt: <reason>'")
    parser.add_argument("--next", required=True, help="next skill name or 'done'")
    parser.add_argument("--artifact", required=True, help="path to prior artifact (may be empty)")
    parser.add_argument("--orientation", required=True, help="one-line orientation")
    parser.add_argument(
        "--taste-test",
        default=None,
        help="optional taste_test: keyed preamble line (omitted when absent)",
    )
    parser.add_argument(
        "--durable-flags",
        default=None,
        help="optional durable_flags: keyed preamble line (omitted when absent)",
    )
    parser.add_argument("--body-file", default=None, help="optional path to body content")
    parser.add_argument(
        "--phase",
        default=None,
        help=(
            "name of THIS phase's own directory under .cheese/ "
            "(path authority). Optional for backward compatibility; "
            "when omitted, falls back to --next."
        ),
    )
    parser.add_argument(
        "--root",
        default=None,
        help="repo root (default: cwd); .cheese/<phase|next>/<slug>.md is written under this",
    )
    parser.set_defaults(func=_cmd_write)


if __name__ == "__main__":
    cli.run(_setup)
