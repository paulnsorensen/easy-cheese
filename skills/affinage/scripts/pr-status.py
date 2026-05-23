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
            "failing": bool,           # True iff gh bucket == "fail" — the
                                       # single source of truth for "this check
                                       # made the build fail"
            "failure_summary": str,   # last ~10 lines of the failing log
            "failed_tests": [str]      # heuristic parse of FAILED test names
          }
        ]
      },
      "merge": {"mergeable": str, "state": str}
    }

Wraps `gh pr checks`, `gh pr view`, and `gh run view --log-failed`. Exits
non-zero so the caller can halt cleanly:

    1  PR / gh API error            -> status: halt: pr-status-unavailable
    2  missing gh binary            -> status: halt: pr-status-unavailable
    3  failing build, no groundable -> status: halt: pr-status-logs-expired
       log evidence (every failing
       check's failure_summary empty)

Exit 3 is the "logs entirely unfetchable" case: the build is failing but no
failing check produced a single line of log to ground on (typically expired
GitHub Actions logs past the retention window). Grading a blank CI line is
worse than halting and asking the human to rerun the failed jobs first.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from typing import Any

FAILURE_TAIL_LINES = 10

# Exit code for "failing build, but no failing check produced any groundable
# log evidence" — see the module docstring.
EXIT_LOGS_EXPIRED = 3

# Heuristic patterns for extracting failed-test names from log output.
# Conservative — false positives are noise but not incorrect grading.
_FAILED_TEST_PATTERNS = (
    # pytest:  FAILED tests/auth.py::test_name
    re.compile(r"FAILED\s+(\S+(?:::\S+)+)"),
    # rust:    test foo::bar ... FAILED
    re.compile(r"test\s+(\S+)\s+\.\.\.\s+FAILED"),
    # jest:    ✗ test name
    re.compile(r"^\s*[✗×]\s+(.+)$", re.MULTILINE),
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
            sys.stderr.write(
                f"pr-status.py: gh {' '.join(args)} failed (exit {result.returncode}); "
                "continuing with empty result\n"
            )
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
    except json.JSONDecodeError as exc:
        sys.stderr.write(
            f"pr-status.py: could not parse gh pr view JSON ({exc}); "
            "treating merge state as UNKNOWN\n"
        )
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
            # `failing` is the single source of truth for "this check made the
            # build fail" — derived from gh's pre-classified `bucket`, the same
            # signal that drives classification and enrichment. Downstream halt
            # logic reads this, never the conclusion string, so the three stay
            # in lockstep across every gh state that maps to bucket==fail.
            "failing": bucket == "fail",
            "failure_summary": "",
            "failed_tests": [],
        }
        if entry["failing"]:
            summary, failed = fetch_failure_summary(entry["url"])
            entry["failure_summary"] = summary
            entry["failed_tests"] = failed
        enriched.append(entry)

    return {
        "pr": pr,
        "build": {"status": status, "checks": enriched},
        "merge": merge,
    }


def all_failures_ungroundable(output: dict[str, Any]) -> bool:
    """True when the build is failing but no failing check produced any log
    evidence (every failing check has an empty `failure_summary`).

    This is the expired-Actions-logs case: there is nothing to ground a CI
    finding on, so the caller should halt rather than grade a blank. Returns
    False as soon as one failing check has a summary — that finding can be
    graded and the empty ones become Needs-investigation.

    "Failing" reads the per-check `failing` flag (gh bucket == "fail"), the same
    signal `build_output` uses to enrich, so this never drifts from the set of
    checks that actually made the build fail.
    """
    build = output.get("build", {})
    if build.get("status") != "failing":
        return False
    failing = [c for c in build.get("checks", []) if c.get("failing")]
    if not failing:
        return False
    return all(not (c.get("failure_summary") or "") for c in failing)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fetch PR status (build + merge) for /affinage grading.",
    )
    parser.add_argument("pr", type=int, help="PR number")
    args = parser.parse_args(argv)

    output = build_output(args.pr)
    json.dump(output, sys.stdout, indent=2)
    sys.stdout.write("\n")
    if all_failures_ungroundable(output):
        sys.stderr.write(
            "pr-status.py: build is failing but no failing check produced any "
            "log evidence (logs likely expired); exiting "
            f"{EXIT_LOGS_EXPIRED} so the caller can halt\n"
        )
        return EXIT_LOGS_EXPIRED
    return 0


if __name__ == "__main__":
    sys.exit(main())
