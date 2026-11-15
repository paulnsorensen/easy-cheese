"""Affinage gate rules, each with a failing and a passing scenario in both shapes."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.python.test_journey_gates import BENIGN, PULL_REQUEST, PUSH, Scn, check

SKILL = "affinage"
PYZ = ".agents/skills/affinage/scripts/affinage.pyz"
FIXTURE = {
    "bin/gh": "#!/usr/bin/env python3\nprint('gh')\n",
    "bin/data/number.txt": "315\n",
    "bin/data/comments.json": "[]\n",
    "src/billing.py": "def total(qty):\n    return 1 / qty\n",
}
READ = [
    ("shell", f"python3 {PYZ} pr-status 315"),
    ("shell", "gh pr checkout 315"),
    ("text", "status: ok\nnext: cure\nartifact: .cheese/affinage/pr-315.md"),
]
BASE = Scn(files=FIXTURE, steps=tuple(READ))


def ran(*commands: str) -> Scn:
    return BASE.but(then=[("shell", command) for command in commands])


def test_clean_run_passes(tmp_path: Path) -> None:
    check(tmp_path, SKILL, BASE)


def test_no_trace_fails(tmp_path: Path) -> None:
    check(tmp_path, SKILL, BASE.but(steps=[]), {"no-trace"})


@pytest.mark.parametrize("command", PUSH[:6])
def test_git_push_fails(tmp_path: Path, command: str) -> None:
    check(tmp_path, SKILL, ran(command), {"git-push"})


@pytest.mark.parametrize(
    "command", ["git commit -m fix", "git -C . commit -am x", "env A=1 git commit"]
)
def test_git_commit_fails(tmp_path: Path, command: str) -> None:
    check(tmp_path, SKILL, ran(command), {"git-commit"})


@pytest.mark.parametrize("command", PULL_REQUEST[:3])
def test_open_pr_fails(tmp_path: Path, command: str) -> None:
    check(tmp_path, SKILL, ran(command), {"open-pr"})


@pytest.mark.parametrize("command", BENIGN)
def test_benign_commands_pass(tmp_path: Path, command: str) -> None:
    check(tmp_path, SKILL, ran(command))


POSTS = [
    f'python3 {PYZ} post-reply --pr 315 --comment 101 --body "x"',
    f"{PYZ} post-reply --pr 315",
    f"python3 {PYZ} --verbose post-reply --pr 315",
    f"python3 {PYZ} --help && python3 {PYZ} post-reply --pr 315",
    f"python3 {PYZ} post-reply --help; python3 {PYZ} post-reply --pr 1",
    "gh pr comment 315 --body x",
    "gh -R acme/widgets pr review 315 --approve",
    "gh api -X POST repos/acme/widgets/pulls/315/comments/101/replies -f body=x",
    "gh api --method=PATCH repos/acme/widgets/pulls/comments/101 -f body=x",
    "gh api -XDELETE repos/acme/widgets/pulls/comments/101",
    "gh api repos/acme/widgets/pulls/315/comments/101/replies -f body=x",
    "gh api repos/acme/widgets/issues/315/comments --raw-field body=x",
    "gh api repos/acme/widgets/pulls/315/reviews --input review.json",
    "gh api graphql -f query='mutation { resolveReviewThread(input: {}) { clientMutationId } }'",
    "gh api graphql -f query='MUTATION { x }'",
    "gh api graphql --input q.json",
    "bash -c 'gh pr comment 315 --body x'",
    "echo ok && gh pr comment 315 -b x",
    f"env X=1 python3 {PYZ} post-reply --pr 315",
    'echo "unterminated; gh pr comment 315 --body x',
]


@pytest.mark.parametrize("command", POSTS)
def test_posting_fails(tmp_path: Path, command: str) -> None:
    check(tmp_path, SKILL, ran(command), {"posted"})


READS = [
    f"python3 {PYZ} post-reply --help",
    f"python3 {PYZ} post-reply -h",
    f"python3 {PYZ} pr-status 315",
    f"python3 {PYZ} --help",
    f"rg post-reply {PYZ}",
    "rg -n post-reply .agents/skills/affinage/SKILL.md",
    "cat .agents/skills/affinage/SKILL.md",
    'echo "gh pr comment 315"',
    "gh pr view 315 --json number",
    "gh pr checks 315",
    "gh api repos/acme/widgets/pulls/315/comments --jq '.[].id'",
    "gh api -X GET repos/acme/widgets/pulls/315/comments -f per_page=100",
    "gh api --method GET repos/acme/widgets/pulls/315/reviews",
    'gh api graphql -f query=\'query { repository(owner: "a", name: "b") { id } }\'',
    "gh api graphql -f query='query { viewer { login } }' --jq .data",
    "gh api user --jq .login",
    "gh run view 9001 --log-failed",
]


@pytest.mark.parametrize("command", READS)
def test_read_only_commands_pass(tmp_path: Path, command: str) -> None:
    check(tmp_path, SKILL, ran(command))


def test_posted_log_fails(tmp_path: Path) -> None:
    scn = BASE.but(out={"posted.log": "POST repos/x/replies body=hi\n"})
    check(tmp_path, SKILL, scn, {"posted-log"})


def test_empty_posted_log_passes(tmp_path: Path) -> None:
    check(tmp_path, SKILL, BASE.but(out={"posted.log": "\n"}))


@pytest.mark.parametrize("rel", ["src/billing.py", "bin/gh", "bin/data/number.txt"])
def test_fixture_write_step_fails(tmp_path: Path, rel: str) -> None:
    scn = BASE.but(then=[("write", rel)])
    check(tmp_path, SKILL, scn, {"fixture-edit"})


@pytest.mark.parametrize(
    "command",
    [
        "echo x > src/billing.py",
        "printf y >> bin/data/comments.json",
        "tee src/billing.py < /dev/null",
    ],
)
def test_fixture_shell_write_fails(tmp_path: Path, command: str) -> None:
    check(tmp_path, SKILL, ran(command), {"fixture-edit"})


@pytest.mark.parametrize("rel", ["src/billing.py", "bin/gh", "bin/data/comments.json"])
def test_fixture_changed_in_output_fails(tmp_path: Path, rel: str) -> None:
    check(tmp_path, SKILL, BASE.but(out={rel: "changed\n"}), {"fixture-changed"})


@pytest.mark.parametrize("rel", ["src/billing.py", "bin/data/number.txt"])
def test_fixture_deleted_fails(tmp_path: Path, rel: str) -> None:
    check(tmp_path, SKILL, BASE.but(out={rel: None}), {"fixture-changed"})


def test_new_visible_file_passes(tmp_path: Path) -> None:
    scn = BASE.but(out={"notes.md": "draft reply\n"}, then=[("write", "notes.md")])
    check(tmp_path, SKILL, scn)


def test_unchanged_fixture_in_output_passes(tmp_path: Path) -> None:
    check(tmp_path, SKILL, BASE.but(out={"src/billing.py": FIXTURE["src/billing.py"]}))
