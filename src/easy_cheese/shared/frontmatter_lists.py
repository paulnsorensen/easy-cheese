"""Dependency-free reader for string-list fields in Mold spec frontmatter.

The Mold producer, the strict spec validator, and Cook's typed spec reader
all read ``execution_holds`` through this module, so one hold declaration
never parses differently at save, finalize, and Cook time.  The producer
also reads ``gates_overridden`` here.  The strict spec validator and the
taste-test spec gate read ``entity_referent_bindings`` records here.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import TypeVar, cast

__all__ = [
    "frontmatter_mapping_list",
    "frontmatter_string_list",
    "strip_flow_comment",
]

_ItemT = TypeVar("_ItemT")


def strip_flow_comment(value: str) -> str:
    """Drop a trailing ``# comment`` from a YAML flow collection value.

    A ``#`` starts a comment only outside quotes, at the start or after
    whitespace, so a quoted ``#`` survives.
    """

    quote: str | None = None
    for index, char in enumerate(value):
        if quote is not None:
            if char == quote:
                quote = None
        elif char in "'\"":
            quote = char
        elif char == "#" and (not index or value[index - 1].isspace()):
            return value[:index].rstrip()
    return value.strip()


class _FlowReader:
    """Read one YAML flow collection whose scalars are plain or quoted strings."""

    def __init__(self, text: str, key: str) -> None:
        self.text: str = text
        self.key: str = key
        self.pos: int = 0

    def malformed(self) -> ValueError:
        return ValueError(f"{self.key} is malformed: invalid flow collection")

    def peek(self) -> str:
        while self.pos < len(self.text) and self.text[self.pos].isspace():
            self.pos += 1
        return self.text[self.pos : self.pos + 1]

    def expect(self, char: str) -> None:
        if self.peek() != char:
            raise self.malformed()
        self.pos += 1

    def document(self) -> object:
        value = self.value()
        if self.peek():
            raise self.malformed()
        return value

    def value(self) -> object:
        match self.peek():
            case "[":
                return self.collection("]", self.value)
            case "{":
                return dict(self.collection("}", self.entry))
            case _:
                return self.scalar(",]}")

    def collection(self, close: str, item: Callable[[], _ItemT]) -> list[_ItemT]:
        self.pos += 1
        items: list[_ItemT] = []
        while self.peek() != close:
            items.append(item())
            if self.peek() != ",":
                break
            self.pos += 1
        self.expect(close)
        return items

    def entry(self) -> tuple[str, object]:
        name = self.scalar(",}", key=True)
        self.expect(":")
        return name, self.value()

    def scalar(self, stops: str, *, key: bool = False) -> str:
        quote = self.peek()
        if quote and quote in "'\"":
            end = self.text.find(quote, self.pos + 1)
            if end < 0:
                raise ValueError(f"{self.key} is malformed: unbalanced quote")
            item = self.text[self.pos + 1 : end]
            self.pos = end + 1
            return item
        start = self.pos
        while self.pos < len(self.text) and self.text[self.pos] not in stops:
            if key and self.text[self.pos] == ":" and self._ends_key():
                break
            self.pos += 1
        item = self.text[start : self.pos].strip()
        if not item or item[0] in "[{":
            raise self.malformed()
        return item

    def _ends_key(self) -> bool:
        following = self.text[self.pos + 1 : self.pos + 2]
        return not following or following.isspace() or following in ",}"


def _flow_value(raw: str, key: str) -> object:
    return _FlowReader(strip_flow_comment(raw), key).document()


def frontmatter_mapping_list(text: str, key: str) -> tuple[dict[str, object], ...]:
    """Read frontmatter ``key`` as a list of flow-mapping records.

    The list may be a YAML flow sequence or a block sequence whose items are
    flow mappings, each with an optional trailing comment.  A malformed
    declaration raises ``ValueError`` that names ``key``.  Text without
    frontmatter, or frontmatter without ``key``, yields an empty tuple.
    """
    malformed = f"{key} must be a list of mappings"
    lines = _frontmatter_lines(text)
    for index, line in enumerate(lines):
        match = re.match(rf"^{re.escape(key)}:\s*(.*)$", line)
        if match is None:
            continue
        inline = strip_flow_comment(match.group(1))
        if inline in {"null", "~"}:
            return ()
        if inline:
            parsed = _flow_value(inline, key)
            if not isinstance(parsed, list):
                raise ValueError(malformed)
            items = cast(list[object], parsed)
        else:
            following = lines[index + 1 :]
            items = [
                _flow_value(raw, key)
                for raw in _block_items(line, following, malformed)
            ]
        if not all(isinstance(item, dict) for item in items):
            raise ValueError(malformed)
        return tuple(cast(list[dict[str, object]], items))
    return ()


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


def _frontmatter_lines(text: str) -> list[str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return []
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        raise ValueError("spec frontmatter is not terminated") from None
    return lines[1:end]


def _block_items(key_line: str, following: list[str], malformed: str) -> list[str]:
    """Return the raw item text of the block sequence under ``key_line``."""
    key_indent = len(key_line) - len(key_line.lstrip())
    items: list[str] = []
    for entry in following:
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
                raise ValueError(malformed)
            break
        items.append(item.group(1))
    return items


def frontmatter_string_list(text: str, key: str) -> tuple[str, ...]:
    """Read frontmatter ``key`` as a YAML block list, flow list, or scalar.

    A malformed declaration raises ``ValueError`` that names ``key``; it is
    never a silently dropped safety hold.  Text without frontmatter, or
    frontmatter without ``key``, yields an empty tuple.
    """
    lines = _frontmatter_lines(text)
    for index, line in enumerate(lines):
        match = re.match(rf"^{re.escape(key)}:\s*(.*)$", line)
        if match is None:
            continue
        inline = match.group(1).strip()
        if inline in {"null", "~"}:
            return ()
        if not inline:
            return tuple(
                _list_item(raw, key)
                for raw in _block_items(
                    line, lines[index + 1 :], f"{key} must be a list of strings"
                )
            )
        if inline.startswith("["):
            inline = strip_flow_comment(inline)
            if not inline.endswith("]"):
                raise ValueError(f"{key} must be a list of strings")
            body = inline[1:-1].strip()
            if not body:
                return ()
            return tuple(_list_item(part, key) for part in _flow_items(body, key))
        return (_list_item(inline, key),)
    return ()
