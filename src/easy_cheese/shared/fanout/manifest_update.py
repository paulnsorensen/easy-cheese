#!/usr/bin/env python3
"""Atomic, schema-validated updates to an /ultracook fan-out run manifest.

Commands rewrite bounded manifest state atomically:

    set-phase         --manifest <path> --phase <new-phase>
    set-curd-status   --manifest <path> --curd <id> --status <status> [--commit-sha <sha>] [review context flags]
    set-post-review   --manifest <path> <review context flags> [post-review fields]
    set-wiring-status --manifest <path> --wiring <id> --status <status> [--commit-sha <sha>]
    check-files       --manifest <path> [--root <repo-root>]

The file is rewritten via tmp-then-rename so a concurrent reader never sees a
partial document. After the rename, the manifest is re-validated in-process
via `validate_manifest.validate_run_manifest`; if it rejects the new file the
original bytes are restored from an in-memory backup and the CLI exits 2 with
the validator's error message.

An advisory lock sidecar (`fcntl.flock` on POSIX, `msvcrt.locking` on
Windows) serialises concurrent read-modify-write cycles so no update is lost.

`check-files` is read-only: it re-checks each curd's `files[]` against the
working tree at dispatch time (Phase 2 fan-out), since the decomposer's file
list may have gone stale between decomposition and dispatch. A missing path
is informational, not an error — it may be a new file the curd will create,
or a genuinely stale/renamed path — so the report is meant to travel with the
dispatch context, not block it.
"""
from __future__ import annotations

import argparse
import contextlib
import os
import tempfile
from pathlib import Path
from typing import Callable, Protocol, TextIO, cast

try:
    import fcntl  # POSIX advisory file locks
    msvcrt = None
except ImportError:  # pragma: no cover - exercised only on Windows
    fcntl = None
    import msvcrt

from easy_cheese.shared import cli  # noqa: E402
from easy_cheese.shared.manifest_io import (  # noqa: E402
    ManifestLoadError,
    parse_mapping,
)

from .validate_manifest import validate_run_manifest  # noqa: E402

# Mirror validate_manifest.PHASES — kept in sync with manifest-schema.json.
PHASES = {
    "gate_approved",
    "seed_complete",
    "curds_complete",
    "merge_complete",
    "wiring_complete",
    "final_merge_complete",
    "post_review_complete",
    "pr_publish_complete",
}
WORK_STATUSES = ("pending", "running", "completed", "failed")


# Mirrors append-attempt.py's _lock helper.
def _lock(fd: int, *, exclusive: bool) -> None:
    """Acquire (exclusive=True) or release an advisory lock on fd, cross-platform."""
    if fcntl is not None:
        fcntl.flock(fd, fcntl.LOCK_EX if exclusive else fcntl.LOCK_UN)
    else:  # pragma: no cover - Windows only
        assert msvcrt is not None
        msvcrt.locking(fd, msvcrt.LK_LOCK if exclusive else msvcrt.LK_UNLCK, 1)


# Mirrors append-attempt.py's _with_flock helper.
def _with_flock(lock_path: Path, fn: Callable[[], None]) -> None:
    """Run fn() while holding an exclusive advisory lock on lock_path.

    Uses POSIX ``fcntl.flock`` where available and falls back to
    ``msvcrt.locking`` on Windows so the concurrency guard is not silently lost.
    """
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    # O_CREAT so concurrent processes share the same lockfile inode. 0o600
    # so the lockfile is not world-readable (CodeQL py/overly-permissive-file).
    fd = os.open(str(lock_path), os.O_RDWR | os.O_CREAT, 0o600)
    try:
        _lock(fd, exclusive=True)
        fn()
    finally:
        try:
            _lock(fd, exclusive=False)
        finally:
            os.close(fd)


def _load_manifest(path: Path) -> tuple[dict[str, object], bytes]:
    """Return (parsed mapping, original bytes for restore on failure)."""
    try:
        original = path.read_bytes()
    except FileNotFoundError as exc:
        raise cli.CliError(f"manifest not found: {path}") from exc
    try:
        data = parse_mapping(original.decode("utf-8"), str(path))
    except ManifestLoadError as exc:
        raise cli.CliError(str(exc)) from exc
    return data, original


