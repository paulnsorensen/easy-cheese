#!/usr/bin/env python3
"""Fetch PR status (build + merge) for /affinage grading.

Returns JSON on stdout:

    {
      "pr": <number>,
      "build": {
        "status": "passing" | "failing" | "pending",
        "checks": [
          {
            "name": str,
            "conclusion": str,
            "url": str,
            "failure_summary": str,   # last ~10 lines of the failing log
            "failed_tests": [str]      # heuristic parse of FAILED test names
          }
        ]
      },
      "merge": {"mergeable": str, "state": str}
    }

Wraps `gh pr checks`, `gh pr view`, and `gh run view --log-failed`. Exits
non-zero (1 on PR/gh API error, 2 on missing gh binary) so the caller can
halt cleanly with `status: halt: pr-status-unavailable`.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from typing import Any

FAILURE_TAIL_LINES = 10

# Heuristic patterns for extracting failed-test names from log output.
# Conservative — false positives are noise but not incorrect grading.
_FAILED_TEST_PATTERNS = (
    # pytest:  FAILED tests/auth.py::test_name
    re.compile(r"FAILED\s+(\S+(?:::\S+)+)"),
    # rust:    test foo::bar ... FAILED
    re.compile(r"test\s+(\S+)\s+\.\.\.\s+FAILED"),
    # jest:    ✗ test name
    re.compile(r"^\s*[✗×]\s+(.+?)$", re.MULTILINE),
)


def _run_gh(args: list[str], *, allow_fail: bool = False) -> str:
    """Invoke gh and return stdout. Exits the process on failure unless allow_fail."""
    try:
        result = subprocess.run(
            ["gh", *args],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        sys.stderr.write("pr-status.py: gh CLI not found in PATH\n")
        sys.exit(2)
    if result.returncode != 0:
        if allow_fail:
            return ""
        sys.stderr.write(
            f"pr-status.py: gh {' '.join(args)} failed (exit {result.returncode}): "
            f"{result.stderr.strip()}\n"
        )
        sys.exit(1)
    return result.stdout


def fetch_checks(pr: int) -> list[dict[str, Any]]:
    """Return raw check entries from `gh pr checks --json`."""
    raw = _run_gh(["pr", "checks", str(pr), "--json", "name,state,bucket,link"])
    if not raw.strip():
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        sys.stderr.write(f"pr-status.py: could not parse gh pr checks JSON: {exc}\n")
        sys.exit(1)
    if not isinstance(data, list):
        sys.stderr.write(
            f"pr-status.py: gh pr checks returned non-list JSON (got {type(data).__name__}); "
            "the CLI schema may have changed\n"
        )
        sys.exit(1)
    return data


def fetch_merge_state(pr: int) -> dict[str, str]:
    raw = _run_gh(["pr", "view", str(pr), "--json", "mergeable,mergeStateStatus"])
    if not raw.strip():
        return {"mergeable": "UNKNOWN", "state": "UNKNOWN"}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {"mergeable": "UNKNOWN", "state": "UNKNOWN"}
    return {
        "mergeable": data.get("mergeable", "UNKNOWN") or "UNKNOWN",
        "state": data.get("mergeStateStatus", "UNKNOWN") or "UNKNOWN",
    }


def extract_run_id(link: str) -> str | None:
    """Parse a github actions URL to extract the run id."""
    if not link:
        return None
    match = re.search(r"/runs/(\d+)", link)
    return match.group(1) if match else None


def extract_failed_tests(log: str) -> list[str]:
    """Heuristically pull failed-test names from a log."""
    seen: list[str] = []
    for pattern in _FAILED_TEST_PATTERNS:
        for match in pattern.finditer(log):
            name = match.group(1).strip()
            if name and name not in seen:
                seen.append(name)
    return seen


def fetch_failure_summary(link: str) -> tuple[str, list[str]]:
    """Return (tail-summary, failed_tests) for a failing check link."""
    run_id = extract_run_id(link)
    if not run_id:
        return "", []
    raw = _run_gh(["run", "view", run_id, "--log-failed"], allow_fail=True)
    if not raw.strip():
        return "", []
    lines = raw.rstrip().splitlines()
    tail = "\n".join(lines[-FAILURE_TAIL_LINES:])
    failed_tests = extract_failed_tests(raw)
    return tail, failed_tests


def classify_status(checks: list[dict[str, Any]]) -> str:
    """Classify overall build state from per-check `bucket` values.

    `gh pr checks` exposes a pre-classified `bucket` field (pass / fail /
    pending / skipping) which is more stable than enumerating raw `state`
    values across event types. Skipping counts as passing.
    """
    if not checks:
        return "passing"
    buckets = {(c.get("bucket") or "").lower() for c in checks}
    if "fail" in buckets:
        return "failing"
    if "pending" in buckets:
        return "pending"
    return "passing"


def build_output(pr: int) -> dict[str, Any]:
    raw_checks = fetch_checks(pr)
    merge = fetch_merge_state(pr)
    status = classify_status(raw_checks)

    enriched: list[dict[str, Any]] = []
    for check in raw_checks:
        bucket = (check.get("bucket") or "").lower()
        state = (check.get("state") or "")
        entry: dict[str, Any] = {
            "name": check.get("name", ""),
            # Output key stays `conclusion` per spec; we derive it from gh's
            # canonical `state` (SUCCESS / FAILURE / CANCELLED / TIMED_OUT /
            # SKIPPED / IN_PROGRESS / QUEUED / ...) lowercased.
            "conclusion": state.lower(),
            "url": check.get("link", "") or "",
            "failure_summary": "",
            "failed_tests": [],
        }
        # Enrich for the whole failure family (failure, cancelled, timed_out)
        # via gh's pre-classified `bucket` so classification and enrichment
        # stay in lockstep.
        if bucket == "fail":
            summary, failed = fetch_failure_summary(entry["url"])
            entry["failure_summary"] = summary
            entry["failed_tests"] = failed
        enriched.append(entry)

    return {
        "pr": pr,
        "build": {"status": status, "checks": enriched},
        "merge": merge,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fetch PR status (build + merge) for /affinage grading.",
    )
    parser.add_argument("pr", type=int, help="PR number")
    args = parser.parse_args(argv)

    output = build_output(args.pr)
    json.dump(output, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
