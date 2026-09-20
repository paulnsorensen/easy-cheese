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

The lock also records a source-only digest and a hash for each review input. They
never decide the gate. They let a refusal say which side moved and name the
file. When only review evidence moved, ``review-lock --refresh-evidence``
captures the lock again. It refuses when the source digest differs, so it cannot
hide an inline fix.

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
import contextlib
import hashlib
import json
import os
import stat
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
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
        with contextlib.suppress(OSError):
            process.kill()
        _ = process.wait()
        raise
    finally:
        stdout.close()
        stderr_stream.close()
    if returncode != 0:
        detail = stderr.decode("utf-8", "replace").strip()
        raise cli.CliError(f"git {' '.join(args)} failed: {detail}")


def _open_regular(path: Path) -> tuple[int, os.stat_result]:
    try:
        handle = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    except OSError as exc:
        raise cli.CliError(f"cannot open evidence path {path}: {exc}") from exc
    try:
        metadata = os.fstat(handle)
    except OSError:
        os.close(handle)
        raise
    if not stat.S_ISREG(metadata.st_mode):
        os.close(handle)
        raise cli.CliError(f"refusing to hash non-regular evidence path {path}")
    return handle, metadata


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
        metadata = os.lstat(path)
        digest.update(b"mode\0")
        digest.update(_evidence_mode(metadata.st_mode).encode("ascii"))
        digest.update(b"\0")
        if stat.S_ISLNK(metadata.st_mode):
            digest.update(b"link\0")
            digest.update(os.fsencode(os.readlink(path)))
        else:
            digest.update(b"file\0")
            handle, _metadata = _open_regular(path)
            with os.fdopen(handle, "rb") as stream:
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


def _hash_untracked(
    root: Path, digest: _Digest, slug: str, *, evidence: bool = True
) -> None:
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
    if not evidence:
        return
    _hash_untracked_listing(
        ["ls-files", "--others", "--full-name", "-z", "--", SCRATCH_DIR],
        root,
        digest,
        slug,
    )


def _hash_source_tree(root: Path, digest: _Digest) -> None:
    pending = bytearray()

    def consume(chunk: bytes) -> None:
        pending.extend(chunk)
        offset = 0
        while (end := pending.find(b"\0", offset)) >= 0:
            entry = bytes(pending[offset:end])
            if b"\t" in entry and not entry.split(b"\t", 1)[1].startswith(
                f"{SCRATCH_DIR}/".encode()
            ):
                digest.update(entry + b"\0")
            offset = end + 1
        if offset:
            del pending[:offset]

    _stream_git(["ls-tree", "-r", "-z", "--full-tree", "HEAD"], root, consume)
    if pending and not bytes(pending).split(b"\t", 1)[1].startswith(
        f"{SCRATCH_DIR}/".encode()
    ):
        digest.update(bytes(pending))


def tree_digest(root: Path, *, slug: str, evidence: bool = True) -> str | None:
    """Hash the captured git tree and, with `evidence`, every review input for `slug`."""
    top = repo_root(root)
    if top is None:
        return None
    head = _run_git(["rev-parse", "--verify", "--quiet", "HEAD"], top)
    if head.returncode not in (0, 1):
        raise cli.CliError(
            f"cannot read HEAD in {top}: {head.stderr.strip() or head.returncode}"
        )
    digest = hashlib.sha256()
    if evidence:
        digest.update(b"age-review-lock-v3\0head\0")
        if head.returncode == 0:
            digest.update(head.stdout.strip().encode("ascii", "replace"))
        else:
            digest.update(b"<unborn>")
    else:
        digest.update(b"age-review-lock-v4\0source-tree\0")
        if head.returncode == 0:
            _hash_source_tree(top, digest)
        else:
            digest.update(b"<unborn>")
    excludes = _exclude_pathspecs(slug)
    if not evidence:
        excludes.append(f":(exclude,glob){SCRATCH_DIR}/**")
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
    _hash_untracked(top, digest, slug, evidence=evidence)
    return digest.hexdigest()


def _evidence_mode(mode: int) -> str:
    return format(stat.S_IFMT(mode) | stat.S_IMODE(mode), "06o")


def _stream_regular(path: Path) -> tuple[os.stat_result, str]:
    handle, metadata = _open_regular(path)
    digest = hashlib.sha256()
    with os.fdopen(handle, "rb") as stream:
        while chunk := stream.read(_GIT_CHUNK_SIZE):
            digest.update(chunk)
    return metadata, digest.hexdigest()


