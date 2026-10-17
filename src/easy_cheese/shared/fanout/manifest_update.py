#!/usr/bin/env python3
"""Atomic, schema-validated updates to an /ultracook fan-out run manifest.

CLI:

    manifest_update set-phase         --manifest <path> --phase <new-phase>
    manifest_update set-curd-status   --manifest <path> --curd <id> --status <status> [--commit-sha <sha>] [review context flags]
    manifest_update set-post-review   --manifest <path> <review context flags> [post-review fields]
    manifest_update set-wiring-status --manifest <path> --wiring <id> --status <status> [--commit-sha <sha>]
    manifest_update check-files       --manifest <path> [--root <repo-root>]

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

import contextlib
import os
import tempfile
from pathlib import Path
from typing import Callable, cast

import fromargs

try:
    import fcntl  # POSIX advisory file locks
    msvcrt = None
except ImportError:  # pragma: no cover - exercised only on Windows
    fcntl = None
    import msvcrt

from easy_cheese.shared.manifest_io import (
    ManifestLoadError,
    parse_mapping,
)

from .validate_manifest import validate_run_manifest

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
        raise fromargs.CliError(f"manifest not found: {path}") from exc
    try:
        data = parse_mapping(original.decode("utf-8"), str(path))
    except ManifestLoadError as exc:
        raise fromargs.CliError(str(exc)) from exc
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
            raise fromargs.CliError("PyYAML is required for YAML manifests") from exc
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
    except fromargs.CliError as exc:
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
        raise fromargs.CliError(f"validation rejected update; restored original ({errors[-1]})")


def _commit(path: Path, data: dict[str, object], original: bytes) -> None:
    _atomic_write(path, data, as_json=_is_json(original))
    _revalidate_or_restore(path, original)

# ----- subcommand handlers -------------------------------------------------


def _find_curd(data: dict[str, object], curd_id: int) -> dict[str, object]:
    curds = data.get("curds")
    if not isinstance(curds, list):
        raise fromargs.CliError("manifest has no curds list")
    items = cast("list[object]", curds)
    for entry in items:
        if not isinstance(entry, dict):
            continue
        entry_dict = cast("dict[str, object]", entry)
        if entry_dict.get("id") == curd_id:
            return entry_dict
    raise fromargs.CliError(f"curd id {curd_id} not found")


def _find_wiring(data: dict[str, object], wiring_id: str) -> dict[str, object]:
    wiring = data.get("wiring")
    if not isinstance(wiring, list):
        raise fromargs.CliError("manifest has no wiring list")
    items = cast("list[object]", wiring)
    for entry in items:
        if not isinstance(entry, dict):
            continue
        entry_dict = cast("dict[str, object]", entry)
        if entry_dict.get("id") == wiring_id:
            return entry_dict
    raise fromargs.CliError(f"wiring id {wiring_id!r} not found")


def set_phase(*, manifest: str, phase: str) -> dict[str, object]:
    """Update the manifest's top-level phase.

    Parameters
    ----------
    manifest
        Path to the run manifest file.
    phase
        New phase; must be one of the known fan-out phases.
    """
    if phase not in PHASES:
        raise fromargs.CliError(f"invalid phase {phase!r}; expected one of {sorted(PHASES)}")
    path = Path(manifest)
    lock = path.parent / ("." + path.name + ".lock")

    def _body() -> None:
        data, original = _load_manifest(path)
        data["phase"] = phase
        _commit(path, data, original)

    _with_flock(lock, _body)
    return {"manifest": manifest, "phase": phase}


def set_curd_status(
    *,
    manifest: str,
    curd: int,
    status: str,
    commit_sha: str | None = None,
    base_commit: str | None = None,
    reviewed_tree_oid: str | None = None,
    diff_hash: str | None = None,
    scope: list[str] | None = None,
) -> dict[str, object]:
    """Update one curd's status, and optionally its commit sha and review context.

    Parameters
    ----------
    manifest
        Path to the run manifest file.
    curd
        Curd id to update.
    status
        New status; must be one of the known work statuses.
    commit_sha
        Commit sha to record on the curd, if any.
    base_commit
        Review context base commit sha; requires the other review flags.
    reviewed_tree_oid
        Review context reviewed tree oid; requires the other review flags.
    diff_hash
        Review context diff hash; requires the other review flags.
    scope
        Review context scope paths (repeatable); requires the other review flags.
    """
    if status not in WORK_STATUSES:
        raise fromargs.CliError(f"invalid status {status!r}; expected one of {list(WORK_STATUSES)}")
    path = Path(manifest)
    lock = path.parent / ("." + path.name + ".lock")

    def _body() -> None:
        data, original = _load_manifest(path)
        curd_entry = _find_curd(data, curd)
        review_values = (base_commit, reviewed_tree_oid, diff_hash, scope)
        if any(value is not None for value in review_values):
            if any(value is None for value in review_values):
                raise fromargs.CliError(
                    "review context requires --base-commit, --reviewed-tree-oid, "
                    + "--diff-hash, and at least one --scope"
                )
            curd_entry["review_context"] = {
                "base_commit": base_commit,
                "reviewed_tree_oid": reviewed_tree_oid,
                "diff_hash": diff_hash,
                "scope": scope,
            }
        curd_entry["status"] = status
        if commit_sha is not None:
            curd_entry["commit_sha"] = commit_sha
        _commit(path, data, original)

    _with_flock(lock, _body)
    return {"manifest": manifest, "curd": curd, "status": status}


def set_post_review(
    *,
    manifest: str,
    base_commit: str,
    reviewed_tree_oid: str,
    diff_hash: str,
    scope: list[str],
    press_slug: str | None = None,
    age_slug: str | None = None,
    cure_slug: str | None = None,
    findings_applied: int | None = None,
    findings_deferred: int | None = None,
) -> dict[str, object]:
    """Atomically record the final post-merge review identity.

    Parameters
    ----------
    manifest
        Path to the run manifest file.
    base_commit
        Review context base commit sha.
    reviewed_tree_oid
        Review context reviewed tree oid.
    diff_hash
        Review context diff hash.
    scope
        Review context scope paths (repeatable).
    press_slug
        Slug of the /press artifact for this review, if any.
    age_slug
        Slug of the /age artifact for this review, if any.
    cure_slug
        Slug of the /cure artifact for this review, if any.
    findings_applied
        Count of findings applied during post-review, if any.
    findings_deferred
        Count of findings deferred during post-review, if any.
    """
    path = Path(manifest)
    lock = path.parent / ("." + path.name + ".lock")
    post_review: dict[str, object] = {}

    def _body() -> None:
        nonlocal post_review
        data, original = _load_manifest(path)
        context = {
            "base_commit": base_commit,
            "reviewed_tree_oid": reviewed_tree_oid,
            "diff_hash": diff_hash,
            "scope": scope,
        }
        data["current_review"] = context
        existing = data.get("post_review")
        existing_dict = cast("dict[str, object]", existing) if isinstance(existing, dict) else {}
        post_review = dict(existing_dict)
        post_review["review_context"] = {**context, "scope": list(scope)}
        if press_slug is not None:
            post_review["press_slug"] = press_slug
        if age_slug is not None:
            post_review["age_slug"] = age_slug
        if cure_slug is not None:
            post_review["cure_slug"] = cure_slug
        if findings_applied is not None:
            post_review["findings_applied"] = findings_applied
        if findings_deferred is not None:
            post_review["findings_deferred"] = findings_deferred
        data["post_review"] = post_review
        _commit(path, data, original)

    _with_flock(lock, _body)
    return {"manifest": manifest, "post_review": post_review}


def set_wiring_status(
    *,
    manifest: str,
    wiring: str,
    status: str,
    commit_sha: str | None = None,
) -> dict[str, object]:
    """Update one wiring row's status.

    Parameters
    ----------
    manifest
        Path to the run manifest file.
    wiring
        Wiring row id to update.
    status
        New status; must be one of the known work statuses.
    commit_sha
        Commit sha to record on the wiring row, if any.
    """
    if status not in WORK_STATUSES:
        raise fromargs.CliError(f"invalid status {status!r}; expected one of {list(WORK_STATUSES)}")
    path = Path(manifest)
    lock = path.parent / ("." + path.name + ".lock")

    def _body() -> None:
        data, original = _load_manifest(path)
        wiring_entry = _find_wiring(data, wiring)
        wiring_entry["status"] = status
        if commit_sha is not None:
            wiring_entry["commit_sha"] = commit_sha
        _commit(path, data, original)

    _with_flock(lock, _body)
    return {"manifest": manifest, "wiring": wiring, "status": status}


def check_files(*, manifest: str, root: str | None = None) -> dict[str, list[str]]:
    """Re-check each curd's files[] against the working tree at dispatch time.

    Parameters
    ----------
    manifest
        Path to the run manifest file.
    root
        Repo root to resolve relative paths against; defaults to cwd.
    """
    path = Path(manifest)
    data, _ = _load_manifest(path)
    if root and not Path(root).is_dir():
        raise fromargs.CliError(f"root is not a directory: {root}")
    root_path = Path(root) if root else Path.cwd()
    curds = data.get("curds")
    if not isinstance(curds, list):
        raise fromargs.CliError("manifest has no curds list")

    stale: dict[str, list[str]] = {}
    for entry in cast("list[object]", curds):
        if not isinstance(entry, dict):
            continue
        entry_dict = cast("dict[str, object]", entry)
        files = entry_dict.get("files")
        if not isinstance(files, list):
            continue
        file_items = cast("list[object]", files)
        missing = [f for f in file_items if isinstance(f, str) and not (root_path / f).is_file()]
        if missing:
            stale[str(entry_dict.get("id"))] = missing
    return stale


# ----- fromargs wiring ------------------------------------------------------


LEAVES = ("set-phase", "set-curd-status", "set-post-review", "set-wiring-status", "check-files")


def build_app() -> fromargs.App:
    app = fromargs.App(
        "manifest-update",
        help="Apply an atomic, schema-validated update to a fan-out run manifest.",
        help_formatter="plain",
    )
    _ = app.command(set_phase, name="set-phase")
    _ = app.command(set_curd_status, name="set-curd-status")
    _ = app.command(set_post_review, name="set-post-review")
    _ = app.command(set_wiring_status, name="set-wiring-status")
    _ = app.command(check_files, name="check-files")
    return app


def main(argv: list[str] | None = None) -> int:
    return build_app().run(argv)


if __name__ == "__main__":
    raise SystemExit(main())