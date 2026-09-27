"""Offline checks for PR mining using a scripted fake `gh` binary."""

from __future__ import annotations

import json
import stat
from pathlib import Path
from typing import cast

import pytest

from agent_lab_mine import (
    _clean_prompt,  # pyright: ignore[reportPrivateUsage]
    make_check_task,
    mine_tasks,
    validate_mined_task,
)


HEAD_SHA_1 = "1" * 40
BASE_SHA_1 = "0" * 40
HEAD_SHA_3 = "3" * 40
BASE_SHA_3 = "2" * 40

ISSUE_BODY_1 = (
    "Calling widget.process([]) crashes with IndexError.\n\n"
    "```diff\n"
    "-    return items[0]\n"
    "+    return items[0] if items else []\n"
    "```\n\n"
    "Fix process() so empty input returns an empty list."
)

DIFF_1 = (
    "diff --git a/widgets/core.py b/widgets/core.py\n"
    "index abc123..def456 100644\n"
    "--- a/widgets/core.py\n"
    "+++ b/widgets/core.py\n"
    "@@ -1,3 +1,3 @@\n"
    " def process(items):\n"
    "-    return items[0]\n"
    "+    return items[0] if items else []\n"
    "diff --git a/tests/test_core.py b/tests/test_core.py\n"
    "index 111111..222222 100644\n"
    "--- a/tests/test_core.py\n"
    "+++ b/tests/test_core.py\n"
    "@@ -1,2 +1,5 @@\n"
    " def test_process_nonempty():\n"
    "     assert process([1]) == 1\n"
    "+\n"
    "+def test_process_empty():\n"
    "+    assert process([]) == []\n"
)

DIFF_3 = (
    "diff --git a/widgets/other.py b/widgets/other.py\n"
    "index 111..222 100644\n"
    "--- a/widgets/other.py\n"
    "+++ b/widgets/other.py\n"
    "@@ -1,1 +1,1 @@\n"
    "-old\n"
    "+new\n"
    "diff --git a/tests/test_other.py b/tests/test_other.py\n"
    "index 333..444 100644\n"
    "--- a/tests/test_other.py\n"
    "+++ b/tests/test_other.py\n"
    "@@ -1,1 +1,1 @@\n"
    "-pass\n"
    "+pass\n"
)

PR_LIST = [
    {
        "number": 1,
        "title": "fix: crash on empty input",
        "body": "See linked issue.",
        "mergeCommit": {"oid": HEAD_SHA_1},
        "baseRefOid": "unused",
        "headRefOid": "unused",
        "authorAssociation": "OWNER",
        "closingIssuesReferences": [
            {
                "id": "I_kwDOexample1",
                "number": 42,
                "repository": {"name": "widgets", "owner": {"login": "acme"}},
                "url": "https://github.com/acme/widgets/issues/42",
            }
        ],
        "files": [{"path": "widgets/core.py"}, {"path": "tests/test_core.py"}],
        "mergedAt": "2026-01-01T00:00:00Z",
    },
    {
        "number": 2,
        "title": "fix: typo in docs",
        "body": "Fixes a typo.",
        "mergeCommit": {"oid": "9" * 40},
        "baseRefOid": "unused",
        "headRefOid": "unused",
        "authorAssociation": "OWNER",
        "closingIssuesReferences": [],
        "files": [{"path": "docs/readme.md"}],
        "mergedAt": "2026-01-01T00:00:00Z",
    },
    {
        "number": 3,
        "title": "chore: bump deps",
        "body": "Bump deps.",
        "mergeCommit": {"oid": HEAD_SHA_3},
        "baseRefOid": "unused",
        "headRefOid": "unused",
        "authorAssociation": "OWNER",
        "closingIssuesReferences": [],
        "files": [{"path": "widgets/other.py"}, {"path": "tests/test_other.py"}],
        "mergedAt": "2026-01-01T00:00:00Z",
    },
]

FAKE_GH = '''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
argv = sys.argv[1:]
control = json.loads(Path(os.environ["FAKE_GH_CONTROL"]).read_text())
log = Path(control["log"])
with log.open("a") as handle:
    handle.write(json.dumps(argv) + "\\n")
if argv[:2] == ["pr", "list"]:
    print(json.dumps(control["pr_list"]))
    sys.exit(0)
if argv[0] == "api":
    sha = argv[1].rsplit("/", 1)[-1]
    parents = control["parents"].get(sha, [])
    print(json.dumps({"parents": [{"sha": parent} for parent in parents]}))
    sys.exit(0)
if argv[:2] == ["pr", "diff"]:
    number = argv[2]
    print(control["diffs"][number])
    sys.exit(0)
if argv[:2] == ["issue", "view"]:
    number = argv[2]
    print(json.dumps({"body": control["issue_bodies"][number]}))
    sys.exit(0)
print(f"no fake gh response for: {argv}", file=sys.stderr)
sys.exit(1)
'''


