#!/usr/bin/env python3
"""Replay the committed writer-output corpus through the real normalizer.

Each corpus case under ``benchmarks/contracts/`` is one writer view plus the
host invocation it was produced against, exactly as an agent emitted it (JSON,
sanitized). ``benchmark_contracts`` replays them through
``normalize_agent_output``; this program turns that report into markdown and
decides whether the contract validity budget is met.

Two facts stay separate, because they answer different questions:

* ``expect_first_pass_valid`` — recorded per case, replayed on every run. A
  mismatch means a contract change flipped a payload's validity, which is the
  cheap deterministic backward-compat canary. ``tests/python`` runs it, so it
  gates ordinary CI.
* ``provenance`` — ``captured`` (real agent output) or ``synthetic`` (authored
  by hand). The <10% first-pass-invalid budget is measured over captured cases
  only; a synthetic corpus cannot say anything about live writer behaviour.

Exit status is 0 when no problem is found, 1 when a recorded expectation is
violated or the captured-case budget is exceeded, and 2 when the corpus itself
is malformed. The weekly workflow (``.github/workflows/contract-benchmarks.yml``)
publishes the markdown to its job summary, so a red weekly run — not a blocked
pull request — is how a budget breach surfaces.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC = str(REPO_ROOT / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from easy_cheese_schemas.benchmarks import (  # noqa: E402
    BenchmarkReport,
    ContractBenchmarkInput,
    benchmark_contracts,
)

CORPUS_ROOT = REPO_ROOT / "benchmarks" / "contracts"
INVALID_BUDGET = 0.10
CAPTURED = "captured"
SYNTHETIC = "synthetic"

_PROVENANCES = frozenset({CAPTURED, SYNTHETIC})
_REQUIRED_KEYS = frozenset(
    {
        "name",
        "provenance",
        "source",
        "expect_first_pass_valid",
        "writer_view",
        "invocation",
    }
)
_ALLOWED_KEYS = _REQUIRED_KEYS | {"repair_view"}


class CorpusError(ValueError):
    """A corpus file is malformed; the harness never sees its contents."""


@dataclass(frozen=True, slots=True)
class CorpusCase:
    """One stored writer capture plus the facts the report is grouped by."""

    name: str
    provenance: str
    source: str
    expect_first_pass_valid: bool
    benchmark_input: ContractBenchmarkInput


def _text(case: dict[str, object], key: str, filename: str) -> str:
    value = case[key]
    if not isinstance(value, str) or not value.strip():
        raise CorpusError(f"{filename}: {key} must be a non-empty string")
    return value


def _mapping(case: dict[str, object], key: str, filename: str) -> dict[str, object]:
    value = case[key]
    if not isinstance(value, dict):
        raise CorpusError(f"{filename}: {key} must be an object")
    return cast("dict[str, object]", value)


def _load_case(path: Path) -> CorpusCase:
    filename = path.name
    try:
        document = cast(object, json.loads(path.read_text(encoding="utf-8")))
    except json.JSONDecodeError as error:
        raise CorpusError(f"{filename}: invalid JSON: {error}") from None
    if not isinstance(document, dict):
        raise CorpusError(f"{filename}: case must be a JSON object")
    case = cast("dict[str, object]", document)

    unknown = sorted(set(case) - _ALLOWED_KEYS)
    if unknown:
        raise CorpusError(f"{filename}: unknown keys: {', '.join(unknown)}")
    missing = sorted(_REQUIRED_KEYS - set(case))
    if missing:
        raise CorpusError(f"{filename}: missing keys: {', '.join(missing)}")

    provenance = _text(case, "provenance", filename)
    if provenance not in _PROVENANCES:
        raise CorpusError(
            f"{filename}: provenance must be one of "
            + f"{', '.join(sorted(_PROVENANCES))}, not {provenance!r}"
        )
    expect_valid = case["expect_first_pass_valid"]
    if not isinstance(expect_valid, bool):
        raise CorpusError(f"{filename}: expect_first_pass_valid must be a boolean")
    raw_repair_view = case.get("repair_view")
    repair_view: dict[str, object] | None = None
    if raw_repair_view is not None:
        if not isinstance(raw_repair_view, dict):
            raise CorpusError(f"{filename}: repair_view must be an object")
        repair_view = cast("dict[str, object]", raw_repair_view)
    if expect_valid and repair_view is not None:
        raise CorpusError(
            f"{filename}: repair_view is unreachable when the case is expected valid"
        )

    name = _text(case, "name", filename)
    return CorpusCase(
        name=name,
        provenance=provenance,
        source=_text(case, "source", filename),
        expect_first_pass_valid=expect_valid,
        benchmark_input=ContractBenchmarkInput(
            name=name,
            writer_view=_mapping(case, "writer_view", filename),
            invocation=_mapping(case, "invocation", filename),
            repair_view=repair_view,
        ),
    )


def load_corpus(root: Path) -> tuple[CorpusCase, ...]:
    """Load every ``*.json`` case under ``root``, ordered by filename."""
    if not root.is_dir():
        raise CorpusError(f"corpus directory not found: {root}")
    paths = sorted(root.glob("*.json"))
    if not paths:
        raise CorpusError(f"corpus directory holds no cases: {root}")
    cases = tuple(_load_case(path) for path in paths)
    counts = Counter(case.name for case in cases)
    duplicates = sorted(name for name, count in counts.items() if count > 1)
    if duplicates:
        raise CorpusError(f"duplicate case names: {', '.join(duplicates)}")
    return cases


def expectation_mismatches(
    cases: Sequence[CorpusCase], report: BenchmarkReport
) -> tuple[str, ...]:
    """Cases whose replayed first-pass validity contradicts the recorded one."""
    return tuple(
        f"{case.name}: recorded expect_first_pass_valid="
        + f"{str(case.expect_first_pass_valid).lower()}, replay produced "
        + f"{str(record.first_pass_valid).lower()}"
        for case, record in zip(cases, report.records)
        if case.expect_first_pass_valid != record.first_pass_valid
    )


def captured_invalid_rate(
    cases: Sequence[CorpusCase], report: BenchmarkReport
) -> float | None:
    """First-pass-invalid share of captured cases, or ``None`` when there are none."""
    captured = [
        record
        for case, record in zip(cases, report.records)
        if case.provenance == CAPTURED
    ]
    if not captured:
        return None
    return sum(not record.first_pass_valid for record in captured) / len(captured)


def corpus_problems(
    cases: Sequence[CorpusCase], report: BenchmarkReport
) -> tuple[str, ...]:
    """Everything that should turn the weekly run red, in report order."""
    problems = list(expectation_mismatches(cases, report))
    rate = captured_invalid_rate(cases, report)
    if rate is not None and rate > INVALID_BUDGET:
        problems.append(
            f"captured first-pass invalid rate {rate:.1%} exceeds the "
            + f"{INVALID_BUDGET:.0%} budget"
        )
    return tuple(problems)


def _budget_status(cases: Sequence[CorpusCase], report: BenchmarkReport) -> str:
    rate = captured_invalid_rate(cases, report)
    if rate is None:
        return (
            "not measurable — the corpus holds no captured cases yet "
            + "(easy-cheese#406)"
        )
    captured = sum(case.provenance == CAPTURED for case in cases)
    verdict = "met" if rate <= INVALID_BUDGET else "NOT MET"
    return f"{verdict} — {rate:.1%} of {captured} captured cases were first-pass invalid"


def _display_path(corpus_root: Path) -> str:
    resolved = corpus_root.resolve()
    if resolved.is_relative_to(REPO_ROOT):
        return str(resolved.relative_to(REPO_ROOT))
    return str(resolved)


def render_report(
    cases: Sequence[CorpusCase], report: BenchmarkReport, corpus_root: Path
) -> str:
    """Render the markdown the weekly job publishes to its job summary."""
    attempts = sum(record.repair_attempted for record in report.records)
    canonical_sizes = [
        record.canonical_bytes
        for record in report.records
        if record.canonical_bytes is not None
    ]
    captured = sum(case.provenance == CAPTURED for case in cases)
    lines = [
        "## Contract validity benchmark",
        "",
        f"Corpus: `{_display_path(corpus_root)}` — {len(cases)} cases "
        + f"({captured} captured, {len(cases) - captured} synthetic)",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| First-pass validity (all cases) | {report.first_pass_validity:.1%} |",
        "| Repair success among attempts | "
        + (f"{report.repair_rate:.1%} |" if attempts else "n/a (none attempted) |"),
        "| Largest canonical payload | "
        + (f"{max(canonical_sizes):,} bytes |" if canonical_sizes else "n/a |"),
        "",
        f"Budget: captured writer output stays under {INVALID_BUDGET:.0%} "
        + "first-pass invalid.",
        f"Status: {_budget_status(cases, report)}",
        "",
        "| Case | Provenance | First pass | Repair | Writer bytes | Canonical bytes |",
        "| --- | --- | --- | --- | ---: | ---: |",
    ]
    for case, record in zip(cases, report.records):
        if not record.repair_attempted:
            repair = "—"
        else:
            repair = "repaired" if record.repair_succeeded else "unrepaired"
        canonical = (
            "n/a" if record.canonical_bytes is None else f"{record.canonical_bytes:,}"
        )
        lines.append(
            f"| {case.name} | {case.provenance} | "
            + f"{'valid' if record.first_pass_valid else 'invalid'} | {repair} | "
            + f"{record.writer_bytes:,} | {canonical} |"
        )

    problems = corpus_problems(cases, report)
    if problems:
        lines.extend(["", "### Problems", ""])
        lines.extend(f"- {problem}" for problem in problems)
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument(
        "--corpus",
        type=Path,
        default=CORPUS_ROOT,
        help="directory of writer-capture JSON cases (default: benchmarks/contracts)",
    )
    args = parser.parse_args(argv)
    corpus_root = cast(Path, args.corpus)

    try:
        cases = load_corpus(corpus_root)
    except CorpusError as error:
        print(f"contract_benchmarks: {error}", file=sys.stderr)
        return 2

    report = benchmark_contracts(case.benchmark_input for case in cases)
    print(render_report(cases, report, corpus_root), end="")
    problems = corpus_problems(cases, report)
    for problem in problems:
        print(f"contract_benchmarks: {problem}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
