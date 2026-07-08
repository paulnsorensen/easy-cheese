"""Shared extractor for relative markdown refs (links + backticked prose),
used by both the live-tree resolve gate (test_reference_resolution.py) and the
staged-tree resolve check (test_stage_release.py)."""

from __future__ import annotations

import re

_MD_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
_BACKTICK_RE = re.compile(r"`([^`]+)`")
_PROSE_REF_RE = re.compile(r"^(?:\.\./)+[\w./-]+\.md(?:#[\w-]+)?$|^references/[\w./-]+\.md(?:#[\w-]+)?$")


def relative_md_refs(text: str) -> list[str]:
    """Every relative markdown-link target and backticked relative-path prose
    ref in ``text``, with any `#fragment` (and ` § heading` prose suffix)
    stripped."""
    refs: list[str] = []
    for match in _MD_LINK_RE.finditer(text):
        target = match.group(1)
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        path = target.split("#", 1)[0]
        if path.endswith(".md"):
            refs.append(path)
    for match in _BACKTICK_RE.finditer(text):
        candidate = match.group(1).split(" § ", 1)[0]
        if _PROSE_REF_RE.match(candidate):
            refs.append(candidate.split("#", 1)[0])
    return refs