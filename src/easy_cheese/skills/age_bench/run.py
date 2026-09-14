"""Drive a case's review unattended via a headless review invocation.

``run`` orchestrates prepare -> headless review -> judge for one (tool,
case) pair. Availability of a headless review invocation is probed by
looking for an executable named ``claude`` on PATH; when found, it is
invoked in the prepared worktree to capture a report, which is then
handed to the existing judge path. When no such executable is available (or
the fixed probe otherwise cannot be satisfied), this exits non-zero with a
message naming the missing capability, leaving prepare-plus-judge usable on
its own either way.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import TextIO, cast

from easy_cheese.shared import cli
from easy_cheese.shared.findings import parse_findings_report
from easy_cheese.skills.age_bench import scoreboard
from easy_cheese.skills.age_bench.errors import AgeBenchError
from easy_cheese.skills.age_bench.judge import JudgeResult, judge_report, transport_for
from easy_cheese.skills.age_bench.prepare import PreparedWorktree, prepare_worktree

HEADLESS_EXECUTABLE = "claude"
HEADLESS_TIMEOUT_SECONDS = 300
# Read-only: the harness never needs to mutate the worktree it is grading.
HEADLESS_ALLOWED_TOOLS = "Read Grep Glob"
_REPORT_LINE_PREFIX = "Age report: "
_CAPTURE_TRUNCATE = 2000


class HeadlessUnavailableError(AgeBenchError):
    """Raised when no headless review invocation is available, naming why."""


def _prompt_for(tool: str) -> str:
    command = "/age" if tool == "age" else "/code-review"
    return f"Run {command} on the current worktree and report your findings."


def _probe_headless_executable() -> str:
    path = shutil.which(HEADLESS_EXECUTABLE)
    if path is None:
        raise HeadlessUnavailableError(
            f"no headless review invocation is available: {HEADLESS_EXECUTABLE!r} "
            + "executable not found on PATH"
        )
    return path


def _truncated(text: str) -> str:
    text = text.strip()
    if len(text) <= _CAPTURE_TRUNCATE:
        return text
    return text[:_CAPTURE_TRUNCATE] + "..."


def _report_path_from_stdout(stdout: str, *, cwd: Path) -> Path | None:
    """Return the report path `/age` (or `/code-review`) printed, if any."""
    for line in reversed(stdout.splitlines()):
        stripped = line.strip()
        if stripped.startswith(_REPORT_LINE_PREFIX):
            candidate = Path(stripped.removeprefix(_REPORT_LINE_PREFIX))
            return candidate if candidate.is_absolute() else cwd / candidate
    return None


def _capture_report(executable: str, *, tool: str, cwd: Path) -> str:
    try:
        result = subprocess.run(
            [
                executable,
                "-p",
                _prompt_for(tool),
                "--allowedTools",
                HEADLESS_ALLOWED_TOOLS,
            ],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=HEADLESS_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = _truncated(cast("str | None", exc.stdout) or "")
        stderr = _truncated(cast("str | None", exc.stderr) or "")
        raise HeadlessUnavailableError(
            f"headless review invocation timed out after {HEADLESS_TIMEOUT_SECONDS}s: "
            + f"{executable} -p did not return (stdout={stdout!r} stderr={stderr!r})"
        ) from exc
    if result.returncode != 0:
        raise HeadlessUnavailableError(
            f"headless review invocation failed: {executable} -p exited "
            + f"{result.returncode}: {result.stderr.strip()}"
        )
    stdout_text = result.stdout
    if not stdout_text.strip():
        raise HeadlessUnavailableError(
            f"headless review invocation produced no capturable report: {executable} -p "
            + f"emitted no output (stderr={_truncated(result.stderr)!r})"
        )
    report_path = _report_path_from_stdout(stdout_text, cwd=cwd)
    report_text = stdout_text
    if report_path is not None and report_path.is_file():
        report_text = report_path.read_text(encoding="utf-8")
    if not parse_findings_report(report_text):
        raise HeadlessUnavailableError(
            "headless review invocation produced a report with no parseable findings: "
            + f"{executable} -p report had no findings (stdout={_truncated(stdout_text)!r})"
        )
    return report_text


def run_case(
    *,
    tool: str,
    case_id: str,
    repo_root: Path | str | None = None,
    transport_fixture: Path | str | None = None,
    run_id: str | None = None,
    prepared: PreparedWorktree | None = None,
) -> JudgeResult:
    executable = _probe_headless_executable()
    owns_prepared = prepared is None
    phase_start = time.monotonic()
    if prepared is None:
        prepared = prepare_worktree(case_id, repo_root=repo_root)
    print(
        f"[{tool}/{case_id}] prepare finished in {time.monotonic() - phase_start:.1f}s",
        file=sys.stderr,
    )
    try:
        phase_start = time.monotonic()
        report_text = _capture_report(executable, tool=tool, cwd=prepared.worktree_dir)
        print(
            f"[{tool}/{case_id}] headless review finished in {time.monotonic() - phase_start:.1f}s",
            file=sys.stderr,
        )
    finally:
        if owns_prepared:
            prepared.cleanup()
    phase_start = time.monotonic()
    transport = transport_for(
        str(transport_fixture) if transport_fixture is not None else None
    )
    result = judge_report(
        tool=tool,
        case_id=case_id,
        report_text=report_text,
        transport=transport,
        run_id=run_id,
        repo_root=repo_root,
    )
    print(
        f"[{tool}/{case_id}] judge finished in {time.monotonic() - phase_start:.1f}s",
        file=sys.stderr,
    )
    return result


def _cmd_run(args: argparse.Namespace) -> int:
    stdout = cast("TextIO | None", args.stdout)
    run_id = cast("str | None", args.run_id)
    json_mode = cast(bool, args.json_mode)
    result = run_case(
        tool=cast(str, args.tool),
        case_id=cast(str, args.case_id),
        repo_root=cast("str | None", args.repo_root),
        transport_fixture=cast("str | None", args.transport_fixture),
        run_id=run_id,
    )
    if run_id:
        _ = scoreboard.write_result(run_id, cast(str, args.tool), result.to_dict())
    cli.emit(result.to_dict(), json_mode=json_mode, stdout=stdout)
    return 0


def _setup(parser: argparse.ArgumentParser) -> None:
    _ = parser.add_argument("--tool", required=True, choices=("age", "code-review"))
    _ = parser.add_argument("--case", dest="case_id", required=True)
    _ = parser.add_argument("--repo-root", dest="repo_root", default=None)
    _ = parser.add_argument(
        "--transport-fixture", dest="transport_fixture", default=None
    )
    _ = parser.add_argument("--run-id", dest="run_id", default=None)
    parser.set_defaults(func=_cmd_run)


def main(argv: list[str]) -> int:
    return cli.run(_setup, argv=argv)
