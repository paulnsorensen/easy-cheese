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
import tomllib
from collections.abc import Sequence
from typing import cast
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
_CORPUS_NAME_RE = re.compile(r"""^name\s*=\s*["']cheese-artifacts["']\s*(?:#.*)?$""")


def _toml_escape(value: str) -> str:
    escapes = {
        "\\": "\\\\",
        '"': '\\"',
        "\b": "\\b",
        "\t": "\\t",
        "\n": "\\n",
        "\f": "\\f",
        "\r": "\\r",
    }
    result: list[str] = []
    for char in value:
        if char in escapes:
            result.append(escapes[char])
        elif ord(char) < 0x20 or ord(char) == 0x7F:
            result.append(f"\\u{ord(char):04X}")
        else:
            result.append(char)
    return "".join(result)


def _toml_unescape(value: str) -> str:
    result: list[str] = []
    i = 0
    while i < len(value):
        if value[i] != "\\" or i + 1 == len(value):
            result.append(value[i])
            i += 1
            continue
        escaped = value[i + 1]
        simple = {"b": "\b", "t": "\t", "n": "\n", "f": "\f", "r": "\r", '"': '"', "\\": "\\"}
        if escaped in simple:
            result.append(simple[escaped])
            i += 2
        elif escaped == "u" and i + 5 < len(value):
            result.append(chr(int(value[i + 2 : i + 6], 16)))
            i += 6
        else:
            result.extend(("\\", escaped))
            i += 2
    return "".join(result)


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


def _has_unmarked_same_name(text: str) -> bool:
    unmarked = remove_marked_block(text, begin=BEGIN, end=END)
    try:
        parsed = cast(dict[str, object], tomllib.loads(unmarked))
    except tomllib.TOMLDecodeError:
        parsed = {}
    corpus_tables: object = parsed.get("corpus", ())
    if isinstance(corpus_tables, list):
        for corpus in cast(list[object], corpus_tables):
            if (
                isinstance(corpus, dict)
                and cast(dict[str, object], corpus).get("name") == "cheese-artifacts"
            ):
                return True

    in_corpus = False
    for line in unmarked.splitlines():
        stripped = line.strip()
        if stripped == "[[corpus]]":
            in_corpus = True
        elif stripped.startswith("["):
            in_corpus = False
        elif in_corpus and _CORPUS_NAME_RE.fullmatch(stripped):
            return True
    return False


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
    """Insert-or-replace the marked cheese-artifacts [[corpus]] block.

    A complete scan retains listed directories that still exist. Incomplete
    scans and unmarked duplicate corpora never mutate the configuration.
    """
    path = resolve_config_path(config_path)
    scan = find_cheese_dirs(roots)
    text = path.read_bytes().decode("utf-8") if path.is_file() else ""
    existing_block = extract_block(text, begin=BEGIN, end=END)
    existing = _listed_paths(existing_block) if existing_block is not None else ()
    diagnostics = "; ".join(scan.errors)
    backend_note = f"backend={scan.backend}"
    if diagnostics:
        backend_note += f"; {diagnostics}"

    if _has_unmarked_same_name(text):
        return Change(
            "artifacts",
            "error",
            str(path),
            "refusing mutation: unmarked cheese-artifacts corpus already exists",
        )
    incomplete = tuple(
        error
        for error in scan.errors
        if error != "rg failed or timed out; fell back to a directory walk"
    )
    if incomplete:
        return Change(
            "artifacts",
            "error",
            str(path),
            f"incomplete scan; refusing mutation: {'; '.join(incomplete)} ({backend_note})",
        )

    discovered = tuple(sorted(str(d) for d in scan.dirs))
    retained = tuple(
        sorted({item for item in existing if Path(item).expanduser().is_dir()})
    )
    desired = tuple(sorted(set(discovered) | set(retained)))
    if not desired:
        if existing_block is None:
            action = "noop"
            detail = f"no .cheese directories found; nothing to register ({backend_note})"
        else:
            action = "remove"
            detail = f"no existing .cheese directories; removing corpus ({backend_note})"
    elif set(desired) == set(existing):
        action = "noop"
        detail = f"cheese-artifacts already lists {len(desired)} dirs ({backend_note})"
    else:
        added = len(set(desired) - set(existing))
        removed = len(set(existing) - set(desired))
        action = "create" if existing_block is None else "replace"
        detail = f"added {added}, removed {removed}, total {len(desired)} ({backend_note})"

    if not apply or action == "noop":
        return Change("artifacts", action, str(path), detail)

    path.parent.mkdir(parents=True, exist_ok=True)
    if action == "remove":
        atomic_write(path, remove_marked_block(text, begin=BEGIN, end=END))
    else:
        atomic_write(
            path, replace_marked_block(text, _block(desired), begin=BEGIN, end=END)
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
    if apply and change.action in {"create", "replace", "remove"}:
        lines.append(
            "[artifacts] run `hallouminate daemon restart` then "
            + "`hallouminate index --corpus cheese-artifacts` to pick up this change"
        )
    return lines
