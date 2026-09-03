"""Review-only gate for /age: prove the production tree did not move.

`/age` reviews; `/cure` applies. That boundary lived only in prose, and the
model routinely continued into repair inside the review context instead of
invoking `/cure` (issue #552). This module turns it into a precondition on
age's terminal act — writing `.cheese/age/<slug>.md`.

Step 1 of the age flow records a digest of the production tree
(``review-lock``); the report write recomputes it and refuses when it differs.
Applying a fix inline moves the digest, so the report cannot be written from a
context that applied one.

Digest scope: the captured ``HEAD`` identity and tracked-file content (the
working diff against ``HEAD``), plus untracked-file paths and content. Review
inputs under ``.cheese/`` are included, except for this phase's lock and report
outputs. Outside a git work tree, no production tree exists for comparison, so
both capture and verification degrade to a no-op rather than blocking the
review.

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
_LOCK_COMMAND = "python3 skills/age/scripts/age.pyz review-lock --slug"
_GIT_CHUNK_SIZE = 128 * 1024
_OUTPUT_PREFIX = f"{SCRATCH_DIR}/{PHASE}/"


class _Digest(Protocol):
    def update(self, data: bytes, /) -> None: ...


def _is_git_worktree(root: Path) -> bool:
    result = git_utils.run_git(["rev-parse", "--is-inside-work-tree"], cwd=root)
    return result.returncode == 0 and result.stdout.strip() == "true"


def _is_review_output(name: str) -> bool:
    if not name.startswith(_OUTPUT_PREFIX):
        return False
    return name.endswith(LOCK_SUFFIX) or name.endswith(".md")


def _stream_git(args: list[str], root: Path, consume: Callable[[bytes], None]) -> None:
    try:
        process: subprocess.Popen[bytes] = subprocess.Popen(
            ["git", "-C", str(root), *args],
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


def _hash_untracked_path(raw_name: bytes, root: Path, digest: _Digest) -> None:
    name = os.fsdecode(raw_name)
    if _is_review_output(name):
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


def _hash_untracked_listing(args: list[str], root: Path, digest: _Digest) -> None:
    pending = bytearray()

    def consume(chunk: bytes) -> None:
        pending.extend(chunk)
        offset = 0
        while (end := pending.find(b"\0", offset)) >= 0:
            raw_name = bytes(pending[offset:end])
            if raw_name:
                _hash_untracked_path(raw_name, root, digest)
            offset = end + 1
        if offset:
            del pending[:offset]

    _stream_git(args, root, consume)
    if pending:
        _hash_untracked_path(bytes(pending), root, digest)


def _hash_untracked(root: Path, digest: _Digest) -> None:
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
    )
    _hash_untracked_listing(
        ["ls-files", "--others", "--full-name", "-z", "--", SCRATCH_DIR],
        root,
        digest,
    )


def tree_digest(root: Path) -> str | None:
    """Hash the captured Git tree and every review input."""
    if not _is_git_worktree(root):
        return None
    head = git_utils.run_git(
        ["rev-parse", "--verify", "--quiet", "HEAD"],
        cwd=root,
    )
    digest = hashlib.sha256()
    digest.update(b"age-review-lock-v2\0head\0")
    if head.returncode == 0:
        digest.update(head.stdout.strip().encode("ascii", "replace"))
    else:
        digest.update(b"<unborn>")
    digest.update(b"\0diff\0")
    diff_args = ["diff", "--no-ext-diff", "--no-color"]
    if head.returncode == 0:
        diff_args.append("HEAD")
    diff_args += [
        "--",
        ".",
        f":(exclude,glob){_OUTPUT_PREFIX}*{LOCK_SUFFIX}",
        f":(exclude,glob){_OUTPUT_PREFIX}*.md",
    ]
    _stream_git(diff_args, root, digest.update)
    _hash_untracked(root, digest)
    return digest.hexdigest()


def lock_path(*, root: Path, slug: str) -> Path:
    if not slug:
        raise cli.CliError("--slug must be non-empty")
    cli.reject_path_segment("--slug", slug)
    return root / SCRATCH_DIR / PHASE / f"{slug}{LOCK_SUFFIX}"


def capture(*, root: Path, slug: str) -> Path:
    """Record the current production-tree digest for `slug`; return the path."""
    target = lock_path(root=root, slug=slug)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {"slug": slug, "digest": tree_digest(root)}
    _ = target.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return target


def verify(*, root: Path, slug: str) -> None:
    """Raise CliError unless the tree still matches `slug`'s review lock."""
    current = tree_digest(root)
    if current is None:
        # No git work tree: no production tree to compare against.
        return
    target = lock_path(root=root, slug=slug)
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
