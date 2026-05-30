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
       Actions check's failure_summary
       empty)

Exit 3 is the expired-Actions-logs case: the build is failing and every failing
check whose logs are fetchable (has a `/runs/<id>` run id) produced no log to
ground on (typically expired GitHub Actions logs past the retention window).
Grading a blank CI line is worse than halting and asking the human to rerun the
failed jobs first. Failing checks with no fetchable run id (external CI /
non-Actions status checks) are excluded — rerunning them won't help — so a build
failing solely on those exits 0 and they become Needs-investigation.
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


def _gh(args: list[str]) -> subprocess.CompletedProcess[str]:
    """Run gh, returning the completed process. Exits 2 if gh is not installed."""
    try:
        return subprocess.run(
            ["gh", *args],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        sys.stderr.write("pr-status.py: gh CLI not found in PATH\n")
        sys.exit(2)


def _run_gh(args: list[str], *, allow_fail: bool = False) -> str:
    """Invoke gh and return stdout. Exits the process on failure unless allow_fail."""
    result = _gh(args)
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


# Plain `gh pr checks` prints the `bucket` label in its STATUS column
# (`cancel` renders as `fail`). This vocabulary is stable from pre-`--json` gh
# (verified at v2.40.0) through current (v2.93.0), so the fallback maps bucket
# -> state directly. Keep inverse to gh's own state -> bucket mapping.
_BUCKET_TO_STATE = {
    "pass": "SUCCESS",
    "fail": "FAILURE",
    "pending": "IN_PROGRESS",
    "skipping": "SKIPPED",
}


def fetch_checks(pr: int) -> list[dict[str, Any]]:
    """Return raw check entries for ``pr``.

    Fast path: `gh pr checks --json name,state,bucket,link` (gh >= 2.49.0).
    `gh` exits non-zero when checks are *failing* yet still prints valid JSON,
    so the fast path succeeds on any parseable list regardless of exit code.
    If `--json` is unsupported (older gh rejects the flag, exit non-zero with
    no JSON), fall back to parsing the plain tab-separated output. Only exit 1
    when both paths fail.
    """
    json_result = _gh(["pr", "checks", str(pr), "--json", "name,state,bucket,link"])
    raw = json_result.stdout
    if raw.strip():
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = None
        if isinstance(data, list):
            return data
    elif json_result.returncode == 0:
        # gh succeeded and reported no checks at all.
        return []

    return _fetch_checks_plain(pr, json_result)


def _fetch_checks_plain(
    pr: int, json_result: subprocess.CompletedProcess[str]
) -> list[dict[str, Any]]:
    """Parse plain `gh pr checks` output when the `--json` fast path is unusable."""
    plain = _gh(["pr", "checks", str(pr)])
    text = plain.stdout
    if not text.strip():
        # `gh pr checks` exits non-zero with empty stdout in two cases that look
        # alike: a PR with no checks ("no checks reported on the ... branch")
        # and a genuine error (PR not found / API failure). Only the former is a
        # real "passing, no checks" answer; the latter must surface as exit 1.
        if "no checks reported" in plain.stderr.lower():
            return []
        sys.stderr.write(
            "pr-status.py: gh pr checks --json failed (exit "
            f"{json_result.returncode}: {json_result.stderr.strip()}) and the "
            f"plain fallback also failed (exit {plain.returncode}: "
            f"{plain.stderr.strip()})\n"
        )
        sys.exit(1)

    checks: list[dict[str, Any]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        cols = line.split("\t")
        name = cols[0] if cols else ""
        bucket = (cols[1].lower() if len(cols) > 1 else "")
        link = next((c for c in cols[2:] if c.startswith("http")), "")
        checks.append(
            {
                "name": name,
                "state": _BUCKET_TO_STATE.get(bucket, ""),
                "bucket": bucket,
                "link": link,
            }
        )
    return checks


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
    """True when the build is failing and every failing check whose logs are
    *fetchable* produced no log evidence — the expired-Actions-logs case, where
    rerunning the failed jobs is the right remediation.

    Only failing checks with an extractable GitHub Actions run id are counted: a
    check whose `url` has no `/runs/<id>` segment (external CI / non-Actions
    status check) has an empty `failure_summary` by design — `fetch_failure_summary`
    never attempts a fetch — not because logs expired, so rerunning a run id
    won't help. A build failing solely on such checks is NOT ungroundable; the
    caller proceeds (exit 0) and those become Needs-investigation rather than a
    misdirected logs-expired halt.

    Returns False as soon as one fetchable failing check has a summary — that
    finding can be graded and the empty ones become Needs-investigation.

    "Failing" reads the per-check `failing` flag (gh bucket == "fail"), the same
    signal `build_output` uses to enrich, so this never drifts from the set of
    checks that actually made the build fail.
    """
    build = output.get("build", {})
    if build.get("status") != "failing":
        return False
    fetchable = [
        c
        for c in build.get("checks", [])
        if c.get("failing") and extract_run_id(c.get("url") or "")
    ]
    if not fetchable:
        return False
    return all(not (c.get("failure_summary") or "") for c in fetchable)


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