def _is_json(original: bytes) -> bool:
    import json as _json
    try:
        _json.loads(original.decode("utf-8"))
        return True
    except (ValueError, UnicodeDecodeError):
        return False


def _atomic_write(path: Path, data: dict[str, object], *, as_json: bool) -> None:
    """Dump data to a unique sibling tmp then rename. tmp is removed on failure.

    Writes JSON when `as_json` is True, YAML otherwise (lazy import).
    The tmp suffix is per-process so two concurrent writers don't collide on
    the same tmp path (which would race the rename).
    """
    if as_json:
        import json
        text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    else:
        try:
            import yaml
        except ImportError as exc:
            raise cli.CliError("PyYAML is required for YAML manifests") from exc
        text = yaml.safe_dump(data, sort_keys=False, default_flow_style=False)
    fd, tmp_name = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=str(path.parent)
    )
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            _ = handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        _ = tmp.replace(path)
    except Exception:
        if tmp.exists():
            with contextlib.suppress(OSError):
                tmp.unlink()
        raise


def _revalidate_or_restore(path: Path, original: bytes) -> None:
    """Re-validate the written manifest in-process; restore <path> on failure."""
    try:
        reparsed, _ = _load_manifest(path)
        errors = validate_run_manifest(reparsed)
    except cli.CliError as exc:
        errors = [str(exc)]
    if errors:
        fd, tmp_name = tempfile.mkstemp(
            prefix=path.name + ".restore.", suffix=".tmp", dir=str(path.parent)
        )
        tmp = Path(tmp_name)
        try:
            with os.fdopen(fd, "wb") as handle:
                _ = handle.write(original)
            _ = tmp.replace(path)
        except Exception:
            if tmp.exists():
                with contextlib.suppress(OSError):
                    tmp.unlink()
            raise
        raise cli.CliError(f"validation rejected update; restored original ({errors[-1]})")


def _commit(path: Path, data: dict[str, object], original: bytes) -> None:
    _atomic_write(path, data, as_json=_is_json(original))
    _revalidate_or_restore(path, original)

# ----- subcommand handlers -------------------------------------------------


class _SetPhaseArgs(Protocol):
    manifest: str
    phase: str
    stdout: TextIO


def cmd_set_phase(args: _SetPhaseArgs) -> None:
    if args.phase not in PHASES:
        raise cli.CliError(f"invalid phase {args.phase!r}; expected one of {sorted(PHASES)}")
    path = Path(args.manifest)
    lock = path.parent / ("." + path.name + ".lock")

    def _body() -> None:
        data, original = _load_manifest(path)
        data["phase"] = args.phase
        _commit(path, data, original)

    _with_flock(lock, _body)
    cli.emit(f"phase set to {args.phase}", stdout=args.stdout)


def _find_curd(data: dict[str, object], curd_id: int) -> dict[str, object]:
    curds = data.get("curds")
    if not isinstance(curds, list):
        raise cli.CliError("manifest has no curds list")
    items = cast("list[object]", curds)
    for entry in items:
        if not isinstance(entry, dict):
            continue
        entry_dict = cast("dict[str, object]", entry)
        if entry_dict.get("id") == curd_id:
            return entry_dict
    raise cli.CliError(f"curd id {curd_id} not found")


class _SetCurdStatusArgs(Protocol):
    manifest: str
    curd: int
    status: str
    commit_sha: str | None
    base_commit: str | None
    reviewed_tree_oid: str | None
    diff_hash: str | None
    scope: list[str] | None
    stdout: TextIO


