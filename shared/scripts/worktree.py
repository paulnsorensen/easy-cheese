#!/usr/bin/env python3
"""Shared worktree floor for isolated sub-agent/worktree dispatch: create, harvest, teardown. Used by /ultracook's parallel-mode fan-out and by the repair-worktree pathway (skills/cook/references/quality-gates.md § Repair pathway).

On Claude Code the native `Agent(isolation:"worktree")` primitive creates the
worktree and returns `{agentId, worktreePath, worktreeBranch}`, so the
orchestrator never guesses the branch name. `create()` is the harness-agnostic
floor for harnesses that lack that primitive.

Both paths share one `.git` object store with the parent, so a curd branch is
`harvest()`-able with **no `git fetch`** — cherry-pick sees the sub-agent's
commits immediately. Worktrees leak unless explicitly removed, so the engine
owns `teardown()` (worktree remove + branch delete) for every completed curd.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from contextlib import suppress
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

# cli is co-staged in the bundled .pyz alongside this module
import cli

WORKTREE_DIR = ".claude/worktrees"


def _worktree_path(slug: str) -> str:
    return f"{WORKTREE_DIR}/agent-{slug}"


def _worktree_branch(slug: str) -> str:
    return f"worktree-agent-{slug}"


def _git(repo: str, *args: str) -> str:
    """Run a git command in `repo`; raise CliError (loud) on failure."""
    result = subprocess.run(
        ["git", "-C", repo, *args],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise cli.CliError(
            f"git {' '.join(args)} failed ({result.returncode}): {result.stderr.strip()}"
        )
    return result.stdout


def _validate_slug(slug: str) -> None:
    """Reject a slug that would escape .claude/worktrees/agent-<slug>: no path
    separators, no parent refs, no empty. The slug names the worktree dir and
    branch, so an unchecked slug is arbitrary path/branch injection."""
    if not slug or "/" in slug or "\\" in slug or ".." in slug:
        raise cli.CliError(
            f"invalid slug {slug!r}: must be non-empty and free of path separators or '..'"
        )


def _validate_teardown_target(path: str, branch: str) -> None:
    """Refuse anything but a .claude/worktrees/agent-* worktree on a
    worktree-agent-* branch: teardown force-removes a worktree and force-deletes
    a branch, so an arbitrary path/branch would be destructive."""
    norm = os.path.normpath(path)
    prefix = WORKTREE_DIR + os.sep
    norm_path = Path(norm)
    if (
        not norm.startswith(prefix)
        or ".." in norm_path.parts
        or not norm_path.name.startswith("agent-")
    ):
        raise cli.CliError(
            f"refusing to tear down {path!r}: not a {WORKTREE_DIR}/agent-* worktree"
        )
    if not branch.startswith("worktree-agent-"):
        raise cli.CliError(
            f"refusing to delete branch {branch!r}: not a worktree-agent-* branch"
        )



def _project_relative(raw: object, *, label: str) -> Path:
    if not isinstance(raw, str) or not raw:
        raise cli.CliError(f"{label} must be a non-empty project-relative path")
    path = Path(raw)
    if path.is_absolute() or "\\" in raw or ".." in path.parts:
        raise cli.CliError(f"{label} must be a project-relative path: {raw!r}")
    return path


def _reject_symlink_components(path: Path, *, label: str) -> None:
    absolute = path.absolute()
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current /= part
        try:
            if current.is_symlink():
                raise cli.CliError(
                    f"{label} must not traverse symlinks: {path}"
                )
        except OSError as exc:
            raise cli.CliError(f"{label} is unavailable: {path}") from exc


def _root_dir(root: Path, *, label: str) -> Path:
    _reject_symlink_components(root, label=label)
    try:
        resolved = root.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise cli.CliError(f"{label} is unavailable: {root}") from exc
    if not resolved.is_dir():
        raise cli.CliError(f"{label} is not a directory: {root}")
    return resolved




def _contained_file(root: Path, relative: Path, *, label: str) -> Path:
    candidate = root / relative
    _reject_symlink_components(candidate, label=label)
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root)
    except (FileNotFoundError, OSError, RuntimeError, ValueError) as exc:
        raise cli.CliError(
            f"{label} is unavailable or escapes the project: {relative}"
        ) from exc
    if resolved != candidate or not resolved.is_file():
        raise cli.CliError(f"{label} must be a regular file: {relative}")
    return candidate


def _target_file(root: Path, relative: Path) -> Path:
    target = root / relative
    _reject_symlink_components(target, label="oracle target")
    try:
        if target.parent.exists() and not target.parent.is_dir():
            raise cli.CliError(
                f"oracle target parent must be a directory: {relative}"
            )
        target.parent.resolve(strict=False).relative_to(root)
    except (OSError, RuntimeError, ValueError) as exc:
        raise cli.CliError(f"oracle target escapes the worktree: {relative}") from exc
    if target.is_symlink():
        raise cli.CliError(f"oracle target must not be a symlink: {relative}")
    if target.exists() and not target.is_file():
        raise cli.CliError(f"oracle target must be a regular file: {relative}")
    return target


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_digest(path: Path, *, label: str) -> str:
    try:
        return _sha256(path)
    except OSError as exc:
        raise cli.CliError(f"{label} is unavailable: {path}") from exc


@dataclass(frozen=True)
class _CopyPlan:
    source: Path
    target: Path
    relative: Path
    expected: str
    original_digest: str | None

    @property
    def needs_copy(self) -> bool:
        return self.original_digest != self.expected


def _plan_copy(
    source_root: Path,
    destination_root: Path,
    relative: Path,
    expected: str,
    *,
    overwrite: bool,
    label: str,
) -> _CopyPlan:
    source = _contained_file(source_root, relative, label=label)
    actual = _file_digest(source, label=label)
    if actual != expected:
        raise cli.CliError(
            f"protected file digest mismatch for {relative}: "
            f"expected {expected}, got {actual}"
        )
    target = _target_file(destination_root, relative)
    original_digest = (
        _file_digest(target, label="oracle target") if target.exists() else None
    )
    if (
        original_digest is not None
        and original_digest != expected
        and not overwrite
    ):
        raise cli.CliError(
            f"oracle harvest conflict for {target}: "
            f"expected {expected}, found {original_digest}"
        )
    return _CopyPlan(source, target, relative, expected, original_digest)


def _ensure_parent_dirs(targets: list[Path], root: Path) -> list[Path]:
    created: list[Path] = []
    for target in targets:
        try:
            target.parent.relative_to(root)
        except ValueError as exc:
            raise cli.CliError(
                f"oracle target escapes the worktree: {target}"
            ) from exc
        missing: list[Path] = []
        parent = target.parent
        while parent != root:
            if parent.exists():
                _reject_symlink_components(parent, label="oracle target")
                if not parent.is_dir():
                    raise cli.CliError(
                        f"oracle target parent must be a directory: {target}"
                    )
                break
            missing.append(parent)
            parent = parent.parent
        for directory in reversed(missing):
            _reject_symlink_components(directory, label="oracle target")
            directory.mkdir()
            created.append(directory)
    return created


def _stage_copy(
    source: Path, target: Path, expected: str, *, label: str
) -> Path:
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
    )
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        shutil.copy2(source, temporary)
        actual = _file_digest(temporary, label=label)
        if actual != expected:
            raise cli.CliError(
                f"{label} digest mismatch for {target}: "
                f"expected {expected}, got {actual}"
            )
    except BaseException:
        with suppress(FileNotFoundError):
            temporary.unlink()
        raise
    return temporary


def _rollback(
    plans: list[_CopyPlan],
    backups: dict[Path, Path],
    created_dirs: list[Path],
) -> None:
    errors: list[str] = []
    for plan in reversed(plans):
        backup = backups.get(plan.target)
        try:
            if backup is not None:
                os.replace(backup, plan.target)
            elif plan.original_digest is None and (
                plan.target.exists() or plan.target.is_symlink()
            ):
                if not plan.target.is_file() and not plan.target.is_symlink():
                    raise OSError(f"cannot remove non-file target {plan.target}")
                plan.target.unlink()
        except OSError as exc:
            errors.append(f"{plan.target}: {exc}")
    for directory in reversed(created_dirs):
        try:
            with suppress(FileNotFoundError):
                directory.rmdir()
        except OSError as exc:
            errors.append(f"{directory}: {exc}")
    if errors:
        raise cli.CliError(
            "oracle transfer rollback failed: " + "; ".join(errors)
        )


def _discard_temporary(paths: list[Path]) -> None:
    for path in paths:
        with suppress(FileNotFoundError):
            path.unlink()


def _commit_copy_set(plans: list[_CopyPlan], root: Path) -> None:
    pending = [plan for plan in plans if plan.needs_copy]
    if not pending:
        return
    created_dirs: list[Path] = []
    staged: dict[Path, Path] = {}
    backups: dict[Path, Path] = {}
    try:
        created_dirs = _ensure_parent_dirs(
            [plan.target for plan in pending], root
        )
        for plan in pending:
            staged[plan.target] = _stage_copy(
                plan.source,
                plan.target,
                plan.expected,
                label="staged oracle",
            )
        for plan in pending:
            if plan.original_digest is not None:
                backups[plan.target] = _stage_copy(
                    plan.target,
                    plan.target,
                    plan.original_digest,
                    label="oracle backup",
                )
        for plan in pending:
            os.replace(staged[plan.target], plan.target)
    except BaseException as exc:
        _discard_temporary(list(staged.values()))
        try:
            _rollback(pending, backups, created_dirs)
        except BaseException as rollback_exc:
            _discard_temporary([*staged.values(), *backups.values()])
            raise cli.CliError(
                f"oracle transfer failed and rollback failed: {rollback_exc}"
            ) from exc
        _discard_temporary([*staged.values(), *backups.values()])
        if isinstance(exc, cli.CliError):
            raise
        raise cli.CliError(f"oracle transfer failed: {exc}") from exc
    _discard_temporary([*staged.values(), *backups.values()])


def inherit_oracle(
    receipt: str,
    worktree_path: str,
    *,
    repo: str = ".",
    expected_producer: str = "cut",
    overwrite: bool = True,
) -> list[str]:
    """Copy one RED receipt and its protected files between worktrees."""
    source_root = _root_dir(Path(repo), label="repository")
    receipt_relative = _project_relative(receipt, label="receipt")
    destination_path = Path(worktree_path)
    if not destination_path.is_absolute():
        if "\\" in worktree_path or ".." in destination_path.parts:
            raise cli.CliError(
                f"worktree path must remain within the repository: {worktree_path!r}"
            )
        destination_path = source_root / destination_path
    destination_root = _root_dir(destination_path, label="worktree path")
    receipt_source = _contained_file(
        source_root, receipt_relative, label="receipt"
    )
    try:
        payload = json.loads(receipt_source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise cli.CliError(f"invalid gate receipt {receipt}: {exc}") from exc
    if (
        not isinstance(payload, Mapping)
        or payload.get("producer") != expected_producer
        or payload.get("disposition") != "red"
    ):
        raise cli.CliError(
            f"oracle inheritance requires a {expected_producer} RED GateReceipt"
        )
    protected = payload.get("protected_files")
    if not isinstance(protected, list) or not protected:
        raise cli.CliError("RED GateReceipt must declare protected_files")

    plans: list[_CopyPlan] = []
    seen: set[Path] = set()
    for index, item in enumerate(protected, start=1):
        if not isinstance(item, Mapping):
            raise cli.CliError(f"protected_files[{index}] must be an object")
        relative = _project_relative(
            item.get("path"), label=f"protected_files[{index}].path"
        )
        if relative in seen:
            raise cli.CliError(f"duplicate protected file path: {relative}")
        seen.add(relative)
        claimed = item.get("sha256")
        if not isinstance(claimed, str):
            raise cli.CliError(f"protected_files[{index}].sha256 must be a digest")
        expected = claimed.removeprefix("sha256:")
        if len(expected) != 64 or any(
            char not in "0123456789abcdefABCDEF" for char in expected
        ):
            raise cli.CliError(
                f"protected_files[{index}].sha256 must be a SHA-256 digest"
            )
        plans.append(
            _plan_copy(
                source_root,
                destination_root,
                relative,
                expected.lower(),
                overwrite=overwrite,
                label=f"protected_files[{index}].path",
            )
        )

    phase_token_ref = payload.get("phase_token_ref")
    phase_token_sha256 = payload.get("phase_token_sha256")
    if (phase_token_ref is None) != (phase_token_sha256 is None):
        raise cli.CliError(
            "GateReceipt phase_token_ref and phase_token_sha256 must be provided together"
        )
    if phase_token_ref is not None:
        token_relative = _project_relative(
            phase_token_ref, label="phase_token_ref"
        )
        token_namespace = Path(".cheese") / expected_producer
        if not token_relative.is_relative_to(token_namespace):
            raise cli.CliError(
                f"phase_token_ref must be beneath .cheese/{expected_producer}/"
            )
        if token_relative in seen or token_relative == receipt_relative:
            raise cli.CliError(f"duplicate oracle transfer path: {token_relative}")
        if not isinstance(phase_token_sha256, str):
            raise cli.CliError("phase_token_sha256 must be a digest")
        token_digest = phase_token_sha256.removeprefix("sha256:")
        if len(token_digest) != 64 or any(
            char not in "0123456789abcdefABCDEF" for char in token_digest
        ):
            raise cli.CliError("phase_token_sha256 must be a SHA-256 digest")
        seen.add(token_relative)
        plans.append(
            _plan_copy(
                source_root,
                destination_root,
                token_relative,
                token_digest.lower(),
                overwrite=overwrite,
                label="phase_token_ref",
            )
        )

    if receipt_relative in seen:
        raise cli.CliError(f"duplicate protected file path: {receipt_relative}")
    receipt_expected = _file_digest(receipt_source, label="receipt")
    plans.append(
        _plan_copy(
            source_root,
            destination_root,
            receipt_relative,
            receipt_expected,
            overwrite=overwrite,
            label="receipt",
        )
    )
    _commit_copy_set(plans, destination_root)
    return [plan.relative.as_posix() for plan in plans]

def create(
    slug: str, base: str, *, repo: str = ".", receipt: str | None = None
) -> dict[str, object]:
    """Create a fresh worktree off ``base`` and optionally inherit a RED oracle."""
    _validate_slug(slug)
    path = _worktree_path(slug)
    branch = _worktree_branch(slug)
    _git(repo, "worktree", "add", "-b", branch, path, base)
    try:
        inherited = (
            inherit_oracle(
                receipt,
                path,
                repo=repo,
                expected_producer="cut",
                overwrite=True,
            )
            if receipt
            else []
        )
    except (cli.CliError, OSError):
        subprocess.run(
            ["git", "-C", repo, "worktree", "remove", "--force", path],
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "-C", repo, "branch", "-D", branch],
            capture_output=True,
            text=True,
        )
        raise
    result: dict[str, object] = {"path": path, "branch": branch}
    if inherited:
        result["inherited"] = inherited
    return result


def harvest(branch: str, onto: str, *, repo: str = ".") -> list[str]:
    """Cherry-pick the commits unique to `branch` onto `onto` (the orchestrator
    branch). Shared `.git` object store means no fetch. Returns the picked SHAs
    (oldest first); an empty list when `branch` added nothing over `onto`."""
    _git(repo, "checkout", onto)
    revs = _git(repo, "rev-list", "--reverse", f"{onto}..{branch}").split()
    if not revs:
        return []
    try:
        _git(repo, "cherry-pick", *revs)
    except cli.CliError:
        # Leave the repo clean for the orchestrator's /melt fallback: a
        # half-finished cherry-pick (unmerged index / CHERRY_PICK_HEAD) would
        # cascade-poison the next harvest's `git checkout onto`.
        subprocess.run(["git", "-C", repo, "cherry-pick", "--abort"], capture_output=True, text=True)
        raise
    return revs


def teardown(path: str, branch: str, *, repo: str = ".") -> None:
    """Remove the worktree at `path` and delete its `branch`. Leaves no
    `worktree-agent-*` branch or `.claude/worktrees/agent-*` dir behind.

    Best-effort and order-independent: a failure removing the worktree must not
    skip the branch delete (that would leak the branch). Both steps are always
    attempted; a combined error is raised at the end if either failed."""
    _validate_teardown_target(path, branch)
    errors: list[str] = []
    for args in (("worktree", "remove", "--force", path), ("branch", "-D", branch)):
        try:
            _git(repo, *args)
        except cli.CliError as exc:
            errors.append(str(exc))
    if errors:
        raise cli.CliError("; ".join(errors))


def _cmd_create(args: argparse.Namespace) -> None:
    cli.emit(
        create(args.slug, args.base, repo=args.repo, receipt=args.receipt),
        json_mode=True,
        stdout=args.stdout,
    )

def _cmd_inherit(args: argparse.Namespace) -> None:
    inherited = inherit_oracle(
        args.receipt,
        args.path,
        repo=args.repo,
        expected_producer="cut",
        overwrite=True,
    )
    cli.emit({"path": args.path, "inherited": inherited}, json_mode=True, stdout=args.stdout)


def _cmd_harvest_oracle(args: argparse.Namespace) -> None:
    inherited = inherit_oracle(
        args.receipt,
        args.path,
        repo=args.repo,
        expected_producer="press",
        overwrite=False,
    )
    cli.emit({"path": args.path, "inherited": inherited}, json_mode=True, stdout=args.stdout)


def _cmd_harvest(args: argparse.Namespace) -> None:
    picked = harvest(args.branch, args.onto, repo=args.repo)
    cli.emit({"picked": picked}, json_mode=True, stdout=args.stdout)


def _cmd_teardown(args: argparse.Namespace) -> None:
    teardown(args.path, args.branch, repo=args.repo)
    cli.emit({"removed": args.path, "deleted_branch": args.branch}, json_mode=True, stdout=args.stdout)


def _setup(parser: argparse.ArgumentParser) -> None:
    parser.description = "Create, harvest, or tear down a curd worktree."
    sub = parser.add_subparsers(dest="action", required=True)

    p_create = sub.add_parser("create", help="Create a worktree off a base ref.")
    p_create.add_argument("--slug", required=True, help="Curd slug (names the worktree + branch).")
    p_create.add_argument("--base", required=True, help="Base ref to branch the worktree from.")
    p_create.add_argument("--repo", default=".", help="Repo root (default: cwd).")
    p_create.add_argument(
        "--receipt",
        help="Project-relative RED GateReceipt to inherit with its protected files.",
    )
    p_create.set_defaults(func=_cmd_create)

    p_inherit = sub.add_parser(
        "inherit", help="Copy a RED receipt and protected files into a worktree."
    )
    p_inherit.add_argument("--receipt", required=True, help="Project-relative GateReceipt.")
    p_inherit.add_argument("--path", required=True, help="Destination worktree path.")
    p_inherit.add_argument("--repo", default=".", help="Oracle source repo (default: cwd).")
    p_inherit.set_defaults(func=_cmd_inherit)

    p_oracle = sub.add_parser(
        "harvest-oracle",
        help="Copy a child Press receipt and protected files to the orchestrator.",
    )
    p_oracle.add_argument(
        "--receipt", required=True, help="Child-relative Press GateReceipt."
    )
    p_oracle.add_argument("--path", required=True, help="Destination orchestrator path.")
    p_oracle.add_argument("--repo", default=".", help="Child worktree root.")
    p_oracle.set_defaults(func=_cmd_harvest_oracle)

    p_harvest = sub.add_parser("harvest", help="Cherry-pick a curd branch onto the orchestrator branch.")
    p_harvest.add_argument("--branch", required=True, help="Curd branch to harvest.")
    p_harvest.add_argument("--onto", required=True, help="Orchestrator branch to cherry-pick onto.")
    p_harvest.add_argument("--repo", default=".", help="Repo root (default: cwd).")
    p_harvest.set_defaults(func=_cmd_harvest)

    p_teardown = sub.add_parser("teardown", help="Remove a worktree and delete its branch.")
    p_teardown.add_argument("--path", required=True, help="Worktree path to remove.")
    p_teardown.add_argument("--branch", required=True, help="Worktree branch to delete.")
    p_teardown.add_argument("--repo", default=".", help="Repo root (default: cwd).")
    p_teardown.set_defaults(func=_cmd_teardown)


if __name__ == "__main__":
    raise SystemExit(cli.run(_setup))
