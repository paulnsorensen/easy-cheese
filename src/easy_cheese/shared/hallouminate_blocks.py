"""Generic marked-block config file manipulation, shared by every leg.

Text-based find/replace/remove of a caller-supplied BEGIN/END marked block
in a TOML-ish config, plus atomic write and hallouminate config-path
resolution. No toml dependency, no cheese-durable defaults -- callers own
their own markers.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Change:
    """One leg's computed or applied action, for reporting + idempotency checks."""

    leg: str
    action: str  # "noop" | "create" | "replace" | "remove" | "init-repo"
    target_path: str
    detail: str


def config_path() -> Path:
    """``${XDG_CONFIG_HOME:-~/.config}/hallouminate/config.toml``.

    ``$HALLOUMINATE_CONFIG`` overrides outright (tests point this at a temp file).
    """
    override = os.environ.get("HALLOUMINATE_CONFIG", "").strip()
    if override:
        return Path(override)
    raw = os.environ.get("XDG_CONFIG_HOME", "").strip()
    base = Path(raw) if raw and Path(raw).is_absolute() else Path.home() / ".config"
    return base / "hallouminate" / "config.toml"


def resolve_config_path(explicit: Path | None) -> Path:
    return Path(explicit) if explicit is not None else config_path()


def find_marked_span(
    lines: list[str], *, begin: str, end: str
) -> tuple[int, int] | None:
    """``(begin_idx, end_idx)`` (inclusive) of the marked block, or None.

    An orphan `begin` with no closing `end` (a half-written/truncated block)
    spans begin→EOF, so it is replaced in place rather than left to trip the
    blind-append path into a duplicate corpus.
    """
    begin_idx = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == begin:
            begin_idx = i
        elif stripped == end and begin_idx is not None:
            return begin_idx, i
    if begin_idx is not None:
        return begin_idx, len(lines) - 1
    return None


def atomic_write(path: Path, text: str) -> None:
    """Write via a temp sibling + ``os.replace`` so an interrupted write can
    never truncate the shared user config (it holds unrelated corpora)."""
    tmp = path.with_name(f"{path.name}.ec-tmp")
    # write_bytes (not write_text) so line endings pass through verbatim on
    # every Python -- write_text(newline=...) is 3.13+, CI runs 3.12.
    _ = tmp.write_bytes(text.encode("utf-8"))
    _ = tmp.replace(path)


def extract_block(text: str, *, begin: str, end: str) -> str | None:
    lines = text.splitlines(keepends=True)
    span = find_marked_span(lines, begin=begin, end=end)
    if span is None:
        return None
    begin_idx, end_idx = span
    return "".join(lines[begin_idx : end_idx + 1])


def dominant_newline(text: str) -> str:
    """The config's prevailing line ending, so a rewritten block does not mix
    CRLF and LF in a shared user config that is CRLF-terminated."""
    crlf = text.count("\r\n")
    lf_only = text.count("\n") - crlf
    return "\r\n" if crlf > lf_only else "\n"


def replace_marked_block(text: str, new_block: str, *, begin: str, end: str) -> str:
    newline = dominant_newline(text)
    if newline != "\n":
        new_block = new_block.replace("\r\n", "\n").replace("\n", newline)
    lines = text.splitlines(keepends=True)
    span = find_marked_span(lines, begin=begin, end=end)
    if span is not None:
        begin_idx, end_idx = span
        return "".join(lines[:begin_idx]) + new_block + "".join(lines[end_idx + 1 :])
    prefix = text
    if prefix and not prefix.endswith(("\n", "\r\n")):
        prefix += newline
    return prefix + new_block


def remove_marked_block(text: str, *, begin: str, end: str) -> str:
    """Delete the marked block outright, or return `text` unchanged if absent."""
    lines = text.splitlines(keepends=True)
    span = find_marked_span(lines, begin=begin, end=end)
    if span is None:
        return text
    begin_idx, end_idx = span
    return "".join(lines[:begin_idx]) + "".join(lines[end_idx + 1 :])
