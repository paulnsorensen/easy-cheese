"""Register every `.cheese` directory as one Hallouminate corpus.

Writes the ~/.config/hallouminate/config.toml [[corpus]] block that lists
every `.cheese` directory found on the machine, so the artifacts each repo
accumulates (notes, ADRs, wiki drafts) are searchable across sessions. A
gitignored `.cheese` dir is only indexed when a [[corpus]] `paths` entry
names that dir itself, so the block lists each directory explicitly rather
than a shared parent root. Marked-block text manipulation only -- no toml
dependency.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from easy_cheese.shared.hallouminate_blocks import (
    Change,
    atomic_write,
    extract_block,
    remove_marked_block,
    replace_marked_block,
    resolve_config_path,
)
from easy_cheese.shared.wheypoint.discovery_notes import find_cheese_dirs

BEGIN = "# >>> easy-cheese:cheese-artifacts"
END = "# <<< easy-cheese:cheese-artifacts"

_PATH_LINE_RE = re.compile(r'^\s*"((?:[^"\\]|\\.)*)",?\s*$')


def _toml_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _toml_unescape(value: str) -> str:
    return value.replace('\\"', '"').replace("\\\\", "\\")


def _block(dirs: Sequence[str]) -> str:
    paths_lines = "".join(f'  "{_toml_escape(d)}",\n' for d in dirs)
    return (
        f"{BEGIN}\n"
        "[[corpus]]\n"
        'name = "cheese-artifacts"\n'
        "paths = [\n"
        f"{paths_lines}"
        "]\n"
        'globs = ["**/*.md"]\n'
        'exclude = ["**/.git/**"]\n'
        f"{END}\n"
    )


def _listed_paths(block: str) -> tuple[str, ...]:
    in_paths = False
    result: list[str] = []
    for line in block.splitlines():
        stripped = line.strip()
        if stripped.startswith("paths"):
            in_paths = True
            continue
        if not in_paths:
            continue
        if stripped.startswith("]"):
            break
        match = _PATH_LINE_RE.match(line)
        if match is not None:
            result.append(_toml_unescape(match.group(1)))
    return tuple(result)


@dataclass(frozen=True)
class ArtifactsState:
    """The cheese-artifacts block's listed paths, plus any that no longer exist."""

    listed: tuple[str, ...]
    missing: tuple[str, ...]


def detect_artifacts_state(config_path: Path | None = None) -> ArtifactsState:
    """Listed paths, plus which of them no longer exist on disk (drift)."""
    path = resolve_config_path(config_path)
    if not path.is_file():
        return ArtifactsState(listed=(), missing=())
    block = extract_block(path.read_text(encoding="utf-8"), begin=BEGIN, end=END)
    if block is None:
        return ArtifactsState(listed=(), missing=())
    listed = _listed_paths(block)
    missing = tuple(p for p in listed if not Path(p).expanduser().exists())
    return ArtifactsState(listed=listed, missing=missing)


def apply_artifacts(
    config_path: Path | None = None, *, apply: bool, roots: Sequence[Path | str] = ()
) -> Change:
    """Insert-or-replace the marked cheese-artifacts [[corpus]] block with
    every discovered `.cheese` directory.

    Noop when the block already lists exactly the discovered dirs. Removes
    the block when discovery finds none -- a corpus with no paths is
    useless. Idempotent: a second ``apply=True`` run leaves the file
    byte-identical.
    """
    path = resolve_config_path(config_path)
    scan = find_cheese_dirs(roots)
    discovered = tuple(sorted(str(d) for d in scan.dirs))
    text = path.read_bytes().decode("utf-8") if path.is_file() else ""
    existing_block = extract_block(text, begin=BEGIN, end=END)
    existing = _listed_paths(existing_block) if existing_block is not None else ()
    backend_note = f"backend={scan.backend}"

    if not discovered:
        if existing_block is None:
            action = "noop"
            detail = (
                f"no .cheese directories found; nothing to register ({backend_note})"
            )
        else:
            action = "remove"
            detail = (
                f"no .cheese directories found; removing empty corpus ({backend_note})"
            )
    elif set(discovered) == set(existing):
        action = "noop"
        detail = (
            f"cheese-artifacts already lists {len(discovered)} dirs ({backend_note})"
        )
    else:
        added = len(set(discovered) - set(existing))
        removed = len(set(existing) - set(discovered))
        action = "create" if existing_block is None else "replace"
        detail = f"added {added}, removed {removed}, total {len(discovered)} ({backend_note})"

    if not apply or action == "noop":
        return Change("artifacts", action, str(path), detail)

    path.parent.mkdir(parents=True, exist_ok=True)
    if action == "remove":
        atomic_write(path, remove_marked_block(text, begin=BEGIN, end=END))
    else:
        atomic_write(
            path, replace_marked_block(text, _block(discovered), begin=BEGIN, end=END)
        )
    return Change("artifacts", action, str(path), detail)


def _report(change: Change) -> str:
    return f"[{change.leg}] {change.action}: {change.target_path} -- {change.detail}"


def run_leg(*, apply: bool, roots: Sequence[str] = ()) -> list[str]:
    """The `artifacts` leg's report lines, for `hallouminate_setup._run_leg`."""
    change = apply_artifacts(apply=apply, roots=roots)
    lines = [_report(change)]
    state = detect_artifacts_state()
    if state.missing:
        lines.append(
            "[artifacts] drift: these listed paths no longer exist: "
            + ", ".join(state.missing)
        )
    if apply and change.action != "noop":
        lines.append(
            "[artifacts] run `hallouminate daemon restart` then "
            + "`hallouminate index --corpus cheese-artifacts` to pick up this change"
        )
    return lines
