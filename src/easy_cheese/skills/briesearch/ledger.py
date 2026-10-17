#!/usr/bin/env python3
"""Parse the per-invocation research ledger written beside a report.

`references/context-isolation.md` tells /briesearch to write a
`manifest.json` recording the report slug, a safe URL display value, its
digest, the selected provider, the title, and the fetch date for every stored
body. This module parses that file
back as a trust boundary, so a report cannot cite a URL that no provider
retrieval tool opened (#493), and one invocation cannot extract the same URL
repeatedly without being noticed (#549).

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
         "url": "https://example.com/a",
         "url_digest": "a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3",
         "title": "A", "fetched": "2026-08-30", "status": "ok"},
        {"kind": "spawn",   "provider": "researcher", "status": "ok"}
      ]
    }
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final, cast
from urllib.parse import SplitResult, urlsplit, urlunsplit

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
_URL_DIGEST: Final = re.compile(r"^[0-9a-fA-F]{64}$")
_URL_USERINFO_ERROR: Final = "URL user information is not allowed"
_ISO_DATE: Final = re.compile(r"\d{4}-\d{2}-\d{2}")


def _netloc(parts: "SplitResult", scheme: str) -> str:
    """Return a host and meaningful port without user information."""
    host = (parts.hostname or "").casefold()
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    port = parts.port
    return host if port in (None, _DEFAULT_PORTS.get(scheme)) else f"{host}:{port}"


def render_url(raw: str) -> str:
    """Render a URL without user information, query values, or fragments."""
    text = raw.strip()
    try:
        parts = urlsplit(text)
        if not parts.scheme or not parts.netloc:
            return "<invalid URL>"
        scheme = parts.scheme.casefold()
        netloc = _netloc(parts, scheme)
    except ValueError:
        return "<invalid URL>"
    return urlunsplit((scheme, netloc, parts.path or "/", "", ""))


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
    # URL fields are safe to retain in memory and diagnostics. The digest is
    # the identity used for correlation because it includes the full URL.
    url: str = ""
    url_digest: str = ""
    title: str = ""
    # ISO ``YYYY-MM-DD`` date the body was retrieved. A report row binds its
    # Freshness value to this date, so the ledger must retain it.
    fetched: str = ""
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

    slug: str = ""
    invocation: str = TOP_LEVEL
    calls: tuple[Call, ...] = ()
    budget: dict[str, int] = field(default_factory=dict)
    extensions: tuple[Extension, ...] = ()

    def retrieved(self) -> dict[str, Call]:
        """URL digest -> the first successful retrieval that named its tool.

        Each call has its full URL digest and its safe display URL digest. This
        lets a redacted citation correlate without retaining query values.
        """
        out: dict[str, Call] = {}
        for call in self.calls:
            if call.kind != EXTRACT or not call.ok or not call.tool:
                continue
            identities = {call.url_digest}
            if call.url:
                identities.add(url_digest(call.url))
            for identity in identities:
                if identity:
                    _ = out.setdefault(identity, call)
        return out


def canonical_url(raw: str) -> str:
    """Normalize a URL for correlation without merging distinct resources.

    Scheme and host case, a default port, and a fragment do not change what was
    fetched. The query and path do, including a non-root trailing slash. An
    empty path is normalized to ``/``. URLs with user information are rejected
    rather than retained.
    """
    text = raw.strip()
    try:
        parts = urlsplit(text)
    except ValueError:
        return text
    if parts.username is not None or parts.password is not None:
        raise ValueError(_URL_USERINFO_ERROR)
    if not parts.scheme or not parts.netloc:
        return text
    try:
        scheme = parts.scheme.casefold()
        netloc = _netloc(parts, scheme)
    except ValueError:
        return text
    return urlunsplit((scheme, netloc, parts.path or "/", parts.query, ""))


def url_digest(raw: str) -> str:
    """Return a non-reversible SHA-256 identity for the full canonical URL."""
    return hashlib.sha256(canonical_url(raw).encode("utf-8")).hexdigest()


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


def _url_fields(entry: dict[str, object], what: str, raw_url: str) -> tuple[str, str]:
    """Return a safe display URL and the full-URL digest."""
    if not raw_url:
        supplied = _text(entry, "url_digest", what, required=False)
        if supplied:
            raise LedgerError(f"{what} field 'url_digest' requires a URL")
        return "", ""
    try:
        parts = urlsplit(raw_url)
        computed = url_digest(raw_url)
    except ValueError as exc:
        raise LedgerError(
            f"{what} field 'url' contains forbidden user information at "
            + f"{render_url(raw_url)!r}"
        ) from exc
    if parts.query:
        raise LedgerError(
            f"{what} field 'url' must omit query values; use 'url_digest' "
            + "for the full URL identity"
        )
    supplied = _text(entry, "url_digest", what, required=False)
    if supplied:
        digest = supplied.removeprefix("sha256:")
        if _URL_DIGEST.fullmatch(digest) is None:
            raise LedgerError(
                f"{what} field 'url_digest' must be a SHA-256 hexadecimal digest"
            )
        digest = digest.casefold()
    else:
        digest = computed
    return render_url(raw_url), digest


def _parse_call(value: object, index: int) -> Call:
    what = f"calls[{index}]"
    entry = _as_object(value, what)
    kind = _text(entry, "kind", what, required=True)
    if kind not in CALL_KINDS:
        raise LedgerError(
            f"{what} has unknown kind {kind!r}; expected one of "
            + ", ".join(sorted(CALL_KINDS))
        )
    raw_url = _text(entry, "url", what, required=kind == EXTRACT)
    display_url, digest = _url_fields(entry, what, raw_url)
    return Call(
        kind=kind,
        provider=_text(entry, "provider", what, required=True),
        # Which provider tool ran is the whole point of #493: a generic fetch and
        # the provider's own extraction tool are not interchangeable evidence.
        tool=_text(entry, "tool", what, required=kind != SPAWN),
        status=_text(entry, "status", what, required=False) or OK,
        query=_text(entry, "query", what, required=kind == SEARCH),
        filters=_filters(entry, what),
        url=display_url,
        url_digest=digest,
        title=_text(entry, "title", what, required=False),
        fetched=_fetched(entry, what),
        file=_text(entry, "file", what, required=False),
        refresh=_flag(entry, "refresh", what),
        cached=_flag(entry, "cached", what),
    )


def _fetched(entry: dict[str, object], what: str) -> str:
    """Return the retrieval date. An unparsable date is a corrupt manifest."""
    value = _text(entry, "fetched", what, required=False)
    if value and _ISO_DATE.fullmatch(value) is None:
        raise LedgerError(f"{what} field 'fetched' must be an ISO YYYY-MM-DD date")
    return value


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
        slug=_text(document, "slug", "manifest", required=False),
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