def _evidence_identity(path: Path) -> str:
    try:
        metadata = os.lstat(path)
        if stat.S_ISLNK(metadata.st_mode):
            return f"mode:{_evidence_mode(metadata.st_mode)}:link:{os.readlink(path)}"
        if not stat.S_ISREG(metadata.st_mode):
            return "absent"
        metadata, content_digest = _stream_regular(path)
    except FileNotFoundError:
        return "absent"
    return f"mode:{_evidence_mode(metadata.st_mode)}:sha256:{content_digest}"


def _evidence_files(root: Path, slug: str) -> dict[str, str]:
    """Hash each review input under `.cheese/`, so a mismatch can name the file."""
    if repo_root(root) is None:
        return {}
    pending = bytearray()
    raw_names: list[bytes] = []

    def consume(chunk: bytes) -> None:
        pending.extend(chunk)
        offset = 0
        while (end := pending.find(b"\0", offset)) >= 0:
            raw_name = bytes(pending[offset:end])
            if raw_name:
                raw_names.append(raw_name)
            offset = end + 1
        if offset:
            del pending[:offset]

    _stream_git(
        ["ls-files", "--cached", "--others", "--full-name", "-z", "--", SCRATCH_DIR],
        root,
        consume,
    )
    if pending:
        raw_names.append(bytes(pending))
    files: dict[str, str] = {}
    for raw_name in raw_names:
        name = os.fsdecode(raw_name)
        if _is_review_output(name, slug):
            continue
        path = root / name
        try:
            files[name] = _evidence_identity(path)
        except OSError as exc:
            display = os.fsencode(name).decode("utf-8", "backslashreplace")
            raise cli.CliError(f"cannot hash review input {display!r}: {exc}") from exc
    return files


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


@dataclass(frozen=True)
class _ReviewLock:
    slug: str | None
    digest: str
    source_digest: str | None
    evidence_files: Mapping[str, str] | None


def _capture_payload(root: Path, slug: str) -> dict[str, object]:
    source_before = tree_digest(root, slug=slug, evidence=False)
    payload: dict[str, object] = {
        "slug": slug,
        "digest": tree_digest(root, slug=slug),
        # The two fields below only explain a mismatch. `digest` decides it.
        "source_digest": source_before,
        "evidence_files": _evidence_files(root, slug),
    }
    source_after = tree_digest(root, slug=slug, evidence=False)
    if source_before != source_after:
        raise cli.CliError(
            f"the source tree changed while capturing {slug!r}; capture the review lock again"
        )
    payload["source_digest"] = source_after
    return payload


