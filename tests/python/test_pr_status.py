"""Tests for skills/affinage/scripts/pr-status.py."""

from __future__ import annotations

import json
import subprocess
from typing import Callable, Iterable

import pytest


class _FakeCompletedProcess:
    def __init__(self, stdout: str = "", returncode: int = 0, stderr: str = ""):
        self.stdout = stdout
        self.returncode = returncode
        self.stderr = stderr


def _matcher(prefix: Iterable[str]) -> Callable[[list[str]], bool]:
    needle = list(prefix)
    return lambda cmd: cmd[: len(needle)] == needle


def _fake_run(responses: list[tuple[Callable[[list[str]], bool], str, int]]):
    """Return a fake subprocess.run that dispatches by argv prefix.

    Each response is (matcher, stdout, returncode). First match wins.
    """

    def runner(cmd, **kwargs):
        for matcher, stdout, rc in responses:
            if matcher(cmd):
                return _FakeCompletedProcess(stdout=stdout, returncode=rc)
        raise AssertionError(f"unmocked subprocess call: {cmd}")

    return runner


def test_passing_build_no_checks(pr_status, monkeypatch):
    """Empty check list classifies as passing."""
    monkeypatch.setattr(
        subprocess,
        "run",
        _fake_run(
            [
                (_matcher(["gh", "pr", "checks"]), "[]", 0),
                (
                    _matcher(["gh", "pr", "view"]),
                    json.dumps({"mergeable": "MERGEABLE", "mergeStateStatus": "CLEAN"}),
                    0,
                ),
            ]
        ),
    )
    output = pr_status.build_output(42)
    assert output["pr"] == 42
    assert output["build"]["status"] == "passing"
    assert output["build"]["checks"] == []
    assert output["merge"] == {"mergeable": "MERGEABLE", "state": "CLEAN"}


def test_failing_build_extracts_summary_and_tests(pr_status, monkeypatch):
    """A failing check enriches the entry with summary + failed tests."""
    checks_json = json.dumps(
        [
            {
                "name": "test-suite",
                "state": "completed",
                "conclusion": "failure",
                "link": "https://github.com/foo/bar/actions/runs/12345/job/67890",
            }
        ]
    )
    log_lines = [
        "Running tests...",
        "PASS tests/format.test.ts",
        "FAIL tests/auth.test.ts",
        "FAILED tests/auth.test.ts::rejects_invalid_token",
        "FAILED tests/auth.test.ts::rejects_missing_header",
        "FAILED tests/auth.test.ts::rejects_expired_token",
        "",
        "3 failed, 8 passed (11)",
        "",
        "::error::Tests failed",
        "##[error]Process completed with exit code 1",
    ]
    monkeypatch.setattr(
        subprocess,
        "run",
        _fake_run(
            [
                (_matcher(["gh", "pr", "checks"]), checks_json, 0),
                (
                    _matcher(["gh", "pr", "view"]),
                    json.dumps({"mergeable": "MERGEABLE", "mergeStateStatus": "CLEAN"}),
                    0,
                ),
                (_matcher(["gh", "run", "view"]), "\n".join(log_lines), 0),
            ]
        ),
    )
    output = pr_status.build_output(42)
    assert output["build"]["status"] == "failing"
    assert len(output["build"]["checks"]) == 1
    check = output["build"]["checks"][0]
    assert check["name"] == "test-suite"
    assert check["conclusion"] == "failure"
    # tail summary contains the closing lines from the log
    assert "Process completed with exit code 1" in check["failure_summary"]
    # failed-test extraction finds the three test names
    assert "tests/auth.test.ts::rejects_invalid_token" in check["failed_tests"]
    assert "tests/auth.test.ts::rejects_missing_header" in check["failed_tests"]
    assert "tests/auth.test.ts::rejects_expired_token" in check["failed_tests"]


def test_pending_check_classified_pending(pr_status, monkeypatch):
    """A check still in_progress reports pending."""
    checks_json = json.dumps(
        [{"name": "slow-job", "state": "in_progress", "conclusion": "", "link": ""}]
    )
    monkeypatch.setattr(
        subprocess,
        "run",
        _fake_run(
            [
                (_matcher(["gh", "pr", "checks"]), checks_json, 0),
                (
                    _matcher(["gh", "pr", "view"]),
                    json.dumps({"mergeable": "MERGEABLE", "mergeStateStatus": "UNSTABLE"}),
                    0,
                ),
            ]
        ),
    )
    output = pr_status.build_output(42)
    assert output["build"]["status"] == "pending"


