#!/usr/bin/env python3
"""Detect honesty-rule violations in a /cook package report.

Reads a `/cook` package-ready report (markdown) and emits a JSON list of
violations against the honesty rules in `skills/cook/references/package-report.md`
(the confirmation-bias killer for cook's self-eval — the LLM tends to score
itself green even when partial work was shipped).

Violation kinds (regex over the report text):
  - skipped-claimed-pass: report contains BOTH a skip marker
      ("skipped" / "@pytest.mark.skip") AND a green claim
      ("all tests pass" / "all green").
  - unverified-claim: report contains hedging language
      ("should work" / "probably" / "I think") near a correctness assertion.
  - scope-creep: report mentions changes outside the spec's file list
      ("while I was there" / "also fixed" / "also updated" / "additionally").

Each violation entry: {kind, line, snippet}. Exit 1 when any violation found;
exit 0 on clean report. Missing file raises cli.CliError -> exit 2.

CLI:
    python3 skills/cook/scripts/self_eval_check.py --report .cheese/cook/<slug>.md
    python3 skills/cook/scripts/self_eval_check.py --report <path> --json
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Load shared cli helper from repo-root/shared/scripts.
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "shared" / "scripts"))
import cli  # noqa: E402


SKIP_RE = re.compile(r"\bskipped\b|@pytest\.mark\.skip", re.IGNORECASE)
GREEN_RE = re.compile(r"all tests pass|all green", re.IGNORECASE)
HEDGE_RE = re.compile(r"\b(should work|probably|i think)\b", re.IGNORECASE)
SCOPE_CREEP_RE = re.compile(
    r"while i was there|also fixed|also updated|additionally",
    re.IGNORECASE,
)


def _line_of(text: str, match: re.Match[str]) -> tuple[int, str]:
    """Return (1-based line number, line text) for a regex match in text."""
    line_no = text.count("\n", 0, match.start()) + 1
    line_start = text.rfind("\n", 0, match.start()) + 1
    line_end = text.find("\n", match.end())
    if line_end == -1:
        line_end = len(text)
    return line_no, text[line_start:line_end].strip()


def detect_violations(report_text: str) -> list[dict]:
    """Scan report text for honesty-rule violations.

    skipped-claimed-pass fires once per skip-marker line when any green claim
    also exists in the report — both signals must be present.
    """
    violations: list[dict] = []
    has_green = bool(GREEN_RE.search(report_text))
    if has_green:
        for m in SKIP_RE.finditer(report_text):
            line_no, snippet = _line_of(report_text, m)
            violations.append({"kind": "skipped-claimed-pass", "line": line_no, "snippet": snippet})
    for m in HEDGE_RE.finditer(report_text):
        line_no, snippet = _line_of(report_text, m)
        violations.append({"kind": "unverified-claim", "line": line_no, "snippet": snippet})
    for m in SCOPE_CREEP_RE.finditer(report_text):
        line_no, snippet = _line_of(report_text, m)
        violations.append({"kind": "scope-creep", "line": line_no, "snippet": snippet})
    violations.sort(key=lambda v: (v["line"], v["kind"]))
    return violations


def _cmd_check(args: argparse.Namespace) -> None:
    report_path = Path(args.report)
    if not report_path.is_file():
        raise cli.CliError(f"report not found: {report_path}")
    text = report_path.read_text(encoding="utf-8")
    violations = detect_violations(text)
    # Script's purpose is a JSON list of violations; --json/--full are honored
    # by cli.emit but JSON is the canonical shape downstream consumers parse.
    cli.emit(violations, json_mode=True, full=getattr(args, "full", False))
    if violations:
        sys.exit(1)


def _setup(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--report", required=True, help="Path to /cook package report markdown.")
    parser.set_defaults(func=_cmd_check)


if __name__ == "__main__":
    cli.run(_setup)