def _write_payload(target: Path, payload: dict[str, object]) -> None:
    _write_no_follow(target, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def capture(*, root: Path, slug: str) -> Path:
    """Record the current production-tree digest for `slug`; return the path."""
    top = repo_root(root) or root
    target = lock_path(root=top, slug=slug)
    target.parent.mkdir(parents=True, exist_ok=True)
    _reject_symlink_components(top, target)
    _write_payload(target, _capture_payload(top, slug))
    return target


def _read_lock(target: Path, slug: str) -> _ReviewLock:
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
    fields = cast("dict[str, object]", payload) if isinstance(payload, dict) else {}
    digest = fields.get("digest")
    if not isinstance(digest, str):
        raise cli.CliError(
            f"review lock {target} recorded no digest: re-run `{_LOCK_COMMAND} {slug}` "
            + "from inside the git work tree under review."
        )
    lock_slug = fields.get("slug")
    if lock_slug is not None and not isinstance(lock_slug, str):
        raise cli.CliError(f"review lock {target} has invalid slug")
    source_digest = fields.get("source_digest")
    if source_digest is not None and not isinstance(source_digest, str):
        raise cli.CliError(f"review lock {target} has invalid source_digest")
    evidence_value = fields.get("evidence_files")
    evidence_files: Mapping[str, str] | None = None
    if evidence_value is not None:
        if not isinstance(evidence_value, dict):
            raise cli.CliError(f"review lock {target} has invalid evidence_files")
        validated: dict[str, str] = {}
        for name, value in cast(dict[object, object], evidence_value).items():
            if not isinstance(name, str) or not isinstance(value, str):
                raise cli.CliError(f"review lock {target} has invalid evidence_files")
            validated[name] = value
        evidence_files = MappingProxyType(validated)
    return _ReviewLock(
        slug=lock_slug,
        digest=digest,
        source_digest=source_digest,
        evidence_files=evidence_files,
    )


def verify(*, root: Path, slug: str) -> None:
    """Raise CliError unless the tree still matches `slug`'s review lock."""
    top = repo_root(root)
    if top is None:
        # No git work tree: no production tree to compare against.
        return
    # Validate the lock before the digest: a missing lock must not pay for the
    # git walk first.
    payload = _read_lock(lock_path(root=top, slug=slug), slug)
    if payload.digest == tree_digest(top, slug=slug):
        return
    if payload.source_digest == tree_digest(top, slug=slug, evidence=False):
        before = payload.evidence_files or {}
        after = _evidence_files(top, slug)
        moved = sorted(
            name for name in before.keys() | after.keys() if before.get(name) != after.get(name)
        )
        raise cli.CliError(
            f"review evidence changed after {slug!r}'s review lock, and the source tree "
            + f"did not: {', '.join(moved) or 'unknown file'}. Write the packet and every "
            + "other .cheese/ input before the lock. To continue this review, run "
            + f"`{_LOCK_COMMAND} {slug} --refresh-evidence`, then write the report again."
        )
    raise cli.CliError(
        f"the production tree changed after {slug!r}'s review lock: /age does not "
        + "apply fixes — invoke /cure with the findings instead. If the change came "
        + f"from outside this review, re-run `{_LOCK_COMMAND} {slug}` and review again. "
        + "Run `git status --short` to see the changed files."
    )


def refresh_evidence(*, root: Path, slug: str) -> Path:
    """Capture the lock again after review evidence moved; refuse a source change.

    The source digest must equal the locked one, so this command cannot hide an
    inline fix.
    """
    top = repo_root(root) or root
    payload = _read_lock(lock_path(root=top, slug=slug), slug)
    locked_source = payload.source_digest
    if locked_source is None:
        raise cli.CliError(
            f"review lock for {slug!r} recorded no source digest: "
            + f"re-run `{_LOCK_COMMAND} {slug}` and review again."
        )
    locked_files = payload.evidence_files
    if locked_files is None:
        raise cli.CliError(
            f"review lock for {slug!r} recorded no evidence files: "
            + f"re-run `{_LOCK_COMMAND} {slug}` and review again."
        )
    candidate = _capture_payload(top, slug)
    if locked_source != candidate["source_digest"]:
        raise cli.CliError(
            f"the source tree changed after {slug!r}'s review lock, so the evidence "
            + "refresh is refused: /age does not apply fixes — invoke /cure with the "
            + "findings instead. Run `git status --short` to see the changed files."
        )
    candidate_files = cast("dict[str, str]", candidate["evidence_files"])
    moved = sorted(
        name
        for name in locked_files
        if candidate_files.get(name) != locked_files[name]
    )
    packet_name = f"{_OUTPUT_PREFIX}{slug}-packet.md"
    unexpected = sorted(set(candidate_files) - set(locked_files) - {packet_name})
    if moved or unexpected:
        changed = [*moved, *unexpected]
        display = ", ".join(
            os.fsencode(name).decode("utf-8", "backslashreplace") for name in changed
        )
        raise cli.CliError(
            f"review evidence changed after {slug!r}'s review lock, so the evidence "
            + f"refresh is refused: {display}. Require a fresh review."
        )
    target = lock_path(root=top, slug=slug)
    _write_payload(target, candidate)
    return target


def _cmd_lock(args: argparse.Namespace) -> None:
    root = Path(cast("str | None", args.root) or Path.cwd())
    slug = cast(str, args.slug)
    if cast(bool, args.refresh_evidence):
        target = refresh_evidence(root=root, slug=slug)
    else:
        target = capture(root=root, slug=slug)
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
    _ = parser.add_argument(
        "--refresh-evidence",
        action="store_true",
        help=(
            "capture the lock again after a file under .cheese/ moved; "
            "refused when the source tree differs from the existing lock"
        ),
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
    # The gate and the writer must read one argv, so repair it before the gate.
    argv = cli.repair_argv(write_handoff_artifact.setup_parser, argv)
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
