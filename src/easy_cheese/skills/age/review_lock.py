"""Review-only gate for /age: prove the production tree did not move.

`/age` reviews; `/cure` applies. That boundary lived only in prose, and the
model routinely continued into repair inside the review context instead of
invoking `/cure` (issue #552). This module turns it into a precondition on
age's terminal act — writing `.cheese/age/<slug>.md`.

Step 1 of the age flow records a digest of the production tree
(``review-lock``); the report write recomputes it and refuses when it differs.
Applying a fix inline moves the digest, so the report cannot be written from a
context that applied one.

Digest scope: tracked-file content (``git diff`` against ``HEAD``) plus
untracked-file paths and content. Both checks exclude ``.cheese/``, which is the
phase's own scratch directory. Outside a git work tree, no production tree
exists for comparison, so both
capture and verification degrade to a no-op rather than blocking the review.

The gate raises the cost of the boundary; it does not make it unbypassable. An
agent that captures the lock *after* editing still passes. What it removes is
the silent path: skipping the lock now fails the write with an instruction.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import TextIO, cast

from easy_cheese.shared import cli, git_utils, write_handoff_artifact

PHASE = "age"
SCRATCH_DIR = ".cheese"
LOCK_SUFFIX = ".review-lock.json"
_LOCK_COMMAND = "python3 skills/age/scripts/age.pyz review-lock --slug"


def _is_git_worktree(root: Path) -> bool:
    result = git_utils.run_git(["rev-parse", "--is-inside-work-tree"], cwd=root)
    return result.returncode == 0 and result.stdout.strip() == "true"


def _git_text(args: list[str], root: Path) -> str:
    result = git_utils.run_git(args, cwd=root)
    if result.returncode != 0:
        raise cli.CliError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def tree_digest(root: Path) -> str | None:
    """sha256 over the production tree, or None outside a git work tree."""
    if not _is_git_worktree(root):
        return None
    exclude = f":(exclude){SCRATCH_DIR}"
    head_exists = (
        git_utils.run_git(["rev-parse", "--verify", "--quiet", "HEAD"], cwd=root).returncode == 0
    )
    diff_args = ["diff", "--no-ext-diff", "--no-color"]
    if head_exists:
        diff_args.append("HEAD")
    diff_args += ["--", ".", exclude]
    tracked = _git_text(diff_args, root)
    untracked = _git_text(
        ["ls-files", "--others", "--exclude-standard", "-z", "--", ".", exclude],
        root,
    )
    digest = hashlib.sha256()
    digest.update(tracked.encode("utf-8", "replace"))
    digest.update(b"\x00")
    for name in sorted(filter(None, untracked.split("\x00"))):
        digest.update(name.encode("utf-8", "replace"))
        digest.update(b"\x00")
        path = root / name
        try:
            if path.is_symlink():
                digest.update(b"link\x00")
                digest.update(str(path.readlink()).encode("utf-8", "replace"))
            else:
                digest.update(b"file\x00")
                with path.open("rb") as stream:
                    while chunk := stream.read(128 * 1024):
                        digest.update(chunk)
        except OSError as exc:
            raise cli.CliError(f"cannot hash untracked path {name!r}: {exc}") from exc
        digest.update(b"\x00")
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
    locked = cast("dict[str, object]", payload).get("digest") if isinstance(payload, dict) else None
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
    _ = parser.add_argument("--slug", required=True, help="review slug (lock filename stem)")
    _ = parser.add_argument(
        "--root", default=None, help="repo root (default: cwd); the lock lands under .cheese/age/"
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
