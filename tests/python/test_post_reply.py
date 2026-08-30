"""Tests for src/affinage/post-reply.py (bundled as the `post-reply` subcommand
of affinage.pyz). Ports the contract previously covered by
tests/bash/test_post_reply.bats and adds the exact-suffix-match edge case.

subprocess.run is faked by argv prefix so no real gh/git is invoked; the fake
records every POST so endpoint routing and the composed body can be asserted.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Iterable
from typing import Protocol

import pytest


class _PostReplyModule(Protocol):
    def main(self, argv: list[str] | None = None) -> int: ...
    def compose_body(self, body: str, handle: str) -> str: ...


class _FakeCompletedProcess:
    def __init__(self, stdout: str = "", returncode: int = 0, stderr: str = "") -> None:
        self.stdout: str = stdout
        self.returncode: int = returncode
        self.stderr: str = stderr


def _matcher(prefix: Iterable[str]) -> Callable[[list[str]], bool]:
    needle = list(prefix)
    return lambda cmd: cmd[: len(needle)] == needle


_Response = tuple[Callable[[list[str]], bool], str, int]


def _fake_run(
    responses: list[_Response], recorder: list[list[str]] | None = None
) -> Callable[..., _FakeCompletedProcess]:
    """Fake subprocess.run dispatching by argv prefix. Each response is
    (matcher, stdout, returncode); first match wins. Every call is appended to
    `recorder` if given."""

    def runner(cmd: list[str], **_kwargs: object) -> _FakeCompletedProcess:
        if recorder is not None:
            recorder.append(list(cmd))
        for matcher, stdout, rc in responses:
            if matcher(cmd):
                return _FakeCompletedProcess(stdout=stdout, returncode=rc)
        raise AssertionError(f"unmocked subprocess call: {cmd}")

    return runner


# Canned responses for a healthy environment: resolves handle + repo, POST ok.
def _healthy(recorder: list[list[str]]) -> Callable[..., _FakeCompletedProcess]:
    return _fake_run(
        [
            (_matcher(["gh", "api", "user"]), "stub-user", 0),
            (_matcher(["gh", "repo", "view"]), "owner/repo", 0),
            (_matcher(["gh", "api", "--method", "POST"]), "", 0),
            (_matcher(["git", "config", "user.name"]), "git-name", 0),
        ],
        recorder,
    )


def _posted_body(recorder: list[list[str]]) -> str:
    """Extract the body= value from the recorded POST call."""
    for cmd in recorder:
        if cmd[:4] == ["gh", "api", "--method", "POST"]:
            for arg in cmd:
                if arg.startswith("body="):
                    return arg[len("body=") :]
    raise AssertionError(f"no POST recorded in {recorder}")


def _posted_path(recorder: list[list[str]]) -> str:
    for cmd in recorder:
        if cmd[:4] == ["gh", "api", "--method", "POST"]:
            # api path is the first arg after the --method POST flag pair
            return cmd[4]
    raise AssertionError(f"no POST recorded in {recorder}")


@pytest.fixture(autouse=True)
def _clear_handle_env(monkeypatch: pytest.MonkeyPatch) -> None:  # pyright: ignore[reportUnusedFunction]
    monkeypatch.delenv("RESPOND_GH_HANDLE", raising=False)


# --- endpoint routing -----------------------------------------------------


def test_thread_mode_hits_replies_endpoint(post_reply: _PostReplyModule, monkeypatch: pytest.MonkeyPatch) -> None:
    rec: list[list[str]] = []
    monkeypatch.setattr(subprocess, "run", _healthy(rec))
    assert post_reply.main(["--thread", "--pr", "42", "--comment-id", "999", "--body", "Fixed."]) == 0
    assert _posted_path(rec) == "repos/owner/repo/pulls/42/comments/999/replies"


def test_issue_mode_hits_issues_endpoint(post_reply: _PostReplyModule, monkeypatch: pytest.MonkeyPatch) -> None:
    rec: list[list[str]] = []
    monkeypatch.setattr(subprocess, "run", _healthy(rec))
    assert post_reply.main(["--issue", "--pr", "42", "--body", "Re: @alice — fixed."]) == 0
    assert _posted_path(rec) == "repos/owner/repo/issues/42/comments"


# --- attribution ----------------------------------------------------------


def test_attribution_appended_with_resolved_handle(post_reply: _PostReplyModule, monkeypatch: pytest.MonkeyPatch) -> None:
    rec: list[list[str]] = []
    monkeypatch.setattr(subprocess, "run", _healthy(rec))
    _ = post_reply.main(["--issue", "--pr", "42", "--body", "Hello world."])
    assert "agent on behalf of stub-user" in _posted_body(rec)


def test_respond_gh_handle_overrides_resolution(post_reply: _PostReplyModule, monkeypatch: pytest.MonkeyPatch) -> None:
    rec: list[list[str]] = []
    monkeypatch.setenv("RESPOND_GH_HANDLE", "override-handle")
    monkeypatch.setattr(subprocess, "run", _healthy(rec))
    _ = post_reply.main(["--issue", "--pr", "42", "--body", "Hello."])
    assert "agent on behalf of override-handle" in _posted_body(rec)
    # gh api user must never be called when the env var short-circuits.
    assert not any(cmd[:3] == ["gh", "api", "user"] for cmd in rec)


def test_idempotent_no_double_append(post_reply: _PostReplyModule, monkeypatch: pytest.MonkeyPatch) -> None:
    rec: list[list[str]] = []
    monkeypatch.setattr(subprocess, "run", _healthy(rec))
    body = "Hello.\n\n---\nagent on behalf of stub-user"
    _ = post_reply.main(["--issue", "--pr", "42", "--body", body])
    assert _posted_body(rec).count("agent on behalf of stub-user") == 1


def test_idempotent_tolerates_trailing_newline(post_reply: _PostReplyModule, monkeypatch: pytest.MonkeyPatch) -> None:
    rec: list[list[str]] = []
    monkeypatch.setattr(subprocess, "run", _healthy(rec))
    body = "Hello.\n\n---\nagent on behalf of stub-user\n"
    _ = post_reply.main(["--issue", "--pr", "42", "--body", body])
    assert _posted_body(rec).count("agent on behalf of stub-user") == 1


def test_attribution_appended_when_body_only_quotes_it(post_reply: _PostReplyModule) -> None:
    """Exact-suffix match, not substring: a body that mentions the attribution
    phrase mid-text but does not END with the suffix block still gets a real
    attribution appended."""
    out = post_reply.compose_body(
        'I cited "agent on behalf of someone" in the spec, but this is the reply.',
        "stub-user",
    )
    assert out.rstrip().endswith("---\nagent on behalf of stub-user")
    assert out.count("agent on behalf of") == 2


def test_compose_body_preserves_metacharacters(post_reply: _PostReplyModule) -> None:
    body = 'Backticks `code` and $vars and "quotes" and newlines\nstill survive.'
    out = post_reply.compose_body(body, "u")
    assert "Backticks `code` and $vars" in out
    assert out.endswith("---\nagent on behalf of u\n")


# --- handle resolution precedence -----------------------------------------


def test_handle_falls_through_to_git_config(post_reply: _PostReplyModule, monkeypatch: pytest.MonkeyPatch) -> None:
    rec: list[list[str]] = []
    monkeypatch.setattr(
        subprocess,
        "run",
        _fake_run(
            [
                (_matcher(["gh", "api", "user"]), "", 1),  # gh user fails
                (_matcher(["git", "config", "user.name"]), "fallback-user", 0),
                (_matcher(["gh", "repo", "view"]), "owner/repo", 0),
                (_matcher(["gh", "api", "--method", "POST"]), "", 0),
            ],
            rec,
        ),
    )
    _ = post_reply.main(["--issue", "--pr", "42", "--body", "Hello."])
    assert "agent on behalf of fallback-user" in _posted_body(rec)


def test_handle_resolution_exhausted_exits_1(post_reply: _PostReplyModule, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        subprocess,
        "run",
        _fake_run(
            [
                (_matcher(["gh", "api", "user"]), "", 1),
                (_matcher(["git", "config", "user.name"]), "", 1),
            ]
        ),
    )
    with pytest.raises(SystemExit) as exc:
        _ = post_reply.main(["--issue", "--pr", "42", "--body", "Hello."])
    assert exc.value.code == 1


def test_repo_resolution_failure_exits_1(post_reply: _PostReplyModule, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        subprocess,
        "run",
        _fake_run(
            [
                (_matcher(["gh", "api", "user"]), "stub-user", 0),
                (_matcher(["gh", "repo", "view"]), "", 1),
            ]
        ),
    )
    with pytest.raises(SystemExit) as exc:
        _ = post_reply.main(["--issue", "--pr", "42", "--body", "Hello."])
    assert exc.value.code == 1


# --- argument validation --------------------------------------------------


def test_post_api_failure_exits_1(post_reply: _PostReplyModule, monkeypatch: pytest.MonkeyPatch) -> None:
    """A failed `gh api POST` must fail loud (exit 1), never silently succeed —
    a swallowed POST error would drop the reply while reporting success."""
    monkeypatch.setattr(
        subprocess,
        "run",
        _fake_run(
            [
                (_matcher(["gh", "api", "user"]), "stub-user", 0),
                (_matcher(["gh", "repo", "view"]), "owner/repo", 0),
                (_matcher(["gh", "api", "--method", "POST"]), "", 1),  # POST fails
            ]
        ),
    )
    with pytest.raises(SystemExit) as exc:
        _ = post_reply.main(["--issue", "--pr", "42", "--body", "Hello."])
    assert exc.value.code == 1


@pytest.mark.parametrize(
    "argv, code",
    [
        (["--thread", "--comment-id", "999", "--body", "x"], 1),  # missing --pr
        (["--thread", "--pr", "42", "--body", "x"], 1),  # missing --comment-id
        (["--issue", "--pr", "42", "--comment-id", "999", "--body", "x"], 1),  # comment-id w/ issue
        (["--issue", "--pr", "42", "--body", "x", "--bogus", "v"], 1),  # unknown flag
        (["--thread", "--issue", "--pr", "42", "--comment-id", "1", "--body", "x"], 1),  # combine
        (["--issue", "--pr", "42"], 1),  # missing --body
        (["--pr", "42", "--body", "x"], 2),  # no mode -> usage
    ],
)
def test_arg_validation_exit_codes(post_reply: _PostReplyModule, argv: list[str], code: int) -> None:
    with pytest.raises(SystemExit) as exc:
        _ = post_reply.main(argv)
    assert exc.value.code == code


# --- help flag ------------------------------------------------------------


@pytest.mark.parametrize("flag", ["-h", "--help"])
def test_help_prints_usage_to_stdout_and_exits_0(
    post_reply: _PostReplyModule, flag: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """--help / -h must write usage to stdout and exit 0 — it is not an error."""
    with pytest.raises(SystemExit) as exc:
        _ = post_reply.main([flag])
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "Usage" in captured.out
    assert captured.err == ""
