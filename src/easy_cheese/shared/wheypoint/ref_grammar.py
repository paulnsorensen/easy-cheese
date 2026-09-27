"""The per-scheme grammar of a `WorkRef` and its one canonical spelling.

This module does no I/O, so `records` can parse a reference without an
import cycle through `storage`. `refs` re-exports it and adds resolution.
"""

from __future__ import annotations

import re
from enum import Enum

from attrs import define
from easy_cheese_schemas import LOWER_IDENTIFIER_RE

__all__ = ["ParsedRef", "Scheme", "is_pinnable", "normalize_ref", "parse_ref"]


class Scheme(str, Enum):
    REPO = "repo"
    XDG = "xdg"
    WHEYPOINT = "wheypoint"
    MILKNADO = "milknado"
    HTTPS = "https"


_PINNABLE = frozenset({Scheme.REPO, Scheme.XDG, Scheme.WHEYPOINT})
_WHEYPOINT_RE = re.compile(
    r"(?P<project>[^/@#]+)/(?P<work>[^/@#]+)"
    + r"(?:@(?P<revision>[^/@#]+))?(?:#(?P<entry>[^/@#]+))?"
)


@define(frozen=True, kw_only=True)
class ParsedRef:
    scheme: Scheme
    project_key: str | None = None
    path: str | None = None
    work_id: str | None = None
    revision_id: str | None = None
    entry_id: str | None = None
    raw: str


def is_pinnable(scheme: Scheme) -> bool:
    """Whether a reference in this scheme can carry a digest pin."""
    return scheme in _PINNABLE


def parse_ref(ref: str) -> ParsedRef:
    """Split `ref` into its scheme parts, or raise `ValueError` naming why."""
    scheme_text, separator, body = ref.partition(":")
    try:
        scheme = Scheme(scheme_text.lower()) if separator else None
    except ValueError:
        scheme = None
    if scheme is None:
        known = ", ".join(f"{item.value}:" for item in Scheme)
        raise ValueError(f"unknown-scheme: {ref!r} names none of {known}")
    body = body.rstrip("/")
    if scheme is Scheme.REPO:
        return ParsedRef(scheme=scheme, path=_contained(body, ref), raw=ref)
    if scheme is Scheme.XDG:
        project, _, rest = body.partition("/")
        if not rest:
            raise ValueError(f"xdg: {ref!r} must be xdg:<project_key>/<path>")
        return ParsedRef(
            scheme=scheme,
            project_key=_segment(project, ref),
            path=_contained(rest, ref),
            raw=ref,
        )
    if scheme is Scheme.WHEYPOINT:
        return _parse_wheypoint(body, ref)
    if scheme is Scheme.MILKNADO:
        project, _, node = body.partition("/")
        if not node:
            raise ValueError(
                f"milknado: {ref!r} must be milknado:<project_key>/<node_key>"
            )
        return ParsedRef(
            scheme=scheme, project_key=_segment(project, ref), path=node, raw=ref
        )
    if not body.startswith("//") or len(body) == 2:
        raise ValueError(f"https: {ref!r} must be https://<host>[/<path>]")
    return ParsedRef(scheme=scheme, path=body, raw=ref)


def normalize_ref(ref: str) -> str:
    """The one canonical spelling of `ref`."""
    return _render(parse_ref(ref))


def _parse_wheypoint(body: str, ref: str) -> ParsedRef:
    match = _WHEYPOINT_RE.fullmatch(body)
    ids = () if match is None else (match["work"], match["revision"], match["entry"])
    if match is None or not all(
        LOWER_IDENTIFIER_RE.fullmatch(value) for value in ids if value is not None
    ):
        raise ValueError(
            f"wheypoint: {ref!r} must be "
            + "wheypoint:<project_key>/<work_id>[@<revision_id>][#<entry_id>]"
        )
    return ParsedRef(
        scheme=Scheme.WHEYPOINT,
        project_key=_segment(match["project"], ref),
        work_id=match["work"],
        revision_id=match["revision"],
        entry_id=match["entry"],
        raw=ref,
    )


def _render(parsed: ParsedRef) -> str:
    scheme = parsed.scheme
    if scheme is Scheme.REPO or scheme is Scheme.HTTPS:
        return f"{scheme.value}:{parsed.path}"
    if scheme is Scheme.WHEYPOINT:
        revision = "" if parsed.revision_id is None else f"@{parsed.revision_id}"
        entry = "" if parsed.entry_id is None else f"#{parsed.entry_id}"
        return f"wheypoint:{parsed.project_key}/{parsed.work_id}{revision}{entry}"
    return f"{scheme.value}:{parsed.project_key}/{parsed.path}"


def _segment(value: str, ref: str) -> str:
    if value in {"", ".", ".."}:
        raise ValueError(f"escapes: {ref!r} names no single project segment")
    return value


def _contained(text: str, ref: str) -> str:
    """`text` as a POSIX path that stays under its root."""
    if text.startswith("/"):
        raise ValueError(f"escapes: {ref!r} names an absolute path")
    parts = [part for part in text.split("/") if part not in {"", "."}]
    if ".." in parts:
        raise ValueError(f"escapes: {ref!r} climbs out of its root")
    if not parts:
        raise ValueError(f"empty-path: {ref!r} names no path")
    return "/".join(parts)
