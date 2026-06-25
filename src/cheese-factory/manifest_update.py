#!/usr/bin/env python3
"""Atomic, schema-validated updates to a cheese-factory run manifest.

Three subcommands rewrite one field at a time:

    set-phase         --manifest <path> --phase <new-phase>
    set-curd-status   --manifest <path> --curd <id> --status <status> [--commit-sha <sha>]
    set-wiring-status --manifest <path> --wiring <id> --status <status> [--commit-sha <sha>]

The file is rewritten via tmp-then-rename so a concurrent reader never sees a
partial document. After the rename, the manifest is re-validated in-process
via `validate_manifest.validate_run_manifest`; if it rejects the new file the
original bytes are restored from an in-memory backup and the CLI exits 2 with
the validator's error message.

An advisory lock sidecar (`fcntl.flock` on POSIX, `msvcrt.locking` on
Windows) serialises concurrent read-modify-write cycles so no update is lost.
"""
from __future__ import annotations

import argparse
import os
import tempfile
from pathlib import Path
from typing import Any

try:
    import fcntl  # POSIX advisory file locks
except ImportError:  # pragma: no cover - exercised only on Windows
    fcntl = None
    import msvcrt

import cli  # noqa: E402
from manifest_io import ManifestLoadError, parse_mapping  # noqa: E402
from validate_manifest import validate_run_manifest  # noqa: E402

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
        msvcrt.locking(fd, msvcrt.LK_LOCK if exclusive else msvcrt.LK_UNLCK, 1)


# Mirrors append-attempt.py's _with_flock helper.
def _with_flock(lock_path: Path, fn) -> None:
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


def _load_manifest(path: Path) -> tuple[dict[str, Any], bytes]:
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


def _atomic_write(path: Path, data: dict[str, Any], *, as_json: bool) -> None:
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
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except Exception:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                # tmpfile is gone or already locked; nothing to undo. Swallow
                # so the original write error propagates uncovered.
                pass
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
                handle.write(original)
            os.replace(tmp, path)
        except Exception:
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass
            raise
        raise cli.CliError(f"validation rejected update; restored original ({errors[-1]})")


def _commit(path: Path, data: dict[str, Any], original: bytes) -> None:
    _atomic_write(path, data, as_json=_is_json(original))
    _revalidate_or_restore(path, original)

# ----- subcommand handlers -------------------------------------------------


def cmd_set_phase(args: argparse.Namespace) -> None:
    if args.phase not in PHASES:
        raise cli.CliError(f"invalid phase {args.phase!r}; expected one of {sorted(PHASES)}")
    path = Path(args.manifest)
    lock = path.parent / ("." + path.name + ".lock")

    def _body() -> None:
        data, original = _load_manifest(path)
        data["phase"] = args.phase
        _commit(path, data, original)

    _with_flock(lock, _body)
    cli.emit(f"phase set to {args.phase}")


def _find_curd(data: dict[str, Any], curd_id: int) -> dict[str, Any]:
    curds = data.get("curds")
    if not isinstance(curds, list):
        raise cli.CliError("manifest has no curds list")
    for entry in curds:
        if isinstance(entry, dict) and entry.get("id") == curd_id:
            return entry
    raise cli.CliError(f"curd id {curd_id} not found")


def cmd_set_curd_status(args: argparse.Namespace) -> None:
    if args.status not in WORK_STATUSES:
        raise cli.CliError(f"invalid status {args.status!r}; expected one of {list(WORK_STATUSES)}")
    path = Path(args.manifest)
    lock = path.parent / ("." + path.name + ".lock")

    def _body() -> None:
        data, original = _load_manifest(path)
        curd = _find_curd(data, args.curd)
        curd["status"] = args.status
        if args.commit_sha is not None:
            curd["commit_sha"] = args.commit_sha
        _commit(path, data, original)

    _with_flock(lock, _body)
    cli.emit(f"curd {args.curd} status set to {args.status}")


def _find_wiring(data: dict[str, Any], wiring_id: str) -> dict[str, Any]:
    wiring = data.get("wiring")
    if not isinstance(wiring, list):
        raise cli.CliError("manifest has no wiring list")
    for entry in wiring:
        if isinstance(entry, dict) and entry.get("id") == wiring_id:
            return entry
    raise cli.CliError(f"wiring id {wiring_id!r} not found")


def cmd_set_wiring_status(args: argparse.Namespace) -> None:
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
    cli.emit(f"wiring {args.wiring} status set to {args.status}")


# ----- argparse wiring -----------------------------------------------------


def _setup(parser: argparse.ArgumentParser) -> None:
    subs = parser.add_subparsers(dest="cmd")

    sp = subs.add_parser("set-phase", help="update top-level phase")
    sp.add_argument("--manifest", required=True)
    sp.add_argument("--phase", required=True)
    sp.set_defaults(func=cmd_set_phase)

    sc = subs.add_parser("set-curd-status", help="update one curd's status")
    sc.add_argument("--manifest", required=True)
    sc.add_argument("--curd", required=True, type=int)
    sc.add_argument("--status", required=True)
    sc.add_argument("--commit-sha", default=None)
    sc.set_defaults(func=cmd_set_curd_status)

    sw = subs.add_parser("set-wiring-status", help="update one wiring row's status")
    sw.add_argument("--manifest", required=True)
    sw.add_argument("--wiring", required=True)
    sw.add_argument("--status", required=True)
    sw.add_argument("--commit-sha", default=None)
    sw.set_defaults(func=cmd_set_wiring_status)


if __name__ == "__main__":
    cli.run(_setup)
