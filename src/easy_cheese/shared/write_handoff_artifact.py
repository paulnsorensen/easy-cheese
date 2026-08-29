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

``--phase`` is mandatory and names *this* phase's own directory. The value is
validated against the generated phase registry before any output directory or
file is created. ``--next`` is preamble-content only — it tells the *next*
phase where the chain should go, but does not influence where this artifact
lands.
"""

import argparse
import contextlib
import os
import tempfile
from pathlib import Path
from typing import Protocol, TextIO, cast

from easy_cheese.shared import cli, handoff

from easy_cheese_schemas.phase_contracts import (
    COMPILED_TRANSITION_REGISTRY,
    TransitionError,
    validate_transition,
)


def _validate_transition(
    source: str, destination: str, payload_schema_uri: str | None
) -> None:
    try:
        _ = validate_transition(
            COMPILED_TRANSITION_REGISTRY,
            source=source,
            destination=destination,
            payload_schema_uri=payload_schema_uri,
        )
    except TransitionError as exc:
        raise cli.CliError(str(exc)) from exc

def _render_preamble(
    *,
    status: str,
    next_skill: str,
    artifact: str,
    orientation: str,
    taste_test: str | None = None,
    durable_flags: str | None = None,
    baseline: str | None = None,
) -> str:
    """Render the preamble via handoff.render_handoff_slug (single SSOT)."""
    # Parse status into (status_kind, halt_reason).
    if status.startswith("halt:"):
        halt_reason = status[len("halt:") :].strip()
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
        baseline=baseline,
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
    phase: str,
    payload_schema_uri: str | None = None,
    taste_test: str | None = None,
    durable_flags: str | None = None,
    baseline: str | None = None,
) -> Path:
    """Write the artifact atomically; return the final path."""
    if not slug:
        raise cli.CliError("--slug must be non-empty")
    if not next_skill:
        raise cli.CliError("--next must be non-empty")
    if not phase:
        raise cli.CliError("--phase must be non-empty")
    if not orientation:
        raise cli.CliError("--orientation must be non-empty")
    _reject_traversal("--slug", slug)
    _reject_traversal("--phase", phase)
    _validate_transition(phase, next_skill, payload_schema_uri)

    cheese_root = (root / ".cheese").resolve()
    target = cheese_root / phase / f"{slug}.md"
    # Phase names are validated against the compiled registry and therefore
    # select exactly one directory beneath .cheese/.
    if cheese_root not in target.resolve().parents:
        raise cli.CliError(f"--phase must stay under .cheese/: {phase!r}")
    target_dir = target.parent
    target_dir.mkdir(parents=True, exist_ok=True)

    preamble = _render_preamble(
        status=status,
        next_skill=next_skill,
        artifact=artifact,
        orientation=orientation,
        taste_test=taste_test,
        durable_flags=durable_flags,
        baseline=baseline,
    )
    contents = _build_contents(preamble=preamble, body=body)

    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=target_dir,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            fd = -1
            _ = handle.write(contents)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, target)
    except BaseException:
        if fd != -1:
            with contextlib.suppress(OSError):
                os.close(fd)
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp_name)
        raise
    return target


class _Args(Protocol):
    slug: str
    status: str
    next: str
    artifact: str
    orientation: str
    taste_test: str | None
    durable_flags: str | None
    baseline: str | None
    body_file: str | None
    phase: str
    payload_schema: str | None
    root: str | None
    stdout: TextIO


def _cmd_write(args: argparse.Namespace) -> None:
    a = cast(_Args, cast(object, args))
    body: str | None = None
    if a.body_file is not None:
        body_path = Path(a.body_file)
        if not body_path.is_file():
            raise cli.CliError(f"--body-file not found: {body_path}")
        body = body_path.read_text(encoding="utf-8")

    root = Path(a.root) if a.root else Path.cwd()
    target = write_artifact(
        slug=a.slug,
        status=a.status,
        next_skill=a.next,
        artifact=a.artifact,
        orientation=a.orientation,
        body=body,
        root=root,
        phase=a.phase,
        payload_schema_uri=a.payload_schema,
        taste_test=a.taste_test,
        durable_flags=a.durable_flags,
        baseline=a.baseline,
    )
    cli.emit(str(target), stdout=a.stdout)


def _setup(parser: argparse.ArgumentParser) -> None:
    _ = parser.add_argument("--slug", required=True, help="artifact slug (filename stem)")
    _ = parser.add_argument("--status", required=True, help="'ok' or 'halt: <reason>'")
    _ = parser.add_argument("--next", required=True, help="next skill name or 'done'")
    _ = parser.add_argument(
        "--artifact", required=True, help="path to prior artifact (may be empty)"
    )
    _ = parser.add_argument("--orientation", required=True, help="one-line orientation")
    _ = parser.add_argument(
        "--taste-test",
        default=None,
        help="optional taste_test: keyed preamble line (omitted when absent)",
    )
    _ = parser.add_argument(
        "--durable-flags",
        default=None,
        help="optional durable_flags: keyed preamble line (omitted when absent)",
    )
    _ = parser.add_argument(
        "--baseline",
        default=None,
        help="optional baseline: keyed preamble line (omitted when absent)",
    )
    _ = parser.add_argument(
        "--body-file", default=None, help="optional path to body content"
    )
    _ = parser.add_argument(
        "--phase",
        required=True,
        help="name of THIS phase's own directory under .cheese/ (path authority)",
    )
    _ = parser.add_argument(
        "--payload-schema",
        default=None,
        help="payload schema URI for transition validation",
    )
    _ = parser.add_argument(
        "--root",
        default=None,
        help="repo root (default: cwd); .cheese/<phase>/<slug>.md is written under this",
    )
    parser.set_defaults(func=_cmd_write)


def main(argv: list[str]) -> int:
    return cli.run(_setup, argv=argv)


if __name__ == "__main__":
    raise SystemExit(cli.run(_setup))
