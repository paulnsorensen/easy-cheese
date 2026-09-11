"""Write a handoff artifact (handoff preamble + optional body) atomically.

CLI:

    python3 shared/scripts/write_handoff_artifact.py \\
        --slug my-task --status ok --phase press --next age \\
        --artifact .cheese/cook/my-task.md \\
        --orientation "press hardened X" \\
        [--body-file path/to/body.md]

Writes ``.cheese/<phase>/<slug>.md`` containing the canonical preamble
(status / next / artifact / optional ``taste_test:``, ``durable_flags:``, and
``baseline:`` keyed lines / orientation). ``--status`` is validated against
the declared handback vocabulary before any directory is created. An
optional body follows, separated by a blank line. The write is atomic:
contents land in a tmp file inside the target directory and are then
``os.replace``'d into place (atomic overwrite on POSIX and Windows alike),
so readers never observe a half-written file.

``--phase`` is mandatory and names *this* phase's own directory. The value is
validated against the generated phase registry before any output directory or
file is created. ``--next`` is preamble-content only — it tells the *next*
phase where the chain should go, but does not influence where this artifact
lands.
"""

import argparse
import contextlib
import os
import sys
import tempfile
import traceback
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Protocol, TextIO, cast

from easy_cheese.shared import cli, handoff, paths

from easy_cheese_schemas.phase_contracts import (
    COMPILED_TRANSITION_REGISTRY,
    StatusError,
    TransitionError,
    parse_status_field,
    status_vocabulary,
    validate_transition,
)


def _validate_transition(
    source: str, destination: str, payload_schema_uri: str | None, *, slug: str
) -> None:
    try:
        _ = validate_transition(
            COMPILED_TRANSITION_REGISTRY,
            source=source,
            destination=destination,
            payload_schema_uri=payload_schema_uri,
        )
    except TransitionError as exc:
        raise cli.contract_error(exc, context=f"--phase {source} --slug {slug}") from exc

def _render_preamble(
    *,
    status: str,
    next_skill: str,
    artifact: str,
    orientation: str,
    phase: str,
    slug_name: str,
    taste_test: str | None = None,
    durable_flags: str | None = None,
    baseline: str | None = None,
) -> str:
    """Render the preamble via handoff.render_handoff_slug (single SSOT).

    Any `StatusError` -- from parsing `--status` or from render-time
    single-line validation of the other preamble fields -- is wrapped with
    the dispatch it came from so the operator can attribute the violation.
    """
    context = f"--phase {phase} --slug {slug_name}"
    try:
        status_kind, reason = parse_status_field(status)
    except StatusError as exc:
        raise cli.contract_error(exc, context=context) from exc

    handoff_slug = handoff.HandoffSlug(
        status=status_kind,
        reason=reason,
        next_skill=next_skill,
        artifact=artifact or None,
        orientation=orientation,
        taste_test=taste_test,
        durable_flags=durable_flags,
        baseline=baseline,
    )
    try:
        return handoff.render_handoff_slug(handoff_slug)
    except StatusError as exc:
        raise cli.contract_error(exc, context=context) from exc


def _reject_traversal(field: str, value: str) -> None:
    """Reject path-traversal segments in values used to build the on-disk path."""
    if ".." in value or "/" in value or "\\" in value:
        raise cli.CliError(f"{field} rejects path traversal: {value!r}")


def _build_contents(*, preamble: str, body: str | None) -> str:
    if body is None:
        return preamble + "\n"
    return preamble + "\n\n" + body


def _wheypoint_error(exc: Exception, *, message: str | None = None) -> cli.CliError:
    """Classify a wheypoint kernel failure and print its traceback to stderr."""
    traceback.print_exc(file=sys.stderr)
    detail = f"{type(exc).__name__}: {exc}"
    text = f"wheypoint: {detail}" if message is None else message.format(detail)
    return cli.CliError(text, exit_code=cli.WHEYPOINT_EXIT_CODE)


def _atomic_write(target: Path, contents: str) -> None:
    """Write ``contents`` into ``target`` atomically via a sibling tmp file."""
    target_dir = target.parent
    target_dir.mkdir(parents=True, exist_ok=True)
    try:
        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{target.name}.",
            suffix=".tmp",
            dir=target_dir,
        )
    except OSError as exc:
        raise cli.CliError(f"cannot write {target}: {exc}") from exc

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            fd = -1
            _ = handle.write(contents)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, target)
    except OSError as exc:
        _cleanup_tmp(fd, tmp_name)
        raise cli.CliError(f"cannot write {target}: {exc}") from exc
    except BaseException:
        _cleanup_tmp(fd, tmp_name)
        raise


