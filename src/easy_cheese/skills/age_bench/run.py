"""Drive a case's review unattended via a headless review invocation.

``run`` orchestrates prepare -> headless review -> judge for one (tool,
case) pair. Availability of a headless review invocation is probed by
looking for a ``claude`` executable on PATH that accepts ``-p``; when found,
it is invoked in the prepared worktree to capture a report, which is then
handed to the existing judge path. When no such executable is available (or
the fixed probe otherwise cannot be satisfied), this exits non-zero with a
message naming the missing capability, leaving prepare-plus-judge usable on
its own either way.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

from easy_cheese.shared import cli
from easy_cheese.skills.age_bench.judge import (
    JudgeResult,
    JudgeTransport,
    default_transport,
    judge_report,
    recorded_transport,
)
from easy_cheese.skills.age_bench.prepare import prepare_worktree

HEADLESS_EXECUTABLE = "claude"
HEADLESS_TIMEOUT_SECONDS = 300


class HeadlessUnavailableError(Exception):
    """Raised when no headless review invocation is available, naming why."""


def _prompt_for(tool: str) -> str:
    command = "/age" if tool == "age" else "/code-review"
    return f"Run {command} on the current worktree and report your findings."


def _probe_headless_executable() -> str:
    path = shutil.which(HEADLESS_EXECUTABLE)
    if path is None:
        raise HeadlessUnavailableError(
            f"no headless review invocation is available: {HEADLESS_EXECUTABLE!r} "
            "executable not found on PATH"
        )
    return path


def _capture_report(executable: str, *, tool: str, cwd: Path) -> str:
    try:
        result = subprocess.run(
            [executable, "-p", _prompt_for(tool)],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=HEADLESS_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise HeadlessUnavailableError(
            f"headless review invocation timed out after {HEADLESS_TIMEOUT_SECONDS}s: "
            f"{executable} -p did not return"
        ) from exc
    if result.returncode != 0:
        raise HeadlessUnavailableError(
            f"headless review invocation failed: {executable} -p exited "
            f"{result.returncode}: {result.stderr.strip()}"
        )
    report_text = result.stdout
    if not report_text.strip():
        raise HeadlessUnavailableError(
            f"headless review invocation produced no capturable report: {executable} -p "
            "emitted no output"
        )
    return report_text


def run_case(
    *,
    tool: str,
    case_id: str,
    repo_root: Path | str | None = None,
    transport_fixture: Path | str | None = None,
) -> JudgeResult:
    executable = _probe_headless_executable()
    prepared = prepare_worktree(case_id, repo_root=repo_root)
    try:
        report_text = _capture_report(executable, tool=tool, cwd=prepared.worktree_dir)
    finally:
        subprocess.run(
            ["git", "worktree", "remove", "-f", str(prepared.worktree_dir)],
            cwd=prepared.scratch_dir / "repo",
            capture_output=True,
            text=True,
        )
        shutil.rmtree(prepared.scratch_dir, ignore_errors=True)
    transport: JudgeTransport = (
        recorded_transport(Path(transport_fixture))
        if transport_fixture is not None
        else default_transport
    )
    return judge_report(
        tool=tool,
        case_id=case_id,
        report_text=report_text,
        transport=transport,
        repo_root=repo_root,
    )


def _cmd_run(args: argparse.Namespace) -> int:
    try:
        result = run_case(
            tool=args.tool,
            case_id=args.case_id,
            repo_root=args.repo_root,
            transport_fixture=args.transport_fixture,
        )
    except Exception as exc:  # noqa: BLE001 - surfaced as a CliError below
        raise cli.CliError(str(exc)) from exc
    print(json.dumps(result.to_dict()), file=args.stdout)
    return 0


def _setup(parser: argparse.ArgumentParser) -> None:
    _ = parser.add_argument("--tool", required=True, choices=("age", "code-review"))
    _ = parser.add_argument("--case", dest="case_id", required=True)
    _ = parser.add_argument("--repo-root", dest="repo_root", default=None)
    _ = parser.add_argument("--transport-fixture", dest="transport_fixture", default=None)
    parser.set_defaults(func=_cmd_run)


def main(argv: list[str]) -> int:
    return cli.run(_setup, argv=argv)
