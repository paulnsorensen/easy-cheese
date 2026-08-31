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
    containing one of those citation shapes. Local line anchors must be in bounds.
    A claim with none is un-grounded.
  - CONFIDENCE (error): the confidence cell is exactly one of the three label
    values (``certain`` / ``speculating`` / ``don't know``), not a synonym.
  - ABSENCE (advisory): a negative/absence-shaped claim marked ``certain`` that
    carries no ruling-out phrase. Whether an absence was *observed* (a cited
    source states it) or *inferred* (synthesised from silence) is not decidable
    from text, so this is surfaced, not failed — it feeds the synthesis-fidelity
    self-check, which downgrades inferred absences to "not found in <sources>".
  - REMOTE (error): a cited ``http(s)`` URL that the run's capture manifest does
    not record as retrieved through a provider retrieval tool (#493). Routing
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
from pathlib import Path
from typing import cast

from easy_cheese.skills.briesearch.ledger import (
    Ledger,
    LedgerError,
    canonical_url,
    find_ledger,
    load_ledger,
)

CONFIDENCE_LABELS = {"certain", "speculating", "don't know"}

# A verifiable citation marker: footnote ref, URL, inline path:line, or a
# durable-corpus / raw-capture path. A prose source name can describe evidence,
# but it cannot be re-checked by the gate.
_FOOTNOTE_REF = re.compile(r"\[\^([^\]]+)\]")
_FOOTNOTE_DEFINITION = re.compile(r"^\[\^([^\]]+)\]:\s*(.*)$")
_LOCAL_PATH = re.compile(r"(?<![\w./-])((?:\.cheese|raw)/[^\s|]+)", re.IGNORECASE)
_LINE_ANCHOR = re.compile(r"#L(\d+)(?:-L?(\d+))?$", re.IGNORECASE)
_DIRECT_CITATION = re.compile(
    (
        r"https?://\S+"  # URL
        r"|[\w./-]+\.[A-Za-z]\w*:\d+(?:-\d+)?"  # inline path:line(-line)
        r"|(?:\.cheese|raw)/\S+"  # corpus or raw-capture path
    ),
    re.IGNORECASE,
)
_CITATION = re.compile(r"\[\^[^\]]+\]|" + _DIRECT_CITATION.pattern, re.IGNORECASE)
_REMOTE_URL = re.compile(r"https?://[^\s<>|\"'`)\]}]+", re.IGNORECASE)

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
    """Split a markdown table row into trimmed cells, dropping the edge pipes."""
    inner = line.strip()
    if inner.startswith("|"):
        inner = inner[1:]
    if inner.endswith("|"):
        inner = inner[:-1]
    return [cell.strip() for cell in inner.split("|")]


def _is_separator(cells: list[str]) -> bool:
    return all(re.fullmatch(r":?-{1,}:?", c) is not None for c in cells if c)


def _find_columns(header: list[str]) -> tuple[int, int, int] | None:
    """Return (claim, evidence, confidence) column indices, or None if this is
    not an evidence table. Evidence column matches "Evidence" or "Source"."""
    lower = [h.lower() for h in header]
    claim = evidence = confidence = -1
    for i, h in enumerate(lower):
        if claim < 0 and "claim" in h:
            claim = i
        if evidence < 0 and ("evidence" in h or "source" in h):
            evidence = i
        if confidence < 0 and "confidence" in h:
            confidence = i
    if claim < 0 or confidence < 0:
        return None
    if evidence < 0:
        evidence = claim  # degenerate table: cite inside the claim cell
    return claim, evidence, confidence


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


def _check_line_anchor(
    target: Path, anchor: re.Match[str], reference: str, row_no: int
) -> list[Violation]:
    start = int(anchor.group(1))
    end = int(anchor.group(2) or start)
    try:
        with target.open("rb") as stream:
            line_count = sum(1 for _ in stream)
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


def _check_local_paths(
    text: str, report_dir: Path, invocation_dir: Path, row_no: int
) -> list[Violation]:
    violations: list[Violation] = []
    for match in _LOCAL_PATH.finditer(text):
        reference = match.group(1).rstrip("`>.,;:!?)]}'\"*_~")
        anchor = _LINE_ANCHOR.search(reference)
        local_path = reference[: anchor.start()] if anchor else reference
        root = (
            report_dir / "raw"
            if local_path.casefold().startswith("raw/")
            else invocation_dir / ".cheese"
        ).resolve()
        target = (
            report_dir / local_path
            if local_path.casefold().startswith("raw/")
            else invocation_dir / local_path
        ).resolve()
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
            violations.extend(_check_line_anchor(target, anchor, local_path, row_no))
    return violations


def _remote_urls(text: str) -> list[str]:
    """Every http(s) citation in one evidence cell or footnote definition."""
    return [
        match.group(0).rstrip("`>.,;:!?)]}'\"*_~")
        for match in _REMOTE_URL.finditer(text)
    ]


def _check_remote(
    citations: list[str], ledger: Ledger, row_no: int
) -> list[Violation]:
    """Fail any cited URL the ledger does not record as provider-retrieved."""
    violations: list[Violation] = []
    retrieved = ledger.retrieved()
    for url in dict.fromkeys(citations):
        if canonical_url(url) in retrieved:
            continue
        violations.append(
            Violation(
                "error",
                row_no,
                "REMOTE",
                "cited URL was never retrieved through a provider retrieval tool: "
                + f"{url!r} (no successful entry in the capture manifest)",
            )
        )
    return violations


def _check_row(
    cells: list[str],
    cols: tuple[int, int, int],
    row_no: int,
    footnotes: dict[str, str],
    report_dir: Path,
    invocation_dir: Path,
    ledger: Ledger | None,
    remote_seen: set[str],
) -> list[Violation]:
    claim_i, ev_i, conf_i = cols
    width = max(cols) + 1
    if len(cells) < width:
        return [Violation("error", row_no, "MALFORMED", f"row has {len(cells)} cells, expected ≥ {width}")]

    claim = cells[claim_i]
    evidence = cells[ev_i]
    confidence = cells[conf_i].strip().strip("`").strip()
    out: list[Violation] = []
    citations = _remote_urls(evidence)

    if not _CITATION.search(evidence):
        out.append(
            Violation("error", row_no, "CITATION", f"claim has no verifiable citation: {claim!r}")
        )

    for label in cast("list[str]", _FOOTNOTE_REF.findall(evidence)):
        definition = footnotes.get(label)
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
                _check_local_paths(definition, report_dir, invocation_dir, row_no)
            )
    out.extend(_check_local_paths(evidence, report_dir, invocation_dir, row_no))
    remote_seen.update(citations)
    if ledger is not None:
        out.extend(_check_remote(citations, ledger, row_no))

    if confidence.lower() not in CONFIDENCE_LABELS:
        out.append(
            Violation(
                "error",
                row_no,
                "CONFIDENCE",
                f"confidence {confidence!r} is not one of certain / speculating / don't know",
            )
        )

    if (
        confidence.lower() == "certain"
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


def check_report(
    text: str,
    report_dir: Path | None = None,
    invocation_dir: Path | None = None,
    ledger: Ledger | None = None,
) -> tuple[list[Violation], int]:
    """Return (violations, tables_checked). A report with claims but no evidence
    table is itself a grounding failure (caller maps that to a non-zero exit)."""
    lines = text.splitlines()
    footnotes, duplicate_footnotes = _footnote_definitions(lines)
    invocation_dir = (invocation_dir or Path.cwd()).resolve()
    report_dir = (report_dir or invocation_dir).resolve()
    violations = [
        Violation(
            "error",
            0,
            "FOOTNOTE",
            f"footnote [^{label}] has a duplicate definition",
        )
        for label in sorted(duplicate_footnotes)
    ]
    tables_checked = 0
    remote_seen: set[str] = set()
    i = 0
    n = len(lines)
    while i < n:
        if "|" in lines[i]:
            header = _split_row(lines[i])
            cols = _find_columns(header)
            if cols and i + 1 < n and "|" in lines[i + 1] and _is_separator(_split_row(lines[i + 1])):
                tables_checked += 1
                j = i + 2
                row_no = 0
                while j < n and "|" in lines[j] and lines[j].strip():
                    cells = _split_row(lines[j])
                    if not _is_separator(cells):
                        row_no += 1
                        violations.extend(
                            _check_row(
                                cells,
                                cols,
                                row_no,
                                footnotes,
                                report_dir,
                                invocation_dir,
                                ledger,
                                remote_seen,
                            )
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
    _ = parser.add_argument("report", help="Path to the synthesis report markdown file.")
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

    violations, tables = check_report(text, report_dir, Path.cwd(), ledger)

    if tables == 0:
        print(f"error: no evidence table found in {report}", file=sys.stderr)
        return 1

    for v in violations:
        print(v.render(), file=sys.stderr)

    errors = sum(1 for v in violations if v.level == "error")
    if errors:
        print(f"\n{errors} grounding error(s) across {tables} table(s)", file=sys.stderr)
        return 1
    print(f"grounding ok: {tables} table(s) checked", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
