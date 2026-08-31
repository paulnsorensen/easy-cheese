#!/usr/bin/env python3
"""Parse the per-invocation research ledger written beside a report.

`references/context-isolation.md` has always told /briesearch to write a
`manifest.json` recording the URL, title, selected provider, and fetch date of
every stored body. That contract was prose only — nothing ever read the file
back — so a report could cite a URL no provider retrieval tool ever opened
(#493) and one invocation could extract the same canonical URL repeatedly with
nothing noticing (#549).

This module parses that file into a validated ledger. It is a trust boundary:
the JSON is written by an agent mid-run, so every field is checked here and
callers see typed calls or a `LedgerError`.

Ledger shape::

    {
      "slug": "hybrid-retrieval-fusion",
      "invocation": "top-level",              # or "sidechain"
      "budget": {"search": 12, "extract": 6}, # optional soft budget
      "extensions": [{"gap": "no-primary-source", "note": "…"}],
      "calls": [
        {"kind": "search",  "provider": "tavily", "tool": "tavily_search",
         "query": "rrf fusion", "filters": {"days": 30}, "status": "ok"},
        {"kind": "extract", "provider": "tavily", "tool": "tavily_extract",
         "url": "https://example.com/a", "file": "raw/01-example.md",
         "title": "A", "fetched": "2026-08-30", "status": "ok"},
        {"kind": "spawn",   "provider": "researcher", "status": "ok"}
      ]
    }
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final, cast
from urllib.parse import urlsplit, urlunsplit

MANIFEST_NAME: Final = "manifest.json"

SEARCH: Final = "search"
EXTRACT: Final = "extract"
SPAWN: Final = "spawn"
CALL_KINDS: Final = frozenset({SEARCH, EXTRACT, SPAWN})

OK: Final = "ok"
TOP_LEVEL: Final = "top-level"
SIDECHAIN: Final = "sidechain"
INVOCATIONS: Final = frozenset({TOP_LEVEL, SIDECHAIN})

# The only reasons `references/budgets.md` accepts for spending past a declared
# soft budget. An extension naming anything else is a free-text escape hatch,
# which is exactly the budget-defeating move the check exists to catch.
EVIDENCE_GAPS: Final = frozenset(
    {
        "no-primary-source",
        "unresolved-contradiction",
        "missing-freshness",
        "unanswered-question",
        "unsupported-claim",
    }
)

_DEFAULT_PORTS: Final = {"http": 80, "https": 443}


class LedgerError(ValueError):
    """The manifest exists but is not a ledger this code can trust."""


@dataclass(frozen=True)
class Call:
    """One recorded provider call: a search, an extraction, or a worker spawn."""

    kind: str
    provider: str
    tool: str = ""
    status: str = OK
    query: str = ""
    # Canonical JSON of the call's filter arguments (date window, domain
    # include/exclude, depth). Two searches differing only in key order are the
    # same search, so the sorted encoding — not the dict — is the identity.
    filters: str = ""
    url: str = ""
    canonical: str = ""
    file: str = ""
    refresh: bool = False
    cached: bool = False

    @property
    def ok(self) -> bool:
        return self.status == OK


@dataclass(frozen=True)
class Extension:
    """A recorded reason for spending past a declared soft budget."""

    gap: str
    note: str = ""


@dataclass(frozen=True)
class Ledger:
    """A parsed `manifest.json`: what this invocation actually called."""

    invocation: str = TOP_LEVEL
    calls: tuple[Call, ...] = ()
    budget: dict[str, int] = field(default_factory=dict)
    extensions: tuple[Extension, ...] = ()

    def retrieved(self) -> dict[str, Call]:
        """Canonical URL -> the first successful retrieval that named its tool.

        A URL that was only *discovered* by a search, or whose retrieval failed,
        is absent: those never satisfy "verify then cite".
        """
        out: dict[str, Call] = {}
        for call in self.calls:
            if call.kind != EXTRACT or not call.ok or not call.tool:
                continue
            _ = out.setdefault(call.canonical, call)
        return out


def canonical_url(raw: str) -> str:
    """Collapse the spellings of one URL that name the same resource.

    Scheme and host case, a default port, a trailing slash, and a fragment do
    not change what was fetched. The query does, and so does the rest of the
    path — deduplication that merged those would merge distinct evidence.
    """
    text = raw.strip()
    parts = urlsplit(text)
    if not parts.scheme or not parts.netloc:
        return text
    try:
        port = parts.port
    except ValueError:
        return text
    host = (parts.hostname or "").casefold()
    scheme = parts.scheme.casefold()
    netloc = host if port in (None, _DEFAULT_PORTS.get(scheme)) else f"{host}:{port}"
    return urlunsplit((scheme, netloc, parts.path.rstrip("/"), parts.query, ""))


def _as_object(value: object, what: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise LedgerError(f"{what} must be a JSON object, got {type(value).__name__}")
    return {str(k): v for k, v in cast("dict[object, object]", value).items()}


def _text(entry: dict[str, object], key: str, what: str, *, required: bool) -> str:
    value = entry.get(key)
    if value is None or value == "":
        if required:
            raise LedgerError(f"{what} is missing required field {key!r}")
        return ""
    if not isinstance(value, str):
        raise LedgerError(f"{what} field {key!r} must be a string")
    return value.strip()


def _flag(entry: dict[str, object], key: str, what: str) -> bool:
    value = entry.get(key, False)
    if not isinstance(value, bool):
        raise LedgerError(f"{what} field {key!r} must be true or false")
    return value


def _filters(entry: dict[str, object], what: str) -> str:
    """Canonical JSON for the call's filters, so key order is not identity."""
    value = entry.get("filters")
    if value is None:
        return ""
    filters = _as_object(value, f"{what} field 'filters'")
    if not filters:
        return ""
    try:
        return json.dumps(filters, sort_keys=True, separators=(",", ":"))
    except TypeError as exc:
        raise LedgerError(f"{what} field 'filters' is not JSON-encodable: {exc}") from exc


