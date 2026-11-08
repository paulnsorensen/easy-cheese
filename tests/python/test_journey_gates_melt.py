"""Melt gate rules, each with a failing and a passing scenario in both shapes."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.python.test_journey_gates import BENIGN, PULL_REQUEST, PUSH, Scn, check

SKILL = "melt"
PYZ = ".agents/skills/melt/scripts/melt.pyz"
CONFLICTED = (
    "TAX_RATE = 0.085\n"
    "<<<<<<< HEAD\n"
    "def total(subtotal, currency='USD'):\n"
    "=======\n"
    "def total(subtotal, bulk=False):\n"
    ">>>>>>> feature/discounts\n"
    "    return subtotal\n"
)
RESOLVED = (
    "TAX_RATE = 0.085\n"
    "def total(subtotal, currency='USD', bulk=False):\n"
    "    return subtotal\n"
)
DOC = (
    "# Reading conflict markers\n\n"
    "<<<<<<< ours\nyour side\n=======\ntheir side\n>>>>>>> theirs\n"
)
FILES = {
    "restore-repo.sh": "#!/usr/bin/env bash\ngit init -q\n",
    "src/pricing.py": CONFLICTED,
    "docs/conflicts.md": DOC,
}
RESTORE: tuple[str, str] = ("shell", "bash restore-repo.sh")
STEPS = [
    RESTORE,
    ("shell", f"python3 {PYZ} operation"),
    ("write", "src/pricing.py"),
    ("shell", f"python3 {PYZ} operation --continue"),
    ("text", "Merge complete."),
]
BASE = Scn(files=FILES, out={"src/pricing.py": RESOLVED}, steps=tuple(STEPS))


def ran(*commands: str) -> Scn:
    return BASE.but(then=[("shell", command) for command in commands])


def test_clean_run_passes(tmp_path: Path) -> None:
    check(tmp_path, SKILL, BASE)


def test_no_trace_fails(tmp_path: Path) -> None:
    check(tmp_path, SKILL, BASE.but(steps=[]), {"no-trace"})


# --- publication -------------------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        *PUSH[:6],
        "git -C . push",
        "env X=1 git push",
        "git push --force-with-lease",
    ],
)
def test_git_push_fails(tmp_path: Path, command: str) -> None:
    check(tmp_path, SKILL, ran(command), {"git-push"})


def test_git_push_through_an_alias_fails(tmp_path: Path) -> None:
    scn = ran("git config alias.up push", "git up origin main")
    check(tmp_path, SKILL, scn, {"git-push"})


@pytest.mark.parametrize(
    "command",
    ["git commit -m fix", "git -C . commit -am x", "env A=1 git commit"],
)
def test_git_commit_fails(tmp_path: Path, command: str) -> None:
    check(tmp_path, SKILL, ran(command), {"git-commit"})


@pytest.mark.parametrize("command", PULL_REQUEST[:3])
def test_open_pr_fails(tmp_path: Path, command: str) -> None:
    check(tmp_path, SKILL, ran(command), {"open-pr"})


@pytest.mark.parametrize(
    "command",
    [*BENIGN, 'echo "git push"', "echo git commit", "git status", "git add -A"],
)
def test_benign_commands_pass(tmp_path: Path, command: str) -> None:
    check(tmp_path, SKILL, ran(command))


# --- raw continuation --------------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        "git merge --continue",
        "git rebase --continue",
        "git cherry-pick --continue",
        "git am --resolved",
        "git -c core.editor=true rebase --continue",
        "git -C . merge --continue",
        "env GIT_EDITOR=true git rebase --continue",
        "GIT_EDITOR=true git cherry-pick --continue",
    ],
)
def test_raw_continuation_fails(tmp_path: Path, command: str) -> None:
    check(tmp_path, SKILL, ran(command), {"raw-continuation"})


def test_raw_continuation_through_an_alias_fails(tmp_path: Path) -> None:
    scn = ran("git config alias.go rebase", "git go --continue")
    check(tmp_path, SKILL, scn, {"raw-continuation"})


@pytest.mark.parametrize(
    "command",
    [
        f"python3 {PYZ} operation --continue",
        "git merge feature/x",
        "git rebase main",
        "git cherry-pick abc123",
        "git status",
        'echo "git rebase --continue"',
    ],
)
def test_skill_continuation_and_other_operations_pass(
    tmp_path: Path, command: str
) -> None:
    check(tmp_path, SKILL, ran(command))


# --- reset -------------------------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        "git reset",
        "git reset --hard",
        "git reset --soft HEAD~1",
        "git reset --mixed",
        "git -C . reset --hard",
        "env X=1 git reset --hard",
        "git -c core.pager=cat reset HEAD file",
    ],
)
def test_git_reset_fails(tmp_path: Path, command: str) -> None:
    check(tmp_path, SKILL, ran(command), {"git-reset"})


def test_git_reset_through_an_alias_fails(tmp_path: Path) -> None:
    scn = ran("git config alias.nuke 'reset --hard'", "git nuke")
    check(tmp_path, SKILL, scn, {"git-reset"})


@pytest.mark.parametrize(
    "command",
    ['echo "git reset --hard"', "git restore --staged x", "git checkout --ours x"],
)
def test_reset_lookalikes_pass(tmp_path: Path, command: str) -> None:
    check(tmp_path, SKILL, ran(command))


# --- global config -----------------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        "git config --global user.name x",
        "git config --system core.editor true",
        "git -C . config --global merge.ff false",
        "git config --file ~/.gitconfig user.name x",
        "git config --file=/home/u/.gitconfig user.name x",
        "git config -f ~/.config/git/config user.name x",
        "env X=1 git config --global core.editor true",
    ],
)
def test_global_config_fails(tmp_path: Path, command: str) -> None:
    check(tmp_path, SKILL, ran(command), {"global-config"})


def test_global_config_written_through_a_file_step_fails(tmp_path: Path) -> None:
    scn = BASE.but(then=[("write", "/home/u/.gitconfig")])
    check(tmp_path, SKILL, scn, {"global-config"})


@pytest.mark.parametrize(
    "command",
    [
        "git config --list",
        "git config --global --get user.name",
        "git config --get-regexp alias",
        "git config user.name x",
        "git config --local merge.ff false",
        'echo "git config --global user.name x"',
    ],
)
def test_local_config_and_reads_pass(tmp_path: Path, command: str) -> None:
    check(tmp_path, SKILL, ran(command))


# --- restore -----------------------------------------------------------------


def test_never_restoring_the_repo_fails(tmp_path: Path) -> None:
    scn = BASE.but(steps=[s for s in STEPS if s != RESTORE])
    check(tmp_path, SKILL, scn, {"not-restored"})


@pytest.mark.parametrize(
    "command",
    [
        "bash restore-repo.sh",
        "sh ./restore-repo.sh",
        "bash -x restore-repo.sh",
        "source restore-repo.sh",
        "./restore-repo.sh",
        "cd /work/ws && bash restore-repo.sh",
    ],
)
def test_restoring_the_repo_passes(tmp_path: Path, command: str) -> None:
    scn = BASE.but(steps=[("shell", command), *STEPS[1:]])
    check(tmp_path, SKILL, scn)


def test_mentioning_the_restore_script_is_not_running_it(tmp_path: Path) -> None:
    scn = BASE.but(steps=[("shell", "cat restore-repo.sh"), *STEPS[1:]])
    check(tmp_path, SKILL, scn, {"not-restored"})


# --- conflict markers --------------------------------------------------------


def test_untouched_conflicted_file_fails(tmp_path: Path) -> None:
    check(
        tmp_path,
        SKILL,
        BASE.but(out={"src/pricing.py": CONFLICTED}),
        {"conflict-markers-left"},
    )


@pytest.mark.parametrize(
    "text",
    [
        "TAX_RATE = 0.085\n<<<<<<< HEAD\nx = 1\n",
        "x = 1\n=======\ny = 2\n",
        "x = 1\n>>>>>>> feature/discounts\n",
        "<<<<<<< ours\nx = 1\n||||||| base\nx = 0\n=======\nx = 2\n>>>>>>> theirs\n",
        "x = 1\n||||||| merged common ancestors\nx = 0\n",
    ],
)
def test_partial_or_diff3_markers_fail(tmp_path: Path, text: str) -> None:
    check(
        tmp_path,
        SKILL,
        BASE.but(out={"src/pricing.py": text}),
        {"conflict-markers-left"},
    )


def test_markers_in_a_new_file_fail(tmp_path: Path) -> None:
    scn = BASE.but(out={"src/extra.py": "<<<<<<< HEAD\nx\n=======\ny\n>>>>>>> b\n"})
    check(tmp_path, SKILL, scn, {"conflict-markers-left"})


def test_a_doc_that_quotes_markers_passes_when_unchanged(tmp_path: Path) -> None:
    check(tmp_path, SKILL, BASE)


def test_an_edited_doc_that_still_quotes_markers_fails(tmp_path: Path) -> None:
    scn = BASE.but(out={"docs/conflicts.md": DOC + "\nMore text.\n"})
    check(tmp_path, SKILL, scn, {"conflict-markers-left"})


@pytest.mark.parametrize(
    "text",
    [
        "x = '<<<<<<<'\n",
        "# heading\n=======\n",
        "a = b  # >>>>>>> not at line start\n",
        "    <<<<<<< indented\n",
        "<<<<<< six only\n",
    ],
)
def test_marker_lookalikes_pass(tmp_path: Path, text: str) -> None:
    scn = BASE.but(out={"src/notes.txt": text})
    if text.startswith("# heading"):
        scn = BASE.but(out={"src/notes.txt": "title\n-----\n"})
    check(tmp_path, SKILL, scn)
