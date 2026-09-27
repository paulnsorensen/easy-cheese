"""Scheme-typed references: one string names a file, a document, or a record.

A `WorkRef` is an absolute URI string. This module re-exports the grammar
from `ref_grammar` and owns the digest a reference pins:

| Scheme       | Form                                                    | Digest pin |
| ------------ | ------------------------------------------------------- | ---------- |
| `repo:`      | `repo:<repo-relative path>`                             | sha256 of the file bytes |
| `xdg:`       | `xdg:<project_key>/<path>`                              | sha256 of the file bytes |
| `wheypoint:` | `wheypoint:<project_key>/<work_id>[@<rev>][#<entry>]`   | the target `record_digest` |
| `milknado:`  | `milknado:<project_key>/<node_key>`                     | none |
| `https:`     | a PR, issue, or URL                                     | none |

A `repo:` or `xdg:` path that climbs out of its root is refused, and a
file reached through a symlink outside that root has no digest. A
`wheypoint:` target is read without its lock: the read is a pin, not a write.
An unpinnable scheme is never checked for existence.
"""

from __future__ import annotations

import functools
from collections.abc import Callable
from pathlib import Path

from attrs import define

from . import records, storage
from .ref_grammar import ParsedRef, Scheme, is_pinnable, normalize_ref, parse_ref

__all__ = [
    "ParsedRef",
    "ResolvedRef",
    "Scheme",
    "digest_ref",
    "digester",
    "is_pinnable",
    "normalize_ref",
    "parse_ref",
    "resolve_ref",
]


@define(frozen=True, kw_only=True)
class ResolvedRef:
    ref: str
    scheme: Scheme
    location: Path | None
    digest: str | None


def resolve_ref(ref: str, *, checkout: Path, corpus_home: Path) -> ResolvedRef:
    """Where `ref` points and the digest it pins now, if it pins one."""
    parsed = parse_ref(ref)
    location: Path | None = None
    digest: str | None = None
    if parsed.scheme is Scheme.REPO:
        location, digest = _file(Path(checkout), _required(parsed.path))
    elif parsed.scheme is Scheme.XDG:
        root = Path(corpus_home) / _required(parsed.project_key)
        location, digest = _file(root, _required(parsed.path))
    elif parsed.scheme is Scheme.WHEYPOINT:
        location, digest = _record(parsed, Path(corpus_home))
    return ResolvedRef(
        ref=normalize_ref(ref), scheme=parsed.scheme, location=location, digest=digest
    )


def digest_ref(ref: str, *, checkout: Path, corpus_home: Path) -> str | None:
    """The digest `ref` pins now, or None when it pins nothing."""
    return resolve_ref(ref, checkout=checkout, corpus_home=corpus_home).digest


def digester(checkout: Path, corpus_home: Path) -> Callable[[str], str | None]:
    """A memoized digest callback; a malformed reference digests to None."""

    @functools.cache
    def digest(ref: str) -> str | None:
        try:
            return digest_ref(ref, checkout=checkout, corpus_home=corpus_home)
        except ValueError:
            return None

    return digest


def _required(value: str | None) -> str:
    if value is None:
        raise ValueError("parsed reference lacks a part its scheme requires")
    return value


def _file(root: Path, relative: str) -> tuple[Path, str | None]:
    location = root / relative
    try:
        resolved_root = root.resolve()
        resolved = location.resolve()
        if not resolved.is_relative_to(resolved_root) or not resolved.is_file():
            return location, None
        return location, storage.file_digest(resolved)
    except (OSError, RuntimeError):
        return location, None


def _record(parsed: ParsedRef, corpus_home: Path) -> tuple[Path, str | None]:
    store = storage.WorkStore.open(
        _required(parsed.work_id),
        corpus_root=corpus_home / _required(parsed.project_key),
    )
    try:
        if parsed.revision_id is not None:
            receipt = store.find_complete_revision(parsed.revision_id)
            return store.root, None if receipt is None else receipt.record_digest
        record = store.read_record()
    except (OSError, ValueError):
        return store.root, None
    return store.root, None if record is None else records.record_digest(record)
