"""Build-only compiler for the marker-derived schema catalog.

This module is intentionally excluded from wheels and runtime bundles.  The
runtime imports only the generated ``_schema_catalog`` projection.
"""

from __future__ import annotations

import inspect
import re
from types import ModuleType
from typing import Sequence

SCHEMA_ROOT = "https://schemas.easy-cheese.dev"
_MARKER = "__contract_slug__"
_IDENTIFIER_RE = re.compile(r"[^A-Za-z0-9]+")


def collect(module: ModuleType) -> tuple[tuple[str, str], ...]:
    """Collect marked contract classes from ``module`` in slug order."""
    pairs: list[tuple[str, str]] = []
    for value in vars(module).values():
        if not inspect.isclass(value):
            continue
        slug = getattr(value, _MARKER, None)
        if slug is None:
            continue
        if not isinstance(slug, str) or not slug:
            raise ValueError("contract marker must be a non-empty string")
        pairs.append((slug, value.__name__))

    pairs.sort()
    for previous, current in zip(pairs, pairs[1:]):
        if previous[0] == current[0]:
            raise ValueError(f"duplicate contract marker {current[0]!r}")
    return tuple(pairs)


def _constant_name(slug: str) -> str:
    stem = _IDENTIFIER_RE.sub("_", slug).strip("_").upper()
    if not stem or stem[0].isdigit():
        raise ValueError(f"contract marker cannot form a constant name: {slug!r}")
    return f"{stem}_SCHEMA_URI"


def render(pairs: Sequence[tuple[str, str]]) -> str:
    """Render deterministic, dependency-free catalog source for ``pairs``."""
    ordered = tuple(sorted(pairs))
    slugs = [slug for slug, _class_name in ordered]
    if len(slugs) != len(set(slugs)):
        raise ValueError("duplicate contract marker")
    constants = [(_constant_name(slug), slug) for slug, _class_name in ordered]
    names = [name for name, _slug in constants]
    if len(names) != len(set(names)):
        raise ValueError("contract markers produce duplicate constants")

    lines = [
        '"""Generated dependency-free canonical contract schema catalogue."""',
        "",
        "from __future__ import annotations",
        "",
        f'SCHEMA_ROOT = {SCHEMA_ROOT!r}',
    ]
    lines.extend(f'{name} = f"{{SCHEMA_ROOT}}/{slug}"' for name, slug in constants)
    lines.extend(["", "REGISTERED_CONTRACT_SCHEMA_URIS = frozenset(", "    {"])
    lines.extend(f"        {name}," for name in names)
    lines.extend(["    }", ")", ""])
    return "\n".join(lines)