def _parse_call(value: object, index: int) -> Call:
    what = f"calls[{index}]"
    entry = _as_object(value, what)
    kind = _text(entry, "kind", what, required=True)
    if kind not in CALL_KINDS:
        raise LedgerError(
            f"{what} has unknown kind {kind!r}; expected one of "
            + ", ".join(sorted(CALL_KINDS))
        )
    url = _text(entry, "url", what, required=kind == EXTRACT)
    return Call(
        kind=kind,
        provider=_text(entry, "provider", what, required=True),
        # Which provider tool ran is the whole point of #493: a generic fetch and
        # the provider's own extraction tool are not interchangeable evidence.
        tool=_text(entry, "tool", what, required=kind != SPAWN),
        status=_text(entry, "status", what, required=False) or OK,
        query=_text(entry, "query", what, required=kind == SEARCH),
        filters=_filters(entry, what),
        url=url,
        canonical=canonical_url(url) if url else "",
        file=_text(entry, "file", what, required=False),
        refresh=_flag(entry, "refresh", what),
        cached=_flag(entry, "cached", what),
    )


def _parse_extension(value: object, index: int) -> Extension:
    """Parse a budget extension. The gap label is *not* validated here — an
    unrecognised label is a budget finding to report, not a corrupt manifest."""
    what = f"extensions[{index}]"
    entry = _as_object(value, what)
    return Extension(
        gap=_text(entry, "gap", what, required=True),
        note=_text(entry, "note", what, required=False),
    )


def _parse_budget(value: object) -> dict[str, int]:
    if value is None:
        return {}
    entry = _as_object(value, "budget")
    budget: dict[str, int] = {}
    for kind, limit in entry.items():
        if kind not in CALL_KINDS:
            raise LedgerError(f"budget names unknown call kind {kind!r}")
        if not isinstance(limit, int) or isinstance(limit, bool) or limit < 0:
            raise LedgerError(f"budget[{kind!r}] must be a non-negative integer")
        budget[kind] = limit
    return budget


def _sequence(data: dict[str, object], key: str) -> list[object]:
    value = data.get(key, [])
    if not isinstance(value, list):
        raise LedgerError(f"{key!r} must be a JSON array")
    return list(value)  # pyright: ignore[reportUnknownArgumentType]


def parse_ledger(data: object) -> Ledger:
    """Validate a decoded manifest document into a `Ledger`."""
    document = _as_object(data, "manifest")
    invocation = _text(document, "invocation", "manifest", required=False) or TOP_LEVEL
    if invocation not in INVOCATIONS:
        raise LedgerError(
            f"manifest invocation {invocation!r} must be "
            + " or ".join(sorted(INVOCATIONS))
        )
    return Ledger(
        invocation=invocation,
        calls=tuple(
            _parse_call(call, i) for i, call in enumerate(_sequence(document, "calls"))
        ),
        budget=_parse_budget(document.get("budget")),
        extensions=tuple(
            _parse_extension(ext, i)
            for i, ext in enumerate(_sequence(document, "extensions"))
        ),
    )


def load_ledger(path: Path) -> Ledger:
    """Read and validate the ledger at `path`. Raises `LedgerError` on any fault."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise LedgerError(f"cannot read {path}: {exc}") from exc
    try:
        data = cast(object, json.loads(text))
    except json.JSONDecodeError as exc:
        raise LedgerError(f"{path} is not valid JSON: {exc}") from exc
    return parse_ledger(data)


def find_ledger(report_dir: Path) -> Path | None:
    """The capture manifest `/briesearch` writes beside a deep report, if present."""
    candidate = report_dir / MANIFEST_NAME
    return candidate if candidate.is_file() else None
