#!/usr/bin/env python3
"""Enforce the /briesearch search budget and dedup rules from the run ledger.

`references/budgets.md` gives an invocation a soft call budget and one way out
of it: record the evidence gap that justified spending more. Prose alone never
held — a run could re-issue the same Tavily query with the same filters, or
re-extract a URL it had already stored, and nothing noticed (#549). Repeat calls
cost wall-clock time and burn provider quota without adding a single new claim.

Reads the same `manifest.json` that `ground-check` reads (see `ledger.py`) and
reports:

  - DUPLICATE_SEARCH: two successful searches with the same provider, the same
    normalised query, and the same filters. Same inputs, same answer.
  - DUPLICATE_EXTRACT: the same canonical URL retrieved twice without
    ``"refresh": true``. Re-fetching for freshness is legitimate and must be
    declared; re-fetching because the run forgot is the waste.
  - FAILED_EVIDENCE: a call that did not succeed yet named a stored body. That
    file is the debris of a failed retrieval and must not be cited as evidence.
  - EXTENSION_GAP: a budget extension naming a gap outside the five in
    `EVIDENCE_GAPS`. A free-text reason is not a reason.
  - BUDGET: more calls of a kind than the declared soft budget allows, with no
    recognised extension recorded.

Always prints a metrics object on stdout — invocation class, per-kind call
counts, duplicates, cache hits, failures, budget, extensions — so a run's cost
is inspectable even when nothing is wrong.

Exit: 0 clean, 1 on any violation or an untrusted manifest, 2 when no manifest
is found at the given path.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from easy_cheese.skills.briesearch.ledger import (
    CALL_KINDS,
    EVIDENCE_GAPS,
    EXTRACT,
    MANIFEST_NAME,
    SEARCH,
    Call,
    Ledger,
    LedgerError,
    find_ledger,
    load_ledger,
)


@dataclass(frozen=True)
class Finding:
    """One budget or duplication violation, keyed by check name."""

    kind: str
    message: str

    def render(self) -> str:
        return f"ERROR {self.kind}: {self.message}"


@dataclass(frozen=True)
class Report:
    """Findings plus the run metrics, which are emitted whether or not it passed."""

    findings: tuple[Finding, ...]
    metrics: dict[str, object]


def _search_key(call: Call) -> tuple[str, str, str]:
    """What makes two searches the same search: provider, query, filters.

    Case and internal whitespace do not change what a provider returns, so they
    do not make a query new. The filters are already canonical JSON.
    """
    return (
        call.provider.casefold(),
        " ".join(call.query.casefold().split()),
        call.filters,
    )


def _describe(call: Call, index: int) -> str:
    tool = call.tool or call.kind
    return f"call {index} ({call.provider} {tool})"


def check_ledger(ledger: Ledger) -> Report:
    """Run every budget check over a parsed ledger and collect the run metrics."""
    findings: list[Finding] = []
    counts = dict.fromkeys(sorted(CALL_KINDS), 0)
    duplicates = {SEARCH: 0, EXTRACT: 0}
    cached = 0
    failed = 0
    first_search: dict[tuple[str, str, str], int] = {}
    first_extract: dict[str, int] = {}

    for index, call in enumerate(ledger.calls, start=1):
        counts[call.kind] += 1
        if call.cached:
            cached += 1
        if not call.ok:
            failed += 1
            if call.file:
                findings.append(
                    Finding(
                        "FAILED_EVIDENCE",
                        f"{_describe(call, index)} failed with status "
                        + f"{call.status!r} but recorded a stored body at "
                        + f"{call.file!r}; debris from a failed retrieval is not evidence",
                    )
                )
            continue
        if call.kind == SEARCH:
            key = _search_key(call)
            earlier = first_search.get(key)
            if earlier is None:
                first_search[key] = index
            else:
                duplicates[SEARCH] += 1
                findings.append(
                    Finding(
                        "DUPLICATE_SEARCH",
                        f"{_describe(call, index)} repeats call {earlier}: same "
                        + f"provider, query {call.query!r}, and filters "
                        + f"{call.filters or '{}'} — same inputs, same answer",
                    )
                )
        elif call.kind == EXTRACT:
            earlier = first_extract.get(call.canonical)
            if earlier is None:
                first_extract[call.canonical] = index
            elif not call.refresh:
                duplicates[EXTRACT] += 1
                findings.append(
                    Finding(
                        "DUPLICATE_EXTRACT",
                        f"{_describe(call, index)} re-extracts {call.canonical} "
                        + f"already retrieved by call {earlier}; declare a deliberate "
                        + 'refetch with "refresh": true',
                    )
                )

    extensions: list[dict[str, str]] = []
    for extension in ledger.extensions:
        extensions.append({"gap": extension.gap, "note": extension.note})
        if extension.gap not in EVIDENCE_GAPS:
            findings.append(
                Finding(
                    "EXTENSION_GAP",
                    f"extension names gap {extension.gap!r}, which is not one of "
                    + ", ".join(sorted(EVIDENCE_GAPS)),
                )
            )

    # Only a recognised gap buys budget: an unrecognised one is the free-text
    # escape hatch the EXTENSION_GAP check exists to close.
    excused = any(extension.gap in EVIDENCE_GAPS for extension in ledger.extensions)
    for kind, limit in sorted(ledger.budget.items()):
        if counts[kind] > limit and not excused:
            findings.append(
                Finding(
                    "BUDGET",
                    f"{counts[kind]} {kind} call(s) against a declared budget of "
                    + f"{limit}, with no extension recorded; name the evidence gap "
                    + "that justified spending past it",
                )
            )

    metrics: dict[str, object] = {
        "invocation": ledger.invocation,
        "calls": counts,
        "duplicates": duplicates,
        "cached": cached,
        "failed": failed,
        "budget": dict(sorted(ledger.budget.items())),
        "extensions": extensions,
    }
    return Report(tuple(findings), metrics)


def _find_manifest(target: Path) -> Path | None:
    """Accept either the research directory or the manifest file itself."""
    if target.is_dir():
        return find_ledger(target)
    return target if target.is_file() else None


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    _ = parser.add_argument(
        "path",
        help=f"Research directory holding {MANIFEST_NAME}, or the manifest file.",
    )
    args = parser.parse_args(argv)

    target = Path(cast(str, args.path))
    manifest = _find_manifest(target)
    if manifest is None:
        print(f"error: no {MANIFEST_NAME} found at {target}", file=sys.stderr)
        return 2
    try:
        ledger = load_ledger(manifest)
    except LedgerError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    report = check_ledger(ledger)
    print(json.dumps(report.metrics, indent=2, sort_keys=True))
    for finding in report.findings:
        print(finding.render(), file=sys.stderr)
    if report.findings:
        print(
            f"\n{len(report.findings)} budget violation(s) in {manifest}",
            file=sys.stderr,
        )
        return 1
    print(f"budget ok: {len(ledger.calls)} call(s) checked", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