class FakeGh:
    """A scripted `gh` binary plus the invocation log it writes."""

    def __init__(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        *,
        pr_list: list[dict[str, object]] | None = None,
        parents: dict[str, list[str]] | None = None,
        diffs: dict[str, str] | None = None,
        issue_bodies: dict[str, str] | None = None,
    ) -> None:
        binary_dir = tmp_path / "bin"
        binary_dir.mkdir()
        self.binary: Path = binary_dir / "gh"
        _ = self.binary.write_text(FAKE_GH, encoding="utf-8")
        self.binary.chmod(self.binary.stat().st_mode | stat.S_IXUSR)
        self.log: Path = tmp_path / "gh_calls.jsonl"
        control = tmp_path / "gh_control.json"
        _ = control.write_text(
            json.dumps(
                {
                    "log": str(self.log),
                    "pr_list": pr_list if pr_list is not None else PR_LIST,
                    "parents": parents
                    if parents is not None
                    else {HEAD_SHA_1: [BASE_SHA_1], HEAD_SHA_3: [BASE_SHA_3]},
                    "diffs": diffs if diffs is not None else {"1": DIFF_1, "3": DIFF_3},
                    "issue_bodies": issue_bodies if issue_bodies is not None else {"42": ISSUE_BODY_1},
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.setenv("FAKE_GH_CONTROL", str(control))

    def calls(self) -> list[list[str]]:
        if not self.log.exists():
            return []
        return [
            cast(list[str], json.loads(line))
            for line in self.log.read_text(encoding="utf-8").splitlines()
            if line
        ]


def test_mine_tasks_filters_by_title_and_test_changes_then_gates_on_check_task(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeGh(tmp_path, monkeypatch)
    gated_ids_seen: list[set[str]] = []

    def fake_check_task(tasks_path: Path) -> set[str]:
        payload = cast(dict[str, object], json.loads(tasks_path.read_text(encoding="utf-8")))
        ids = {cast(str, task["id"]) for task in cast(list[dict[str, object]], payload["tasks"])}
        gated_ids_seen.append(ids)
        return ids

    tasks = mine_tasks(
        "acme/widgets", gh_bin=str(fake.binary), check_task=fake_check_task
    )

    assert len(tasks) == 1
    task = tasks[0]
    assert task["id"] == "acme-widgets-1"
    assert task["base_sha"] == BASE_SHA_1
    assert task["head_sha"] == HEAD_SHA_1
    assert len(cast(str, task["base_sha"])) == 40
    assert task["test_command"] == ["python3", "-m", "pytest", "tests/test_core.py", "-q"]
    assert "```" not in cast(str, task["prompt"])
    assert "return items[0] if items else []" not in cast(str, task["prompt"])
    assert "IndexError" in cast(str, task["prompt"])
    assert "def test_process_empty" in cast(str, task["test_patch"])
    assert "def process(items)" not in cast(str, task["test_patch"])
    assert task["reference_changed_lines"] == 2

    # PR #2 had no test-file changes and PR #3 was not a `fix:` PR; only PR #1
    # reaches the check_task gate.
    assert gated_ids_seen == [{"acme-widgets-1"}]

    calls = fake.calls()
    assert any(call[:2] == ["pr", "list"] for call in calls)
    assert any(call[:2] == ["pr", "diff"] and call[2] == "1" for call in calls)
    assert not any(call[:2] == ["pr", "diff"] and call[2] == "3" for call in calls)


def test_go_test_files_infer_a_go_test_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    head_sha = "4" * 40
    base_sha = "5" * 40
    diff = (
        "diff --git a/pkg/thing.go b/pkg/thing.go\n"
        "index 111..222 100644\n"
        "--- a/pkg/thing.go\n"
        "+++ b/pkg/thing.go\n"
        "@@ -1,1 +1,1 @@\n"
        "-old\n"
        "+new\n"
        "diff --git a/pkg/thing_test.go b/pkg/thing_test.go\n"
        "index 333..444 100644\n"
        "--- a/pkg/thing_test.go\n"
        "+++ b/pkg/thing_test.go\n"
        "@@ -1,1 +1,1 @@\n"
        "-pass\n"
        "+pass\n"
    )
    pr_list: list[dict[str, object]] = [
        {
            "number": 4,
            "title": "fix: data race in Compute",
            "body": "thing.go has a data race when two goroutines call Compute concurrently.",
            "mergeCommit": {"oid": head_sha},
            "baseRefOid": "unused",
            "headRefOid": "unused",
            "authorAssociation": "OWNER",
            "closingIssuesReferences": [],
            "files": [{"path": "pkg/thing.go"}, {"path": "pkg/thing_test.go"}],
            "mergedAt": "2026-01-01T00:00:00Z",
        }
    ]
    fake = FakeGh(
        tmp_path,
        monkeypatch,
        pr_list=pr_list,
        parents={head_sha: [base_sha]},
        diffs={"4": diff},
        issue_bodies={},
    )

    def fake_check_task(tasks_path: Path) -> set[str]:
        payload = cast(dict[str, object], json.loads(tasks_path.read_text(encoding="utf-8")))
        return {cast(str, task["id"]) for task in cast(list[dict[str, object]], payload["tasks"])}

    tasks = mine_tasks("acme/widgets", gh_bin=str(fake.binary), check_task=fake_check_task)
    assert len(tasks) == 1
    assert tasks[0]["test_command"] == ["go", "test", "./pkg"]


def test_check_task_fail_drops_the_task(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeGh(tmp_path, monkeypatch)

    def failing_check_task(_tasks_path: Path) -> set[str]:
        return set()

    tasks = mine_tasks("acme/widgets", gh_bin=str(fake.binary), check_task=failing_check_task)
    assert tasks == []


def test_clean_prompt_preserves_markdown_bullets_outside_fences() -> None:
    text = (
        "Widget crashes on empty input.\n\n"
        "- Steps to reproduce: call widget.process([])\n"
        "- Expected: an empty list\n"
    )
    cleaned = _clean_prompt(text)
    assert "Steps to reproduce: call widget.process([])" in cleaned
    assert "Expected: an empty list" in cleaned


def test_untrusted_author_pr_is_dropped_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pr_list: list[dict[str, object]] = [dict(PR_LIST[0], authorAssociation="NONE")]
    fake = FakeGh(tmp_path, monkeypatch, pr_list=pr_list)

    def fake_check_task(tasks_path: Path) -> set[str]:
        payload = cast(dict[str, object], json.loads(tasks_path.read_text(encoding="utf-8")))
        return {cast(str, task["id"]) for task in cast(list[dict[str, object]], payload["tasks"])}

    tasks = mine_tasks("acme/widgets", gh_bin=str(fake.binary), check_task=fake_check_task)
    assert tasks == []


def test_untrusted_author_pr_is_kept_when_explicitly_allowed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pr_list: list[dict[str, object]] = [dict(PR_LIST[0], authorAssociation="NONE")]
    fake = FakeGh(tmp_path, monkeypatch, pr_list=pr_list)

    def fake_check_task(tasks_path: Path) -> set[str]:
        payload = cast(dict[str, object], json.loads(tasks_path.read_text(encoding="utf-8")))
        return {cast(str, task["id"]) for task in cast(list[dict[str, object]], payload["tasks"])}

    tasks = mine_tasks(
        "acme/widgets",
        gh_bin=str(fake.binary),
        check_task=fake_check_task,
        allow_untrusted_authors=True,
    )
    assert len(tasks) == 1
    assert tasks[0]["id"] == "acme-widgets-1"


def test_cross_repo_linked_issue_is_ignored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pr: dict[str, object] = dict(PR_LIST[0])
    pr["closingIssuesReferences"] = [
        {
            "id": "I_kwDOexample2",
            "number": 7,
            "repository": {"name": "other", "owner": {"login": "acme"}},
            "url": "https://github.com/acme/other/issues/7",
        }
    ]
    fake = FakeGh(tmp_path, monkeypatch, pr_list=[pr], issue_bodies={})

    def fake_check_task(tasks_path: Path) -> set[str]:
        payload = cast(dict[str, object], json.loads(tasks_path.read_text(encoding="utf-8")))
        return {cast(str, task["id"]) for task in cast(list[dict[str, object]], payload["tasks"])}

    tasks = mine_tasks("acme/widgets", gh_bin=str(fake.binary), check_task=fake_check_task)
    assert len(tasks) == 1
    assert tasks[0]["prompt"] == "See linked issue."
    assert not any(call[:2] == ["issue", "view"] for call in fake.calls())


def test_linked_issue_lookup_failure_falls_back_to_pr_body(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeGh(tmp_path, monkeypatch, issue_bodies={})

    def fake_check_task(tasks_path: Path) -> set[str]:
        payload = cast(dict[str, object], json.loads(tasks_path.read_text(encoding="utf-8")))
        return {cast(str, task["id"]) for task in cast(list[dict[str, object]], payload["tasks"])}

    tasks = mine_tasks("acme/widgets", gh_bin=str(fake.binary), check_task=fake_check_task)
    assert len(tasks) == 1
    assert tasks[0]["prompt"] == "See linked issue."


def test_pr_build_failure_is_dropped_without_aborting_the_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    broken_pr: dict[str, object] = dict(
        PR_LIST[0],
        number=5,
        title="fix: something else",
        body="Body",
        mergeCommit={"oid": "6" * 40},
        closingIssuesReferences=[],
        files=[{"path": "widgets/x.py"}, {"path": "tests/test_x.py"}],
    )
    pr_list: list[dict[str, object]] = [cast(dict[str, object], PR_LIST[0]), broken_pr]
    fake = FakeGh(tmp_path, monkeypatch, pr_list=pr_list)

    def fake_check_task(tasks_path: Path) -> set[str]:
        payload = cast(dict[str, object], json.loads(tasks_path.read_text(encoding="utf-8")))
        return {cast(str, task["id"]) for task in cast(list[dict[str, object]], payload["tasks"])}

    drops: list[tuple[int, str]] = []
    tasks = mine_tasks(
        "acme/widgets", gh_bin=str(fake.binary), check_task=fake_check_task, drops=drops
    )

    assert len(tasks) == 1
    assert tasks[0]["id"] == "acme-widgets-1"
    assert any(number == 5 for number, _reason in drops)


def test_make_check_task_raises_when_script_missing(tmp_path: Path) -> None:
    tilth_root = tmp_path / "tilth"
    tilth_root.mkdir()
    with pytest.raises(RuntimeError, match="check_task.py"):
        _ = make_check_task(tilth_root)


def test_make_check_task_raises_when_the_gate_crashes_silently(
    tmp_path: Path,
) -> None:
    tilth_root = tmp_path / "tilth"
    benchmark_dir = tilth_root / "benchmark"
    benchmark_dir.mkdir(parents=True)
    fake_check_task = benchmark_dir / "check_task.py"
    script = "import sys\nprint('boom', file=sys.stderr)\nsys.exit(1)\n"
    _ = fake_check_task.write_text(script, encoding="utf-8")
    tasks_path = tmp_path / "candidates.json"
    _ = tasks_path.write_text(json.dumps({"version": 1, "tasks": []}), encoding="utf-8")

    check_task = make_check_task(tilth_root)
    with pytest.raises(RuntimeError, match="exited 1"):
        _ = check_task(tasks_path)


def test_make_check_task_parses_pass_and_fail_lines(tmp_path: Path) -> None:
    tilth_root = tmp_path / "tilth"
    benchmark_dir = tilth_root / "benchmark"
    benchmark_dir.mkdir(parents=True)
    fake_check_task = benchmark_dir / "check_task.py"
    script = (
        "import argparse, sys\n"
        "parser = argparse.ArgumentParser()\n"
        "parser.add_argument('--tasks-json')\n"
        "args = parser.parse_args()\n"
        "print('PASS good-task: baseline passed; mutation failed')\n"
        "print('FAIL bad-task: baseline did not fail')\n"
    )
    _ = fake_check_task.write_text(script, encoding="utf-8")
    tasks_path = tmp_path / "candidates.json"
    _ = tasks_path.write_text(json.dumps({"version": 1, "tasks": []}), encoding="utf-8")

    check_task = make_check_task(tilth_root)
    assert check_task(tasks_path) == {"good-task"}


def test_validate_mined_task_accepts_a_well_formed_task() -> None:
    task: dict[str, object] = {
        "id": "acme-widgets-1",
        "family": "acme-widgets-1",
        "split": "train",
        "capability": "fix",
        "prompt": "Fix the bug.",
        "test_command": ["python3", "-m", "pytest", "tests/test_core.py", "-q"],
        "repo_url": "https://github.com/acme/widgets",
        "base_sha": "0" * 40,
        "head_sha": "1" * 40,
        "test_patch": "diff --git a/tests/test_core.py b/tests/test_core.py\n",
        "reference_changed_lines": 2,
    }
    validate_mined_task(task)


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("split", "nope", "split"),
        ("base_sha", "short", "base_sha"),
        ("head_sha", "z" * 40, "head_sha"),
        ("test_command", [], "test_command"),
        ("test_patch", "", "test_patch"),
        ("reference_changed_lines", -1, "reference_changed_lines"),
    ],
)
def test_validate_mined_task_rejects_bad_fields(field: str, value: object, match: str) -> None:
    task: dict[str, object] = {
        "id": "acme-widgets-1",
        "family": "acme-widgets-1",
        "split": "train",
        "capability": "fix",
        "prompt": "Fix the bug.",
        "test_command": ["python3", "-m", "pytest", "tests/test_core.py", "-q"],
        "repo_url": "https://github.com/acme/widgets",
        "base_sha": "0" * 40,
        "head_sha": "1" * 40,
        "test_patch": "diff --git a/tests/test_core.py b/tests/test_core.py\n",
        "reference_changed_lines": 2,
    }
    task[field] = value
    with pytest.raises(ValueError, match=match):
        validate_mined_task(task)
