"""Tests for src/affinage/pr-status.py."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable, Iterable
from typing import Protocol, TypedDict, cast

import pytest


class _EnrichedCheck(TypedDict):
    name: str
    conclusion: str
    url: str
    failing: bool
    failure_summary: str
    failed_tests: list[str]


class _BuildInfo(TypedDict):
    status: str
    checks: list[_EnrichedCheck]


class _MergeInfo(TypedDict):
    mergeable: str
    state: str


class _Output(TypedDict):
    pr: int
    build: _BuildInfo
    merge: _MergeInfo


class _PrStatusModule(Protocol):
    def fetch_checks(self, pr: int) -> list[dict[str, object]]: ...
    def fetch_merge_state(self, pr: int) -> _MergeInfo: ...
    def extract_run_id(self, link: str) -> str | None: ...
    def extract_failed_tests(self, log: str) -> list[str]: ...
    def classify_status(self, checks: list[dict[str, object]]) -> str: ...
    def build_output(self, pr: int) -> _Output: ...
    def all_failures_ungroundable(self, output: dict[str, object]) -> bool: ...
    def main(self, argv: list[str] | None = None) -> int: ...


class _FakeCompletedProcess:
    def __init__(self, stdout: str = "", returncode: int = 0, stderr: str = "") -> None:
        self.stdout: str = stdout
        self.returncode: int = returncode
        self.stderr: str = stderr


def _matcher(prefix: Iterable[str]) -> Callable[[list[str]], bool]:
    needle = list(prefix)
    return lambda cmd: cmd[: len(needle)] == needle


_Response = tuple[Callable[[list[str]], bool], str, int]


def _fake_run(responses: list[_Response]) -> Callable[..., _FakeCompletedProcess]:
    """Return a fake subprocess.run that dispatches by argv prefix.

    Each response is (matcher, stdout, returncode). First match wins.
    """

    def runner(cmd: list[str], **_kwargs: object) -> _FakeCompletedProcess:
        for matcher, stdout, rc in responses:
            if matcher(cmd):
                return _FakeCompletedProcess(stdout=stdout, returncode=rc)
        raise AssertionError(f"unmocked subprocess call: {cmd}")

    return runner


def test_passing_build_no_checks(pr_status: _PrStatusModule, monkeypatch: pytest.MonkeyPatch) -> None:
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


def test_failing_build_extracts_summary_and_tests(pr_status: _PrStatusModule, monkeypatch: pytest.MonkeyPatch) -> None:
    """A failing check enriches the entry with summary + failed tests."""
    checks_json = json.dumps(
        [
            {
                "name": "test-suite",
                "state": "FAILURE",
                "bucket": "fail",
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


def test_pending_check_classified_pending(pr_status: _PrStatusModule, monkeypatch: pytest.MonkeyPatch) -> None:
    """A check still in_progress reports pending."""
    checks_json = json.dumps(
        [{"name": "slow-job", "state": "IN_PROGRESS", "bucket": "pending", "link": ""}]
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


def test_merge_conflict_surfaced(pr_status: _PrStatusModule, monkeypatch: pytest.MonkeyPatch) -> None:
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


def test_missing_gh_exits_two(pr_status: _PrStatusModule, monkeypatch: pytest.MonkeyPatch) -> None:
    """FileNotFoundError on subprocess.run → exit 2 (gh not installed)."""

    def raise_fnfe(*_args: object, **_kwargs: object) -> _FakeCompletedProcess:
        raise FileNotFoundError("gh not found")

    monkeypatch.setattr(subprocess, "run", raise_fnfe)
    with pytest.raises(SystemExit) as exc:
        _ = pr_status.fetch_checks(42)
    assert exc.value.code == 2


def test_gh_failure_exits_one(pr_status: _PrStatusModule, monkeypatch: pytest.MonkeyPatch) -> None:
    """Both the --json fast path and the plain fallback failing (e.g. PR not
    found: non-zero exit, empty stdout, no 'no checks reported' marker) → exit 1."""

    def runner(_cmd: list[str], **_kwargs: object) -> _FakeCompletedProcess:
        # Same gh pr checks invocation for both --json and plain: empty stdout,
        # non-zero exit, error stderr that is NOT the no-checks marker.
        return _FakeCompletedProcess(stdout="", returncode=1, stderr="GraphQL: Could not resolve to a PullRequest")

    monkeypatch.setattr(subprocess, "run", runner)
    with pytest.raises(SystemExit) as exc:
        _ = pr_status.fetch_checks(42)
    assert exc.value.code == 1


def test_extract_run_id_from_actions_url(pr_status: _PrStatusModule) -> None:
    url = "https://github.com/foo/bar/actions/runs/123456789/job/987654"
    assert pr_status.extract_run_id(url) == "123456789"


def test_extract_run_id_returns_none_on_empty(pr_status: _PrStatusModule) -> None:
    assert pr_status.extract_run_id("") is None
    assert pr_status.extract_run_id("https://example.com/no/run/here") is None


def test_extract_failed_tests_pytest_style(pr_status: _PrStatusModule) -> None:
    log = "FAILED tests/auth.py::test_foo\nFAILED tests/auth.py::test_bar\nrandom line\n"
    assert pr_status.extract_failed_tests(log) == [
        "tests/auth.py::test_foo",
        "tests/auth.py::test_bar",
    ]


def test_extract_failed_tests_rust_style(pr_status: _PrStatusModule) -> None:
    log = "running 3 tests\ntest foo::bar ... FAILED\ntest foo::baz ... ok\n"
    assert pr_status.extract_failed_tests(log) == ["foo::bar"]


def test_extract_failed_tests_dedups(pr_status: _PrStatusModule) -> None:
    log = "FAILED tests/x::a\nFAILED tests/x::a\n"
    assert pr_status.extract_failed_tests(log) == ["tests/x::a"]


def test_classify_status_with_cancelled_is_failing(pr_status: _PrStatusModule) -> None:
    checks: list[dict[str, object]] = [{"name": "lint", "state": "CANCELLED", "bucket": "fail", "link": ""}]
    assert pr_status.classify_status(checks) == "failing"


def test_main_writes_json_to_stdout(
    pr_status: _PrStatusModule, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
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
    payload = cast(dict[str, object], json.loads(captured.out))
    assert payload["pr"] == 42
    assert cast(dict[str, object], payload["build"])["status"] == "passing"


def test_classify_status_with_timed_out_is_failing(pr_status: _PrStatusModule) -> None:
    """timed_out conclusion classifies as failing (sibling of failure/cancelled)."""
    checks: list[dict[str, object]] = [{"name": "slow", "state": "TIMED_OUT", "bucket": "fail", "link": ""}]
    assert pr_status.classify_status(checks) == "failing"


def test_multiple_failing_checks_get_independent_summaries(pr_status: _PrStatusModule, monkeypatch: pytest.MonkeyPatch) -> None:
    """Each failing check fetches its own log; summaries don't bleed across checks."""
    checks_json = json.dumps(
        [
            {
                "name": "unit-tests",
                "state": "FAILURE",
                "bucket": "fail",
                "link": "https://github.com/foo/bar/actions/runs/111/job/1",
            },
            {
                "name": "e2e",
                "state": "FAILURE",
                "bucket": "fail",
                "link": "https://github.com/foo/bar/actions/runs/222/job/2",
            },
        ]
    )

    def runner(cmd: list[str], **_kwargs: object) -> _FakeCompletedProcess:
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


