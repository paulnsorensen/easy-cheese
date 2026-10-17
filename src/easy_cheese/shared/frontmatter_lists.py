"""Dependency-free reader for string-list fields in Mold spec frontmatter.

The Mold producer, the strict spec validator, and Cook's typed spec reader
all read ``execution_holds`` through this module, so one hold declaration
never parses differently at save, finalize, and Cook time.  The producer
also reads ``gates_overridden`` here.
"""

from __future__ import annotations

import re

__all__ = ["frontmatter_string_list"]


def _flow_items(body: str, key: str) -> list[str]:
    """Split one YAML flow sequence body on the commas outside quoted items."""

    items: list[str] = []
    current: list[str] = []
    quote: str | None = None
    for char in body:
        if quote is not None:
            if char != quote:
                current.append(char)
            else:
                quote = None
        elif char in "'\"":
            quote = char
        elif char == ",":
            items.append("".join(current))
            current = []
        else:
            current.append(char)
    if quote is not None:
        raise ValueError(f"{key} is malformed: unbalanced quote")
    items.append("".join(current))
    return items


def _list_item(raw: str, key: str) -> str:
    item = raw.strip().strip("'\"").strip()
    if not item:
        raise ValueError(f"{key} must be a list of strings")
    return item


def frontmatter_string_list(text: str, key: str) -> tuple[str, ...]:
    """Read frontmatter ``key`` as a YAML block list, flow list, or scalar.

    A malformed declaration raises ``ValueError`` that names ``key``; it is
    never a silently dropped safety hold.  Text without frontmatter, or
    frontmatter without ``key``, yields an empty tuple.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return ()
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        raise ValueError("spec frontmatter is not terminated") from None
    for index in range(1, end):
        match = re.match(rf"^{re.escape(key)}:\s*(.*)$", lines[index])
        if match is None:
            continue
        inline = match.group(1).strip()
        if inline in {"null", "~"}:
            return ()
        if not inline:
            key_indent = len(lines[index]) - len(lines[index].lstrip())
            items: list[str] = []
            for entry in lines[index + 1 : end]:
                stripped = entry.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                # A block sequence may sit at the key's own indentation, so the
                # item pattern must not require a deeper indent.
                item = re.match(r"^\s*-\s*(.*)$", entry)
                if item is None:
                    if len(entry) - len(entry.lstrip()) > key_indent:
                        # A nested value that is not a sequence item is a
                        # malformed declaration, never an absent list.
                        raise ValueError(f"{key} must be a list of strings")
                    break
                items.append(_list_item(item.group(1), key))
            return tuple(items)
        if inline.startswith("["):
            if not inline.endswith("]"):
                raise ValueError(f"{key} must be a list of strings")
            body = inline[1:-1].strip()
            if not body:
                return ()
            return tuple(_list_item(part, key) for part in _flow_items(body, key))
        return (_list_item(inline, key),)
    return ()