def cmd_set_curd_status(args: _SetCurdStatusArgs) -> None:
    if args.status not in WORK_STATUSES:
        raise cli.CliError(f"invalid status {args.status!r}; expected one of {list(WORK_STATUSES)}")
    path = Path(args.manifest)
    lock = path.parent / ("." + path.name + ".lock")

    def _body() -> None:
        data, original = _load_manifest(path)
        curd = _find_curd(data, args.curd)
        review_values = (args.base_commit, args.reviewed_tree_oid, args.diff_hash, args.scope)
        if any(value is not None for value in review_values):
            if any(value is None for value in review_values):
                raise cli.CliError(
                    "review context requires --base-commit, --reviewed-tree-oid, "
                    + "--diff-hash, and at least one --scope"
                )
            curd["review_context"] = {
                "base_commit": args.base_commit,
                "reviewed_tree_oid": args.reviewed_tree_oid,
                "diff_hash": args.diff_hash,
                "scope": args.scope,
            }
        curd["status"] = args.status
        if args.commit_sha is not None:
            curd["commit_sha"] = args.commit_sha
        _commit(path, data, original)

    _with_flock(lock, _body)
    cli.emit(f"curd {args.curd} status set to {args.status}", stdout=args.stdout)


class _SetPostReviewArgs(Protocol):
    manifest: str
    base_commit: str
    reviewed_tree_oid: str
    diff_hash: str
    scope: list[str]
    press_slug: str | None
    age_slug: str | None
    cure_slug: str | None
    findings_applied: int | None
    findings_deferred: int | None
    stdout: TextIO


def cmd_set_post_review(args: _SetPostReviewArgs) -> None:
    path = Path(args.manifest)
    lock = path.parent / ("." + path.name + ".lock")

    def _body() -> None:
        data, original = _load_manifest(path)
        context = {
            "base_commit": args.base_commit,
            "reviewed_tree_oid": args.reviewed_tree_oid,
            "diff_hash": args.diff_hash,
            "scope": args.scope,
        }
        data["current_review"] = context
        existing = data.get("post_review")
        existing_dict = cast("dict[str, object]", existing) if isinstance(existing, dict) else {}
        post_review: dict[str, object] = dict(existing_dict)
        post_review["review_context"] = {**context, "scope": list(args.scope)}
        if args.press_slug is not None:
            post_review["press_slug"] = args.press_slug
        if args.age_slug is not None:
            post_review["age_slug"] = args.age_slug
        if args.cure_slug is not None:
            post_review["cure_slug"] = args.cure_slug
        if args.findings_applied is not None:
            post_review["findings_applied"] = args.findings_applied
        if args.findings_deferred is not None:
            post_review["findings_deferred"] = args.findings_deferred
        data["post_review"] = post_review
        _commit(path, data, original)

    _with_flock(lock, _body)
    cli.emit("post-merge review identity recorded", stdout=args.stdout)


def _find_wiring(data: dict[str, object], wiring_id: str) -> dict[str, object]:
    wiring = data.get("wiring")
    if not isinstance(wiring, list):
        raise cli.CliError("manifest has no wiring list")
    items = cast("list[object]", wiring)
    for entry in items:
        if not isinstance(entry, dict):
            continue
        entry_dict = cast("dict[str, object]", entry)
        if entry_dict.get("id") == wiring_id:
            return entry_dict
    raise cli.CliError(f"wiring id {wiring_id!r} not found")


class _SetWiringStatusArgs(Protocol):
    manifest: str
    wiring: str
    status: str
    commit_sha: str | None
    stdout: TextIO


def cmd_set_wiring_status(args: _SetWiringStatusArgs) -> None:
    if args.status not in WORK_STATUSES:
        raise cli.CliError(f"invalid status {args.status!r}; expected one of {list(WORK_STATUSES)}")
    path = Path(args.manifest)
    lock = path.parent / ("." + path.name + ".lock")

    def _body() -> None:
        data, original = _load_manifest(path)
        wiring = _find_wiring(data, args.wiring)
        wiring["status"] = args.status
        if args.commit_sha is not None:
            wiring["commit_sha"] = args.commit_sha
        _commit(path, data, original)

    _with_flock(lock, _body)
    cli.emit(f"wiring {args.wiring} status set to {args.status}", stdout=args.stdout)


class _CheckFilesArgs(Protocol):
    manifest: str
    root: str | None
    json_mode: bool
    stdout: TextIO