def test_unparseable_json_falls_back_then_exits_one_if_plain_also_fails(
    pr_status: _PrStatusModule, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Unparseable --json output triggers the plain fallback; if the plain path
    also yields nothing usable (empty stdout, error stderr), exit 1 — both
    paths must fail before halting."""
    calls: list[list[str]] = []

    def runner(cmd: list[str], **_kwargs: object) -> _FakeCompletedProcess:
        calls.append(list(cmd))
        if "--json" in cmd:
            # gh emitted garbage instead of JSON on the fast path.
            return _FakeCompletedProcess(stdout="not json at all", returncode=0)
        # Plain fallback: genuine error, not a no-checks PR.
        return _FakeCompletedProcess(stdout="", returncode=1, stderr="API error")

    monkeypatch.setattr(subprocess, "run", runner)
    with pytest.raises(SystemExit) as exc:
        _ = pr_status.fetch_checks(42)
    assert exc.value.code == 1
    # The fallback was actually attempted (a plain, no-`--json` invocation ran).
    assert any("--json" not in c for c in calls if c[:3] == ["gh", "pr", "checks"])


def test_malformed_json_from_gh_pr_view_falls_back_to_unknown(
    pr_status: _PrStatusModule, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Malformed JSON from gh pr view falls back to UNKNOWN/UNKNOWN (less critical than checks)."""
    monkeypatch.setattr(
        subprocess,
        "run",
        _fake_run([(_matcher(["gh", "pr", "view"]), "garbage", 0)]),
    )
    merge = pr_status.fetch_merge_state(42)
    assert merge == {"mergeable": "UNKNOWN", "state": "UNKNOWN"}


def test_failing_check_with_empty_log_yields_empty_summary(
    pr_status: _PrStatusModule, monkeypatch: pytest.MonkeyPatch
) -> None:
    """gh run view returning empty produces empty summary, not a crash."""
    checks_json = json.dumps(
        [
            {
                "name": "slow",
                "state": "FAILURE",
                "bucket": "fail",
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


def test_failing_check_with_no_run_id_in_link_yields_empty_summary(
    pr_status: _PrStatusModule, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failing check whose link has no /runs/<id> segment skips log fetch gracefully."""
    checks_json = json.dumps(
        [
            {
                "name": "weird",
                "state": "FAILURE",
                "bucket": "fail",
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


def test_non_list_json_from_gh_checks_exits_one(
    pr_status: _PrStatusModule, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Valid JSON that isn't a list is treated as an unusable fast path and
    triggers the plain fallback; with the plain path also failing, exit 1 —
    a schema flip is never silently swallowed into a false 'passing'."""

    def runner(cmd: list[str], **_kwargs: object) -> _FakeCompletedProcess:
        if "--json" in cmd:
            return _FakeCompletedProcess(stdout='{"error": "unexpected shape"}', returncode=0)
        return _FakeCompletedProcess(stdout="", returncode=1, stderr="API error")

    monkeypatch.setattr(subprocess, "run", runner)
    with pytest.raises(SystemExit) as exc:
        _ = pr_status.fetch_checks(42)
    assert exc.value.code == 1


def _fallback_runner(
    plain_stdout: str, plain_rc: int = 0, plain_stderr: str = ""
) -> Callable[..., _FakeCompletedProcess]:
    """A subprocess.run fake where `gh pr checks --json` is rejected (old gh)
    and the plain `gh pr checks` returns the given output."""

    def runner(cmd: list[str], **_kwargs: object) -> _FakeCompletedProcess:
        if cmd[:3] == ["gh", "pr", "checks"]:
            if "--json" in cmd:
                return _FakeCompletedProcess(
                    stdout="",
                    returncode=1,
                    stderr="unknown flag: --json\n",
                )
            return _FakeCompletedProcess(
                stdout=plain_stdout, returncode=plain_rc, stderr=plain_stderr
            )
        if cmd[:3] == ["gh", "pr", "view"]:
            return _FakeCompletedProcess(
                stdout=json.dumps({"mergeable": "MERGEABLE", "mergeStateStatus": "CLEAN"})
            )
        if cmd[:3] == ["gh", "run", "view"]:
            return _FakeCompletedProcess(stdout="boom\nProcess completed with exit code 1")
        raise AssertionError(f"unmocked subprocess call: {cmd}")

    return runner


def test_fallback_parses_plain_checks_when_json_unsupported(
    pr_status: _PrStatusModule, monkeypatch: pytest.MonkeyPatch
) -> None:
    """gh < 2.49 rejects --json; the plain tab-separated output is parsed and the
    `bucket` field synthesized from the STATUS column (which already carries gh's
    bucket label), so classify_status/failing still work without the fast path."""
    # NAME \t STATUS(bucket) \t ELAPSED \t URL \t DESCRIPTION
    plain = "\t".join(
        ["unit-tests", "fail", "1m2s", "https://github.com/o/r/actions/runs/77/job/9", "failed"]
    )
    monkeypatch.setattr(subprocess, "run", _fallback_runner(plain, plain_rc=1))

    checks = pr_status.fetch_checks(42)
    assert checks == [
        {
            "name": "unit-tests",
            "state": "FAILURE",
            "bucket": "fail",
            "link": "https://github.com/o/r/actions/runs/77/job/9",
        }
    ]
    # The synthesized shape drives the same downstream classification and enrichment.
    assert pr_status.classify_status(checks) == "failing"


def test_fallback_full_build_output_failing_enriches(
    pr_status: _PrStatusModule, monkeypatch: pytest.MonkeyPatch
) -> None:
    """End-to-end: with only the plain path available, a failing check still gets
    its `failing` flag set and its log fetched/summarized."""
    plain = "\t".join(
        ["e2e", "fail", "30s", "https://github.com/o/r/actions/runs/77/job/9", ""]
    )
    monkeypatch.setattr(subprocess, "run", _fallback_runner(plain, plain_rc=1))

    output = pr_status.build_output(42)
    assert output["build"]["status"] == "failing"
    check = output["build"]["checks"][0]
    assert check["name"] == "e2e"
    assert check["conclusion"] == "failure"
    assert check["failing"] is True
    assert "Process completed with exit code 1" in check["failure_summary"]


def test_fallback_pending_and_pass_buckets(
    pr_status: _PrStatusModule, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The plain STATUS column carries pass/pending buckets directly; a pending
    check classifies the build pending."""
    plain = "\n".join(
        [
            "\t".join(["lint", "pass", "5s", "https://github.com/o/r/actions/runs/1/job/1", ""]),
            "\t".join(["slow", "pending", "0", "https://github.com/o/r/actions/runs/2/job/2", ""]),
        ]
    )
    monkeypatch.setattr(subprocess, "run", _fallback_runner(plain, plain_rc=8))

    checks = pr_status.fetch_checks(42)
    assert [c["bucket"] for c in checks] == ["pass", "pending"]
    assert [c["state"] for c in checks] == ["SUCCESS", "IN_PROGRESS"]
    assert pr_status.classify_status(checks) == "pending"


def test_fallback_no_checks_reported_is_empty_not_error(
    pr_status: _PrStatusModule, monkeypatch: pytest.MonkeyPatch
) -> None:
    """gh exits non-zero with empty stdout and a 'no checks reported' message when
    a PR has no checks — that is a real passing/no-checks answer, not a failure."""
    monkeypatch.setattr(
        subprocess,
        "run",
        _fallback_runner(
            "", plain_rc=1, plain_stderr="no checks reported on the 'feature' branch\n"
        ),
    )
    assert pr_status.fetch_checks(42) == []


def test_json_fast_path_used_when_supported(
    pr_status: _PrStatusModule, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When --json works, the plain fallback is never invoked."""
    plain_called = {"hit": False}

    def runner(cmd: list[str], **_kwargs: object) -> _FakeCompletedProcess:
        if cmd[:3] == ["gh", "pr", "checks"]:
            if "--json" in cmd:
                return _FakeCompletedProcess(
                    stdout=json.dumps(
                        [{"name": "ci", "state": "SUCCESS", "bucket": "pass", "link": ""}]
                    )
                )
            plain_called["hit"] = True
            return _FakeCompletedProcess(stdout="should-not-be-read")
        raise AssertionError(f"unmocked subprocess call: {cmd}")

    monkeypatch.setattr(subprocess, "run", runner)
    checks = pr_status.fetch_checks(42)
    assert checks == [{"name": "ci", "state": "SUCCESS", "bucket": "pass", "link": ""}]
    assert plain_called["hit"] is False, "plain fallback must not run when --json succeeds"


def test_json_fast_path_succeeds_despite_nonzero_exit(
    pr_status: _PrStatusModule, monkeypatch: pytest.MonkeyPatch
) -> None:
    """gh exits non-zero (8) when checks are *failing* yet still prints valid JSON;
    the fast path must accept that output rather than dropping to the fallback."""
    plain_called = {"hit": False}

    def runner(cmd: list[str], **_kwargs: object) -> _FakeCompletedProcess:
        if cmd[:3] == ["gh", "pr", "checks"]:
            if "--json" in cmd:
                return _FakeCompletedProcess(
                    stdout=json.dumps(
                        [{"name": "ci", "state": "FAILURE", "bucket": "fail", "link": ""}]
                    ),
                    returncode=8,
                )
            plain_called["hit"] = True
            return _FakeCompletedProcess(stdout="")
        raise AssertionError(f"unmocked subprocess call: {cmd}")

    monkeypatch.setattr(subprocess, "run", runner)
    checks = pr_status.fetch_checks(42)
    assert checks[0]["bucket"] == "fail"
    assert plain_called["hit"] is False


def test_gh_pr_checks_uses_real_schema_fields(
    pr_status: _PrStatusModule, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression for cure #1: the --json arg passed to `gh pr checks` must use
    fields that the CLI actually returns. The original implementation requested
    `conclusion` (which does not exist on `gh pr checks`) and died on every real
    invocation; only the recursive integration test caught it because the unit
    mocks lied. Lock in the correct shape so future edits stay honest."""
    captured: list[list[str]] = []

    def runner(cmd: list[str], **_kwargs: object) -> _FakeCompletedProcess:
        captured.append(list(cmd))
        if cmd[:3] == ["gh", "pr", "checks"]:
            return _FakeCompletedProcess(stdout="[]")
        return _FakeCompletedProcess(stdout="")

    monkeypatch.setattr(subprocess, "run", runner)
    _ = pr_status.fetch_checks(42)

    check_call = next(c for c in captured if c[:3] == ["gh", "pr", "checks"])
    json_arg_idx = check_call.index("--json") + 1
    fields = check_call[json_arg_idx].split(",")
    # `conclusion` does NOT exist on `gh pr checks --json`; `bucket` is the real
    # pre-classified field. The original bug landed exactly here.
    assert "conclusion" not in fields, (
        "gh pr checks has no `conclusion` field; use `bucket` (pass/fail/pending/skipping)"
    )
    assert "bucket" in fields, "must request `bucket` so classify_status has its input"
    # `state` is also a real field and is used to derive the per-check `conclusion`
    # output value, so it must be requested too.
    assert "state" in fields


def test_all_failures_ungroundable_passing_build_is_false(pr_status: _PrStatusModule) -> None:
    """A passing build is never ungroundable — nothing to halt on."""
    output: dict[str, object] = {"build": {"status": "passing", "checks": []}}
    assert pr_status.all_failures_ungroundable(output) is False


def test_all_failures_ungroundable_pending_build_is_false(pr_status: _PrStatusModule) -> None:
    """A pending build hasn't failed yet, so it isn't ungroundable."""
    output: dict[str, object] = {
        "build": {
            "status": "pending",
            "checks": [{"failing": False, "failure_summary": ""}],
        }
    }
    assert pr_status.all_failures_ungroundable(output) is False


def test_all_failures_ungroundable_all_empty_is_true(pr_status: _PrStatusModule) -> None:
    """Failing build whose every fetchable failing check has an empty summary
    (expired Actions logs) → halt-worthy."""
    output: dict[str, object] = {
        "build": {
            "status": "failing",
            "checks": [
                {
                    "failing": True,
                    "url": "https://github.com/foo/bar/actions/runs/1/job/1",
                    "failure_summary": "",
                }
            ],
        }
    }
    assert pr_status.all_failures_ungroundable(output) is True


def test_all_failures_ungroundable_one_summary_present_is_false(pr_status: _PrStatusModule) -> None:
    """If at least one fetchable failing check has grounded evidence, the
    affineur can ground that one — not ungroundable, no halt."""
    output: dict[str, object] = {
        "build": {
            "status": "failing",
            "checks": [
                {
                    "failing": True,
                    "url": "https://github.com/foo/bar/actions/runs/1/job/1",
                    "failure_summary": "",
                },
                {
                    "failing": True,
                    "url": "https://github.com/foo/bar/actions/runs/2/job/2",
                    "failure_summary": "AssertionError on line 9",
                },
            ],
        }
    }
    assert pr_status.all_failures_ungroundable(output) is False


def test_all_failures_ungroundable_ignores_non_failing_checks(pr_status: _PrStatusModule) -> None:
    """Only checks flagged `failing` count toward grounding. A non-failing check
    carrying a (non-empty) summary must NOT mask an ungroundable failing check —
    this fails if the `failing` filter is dropped and every check is considered."""
    output: dict[str, object] = {
        "build": {
            "status": "failing",
            "checks": [
                {
                    "failing": False,
                    "url": "https://github.com/foo/bar/actions/runs/1/job/1",
                    "failure_summary": "irrelevant noise",
                },
                {
                    "failing": True,
                    "url": "https://github.com/foo/bar/actions/runs/2/job/2",
                    "failure_summary": "",
                },
            ],
        }
    }
    assert pr_status.all_failures_ungroundable(output) is True


def test_all_failures_ungroundable_excludes_non_actions_checks(pr_status: _PrStatusModule) -> None:
    """Finding #3292480022: a build failing solely on a non-Actions check (a
    `url` with no `/runs/<id>` segment) is NOT ungroundable. Its empty summary is
    by design — `fetch_failure_summary` never attempts a fetch — not expired
    Actions logs, so rerunning a run id won't help. The caller proceeds (exit 0)
    and the check becomes Needs-investigation rather than a misdirected
    logs-expired halt. Fails if the run-id filter is dropped from the predicate."""
    output: dict[str, object] = {
        "build": {
            "status": "failing",
            "checks": [
                {
                    "failing": True,
                    "url": "https://external-ci.example.com/build/42",
                    "failure_summary": "",
                }
            ],
        }
    }
    assert pr_status.all_failures_ungroundable(output) is False


def test_all_failures_ungroundable_actions_failure_not_masked_by_non_actions(
    pr_status: _PrStatusModule,
) -> None:
    """A non-Actions failing check (no run id, by-design empty summary) must not
    mask an Actions failing check whose logs expired: the fetchable set is the
    one Actions check with an empty summary, so the build is still ungroundable
    and halt-worthy."""
    output: dict[str, object] = {
        "build": {
            "status": "failing",
            "checks": [
                {
                    "failing": True,
                    "url": "https://external-ci.example.com/build/42",
                    "failure_summary": "",
                },
                {
                    "failing": True,
                    "url": "https://github.com/foo/bar/actions/runs/9/job/1",
                    "failure_summary": "",
                },
            ],
        }
    }
    assert pr_status.all_failures_ungroundable(output) is True


def test_build_output_tags_failing_from_bucket(
    pr_status: _PrStatusModule, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`failing` is derived from gh's bucket, not the conclusion string — so a
    bucket==fail check whose state is OUTSIDE {failure,cancelled,timed_out}
    (e.g. action_required) is still flagged failing, and a bucket==pass check is
    not. This is the single source of truth that keeps the halt predicate in
    lockstep with enrichment."""
    checks_json = json.dumps(
        [
            {
                "name": "needs-approval",
                "state": "ACTION_REQUIRED",
                "bucket": "fail",
                "link": "https://github.com/foo/bar/actions/runs/777/job/1",
            },
            {"name": "lint", "state": "SUCCESS", "bucket": "pass", "link": ""},
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
    checks = pr_status.build_output(42)["build"]["checks"]
    action_required = next(c for c in checks if c["name"] == "needs-approval")
    lint = next(c for c in checks if c["name"] == "lint")
    assert action_required["failing"] is True
    assert lint["failing"] is False


def test_main_exits_three_for_out_of_family_fail_state(
    pr_status: _PrStatusModule, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression for the predicate-divergence finding: a build failing solely on
    a bucket==fail check whose state is outside the old conclusion family
    (action_required) with expired logs must exit 3 — under the old
    conclusion-family filter this returned 0 and graded a blank."""
    checks_json = json.dumps(
        [
            {
                "name": "needs-approval",
                "state": "ACTION_REQUIRED",
                "bucket": "fail",
                "link": "https://github.com/foo/bar/actions/runs/888/job/1",
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
    assert pr_status.main(["42"]) == 3


def test_main_exits_three_when_failing_logs_unfetchable(
    pr_status: _PrStatusModule, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """#76: a failing build with every failing check's log unfetchable (expired
    Actions logs) exits 3 so the skill's halt branch fires instead of grading a
    blank. The JSON is still emitted to stdout for debugging."""
    checks_json = json.dumps(
        [
            {
                "name": "test-suite",
                "state": "FAILURE",
                "bucket": "fail",
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
                # Expired logs: gh run view --log-failed returns non-zero/empty.
                (_matcher(["gh", "run", "view"]), "", 1),
            ]
        ),
    )
    rc = pr_status.main(["42"])
    assert rc == 3
    captured = capsys.readouterr()
    # JSON still printed so a human can inspect the empty-summary failure.
    payload = cast(_Output, json.loads(captured.out))
    assert payload["build"]["status"] == "failing"
    assert payload["build"]["checks"][0]["failure_summary"] == ""


def test_main_exits_zero_when_some_failure_groundable(
    pr_status: _PrStatusModule, monkeypatch: pytest.MonkeyPatch
) -> None:
    """#76: a failing build is NOT halted when at least one failing check has a
    fetchable log — that finding can be graded; the empty ones become
    Needs-investigation, not a blanket halt."""
    checks_json = json.dumps(
        [
            {
                "name": "expired",
                "state": "FAILURE",
                "bucket": "fail",
                "link": "https://github.com/foo/bar/actions/runs/111/job/1",
            },
            {
                "name": "fresh",
                "state": "FAILURE",
                "bucket": "fail",
                "link": "https://github.com/foo/bar/actions/runs/222/job/2",
            },
        ]
    )

    def runner(cmd: list[str], **_kwargs: object) -> _FakeCompletedProcess:
        if cmd[:3] == ["gh", "pr", "checks"]:
            return _FakeCompletedProcess(stdout=checks_json)
        if cmd[:3] == ["gh", "pr", "view"]:
            return _FakeCompletedProcess(
                stdout=json.dumps({"mergeable": "MERGEABLE", "mergeStateStatus": "CLEAN"})
            )
        if cmd[:3] == ["gh", "run", "view"]:
            run_id = cmd[3]
            if run_id == "111":
                return _FakeCompletedProcess(stdout="", returncode=1)  # expired
            if run_id == "222":
                return _FakeCompletedProcess(stdout="FAILED tests/fresh.py::test_b\n")
        raise AssertionError(f"unmocked: {cmd}")

    monkeypatch.setattr(subprocess, "run", runner)
    rc = pr_status.main(["42"])
    assert rc == 0


def test_failing_state_with_cancelled_bucket_fail_enriches(
    pr_status: _PrStatusModule, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression for cure #4: enrichment runs on bucket==fail, so cancelled
    and timed_out states (which gh classifies as bucket=fail) now get summary
    + failed_tests population, not just classification."""
    checks_json = json.dumps(
        [
            {
                "name": "slow",
                "state": "CANCELLED",
                "bucket": "fail",
                "link": "https://github.com/foo/bar/actions/runs/555/job/1",
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
                (
                    _matcher(["gh", "run", "view"]),
                    "job cancelled by user at step 3\nFAILED tests/cancel.py::test_x",
                    0,
                ),
            ]
        ),
    )
    output = pr_status.build_output(42)
    check = output["build"]["checks"][0]
    # state lowercased into conclusion (spec output contract preserved).
    assert check["conclusion"] == "cancelled"
    # bucket==fail triggers enrichment for non-failure states too — the cure #4 fix.
    assert "tests/cancel.py::test_x" in check["failed_tests"]
    assert "cancelled by user" in check["failure_summary"]