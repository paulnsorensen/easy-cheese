"""Review-only gate for /age: prove the production tree did not move.

`/age` reviews; `/cure` applies. That boundary lived only in prose, and the
model routinely continued into repair inside the review context instead of
invoking `/cure` (issue #552). This module turns it into a precondition on
age's terminal act — writing `.cheese/age/<slug>.md`.

Step 1 of the age flow records a digest of the production tree
(``review-lock``); the report write recomputes it and refuses when it differs.
Applying a fix inline moves the digest, so the report cannot be written from a
context that applied one.

Digest scope: the captured ``HEAD`` identity and tracked-file content (index and
worktree), plus untracked-file paths and content. Review inputs under
``.cheese/`` are included, except for this slug's own lock, report body, report,
and HTML copy. Every other ``.cheese/age`` file — the fan-out packet included —
stays in the digest, so a report cannot be certified after its own evidence
moved.

Git runs with text conversion, external diff drivers, hooks, and the file-system
monitor disabled, so a repository under review cannot execute a configured
command with the reviewer's privileges.

Outside a git work tree there is no production tree to compare against, so both
capture and verification degrade to a no-op. Every other git failure is an
error: the gate fails closed rather than certifying an unchecked tree.

The gate raises the cost of the boundary; it does not make it unbypassable. An
agent that captures the lock *after* editing still passes. What it removes is
the silent path: skipping the lock now fails the write with an instruction.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import BinaryIO, Callable, Protocol, TextIO, cast

from easy_cheese.shared import cli, git_utils, write_handoff_artifact

PHASE = "age"
SCRATCH_DIR = ".cheese"
LOCK_SUFFIX = ".review-lock.json"
BODY_SUFFIX = "-body.md"
_LOCK_COMMAND = "python3 skills/age/scripts/age.pyz review-lock --slug"
_GIT_CHUNK_SIZE = 128 * 1024
_OUTPUT_PREFIX = f"{SCRATCH_DIR}/{PHASE}/"
# Git can run repository-configured commands during a diff (textconv filters,
# external diff drivers, hooks, the fs monitor). The review lock reads a tree it
# does not trust, so it disables every command-valued helper.
_GIT_SAFE_CONFIG = (
    "-c",
    "diff.external=",
    "-c",
    "core.fsmonitor=",
    "-c",
    "core.hooksPath=/dev/null",
)
_DIFF_BASE = ("diff", "--no-ext-diff", "--no-textconv", "--no-color")
_NOT_A_REPOSITORY = "not a git repository"


class _Digest(Protocol):
    def update(self, data: bytes, /) -> None: ...


def _run_git(args: list[str], root: Path) -> subprocess.CompletedProcess[str]:
    try:
        return git_utils.run_git([*_GIT_SAFE_CONFIG, *args], cwd=root)
    except OSError as exc:
        raise cli.CliError(f"cannot run git {' '.join(args)}: {exc}") from exc


def repo_root(root: Path) -> Path | None:
    """Return the top-level work tree for `root`, or None outside a repository.

    Raises `CliError` for every other git failure. A probe that cannot answer
    must not read as "no repository": that answer disables the gate.
    """
    result = _run_git(["rev-parse", "--show-toplevel"], root)
    if result.returncode == 0:
        top = result.stdout.strip()
        if not top:
            raise cli.CliError(f"git reported no work tree for {root}")
        return Path(top)
    detail = result.stderr.strip() or f"git exited {result.returncode}"
    if _NOT_A_REPOSITORY in detail.lower():
        return None
    raise cli.CliError(f"cannot resolve the git work tree at {root}: {detail}")


def _output_stems(slug: str) -> tuple[str, ...]:
    """This slug's own report outputs — the only files the lock may ignore.

    The fan-out packet (`<slug>-packet.md`) is review *evidence*, not output, so
    it stays in the digest. Assemble it before the lock.
    """
    return (
        f"{slug}{LOCK_SUFFIX}",
        f"{slug}.md",
        f"{slug}.html",
        f"{slug}{BODY_SUFFIX}",
    )


def _is_review_output(name: str, slug: str) -> bool:
    if not name.startswith(_OUTPUT_PREFIX):
        return False
    return name[len(_OUTPUT_PREFIX) :] in _output_stems(slug)


def _exclude_pathspecs(slug: str) -> list[str]:
    return [f":(exclude,literal){_OUTPUT_PREFIX}{stem}" for stem in _output_stems(slug)]


def _stream_git(args: list[str], root: Path, consume: Callable[[bytes], None]) -> None:
    try:
        process: subprocess.Popen[bytes] = subprocess.Popen(
            ["git", "-C", str(root), *_GIT_SAFE_CONFIG, *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as exc:
        raise cli.CliError(f"cannot run git {' '.join(args)}: {exc}") from exc

    stdout = cast(BinaryIO, process.stdout)
    stderr_stream = cast(BinaryIO, process.stderr)
    try:
        while chunk := stdout.read(_GIT_CHUNK_SIZE):
            consume(chunk)
        stderr = stderr_stream.read()
        returncode = process.wait()
    except BaseException:
        try:
            process.kill()
        except OSError:
            pass
        _ = process.wait()
        raise
    finally:
        stdout.close()
        stderr_stream.close()
    if returncode != 0:
        detail = stderr.decode("utf-8", "replace").strip()
        raise cli.CliError(f"git {' '.join(args)} failed: {detail}")


def _hash_untracked_path(
    raw_name: bytes, root: Path, digest: _Digest, slug: str
) -> None:
    name = os.fsdecode(raw_name)
    if _is_review_output(name, slug):
        return
    digest.update(b"path\0")
    digest.update(raw_name)
    digest.update(b"\0")
    path = root / name
    try:
        if path.is_symlink():
            digest.update(b"link\0")
            digest.update(os.fsencode(os.readlink(path)))
        else:
            digest.update(b"file\0")
            with path.open("rb") as stream:
                while chunk := stream.read(_GIT_CHUNK_SIZE):
                    digest.update(chunk)
    except OSError as exc:
        raise cli.CliError(f"cannot hash untracked path {name!r}: {exc}") from exc
    digest.update(b"\0")


def _hash_untracked_listing(
    args: list[str], root: Path, digest: _Digest, slug: str
) -> None:
    pending = bytearray()

    def consume(chunk: bytes) -> None:
        pending.extend(chunk)
        offset = 0
        while (end := pending.find(b"\0", offset)) >= 0:
            raw_name = bytes(pending[offset:end])
            if raw_name:
                _hash_untracked_path(raw_name, root, digest, slug)
            offset = end + 1
        if offset:
            del pending[:offset]

    _stream_git(args, root, consume)
    if pending:
        _hash_untracked_path(bytes(pending), root, digest, slug)


def _hash_untracked(root: Path, digest: _Digest, slug: str) -> None:
    digest.update(b"untracked\0")
    _hash_untracked_listing(
        [
            "ls-files",
            "--others",
            "--exclude-standard",
            "--full-name",
            "-z",
            "--",
            ".",
            f":(exclude,glob){SCRATCH_DIR}/**",
        ],
        root,
        digest,
        slug,
    )
    _hash_untracked_listing(
        ["ls-files", "--others", "--full-name", "-z", "--", SCRATCH_DIR],
        root,
        digest,
        slug,
    )


def tree_digest(root: Path, *, slug: str) -> str | None:
    """Hash the captured git tree and every review input for `slug`."""
    top = repo_root(root)
    if top is None:
        return None
    head = _run_git(["rev-parse", "--verify", "--quiet", "HEAD"], top)
    if head.returncode not in (0, 1):
        raise cli.CliError(
            f"cannot read HEAD in {top}: {head.stderr.strip() or head.returncode}"
        )
    digest = hashlib.sha256()
    digest.update(b"age-review-lock-v3\0head\0")
    if head.returncode == 0:
        digest.update(head.stdout.strip().encode("ascii", "replace"))
    else:
        digest.update(b"<unborn>")
    excludes = _exclude_pathspecs(slug)
    if head.returncode == 0:
        digest.update(b"\0diff\0")
        _stream_git([*_DIFF_BASE, "HEAD", "--", ".", *excludes], top, digest.update)
    else:
        # No HEAD: `git diff` alone compares the worktree to the index and hides
        # staged content, so hash the index and then the worktree delta.
        digest.update(b"\0index\0")
        _stream_git([*_DIFF_BASE, "--cached", "--", ".", *excludes], top, digest.update)
        digest.update(b"\0worktree\0")
        _stream_git([*_DIFF_BASE, "--", ".", *excludes], top, digest.update)
    _hash_untracked(top, digest, slug)
    return digest.hexdigest()


def _reject_symlink_components(root: Path, target: Path) -> None:
    current = root
    for part in target.relative_to(root).parts:
        current = current / part
        if current.is_symlink():
            raise cli.CliError(
                f"refusing to follow a symlink in the review-lock path: {current}"
            )


def lock_path(*, root: Path, slug: str) -> Path:
    if not slug:
        raise cli.CliError("--slug must be non-empty")
    cli.reject_path_segment("--slug", slug)
    target = root / SCRATCH_DIR / PHASE / f"{slug}{LOCK_SUFFIX}"
    _reject_symlink_components(root, target)
    return target


def _write_no_follow(target: Path, text: str) -> None:
    """Write `text` to `target` atomically without following a symlink."""
    scratch = target.with_name(f".{target.name}.tmp")
    scratch.unlink(missing_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
    try:
        handle = os.open(scratch, flags, 0o600)
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                _ = stream.write(text)
        except BaseException:
            scratch.unlink(missing_ok=True)
            raise
        os.replace(scratch, target)
    except OSError as exc:
        raise cli.CliError(f"cannot write review lock {target}: {exc}") from exc


def capture(*, root: Path, slug: str) -> Path:
    """Record the current production-tree digest for `slug`; return the path."""
    top = repo_root(root) or root
    target = lock_path(root=top, slug=slug)
    target.parent.mkdir(parents=True, exist_ok=True)
    _reject_symlink_components(top, target)
    payload = {"slug": slug, "digest": tree_digest(top, slug=slug)}
    _write_no_follow(target, json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return target


def _locked_digest(target: Path, slug: str) -> str:
    if not target.is_file():
        raise cli.CliError(
            f"no review lock for {slug!r}: run `{_LOCK_COMMAND} {slug}` at the start "
            + "of the review. /age is review-only — the lock is what proves no fix was "
            + "applied inline; /cure owns application."
        )
    try:
        payload = cast(object, json.loads(target.read_text(encoding="utf-8")))
    except ValueError as exc:
        raise cli.CliError(f"unreadable review lock {target}: {exc}") from exc
    locked = (
        cast("dict[str, object]", payload).get("digest")
        if isinstance(payload, dict)
        else None
    )
    if not isinstance(locked, str):
        raise cli.CliError(
            f"review lock {target} recorded no digest: re-run `{_LOCK_COMMAND} {slug}` "
            + "from inside the git work tree under review."
        )
    return locked


def verify(*, root: Path, slug: str) -> None:
    """Raise CliError unless the tree still matches `slug`'s review lock."""
    top = repo_root(root)
    if top is None:
        # No git work tree: no production tree to compare against.
        return
    # Validate the lock before the digest: a missing lock must not pay for the
    # git walk first.
    locked = _locked_digest(lock_path(root=top, slug=slug), slug)
    current = tree_digest(top, slug=slug)
    if locked != current:
        raise cli.CliError(
            f"the production tree changed after {slug!r}'s review lock: /age does not "
            + "apply fixes — invoke /cure with the findings instead. If the change came "
            + f"from outside this review, re-run `{_LOCK_COMMAND} {slug}` and review again."
        )


