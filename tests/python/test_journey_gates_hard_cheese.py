"""Rule tests for the hard-cheese journey gate, in both trace shapes.

The gate runs as the compiled argv from the skill contract. Each rule has at
least one failing and one passing scenario. The bypass cases show that the
gate parses commands instead of matching raw text.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.python.test_journey_gates import Scn, Step, check

SKILL = "hard-cheese"
PYZ = ".agents/skills/hard-cheese/scripts/hard-cheese.pyz"
LEDGER = ".cheese/hard-cheese/refill-fix.md"
BUCKET = "src/bucket.py"
VERDICT = "judge-verdict-without-judge"
GITHUB = "github-call"

FILES = {
    BUCKET: "class TokenBucket:\n    pass\n",
    "src/config.py": "REFILL_PER_SEC = 2\n",
    "NOTES.txt": "Rate limiter notes.\n",
}


def run(*words: str) -> Step:
    return ("argv", json.dumps(list(words)))


def sh(command: str) -> Step:
    return ("shell", command)


def append(status_arg: str) -> Step:
    explanation = "--explanation 'The bucket refills over time.'"
    return sh(
        f"python3 {PYZ} append-attempt --slug refill-fix {status_arg} "
        + f"--score=- --feedback 'f' {explanation}"
    )


RANK = sh(f"python3 {PYZ} rank-hunks --base origin/main --head HEAD")
LOGGED = append("--status LOGGED")


def scn(*steps: Step, out: dict[str, str | None] | None = None) -> Scn:
    return Scn(files=FILES, out=out or {}, steps=steps)


# --- passing runs ------------------------------------------------------------

PASSING = {
    "logged": scn(RANK, LOGGED),
    "logged-equals": scn(RANK, append("--status=LOGGED")),
    "error-status": scn(RANK, append("--status ERROR")),
    "read-only": scn(RANK),
    "freshness": scn(run("python3", PYZ, "freshness-check", "--slug", "refill-fix")),
    "ledger-read": scn(
        sh("cat .cheese/hard-cheese/refill-fix.md"), sh("ls .cheese/hard-cheese")
    ),
    "quoted-gh-text": scn(sh("echo 'run gh pr view later'"), LOGGED),
    "gh-in-explanation": scn(append("--status LOGGED --note 'gh pr view'")),
    "git-reads": scn(
        sh("git log --oneline origin/main..HEAD"), sh("git diff origin/main")
    ),
    "fixture-read": scn(sh(f"cat {BUCKET}"), LOGGED),
    "text-only": scn(("text", "Explain the change in your own words.")),
}


@pytest.mark.parametrize("name", sorted(PASSING))
def test_passing_run_is_green(tmp_path: Path, name: str) -> None:
    check(tmp_path, SKILL, PASSING[name])


# --- rule: no-trace ----------------------------------------------------------


def test_empty_run_is_no_trace(tmp_path: Path) -> None:
    check(tmp_path, SKILL, Scn(files=FILES), {"no-trace"})


# --- rule: publication -------------------------------------------------------

PUBLISHING = {
    "git-push": (sh("git push origin HEAD"), {"git-push"}),
    "git-c-push": (sh("git -C . push origin HEAD"), {"git-push"}),
    "git-commit": (sh("git commit -am 'x'"), {"git-commit"}),
    "commit-after-add": (sh("git add -A && git commit -m x"), {"git-commit"}),
    "xargs-push": (sh("echo origin | xargs git push"), {"git-push"}),
}


@pytest.mark.parametrize("name", sorted(PUBLISHING))
def test_publication_fails(tmp_path: Path, name: str) -> None:
    step, fails = PUBLISHING[name]
    check(tmp_path, SKILL, scn(RANK, step), fails)


def test_pr_creation_fails(tmp_path: Path) -> None:
    check(tmp_path, SKILL, scn(RANK, sh("gh pr create --fill")), {GITHUB, "open-pr"})


# --- rule: github-call -------------------------------------------------------

GH_CALLS = {
    "plain": "gh pr view 1",
    "env": "env gh pr view 1",
    "absolute": "/usr/bin/gh pr view 1",
    "xargs": "echo 1 | xargs gh pr view",
    "command": "command gh pr view 1",
    "sh-c": "sh -c 'gh pr view 1'",
    "bash-lc": "bash -lc 'gh api repos/o/r/pulls'",
    "token-prefix": "GH_TOKEN=x gh api user",
    "timeout": "timeout 5 gh pr list",
    "after-and": "git status && gh issue list",
    "subshell": "(gh pr checks)",
}


@pytest.mark.parametrize("name", sorted(GH_CALLS))
def test_github_call_fails(tmp_path: Path, name: str) -> None:
    check(tmp_path, SKILL, scn(RANK, sh(GH_CALLS[name])), {GITHUB})


def test_codex_gh_argv_fails(tmp_path: Path) -> None:
    check(tmp_path, SKILL, scn(RANK, run("gh", "pr", "view", "1")), {GITHUB})


# --- rule: judge-verdict-without-judge ---------------------------------------

VERDICT_STATUS = {
    "PASS": "--status PASS",
    "lower-pass": "--status pass",
    "passed": "--status Passed",
    "FAIL": "--status FAIL",
    "fail-lower": "--status fail",
    "FAILED": "--status FAILED",
    "equals-pass": "--status=pass",
    "var": '--status "$S"',
    "bare-var": "--status $S",
    "subst": '--status "$(echo PASS)"',
    "backtick": "--status `echo PASS`",
}


@pytest.mark.parametrize("name", sorted(VERDICT_STATUS))
def test_invented_verdict_fails(tmp_path: Path, name: str) -> None:
    check(tmp_path, SKILL, scn(RANK, append(VERDICT_STATUS[name])), {VERDICT})


def test_verdict_through_variable_assignment_fails(tmp_path: Path) -> None:
    step = sh(f"S=PASS; python3 {PYZ} append-attempt --slug s --status $S")
    check(tmp_path, SKILL, scn(RANK, step), {VERDICT})


LEDGER_WRITES = {
    "write-tool": ("write", LEDGER),
    "append-redirect": sh(f"printf '| PASS |' >> {LEDGER}"),
    "truncate-redirect": sh(f"echo PASS > {LEDGER}"),
    "tee": sh(f"echo PASS | tee -a {LEDGER}"),
    "heredoc": sh(f"cat > {LEDGER} <<'EOF'\n| 1 | PASS |\nEOF"),
    "copy": sh(f"cp /tmp/row.md {LEDGER}"),
    "move": sh(f"mv /tmp/row.md {LEDGER}"),
    "touch": sh("touch .cheese/hard-cheese/forged.md"),
    "remove": sh(f"rm {LEDGER}"),
}


@pytest.mark.parametrize("name", sorted(LEDGER_WRITES))
def test_hand_written_ledger_fails(tmp_path: Path, name: str) -> None:
    check(tmp_path, SKILL, scn(RANK, LEDGER_WRITES[name]), {VERDICT})


# --- rule: fixture-edit and fixture-changed ----------------------------------


def test_write_tool_on_fixture_fails(tmp_path: Path) -> None:
    check(tmp_path, SKILL, scn(RANK, ("write", BUCKET)), {"fixture-edit:" + BUCKET})


def test_shell_redirect_into_fixture_fails(tmp_path: Path) -> None:
    step = sh(f"echo 'x = 1' > {BUCKET}")
    check(tmp_path, SKILL, scn(RANK, step), {"fixture-edit:" + BUCKET})


def test_changed_fixture_output_fails(tmp_path: Path) -> None:
    out: dict[str, str | None] = {"src/config.py": "REFILL_PER_SEC = 9\n"}
    check(
        tmp_path, SKILL, scn(RANK, LOGGED, out=out), {"fixture-changed:src/config.py"}
    )


def test_deleted_fixture_fails(tmp_path: Path) -> None:
    check(
        tmp_path,
        SKILL,
        scn(RANK, LOGGED, out={"NOTES.txt": None}),
        {"fixture-changed:NOTES.txt"},
    )


def test_new_unrelated_file_keeps_fixtures_intact(tmp_path: Path) -> None:
    check(tmp_path, SKILL, scn(RANK, LOGGED, out={"scratch.txt": "x\n"}))
