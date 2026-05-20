#!/usr/bin/env python3
"""Detect honesty-rule violations in a /cook package report.

Reads a `/cook` package-ready report (markdown) and emits a JSON list of
violations against the honesty rules in `skills/cook/references/package-report.md`
(the confirmation-bias killer for cook's self-eval — the LLM tends to score
itself green even when partial work was shipped).

Violation kinds (regex over the report text):
  - skipped-claimed-pass: a SINGLE LINE contains both a skip marker
      ("skipped" / "@pytest.mark.skip") AND a green claim
      ("all tests pass" / "all green"). Cross-line co-occurrence (e.g. an
      honest "we skipped lint because the upstream rule is broken" line on
      one line plus a separate "all tests pass" line on another) is NOT a
      violation — those are factually compatible reports the honesty rules
      do not target.
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

    `skipped-claimed-pass` fires only when a single line contains both a
    skip marker AND a green claim. Cross-line co-occurrence — e.g. an honest
    "we skipped the lint pass because the upstream rule is broken" line plus
    a separate factually-true "all tests pass" line — is not a violation.
    """
    violations: list[dict] = []
    for line_no, raw_line in enumerate(report_text.splitlines(), start=1):
        if SKIP_RE.search(raw_line) and GREEN_RE.search(raw_line):
            violations.append(
                {"kind": "skipped-claimed-pass", "line": line_no, "snippet": raw_line.strip()}
            )
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
    # Honor the auto-injected --json toggle per the helper convention
    # (shared/scripts/cli.py says structured-output scripts read
    # args.json_mode rather than hard-coding the shape). With --json or no
    # violations, emit JSON; in plain mode with violations, emit a one-line
    # human summary per violation so callers running interactively get a
    # readable trace and `--json` gives them the parseable form.
    if args.json_mode or not violations:
        cli.emit(violations, json_mode=True, full=getattr(args, "full", False))
    else:
        for v in violations:
            cli.emit(f"{v['kind']} (line {v['line']}): {v['snippet']}")
    if violations:
        sys.exit(1)


def _setup(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--report", required=True, help="Path to /cook package report markdown.")
    parser.set_defaults(func=_cmd_check)


if __name__ == "__main__":
    cli.run(_setup)