def test_merge_conflict_surfaced(pr_status, monkeypatch):
    """CONFLICTING / DIRTY merge state surfaces in the output."""
    monkeypatch.setattr(
        subprocess,
        "run",
        _fake_run(
            [
                (_matcher(["gh", "pr", "checks"]), "[]", 0),
                (
                    _matcher(["gh", "pr", "view"]),
                    json.dumps({"mergeable": "CONFLICTING", "mergeStateStatus": "DIRTY"}),
                    0,
                ),
            ]
        ),
    )
    output = pr_status.build_output(42)
    assert output["merge"]["mergeable"] == "CONFLICTING"
    assert output["merge"]["state"] == "DIRTY"


def test_missing_gh_exits_two(pr_status, monkeypatch):
    """FileNotFoundError on subprocess.run → exit 2 (gh not installed)."""

    def raise_fnfe(*args, **kwargs):
        raise FileNotFoundError("gh not found")

    monkeypatch.setattr(subprocess, "run", raise_fnfe)
    with pytest.raises(SystemExit) as exc:
        pr_status.fetch_checks(42)
    assert exc.value.code == 2


def test_gh_failure_exits_one(pr_status, monkeypatch):
    """gh exits non-zero (e.g. PR not found) → exit 1."""
    monkeypatch.setattr(
        subprocess,
        "run",
        _fake_run([(_matcher(["gh", "pr", "checks"]), "", 1)]),
    )
    with pytest.raises(SystemExit) as exc:
        pr_status.fetch_checks(42)
    assert exc.value.code == 1


def test_extract_run_id_from_actions_url(pr_status):
    url = "https://github.com/foo/bar/actions/runs/123456789/job/987654"
    assert pr_status.extract_run_id(url) == "123456789"


def test_extract_run_id_returns_none_on_empty(pr_status):
    assert pr_status.extract_run_id("") is None
    assert pr_status.extract_run_id("https://example.com/no/run/here") is None


def test_extract_failed_tests_pytest_style(pr_status):
    log = "FAILED tests/auth.py::test_foo\nFAILED tests/auth.py::test_bar\nrandom line\n"
    assert pr_status.extract_failed_tests(log) == [
        "tests/auth.py::test_foo",
        "tests/auth.py::test_bar",
    ]


def test_extract_failed_tests_rust_style(pr_status):
    log = "running 3 tests\ntest foo::bar ... FAILED\ntest foo::baz ... ok\n"
    assert pr_status.extract_failed_tests(log) == ["foo::bar"]


def test_extract_failed_tests_dedups(pr_status):
    log = "FAILED tests/x::a\nFAILED tests/x::a\n"
    assert pr_status.extract_failed_tests(log) == ["tests/x::a"]


def test_classify_status_with_cancelled_is_failing(pr_status):
    checks = [{"name": "lint", "state": "completed", "conclusion": "cancelled", "link": ""}]
    assert pr_status.classify_status(checks) == "failing"


def test_main_writes_json_to_stdout(pr_status, monkeypatch, capsys):
    monkeypatch.setattr(
        subprocess,
        "run",
        _fake_run(
            [
                (_matcher(["gh", "pr", "checks"]), "[]", 0),
                (
                    _matcher(["gh", "pr", "view"]),
                    json.dumps({"mergeable": "MERGEABLE", "mergeStateStatus": "CLEAN"}),
                    0,
                ),
            ]
        ),
    )
    rc = pr_status.main(["42"])
    assert rc == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["pr"] == 42
    assert payload["build"]["status"] == "passing"


def test_classify_status_with_timed_out_is_failing(pr_status):
    """timed_out conclusion classifies as failing (sibling of failure/cancelled)."""
    checks = [{"name": "slow", "state": "completed", "conclusion": "timed_out", "link": ""}]
    assert pr_status.classify_status(checks) == "failing"