def _cmd_lock(args: argparse.Namespace) -> None:
    root = Path(cast("str | None", args.root) or Path.cwd())
    target = capture(root=root, slug=cast(str, args.slug))
    cli.emit(str(target), stdout=cast(TextIO, args.stdout))


def _setup(parser: argparse.ArgumentParser) -> None:
    _ = parser.add_argument(
        "--slug", required=True, help="review slug (lock filename stem)"
    )
    _ = parser.add_argument(
        "--root",
        default=None,
        help="repo root (default: cwd); the lock lands under .cheese/age/",
    )
    parser.set_defaults(func=_cmd_lock)


def main(argv: list[str]) -> int:
    return cli.run(_setup, argv=argv)


def _peek(argv: list[str]) -> tuple[str | None, str | None, Path]:
    """Read --slug/--phase/--root without consuming the writer's own parse."""
    parser = argparse.ArgumentParser(add_help=False)
    _ = parser.add_argument("--slug")
    _ = parser.add_argument("--phase")
    _ = parser.add_argument("--root")
    try:
        known, _rest = parser.parse_known_args(argv)
    except SystemExit:
        return None, None, Path.cwd()
    root = Path(cast("str | None", known.root) or Path.cwd())
    return cast("str | None", known.slug), cast("str | None", known.phase), root


def gated_write_handoff_artifact(argv: list[str]) -> int:
    """`write-handoff-artifact`, refusing an age report written over inline fixes."""
    slug, phase, root = _peek(argv)
    if phase == PHASE and slug:
        try:
            verify(root=root, slug=slug)
        except cli.CliError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
    return write_handoff_artifact.main(argv)


if __name__ == "__main__":
    raise SystemExit(cli.run(_setup))
