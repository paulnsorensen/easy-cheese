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

  - CITATION (error): the evidence/source cell carries a verifiable citation
    marker — a footnote ``[^id]``, a URL, an inline ``path:line``, or a
    corpus/raw path. A claim with none is un-grounded. This is the check that
    catches the original failure: that claim had no citation at all.
  - CONFIDENCE (error): the confidence cell is exactly one of the three label
    values (``certain`` / ``speculating`` / ``don't know``), not a synonym.
  - ABSENCE (advisory): a negative/absence-shaped claim marked ``certain`` that
    carries no ruling-out phrase. Whether an absence was *observed* (a cited
    source states it) or *inferred* (synthesised from silence) is not decidable
    from text, so this is surfaced, not failed — it feeds the synthesis-fidelity
    self-check, which downgrades inferred absences to "not found in <sources>".

Exit: 0 clean (advisories may print), 1 on any error-level violation or when a
report carries no evidence table, 2 on bad args / unreadable file.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

CONFIDENCE_LABELS = {"certain", "speculating", "don't know"}

# A verifiable citation marker: footnote ref, URL, inline path:line, or a
# durable-corpus / raw-capture path. Naming a source in prose ("the X docs") is
# not a citation — it cannot be re-checked.
_CITATION = re.compile(
    r"\[\^[^\]]+\]"  # footnote marker [^source-1]
    r"|https?://\S+"  # URL
    r"|[\w./-]+\.[A-Za-z]\w*:\d+(?:-\d+)?"  # inline path:line(-line) — alpha-led ext, not a numeric ratio
    r"|(?:\.cheese|raw)/\S+",  # corpus or raw-capture path
    re.IGNORECASE,
)

# Negation aimed at existence / support / provision — the shape of an absence
# claim. Whole-word matched so "Cargo" never trips "no".
_ABSENCE = re.compile(
    r"\b(?:no|not|never|none|cannot|can'?t|does\s*n'?t|do\s*n'?t|did\s*n'?t"
    r"|is\s*n'?t|are\s*n'?t|was\s*n'?t|wo\s*n'?t|lacks?|lacking|without"
    r"|absent|missing|unsupported|unavailable)\b",
    re.IGNORECASE,
)

# Phrases that claim a stronger ruling-out than a searched-but-empty source.
_RULED_OUT = re.compile(
    r"ruled out|checked\b",
    re.IGNORECASE,
)


class Violation:
    __slots__ = ("level", "row", "kind", "message")

    def __init__(self, level: str, row: int, kind: str, message: str) -> None:
        self.level = level  # "error" | "advisory"
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


def _check_row(cells: list[str], cols: tuple[int, int, int], row_no: int) -> list[Violation]:
    claim_i, ev_i, conf_i = cols
    width = max(cols) + 1
    if len(cells) < width:
        return [Violation("error", row_no, "MALFORMED", f"row has {len(cells)} cells, expected ≥ {width}")]

    claim = cells[claim_i]
    evidence = cells[ev_i]
    confidence = cells[conf_i].strip().strip("`").strip()
    out: list[Violation] = []

    if not _CITATION.search(evidence):
        out.append(
            Violation("error", row_no, "CITATION", f"claim has no verifiable citation: {claim!r}")
        )

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
                "ruled out; if inferred from silence, downgrade to 'not found in <sources>'",
            )
        )
    return out


def check_report(text: str) -> tuple[list[Violation], int]:
    """Return (violations, tables_checked). A report with claims but no evidence
    table is itself a grounding failure (caller maps that to a non-zero exit)."""
    lines = text.splitlines()
    violations: list[Violation] = []
    tables_checked = 0
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
                        violations.extend(_check_row(cells, cols, row_no))
                    j += 1
                i = j
                continue
        i += 1
    return violations, tables_checked


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("report", help="Path to the synthesis report markdown file.")
    args = parser.parse_args(argv)

    path = Path(args.report)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"error: cannot read {args.report}: {exc}", file=sys.stderr)
        return 2

    violations, tables = check_report(text)

    if tables == 0:
        print(f"error: no evidence table found in {args.report}", file=sys.stderr)
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