def _wheypoint_revision(
    *,
    slug: str,
    phase: str,
    next_skill: str,
    target: Path,
    orientation: str,
    grounded: Sequence[str],
    root: Path,
    corpus_root: Path | str | None,
    write_contents: Callable[[], None],
) -> None:
    """Validate, write, then commit one chain-phase revision; no-op otherwise."""
    if phase not in paths.CHAIN_PHASES:
        write_contents()
        return

    from easy_cheese.shared.wheypoint import phase_commit
    from easy_cheese.shared.wheypoint import storage as wheypoint_storage

    try:
        grounded_entries = phase_commit.validate_grounded(grounded, root=root)
    except phase_commit.GroundedEntryError as exc:
        raise cli.CliError(str(exc)) from exc

    store = wheypoint_storage.WorkStore.open(slug, corpus_root=corpus_root)
    try:
        current = phase_commit.read_current_record(slug, store=store)
        phase_commit.require_genesis_grounding(current, grounded_entries)
    except Exception as exc:
        raise _wheypoint_error(exc) from exc

    write_contents()

    try:
        _ = phase_commit.commit_phase_revision(
            work_id=slug,
            phase=phase,
            next_skill=next_skill,
            artifact=str(target),
            orientation=orientation,
            grounded=grounded_entries,
            provenance=phase_commit.session_provenance_from_environment(),
            root=root,
            current_record=current,
            store=store,
        )
    except Exception as exc:
        raise _wheypoint_error(
            exc,
            message=(
                f"wrote {target}, but the wheypoint revision failed: {{}}; "
                "the next resolve will gate on stale-artifact-link"
            ),
        ) from exc


def _cleanup_tmp(fd: int, tmp_name: str) -> None:
    """Close the open fd (if any) and remove the tmp file, reporting orphans."""
    if fd != -1:
        with contextlib.suppress(OSError):
            os.close(fd)
    try:
        os.unlink(tmp_name)
    except FileNotFoundError:
        pass  # already gone: not an error for a cleanup path
    except OSError:
        print(f"orphaned temp file: {tmp_name}", file=sys.stderr)


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
    grounded: Sequence[str] = (),
    corpus_root: Path | str | None = None,
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
    _validate_transition(phase, next_skill, payload_schema_uri, slug=slug)
    if phase not in paths.CHAIN_PHASES and grounded:
        raise cli.CliError(f"--grounded is only valid for chain phases, not {phase!r}")
    preamble = _render_preamble(
        status=status,
        next_skill=next_skill,
        artifact=artifact,
        orientation=orientation,
        phase=phase,
        slug_name=slug,
        taste_test=taste_test,
        durable_flags=durable_flags,
        baseline=baseline,
    )

    cheese_root = (root / ".cheese").resolve()
    target = cheese_root / phase / f"{slug}.md"
    # Phase names are validated against the compiled registry and therefore
    # select exactly one directory beneath .cheese/.
    if cheese_root not in target.resolve().parents:
        raise cli.CliError(f"--phase must stay under .cheese/: {phase!r}")

    contents = _build_contents(preamble=preamble, body=body)

    _wheypoint_revision(
        slug=slug,
        phase=phase,
        next_skill=next_skill,
        target=target,
        orientation=orientation,
        grounded=grounded,
        root=root,
        corpus_root=corpus_root,
        write_contents=lambda: _atomic_write(target, contents),
    )

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
    grounded: list[str]
    phase: str
    payload_schema: str | None
    root: str | None
    corpus_root: str | None
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
        grounded=a.grounded,
        corpus_root=a.corpus_root,
    )
    cli.emit(str(target), stdout=a.stdout)


def _setup(parser: argparse.ArgumentParser) -> None:
    _ = parser.add_argument("--slug", required=True, help="artifact slug (filename stem)")
    _ = parser.add_argument(
        "--status", required=True, help=f"handback status: {status_vocabulary()}"
    )
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
        "--grounded",
        action="append",
        default=[],
        metavar="PATH[#START-END]",
        help=(
            "grounded file path, optionally pinned to a positive line range; "
            "repeatable; chain phases only"
        ),
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
    _ = parser.add_argument(
        "--corpus-root",
        default=None,
        help="wheypoint corpus root override (default: the per-project XDG corpus)",
    )
    parser.set_defaults(func=_cmd_write)


def main(argv: list[str]) -> int:
    return cli.run(_setup, argv=argv)


if __name__ == "__main__":
    raise SystemExit(cli.run(_setup))
