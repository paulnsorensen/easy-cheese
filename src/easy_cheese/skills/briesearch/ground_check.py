#!/usr/bin/env python3
"""Lint a /briesearch synthesis report for grounding violations.

A synthesis must not assert a claim its own evidence does not support. This is
the mechanical backstop behind ``references/synthesis.md`` § Grounding: the prompt
already says "return citations", yet an un-cited absence claim ("Codex has no
static config permission surface") still shipped and survived ~20 turns. A model
self-check is not enough; this runs every claim row through deterministic checks
so the failure cannot recur silently.

Reads a markdown report, finds every evidence table (a table whose header has a
``Claim`` column and a ``Confidence`` column), and per data row enforces:

  - CITATION (error): the evidence/source cell carries a URL, an inline
    ``path:line``, a confined local path, or a uniquely defined footnote
    containing one of those citation shapes. Every local citation resolves under
    its allowed root, and every line anchor (``path:12-40`` or ``path#L12-40``)
    names lines the file has.
    A claim with none is un-grounded.
  - CONFIDENCE (error): the confidence cell is exactly one of the three label
    values (``certain`` / ``speculating`` / ``don't know``), not a synonym and
    not a case variant.
  - FRESHNESS (error): a row date that disagrees with the manifest fetch date of
    the body it cites.
  - MANIFEST (error): a manifest slug that names another report, or a successful
    capture that stored no confined raw body.
  - ABSENCE (advisory): a negative/absence-shaped claim marked ``certain`` that
    carries no ruling-out phrase. Whether an absence was *observed* (a cited
    source states it) or *inferred* (synthesised from silence) is not decidable
    from text, so this is surfaced, not failed — it feeds the synthesis-fidelity
    self-check, which downgrades inferred absences to "not found in <sources>".
  - REMOTE (error): a cited ``http(s)`` URL that the run's capture manifest does
    not record as retrieved through a provider retrieval tool (#493), or a
    citation that carries user information, a query value, or a fragment. Routing
    tells the agent to open every cited page with the selected provider's own
    extraction tool; without this the claim "verify then cite" was unauditable,
    and a URL that only ever appeared in a search result list could be cited as
    if it had been read. Checked against the ledger, never over the network: the
    bundle does no I/O beyond the corpus. With no manifest beside the report the
    check degrades to a single MANIFEST advisory.

Exit: 0 clean (advisories may print), 1 on any error-level violation or when a
report carries no evidence table, 2 on bad args / unreadable file.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast
from urllib.parse import urlsplit

from easy_cheese.skills.briesearch.ledger import (
    EXTRACT,
    Call,
    Ledger,
    LedgerError,
    find_ledger,
    load_ledger,
    render_url,
    url_digest,
)

CONFIDENCE_LABELS = {"certain", "speculating", "don't know"}

# A verifiable citation marker: footnote ref, URL, inline path:line, or a
# durable-corpus / raw-capture path. A prose source name can describe evidence,
# but it cannot be re-checked by the gate.
_FOOTNOTE_REF = re.compile(r"\[\^([^\]]+)\]")
_DIRECT_CITATION = re.compile(
    (
        r"https?://\S+"  # URL
        r"|[\w./-]+\.[A-Za-z]\w*:\d+(?:-\d+)?"  # inline path:line(-line)
        r"|(?:\.cheese|raw)/\S+"  # corpus or raw-capture path
    ),
    re.IGNORECASE,
)
_CITATION = re.compile(r"\[\^[^\]]+\]|" + _DIRECT_CITATION.pattern, re.IGNORECASE)
_REMOTE_START = re.compile(r"https?://", re.IGNORECASE)
_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_URL_OPENERS = frozenset("([{")
_URL_CLOSERS = {")": "(", "]": "[", "}": "{"}
_FOOTNOTE_DEFINITION = re.compile(r"^\[\^([^\]]+)\]:\s*(.*)$")
_LOCAL_PATH = re.compile(r"(?:^|[\s(])((?:\.cheese|raw)/[^\s|]+)", re.IGNORECASE)
# A local line anchor is written either ``path:12-40`` or ``path#L12-40``.
# `context-isolation.md` § The recipe requires the ``#L`` form for raw captures.
_LINE_ANCHOR = re.compile(r"(?::|#L)(\d+)(?:-L?(\d+))?$", re.IGNORECASE)
# A repository-relative ``path:line`` citation. The line part is required: a bare
# file name is prose, not a location a reader can check.
_INLINE_PATH = re.compile(
    r"(?<![\w/#-])((?:\.\.?/)*(?:[\w][\w.-]*/)*[\w][\w.-]*\.[A-Za-z]\w*:\d+(?:-\d+)?)"
)

# Negation aimed at existence / support / provision — the shape of an absence
# claim. Whole-word matched so "Cargo" never trips "no".
_ABSENCE = re.compile(
    (
        r"\b(?:no|not|never|none|cannot|can'?t|does\s*n'?t|do\s*n'?t|did\s*n'?t"
        r"|is\s*n'?t|are\s*n'?t|was\s*n'?t|wo\s*n'?t|lacks?|lacking|without"
        r"|absent|missing|unsupported|unavailable)\b"
    ),
    re.IGNORECASE,
)

# Phrases that claim a stronger ruling-out than a searched-but-empty source.
_RULED_OUT = re.compile(
    r"ruled out|checked\b",
    re.IGNORECASE,
)


class Violation:
    __slots__: tuple[str, ...] = ("level", "row", "kind", "message")

    level: str  # "error" | "advisory"
    row: int
    kind: str
    message: str

    def __init__(self, level: str, row: int, kind: str, message: str) -> None:
        self.level = level
        self.row = row
        self.kind = kind
        self.message = message

    def render(self) -> str:
        return f"{self.level.upper()} [row {self.row}] {self.kind}: {self.message}"


def _split_row(line: str) -> list[str]:
    """Split a markdown table row into trimmed cells, dropping the edge pipes.

    A backslash escapes a pipe in Markdown. A naive split moves every later cell
    one column left, so a claim that contains ``\\|`` reads the wrong confidence
    value. The escape is removed from the cell text after the split.
    """
    inner = line.strip()
    if inner.startswith("|") and not inner.startswith("\\|"):
        inner = inner[1:]
    if inner.endswith("|") and not inner.endswith("\\|"):
        inner = inner[:-1]
    cells: list[str] = []
    current: list[str] = []
    escaped = False
    for char in inner:
        if escaped:
            current.append(char if char == "|" else f"\\{char}")
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == "|":
            cells.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    if escaped:
        current.append("\\")
    cells.append("".join(current).strip())
    return cells


def _is_separator(cells: list[str]) -> bool:
    return all(re.fullmatch(r":?-{1,}:?", c) is not None for c in cells if c)


@dataclass(frozen=True)
class _Columns:
    """Column indices of one evidence table. `freshness` is -1 when absent."""

    claim: int
    evidence: int
    confidence: int
    freshness: int

    @property
    def width(self) -> int:
        return max(self.claim, self.evidence, self.confidence, self.freshness) + 1


@dataclass
class _Context:
    """Everything one row check reads that the report, not the row, supplies."""

    footnotes: dict[str, str]
    report_dir: Path
    invocation_dir: Path
    retrieved: Mapping[str, Call] | None
    remote_seen: set[str]
    line_counts: dict[Path, int]


def _find_columns(header: list[str]) -> _Columns | None:
    """Return the evidence-table column indices, or None if this is not an
    evidence table. The evidence column matches "Evidence" or "Source"."""
    lower = [h.lower() for h in header]
    claim = evidence = confidence = freshness = -1
    for i, h in enumerate(lower):
        if claim < 0 and "claim" in h:
            claim = i
        if evidence < 0 and ("evidence" in h or "source" in h):
            evidence = i
        if confidence < 0 and "confidence" in h:
            confidence = i
        if freshness < 0 and "freshness" in h:
            freshness = i
    if claim < 0 or confidence < 0:
        return None
    if evidence < 0:
        evidence = claim  # degenerate table: cite inside the claim cell
    return _Columns(claim, evidence, confidence, freshness)


def _footnote_definitions(lines: list[str]) -> tuple[dict[str, str], set[str]]:
    definitions: dict[str, str] = {}
    duplicates: set[str] = set()
    current: str | None = None
    for line in lines:
        if match := _FOOTNOTE_DEFINITION.match(line.strip()):
            label = match.group(1)
            body = match.group(2)
            if label in definitions:
                duplicates.add(label)
                current = None
            else:
                definitions[label] = body
                current = label
        elif current and (line.startswith("    ") or line.startswith("\t")):
            definitions[current] += f"\n{line.strip()}"
        elif line.strip():
            current = None
    return definitions, duplicates


def _line_count(target: Path, cache: dict[Path, int]) -> int:
    """Count lines in `target` once for each report check."""
    cached = cache.get(target)
    if cached is None:
        with target.open("rb") as stream:
            cached = sum(1 for _ in stream)
        cache[target] = cached
    return cached


def _check_line_anchor(
    target: Path,
    anchor: re.Match[str],
    reference: str,
    row_no: int,
    cache: dict[Path, int],
) -> list[Violation]:
    start = int(anchor.group(1))
    end = int(anchor.group(2) or start)
    try:
        line_count = _line_count(target, cache)
    except OSError as exc:
        return [
            Violation(
                "error",
                row_no,
                "LOCAL_PATH",
                f"cannot read local evidence path {reference!r}: {exc}",
            )
        ]
    if 1 <= start <= end <= line_count:
        return []
    return [
        Violation(
            "error",
            row_no,
            "LOCAL_PATH",
            f"line anchor {anchor.group(0)!r} is outside {reference!r} "
            + f"({line_count} line(s))",
        )
    ]


def _local_references(text: str) -> list[str]:
    """Every local citation in `text`: corpus, raw capture, and inline path:line."""
    trailing = "`>.,;:!?)]}'\"*_~"
    references = [
        match.group(1).rstrip(trailing) for match in _LOCAL_PATH.finditer(text)
    ]
    # An inline path inside a URL is part of that URL, not a local file.
    without_urls = text
    for url in _remote_urls(text):
        without_urls = without_urls.replace(url, " " * len(url))
    for match in _INLINE_PATH.finditer(without_urls):
        reference = match.group(1)
        if not reference.casefold().startswith((".cheese/", "raw/")):
            references.append(reference)
    return references


def _resolve_local(
    local_path: str, report_dir: Path, invocation_dir: Path
) -> tuple[Path, Path]:
    """Return the allowed root and the resolved target for one local citation."""
    if local_path.casefold().startswith("raw/"):
        return (report_dir / "raw").resolve(), (report_dir / local_path).resolve()
    if local_path.casefold().startswith(".cheese/"):
        root = (invocation_dir / ".cheese").resolve()
        return root, (invocation_dir / local_path).resolve()
    # A repository-relative location is confined to the invocation directory.
    return invocation_dir.resolve(), (invocation_dir / local_path).resolve()


def _check_local_paths(
    text: str,
    report_dir: Path,
    invocation_dir: Path,
    row_no: int,
    cache: dict[Path, int],
) -> list[Violation]:
    violations: list[Violation] = []
    for reference in _local_references(text):
        anchor = _LINE_ANCHOR.search(reference)
        local_path = reference[: anchor.start()] if anchor else reference
        root, target = _resolve_local(local_path, report_dir, invocation_dir)
        if not target.is_relative_to(root):
            violations.append(
                Violation(
                    "error",
                    row_no,
                    "LOCAL_PATH",
                    f"local evidence path is outside allowed root: {local_path!r}",
                )
            )
        elif not target.is_file():
            violations.append(
                Violation(
                    "error",
                    row_no,
                    "LOCAL_PATH",
                    f"local evidence path does not exist: {local_path!r}",
                )
            )
        elif anchor:
            violations.extend(
                _check_line_anchor(target, anchor, local_path, row_no, cache)
            )
    return violations


def _remote_urls(text: str) -> list[str]:
    """Find URLs while retaining balanced Markdown parentheses."""
    urls: list[str] = []
    for match in _REMOTE_START.finditer(text):
        cursor = match.end()
        stack: list[str] = []
        while cursor < len(text):
            char = text[cursor]
            if char.isspace() or char in ("<", ">", "|", '"', "'", "`"):
                break
            if char in _URL_OPENERS:
                stack.append(char)
            elif char in _URL_CLOSERS:
                if not stack or stack[-1] != _URL_CLOSERS[char]:
                    break
                _ = stack.pop()
            cursor += 1
        url = text[match.start() : cursor].rstrip(".,;:!?")
        if url:
            urls.append(url)
    return urls


def _url_secret(url: str) -> str | None:
    """Name the credential-bearing URL part, or None when the URL is safe."""
    try:
        parts = urlsplit(url)
    except ValueError:
        return None
    if parts.username is not None or parts.password is not None:
        return "user information"
    if parts.query:
        return "query value"
    if parts.fragment:
        return "fragment"
    return None


def _check_remote(
    citations: list[str], retrieved: Mapping[str, Call] | None, row_no: int
) -> list[Violation]:
    """Check cited URLs against the one report-level retrieval map.

    A persisted citation carries the scheme, host, and path only. A query value
    or a fragment can hold a signed token, so `safety.md` forbids it in a stored
    report. The digest match runs after that rejection, never instead of it.
    """
    violations: list[Violation] = []
    for url in dict.fromkeys(citations):
        secret = _url_secret(url)
        if secret is not None:
            violations.append(
                Violation(
                    "error",
                    row_no,
                    "REMOTE",
                    f"cited URL carries a forbidden {secret}: {render_url(url)!r}",
                )
            )
            continue
        try:
            identity = url_digest(url)
        except ValueError:
            violations.append(
                Violation(
                    "error",
                    row_no,
                    "REMOTE",
                    "cited URL contains forbidden user information: "
                    + f"{render_url(url)!r}",
                )
            )
            continue
        if retrieved is None or identity in retrieved:
            continue
        violations.append(
            Violation(
                "error",
                row_no,
                "REMOTE",
                "cited URL was never retrieved through a provider retrieval tool: "
                + f"{render_url(url)!r} (no successful entry in the capture manifest)",
            )
        )
    return violations


def _check_freshness(
    cells: list[str],
    cols: _Columns,
    citations: list[str],
    retrieved: Mapping[str, Call] | None,
    row_no: int,
) -> list[Violation]:
    """Bind the row's Freshness date to the manifest fetch date it cites.

    `context-isolation.md` § The recipe requires this binding. Without it a row
    can report a 2026 check over a body that a 2020 call retrieved.
    """
    if cols.freshness < 0 or retrieved is None:
        return []
    stated = _ISO_DATE.search(cells[cols.freshness])
    if stated is None:
        return []
    for url in dict.fromkeys(citations):
        if _url_secret(url) is not None:
            continue
        call = retrieved.get(url_digest(url))
        if call is None or not call.fetched or call.fetched == stated.group(0):
            continue
        return [
            Violation(
                "error",
                row_no,
                "FRESHNESS",
                f"row reports {stated.group(0)!r} but the capture manifest "
                + f"retrieved {render_url(url)!r} on {call.fetched!r}",
            )
        ]
    return []


def _check_row(
    cells: list[str],
    cols: _Columns,
    row_no: int,
    context: _Context,
) -> list[Violation]:
    if len(cells) < cols.width:
        return [
            Violation(
                "error",
                row_no,
                "MALFORMED",
                f"row has {len(cells)} cells, expected ≥ {cols.width}",
            )
        ]

    claim = cells[cols.claim]
    evidence = cells[cols.evidence]
    confidence = cells[cols.confidence].strip().strip("`").strip()
    out: list[Violation] = []
    citations = _remote_urls(evidence)

    if not _CITATION.search(evidence):
        out.append(
            Violation(
                "error",
                row_no,
                "CITATION",
                f"claim has no verifiable citation: {claim!r}",
            )
        )

    for label in cast("list[str]", _FOOTNOTE_REF.findall(evidence)):
        definition = context.footnotes.get(label)
        if definition is None:
            out.append(
                Violation(
                    "error",
                    row_no,
                    "FOOTNOTE",
                    f"evidence footnote [^{label}] has no matching definition",
                )
            )
        elif not _DIRECT_CITATION.search(definition):
            out.append(
                Violation(
                    "error",
                    row_no,
                    "FOOTNOTE",
                    f"footnote [^{label}] has no verifiable citation",
                )
            )
        else:
            citations.extend(_remote_urls(definition))
            out.extend(
                _check_local_paths(
                    definition,
                    context.report_dir,
                    context.invocation_dir,
                    row_no,
                    context.line_counts,
                )
            )
    out.extend(
        _check_local_paths(
            evidence,
            context.report_dir,
            context.invocation_dir,
            row_no,
            context.line_counts,
        )
    )
    for url in citations:
        try:
            context.remote_seen.add(url_digest(url))
        except ValueError:
            context.remote_seen.add(render_url(url))
    out.extend(_check_remote(citations, context.retrieved, row_no))
    out.extend(_check_freshness(cells, cols, citations, context.retrieved, row_no))

    # `synthesis.md` § Claim-level evidence table calls these exact label values.
    # A case variant is a synonym, so it is not one of the three labels.
    if confidence not in CONFIDENCE_LABELS:
        out.append(
            Violation(
                "error",
                row_no,
                "CONFIDENCE",
                f"confidence {confidence!r} is not one of certain / speculating / don't know",
            )
        )

    if (
        confidence == "certain"
        and _ABSENCE.search(claim)
        and not _RULED_OUT.search(claim)
    ):
        out.append(
            Violation(
                "advisory",
                row_no,
                "ABSENCE",
                "certain absence claim — confirm candidate mechanisms were enumerated and "
                + "ruled out; if inferred from silence, downgrade to 'not found in <sources>'",
            )
        )
    return out


def _check_manifest(
    ledger: Ledger, report_dir: Path, report_stem: str | None
) -> list[Violation]:
    """Bind the capture manifest to the report that sits beside it.

    `context-isolation.md` § Capture manifest puts the slug and one stored body
    in the ledger. Without this check a report can carry the evidence of another
    run, or claim a successful capture that stored nothing.
    """
    out: list[Violation] = []
    if ledger.slug and report_stem and ledger.slug != report_stem:
        out.append(
            Violation(
                "error",
                0,
                "MANIFEST",
                f"manifest slug {ledger.slug!r} does not name this report "
                + f"({report_stem!r})",
            )
        )
    raw_root = (report_dir / "raw").resolve()
    for index, call in enumerate(ledger.calls, start=1):
        if call.kind != EXTRACT or not call.ok:
            continue
        if not call.file:
            out.append(
                Violation(
                    "error",
                    0,
                    "MANIFEST",
                    f"call {index} retrieved {render_url(call.url)!r} but stored "
                    + "no raw body; a deep capture must name its file",
                )
            )
        elif not (report_dir / call.file).resolve().is_relative_to(raw_root):
            out.append(
                Violation(
                    "error",
                    0,
                    "MANIFEST",
                    f"call {index} stored a body outside the raw capture "
                    + f"directory: {call.file!r}",
                )
            )
    return out


def check_report(
    text: str,
    report_dir: Path | None = None,
    invocation_dir: Path | None = None,
    ledger: Ledger | None = None,
    report_stem: str | None = None,
) -> tuple[list[Violation], int]:
    """Return (violations, tables_checked). A report with claims but no evidence
    table is itself a grounding failure (caller maps that to a non-zero exit)."""
    lines = text.splitlines()
    footnotes, duplicate_footnotes = _footnote_definitions(lines)
    invocation_dir = (invocation_dir or Path.cwd()).resolve()
    report_dir = (report_dir or invocation_dir).resolve()
    retrieved = ledger.retrieved() if ledger is not None else None
    violations = [
        Violation(
            "error",
            0,
            "FOOTNOTE",
            f"footnote [^{label}] has a duplicate definition",
        )
        for label in sorted(duplicate_footnotes)
    ]
    if ledger is not None:
        violations.extend(_check_manifest(ledger, report_dir, report_stem))
    tables_checked = 0
    remote_seen: set[str] = set()
    context = _Context(
        footnotes, report_dir, invocation_dir, retrieved, remote_seen, {}
    )
    i = 0
    n = len(lines)
    while i < n:
        if "|" in lines[i]:
            header = _split_row(lines[i])
            cols = _find_columns(header)
            if (
                cols
                and i + 1 < n
                and "|" in lines[i + 1]
                and _is_separator(_split_row(lines[i + 1]))
            ):
                tables_checked += 1
                j = i + 2
                row_no = 0
                while j < n and "|" in lines[j] and lines[j].strip():
                    cells = _split_row(lines[j])
                    if not _is_separator(cells):
                        row_no += 1
                        violations.extend(
                            _check_row(cells, cols, row_no, context)
                        )
                    j += 1
                i = j
                continue
        i += 1
    if ledger is None and remote_seen:
        violations.append(
            Violation(
                "advisory",
                0,
                "MANIFEST",
                f"{len(remote_seen)} remote URL citation(s) were not machine-verified: "
                + "no capture manifest beside the report, so no record of which "
                + "provider retrieval tool opened them",
            )
        )
    return violations, tables_checked


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    _ = parser.add_argument(
        "report", help="Path to the synthesis report markdown file."
    )
    args = parser.parse_args(argv)

    report = cast(str, args.report)
    path = Path(report)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"error: cannot read {report}: {exc}", file=sys.stderr)
        return 2

    report_dir = path.resolve().parent
    manifest = find_ledger(report_dir)
    ledger: Ledger | None = None
    if manifest is not None:
        try:
            ledger = load_ledger(manifest)
        except LedgerError as exc:
            # A manifest that cannot be trusted is worse than none: the report
            # claims a capture record the gate cannot read.
            print(f"error: {exc}", file=sys.stderr)
            return 1

    violations, tables = check_report(
        text, report_dir, Path.cwd(), ledger, path.stem
    )

    if tables == 0:
        print(f"error: no evidence table found in {report}", file=sys.stderr)
        return 1

    for v in violations:
        print(v.render(), file=sys.stderr)

    errors = sum(1 for v in violations if v.level == "error")
    if errors:
        print(
            f"\n{errors} grounding error(s) across {tables} table(s)", file=sys.stderr
        )
        return 1
    print(f"grounding ok: {tables} table(s) checked", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