def test_multiple_failing_checks_get_independent_summaries(pr_status, monkeypatch):
    """Each failing check fetches its own log; summaries don't bleed across checks."""
    checks_json = json.dumps(
        [
            {
                "name": "unit-tests",
                "state": "completed",
                "conclusion": "failure",
                "link": "https://github.com/foo/bar/actions/runs/111/job/1",
            },
            {
                "name": "e2e",
                "state": "completed",
                "conclusion": "failure",
                "link": "https://github.com/foo/bar/actions/runs/222/job/2",
            },
        ]
    )

    def runner(cmd, **kwargs):
        if cmd[:3] == ["gh", "pr", "checks"]:
            return _FakeCompletedProcess(stdout=checks_json)
        if cmd[:3] == ["gh", "pr", "view"]:
            return _FakeCompletedProcess(
                stdout=json.dumps({"mergeable": "MERGEABLE", "mergeStateStatus": "CLEAN"})
            )
        if cmd[:3] == ["gh", "run", "view"]:
            # Dispatch by run id in argv.
            run_id = cmd[3]
            if run_id == "111":
                return _FakeCompletedProcess(stdout="FAILED tests/unit.py::test_a\n")
            if run_id == "222":
                return _FakeCompletedProcess(stdout="FAILED tests/e2e.py::test_b\n")
        raise AssertionError(f"unmocked: {cmd}")

    monkeypatch.setattr(subprocess, "run", runner)
    output = pr_status.build_output(42)
    checks = output["build"]["checks"]
    assert len(checks) == 2
    unit = next(c for c in checks if c["name"] == "unit-tests")
    e2e = next(c for c in checks if c["name"] == "e2e")
    assert "tests/unit.py::test_a" in unit["failed_tests"]
    assert "tests/unit.py::test_a" not in e2e["failed_tests"]
    assert "tests/e2e.py::test_b" in e2e["failed_tests"]
    assert "tests/e2e.py::test_b" not in unit["failed_tests"]


def test_malformed_json_from_gh_checks_exits_one(pr_status, monkeypatch):
    """Non-JSON output from gh pr checks exits 1 (defensive parse)."""
    monkeypatch.setattr(
        subprocess,
        "run",
        _fake_run([(_matcher(["gh", "pr", "checks"]), "not json at all", 0)]),
    )
    with pytest.raises(SystemExit) as exc:
        pr_status.fetch_checks(42)
    assert exc.value.code == 1


def test_malformed_json_from_gh_pr_view_falls_back_to_unknown(pr_status, monkeypatch):
    """Malformed JSON from gh pr view falls back to UNKNOWN/UNKNOWN (less critical than checks)."""
    monkeypatch.setattr(
        subprocess,
        "run",
        _fake_run([(_matcher(["gh", "pr", "view"]), "garbage", 0)]),
    )
    merge = pr_status.fetch_merge_state(42)
    assert merge == {"mergeable": "UNKNOWN", "state": "UNKNOWN"}


def test_failing_check_with_empty_log_yields_empty_summary(pr_status, monkeypatch):
    """gh run view returning empty produces empty summary, not a crash."""
    checks_json = json.dumps(
        [
            {
                "name": "slow",
                "state": "completed",
                "conclusion": "failure",
                "link": "https://github.com/foo/bar/actions/runs/999/job/1",
            }
        ]
    )
    monkeypatch.setattr(
        subprocess,
        "run",
        _fake_run(
            [
                (_matcher(["gh", "pr", "checks"]), checks_json, 0),
                (
                    _matcher(["gh", "pr", "view"]),
                    json.dumps({"mergeable": "MERGEABLE", "mergeStateStatus": "CLEAN"}),
                    0,
                ),
                (_matcher(["gh", "run", "view"]), "", 1),
            ]
        ),
    )
    output = pr_status.build_output(42)
    check = output["build"]["checks"][0]
    assert check["failure_summary"] == ""
    assert check["failed_tests"] == []
    # status still classifies as failing
    assert output["build"]["status"] == "failing"


def test_failing_check_with_no_run_id_in_link_yields_empty_summary(pr_status, monkeypatch):
    """A failing check whose link has no /runs/<id> segment skips log fetch gracefully."""
    checks_json = json.dumps(
        [
            {
                "name": "weird",
                "state": "completed",
                "conclusion": "failure",
                "link": "https://example.com/no-run-id-here",
            }
        ]
    )
    monkeypatch.setattr(
        subprocess,
        "run",
        _fake_run(
            [
                (_matcher(["gh", "pr", "checks"]), checks_json, 0),
                (
                    _matcher(["gh", "pr", "view"]),
                    json.dumps({"mergeable": "MERGEABLE", "mergeStateStatus": "CLEAN"}),
                    0,
                ),
            ]
        ),
    )
    output = pr_status.build_output(42)
    assert output["build"]["checks"][0]["failure_summary"] == ""
    assert output["build"]["checks"][0]["failed_tests"] == []
