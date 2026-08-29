"""Build-only compiler for the marker-derived schema catalog.

This module is intentionally excluded from wheels and runtime bundles.  The
runtime imports only the generated ``_schema_catalog`` projection.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Protocol

SCHEMA_ROOT = "https://schemas.easy-cheese.dev"
_IDENTIFIER_RE = re.compile(r"[^A-Za-z0-9]+")


class _ContractModule(Protocol):
    def _registered_contracts(self) -> tuple[tuple[str, type], ...]: ...


def collect(module: _ContractModule) -> tuple[tuple[str, str], ...]:
    """Project marked contract classes into ``(slug, class name)`` pairs."""
    entries = module._registered_contracts()  # pyright: ignore[reportPrivateUsage]
    return tuple((slug, contract.__name__) for slug, contract in entries)


def _constant_name(slug: str) -> str:
    stem = _IDENTIFIER_RE.sub("_", slug).strip("_").upper()
    if not stem or stem[0].isdigit():
        raise ValueError(f"contract marker cannot form a constant name: {slug!r}")
    return f"{stem}_SCHEMA_URI"


def render(pairs: Sequence[tuple[str, str]]) -> str:
    """Render deterministic, dependency-free catalog source for ``pairs``."""
    ordered = tuple(sorted(pairs))
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
