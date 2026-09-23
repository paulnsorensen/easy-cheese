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

import contextlib
# pyright: reportAny=false, reportUnusedCallResult=false
import os
import sys
import tempfile
import traceback
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Annotated

from cyclopts import App, Parameter

from easy_cheese.shared import cli, handoff, paths

from easy_cheese_schemas.phase_contracts import (
    COMPILED_TRANSITION_REGISTRY,
    StatusError,
    TransitionError,
    parse_status_field,
    validate_transition,
)

# Exit codes a caller branches on. Plain integers, identical on every host: a
# chain driver distinguishes "nothing was written" from "the artifact is on disk
# without a revision" without parsing prose.
EXIT_WHEYPOINT = 4
EXIT_ARTIFACT_ORPHANED = 5


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


def _debug_enabled() -> bool:
    return any(
        os.environ.get(name, "").strip()
        for name in ("EASY_CHEESE_DEBUG", "CHEESE_DEBUG")
    )


def _traceback_if(*, unexpected: bool) -> None:
    """Print a traceback only when it carries information a message cannot.

    A refusal the kernel raises on purpose needs no stack, and the stack leaks
    absolute bundle and corpus paths into transcripts.
    """
    if unexpected or _debug_enabled():
        traceback.print_exc(file=sys.stderr)


def _orphaned(
    exc: BaseException, *, target: Path, root: Path, exit_code: int
) -> cli.CliError:
    """The artifact landed but its revision did not: one greppable line says so.

    The path is printed relative to the repository root, so the line is the same
    on every host and in every transcript.
    """
    shown = target.relative_to(root) if root in target.parents else target
    print(f"wheypoint: artifact-orphaned {shown}", file=sys.stderr)
    return cli.CliError(
        f"wrote {shown}, but the wheypoint revision failed: "
        + f"{type(exc).__name__}: {exc}; "
        + "the next resolve will gate on stale-artifact-link",
        exit_code=exit_code,
    )


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
        _cleanup_tmp(fd, tmp_name, target)
        raise cli.CliError(f"cannot write {target}: {exc}") from exc
    except BaseException:
        _cleanup_tmp(fd, tmp_name, target)
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
    """Adapt the CLI to the phase-commit producer; write directly otherwise.

    `phase_commit` owns the validate -> read -> guard -> write -> commit
    sequence *and* the classification of its own failures, so this wrapper only
    supplies the store and maps one producer exception type onto each exit code.
    """
    if phase not in paths.CHAIN_PHASES:
        write_contents()
        return

    from easy_cheese.shared.wheypoint import phase_commit
    from easy_cheese.shared.wheypoint import storage as wheypoint_storage

    try:
        store = wheypoint_storage.WorkStore.open(slug, corpus_root=corpus_root)
        outcome = phase_commit.commit_phase_revision(
            work_id=slug,
            phase=phase,
            next_skill=next_skill,
            artifact=str(target),
            orientation=orientation,
            grounded=grounded,
            root=root,
            store=store,
            write_contents=write_contents,
        )
    except cli.CliError:
        # The writer's own refusal (e.g. a failed atomic write) already carries
        # its caller-facing message and exit code; the kernel never raises one.
        raise
    except phase_commit.PhaseCommitRefusal as exc:
        _traceback_if(unexpected=False)
        raise cli.CliError(str(exc)) from exc
    except phase_commit.ArtifactOrphaned as exc:
        _traceback_if(unexpected=not exc.expected)
        raise _orphaned(
            exc.cause, target=target, root=root, exit_code=EXIT_ARTIFACT_ORPHANED
        ) from exc
    except Exception as exc:
        _traceback_if(unexpected=not isinstance(exc, wheypoint_storage.StorageError))
        raise cli.CliError(
            f"wheypoint: {type(exc).__name__}: {exc}",
            exit_code=EXIT_WHEYPOINT,
        ) from exc

    revision = outcome.result.revision
    print(
        f"wheypoint: revision work_id={slug} revision_id={revision.revision_id}"
        + f" revision_number={revision.revision_number}"
        + f" retried={str(outcome.retried).lower()}",
        file=sys.stderr,
    )


def _cleanup_tmp(fd: int, tmp_name: str, target: Path) -> None:
    """Close the open fd (if any) and remove the tmp file, reporting orphans."""
    if fd != -1:
        with contextlib.suppress(OSError):
            os.close(fd)
    try:
        os.unlink(tmp_name)
    except FileNotFoundError:
        pass  # already gone: not an error for a cleanup path
    except OSError:
        print(f"wheypoint: orphaned temp file {tmp_name} for {target}", file=sys.stderr)


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
    slug_problem = paths.validate_slug(slug)
    # Every phase, chain or not: the readers that later resolve this
    # artifact all route through `paths`, which admits only kebab-case.
    if slug_problem is not None:
        raise cli.CliError(f"--slug: {slug_problem}")
    # Transition validation runs first: an argv that trips both this and the
    # `--grounded` rule must report the contract error, not the CLI error.
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

    # One resolved root for the artifact and for the link `phase_commit` pins,
    # so a write from a subdirectory cannot land beside a `.cheese/` no reader
    # anchors on.
    root_path = paths.resolve_repo_root(root)
    cheese_root = root_path / ".cheese"
    target = cheese_root / phase / f"{slug}.md"
    # Phase names are validated against the compiled registry and therefore
    # select exactly one directory beneath .cheese/.
    if cheese_root not in target.resolve().parents:
        raise cli.CliError(f"--phase must stay under .cheese/: {phase!r}")

    contents = _build_contents(preamble=preamble, body=body)

    effective_corpus_root = (
        Path(corpus_root)
        if corpus_root is not None
        else paths.project_corpus_root(paths.project_key(root_path))
    )
    _wheypoint_revision(
        slug=slug,
        phase=phase,
        next_skill=next_skill,
        target=target,
        orientation=orientation,
        grounded=grounded,
        root=root_path,
        corpus_root=effective_corpus_root,
        write_contents=lambda: _atomic_write(target, contents),
    )

    return target


def _cmd_write(*, slug: str, status: str, next_skill: Annotated[str, Parameter(name="--next")], artifact: str, orientation: str, phase: str, body_file: str | None = None, taste_test: str | None = None, durable_flags: str | None = None, baseline: str | None = None, grounded: list[str] | None = None, payload_schema: str | None = None, root: str | None = None, corpus_root: str | None = None) -> None:
    body = None
    if body_file is not None:
        body_path = Path(body_file)
        if not body_path.is_file():
            raise cli.CliError(f"--body-file not found: {body_path}")
        body = body_path.read_text(encoding="utf-8")
    target = write_artifact(slug=slug, status=status, next_skill=next_skill, artifact=artifact, orientation=orientation, body=body, root=paths.resolve_repo_root(root), phase=phase, payload_schema_uri=payload_schema, taste_test=taste_test, durable_flags=durable_flags, baseline=baseline, grounded=grounded or [], corpus_root=corpus_root)
    print(target)


app = App(name="write-handoff-artifact")
app.default(_cmd_write)


def main(argv: list[str]) -> int:
    try:
        canonical = cli.repair_argv(app, argv)
        result = app(canonical, print_error=False, exit_on_error=False, help_on_error=False, result_action="return_value")
    except cli.CliError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return exc.exit_code
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0 if result is None else int(result)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