def cmd_check_files(args: _CheckFilesArgs) -> None:
    path = Path(args.manifest)
    data, _ = _load_manifest(path)
    if args.root and not Path(args.root).is_dir():
        raise cli.CliError(f"root is not a directory: {args.root}")
    root = Path(args.root) if args.root else Path.cwd()
    curds = data.get("curds")
    if not isinstance(curds, list):
        raise cli.CliError("manifest has no curds list")

    stale: dict[str, list[str]] = {}
    for entry in cast("list[object]", curds):
        if not isinstance(entry, dict):
            continue
        entry_dict = cast("dict[str, object]", entry)
        files = entry_dict.get("files")
        if not isinstance(files, list):
            continue
        file_items = cast("list[object]", files)
        missing = [f for f in file_items if isinstance(f, str) and not (root / f).is_file()]
        if missing:
            stale[str(entry_dict.get("id"))] = missing

    if args.json_mode:
        cli.emit(stale, json_mode=True, stdout=args.stdout)
        return
    if not stale:
        cli.emit("all curd files present in the working tree", stdout=args.stdout)
        return
    for curd_id, missing in stale.items():
        cli.emit(
            f"curd {curd_id}: not found in working tree — {', '.join(missing)} "
            + "(may be new files the curd creates, or a stale decomposition path; "
            + "pass this along as dispatch context)",
            stdout=args.stdout,
        )


# ----- argparse wiring -----------------------------------------------------


def _setup(parser: argparse.ArgumentParser) -> None:
    subs = parser.add_subparsers(dest="cmd")

    sp = subs.add_parser("set-phase", help="update top-level phase")
    _ = sp.add_argument("--manifest", required=True)
    _ = sp.add_argument("--phase", required=True)
    sp.set_defaults(func=cmd_set_phase)

    sc = subs.add_parser("set-curd-status", help="update one curd's status")
    _ = sc.add_argument("--manifest", required=True)
    _ = sc.add_argument("--curd", required=True, type=int)
    _ = sc.add_argument("--status", required=True)
    _ = sc.add_argument("--commit-sha", default=None)
    _ = sc.add_argument("--base-commit", default=None)
    _ = sc.add_argument("--reviewed-tree-oid", default=None)
    _ = sc.add_argument("--diff-hash", default=None)
    _ = sc.add_argument("--scope", action="append", default=None)
    sc.set_defaults(func=cmd_set_curd_status)

    sr = subs.add_parser(
        "set-post-review", help="atomically record final post-merge review identity"
    )
    _ = sr.add_argument("--manifest", required=True)
    _ = sr.add_argument("--base-commit", required=True)
    _ = sr.add_argument("--reviewed-tree-oid", required=True)
    _ = sr.add_argument("--diff-hash", required=True)
    _ = sr.add_argument("--scope", action="append", required=True)
    _ = sr.add_argument("--press-slug", default=None)
    _ = sr.add_argument("--age-slug", default=None)
    _ = sr.add_argument("--cure-slug", default=None)
    _ = sr.add_argument("--findings-applied", type=int, default=None)
    _ = sr.add_argument("--findings-deferred", type=int, default=None)
    sr.set_defaults(func=cmd_set_post_review)

    sw = subs.add_parser("set-wiring-status", help="update one wiring row's status")
    _ = sw.add_argument("--manifest", required=True)
    _ = sw.add_argument("--wiring", required=True)
    _ = sw.add_argument("--status", required=True)
    _ = sw.add_argument("--commit-sha", default=None)
    sw.set_defaults(func=cmd_set_wiring_status)

    scf = subs.add_parser(
        "check-files", help="re-validate curd file lists against the working tree at dispatch time"
    )
    _ = scf.add_argument("--manifest", required=True)
    _ = scf.add_argument("--root", default=None, help="repo root to resolve relative paths against (default: cwd)")
    scf.set_defaults(func=cmd_check_files)


def main(argv: list[str]) -> int:
    return cli.run(_setup, argv=argv)


if __name__ == "__main__":
    raise SystemExit(cli.run(_setup))
