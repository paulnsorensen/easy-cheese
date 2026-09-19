"""Run a bounded OMP task-agent trace against a fixture repository."""

from __future__ import annotations

import argparse
import json
import os
import selectors
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

from tests.python.mold_cook_transcript_checker import (
    TranscriptCheckError,
    TranscriptReport,
    check_transcript,
)

MAX_RESPONSES = 32
MAX_RESPONSE_BYTES = 4096
MAX_TRACE_BYTES = 64 * 4096


class AgentScenarioError(RuntimeError):
    """The task agent did not produce a consumer-checkable trace."""


def _load_responses(path: Path) -> dict[str, str]:
    try:
        decoded = cast(object, json.loads(path.read_text(encoding="utf-8")))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AgentScenarioError(f"invalid harness responses: {exc}") from exc
    if not isinstance(decoded, Mapping):
        raise AgentScenarioError("harness responses must be a map")
    responses = cast(Mapping[str, object], decoded)
    if len(responses) > MAX_RESPONSES:
        raise AgentScenarioError("harness responses must contain at most 32 items")
    result: dict[str, str] = {}
    for key, response in responses.items():
        if not isinstance(response, str):
            raise AgentScenarioError("harness responses must contain string values")
        if len(key) > 128 or len(response.encode()) > MAX_RESPONSE_BYTES:
            raise AgentScenarioError("harness response exceeds its bound")
        result[key] = response
    return result


def _run_bounded(
    command: Sequence[str],
    *,
    cwd: Path,
    env: Mapping[str, str],
    timeout: float,
) -> tuple[int, bytes, bytes]:
    try:
        process = subprocess.Popen(
            list(command),
            cwd=cwd,
            env=dict(env),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as exc:
        raise AgentScenarioError(f"task agent failed to run: {exc}") from exc
    assert process.stdout is not None
    assert process.stderr is not None
    selector = selectors.DefaultSelector()
    _ = selector.register(process.stdout, selectors.EVENT_READ, "stdout")
    _ = selector.register(process.stderr, selectors.EVENT_READ, "stderr")
    streams: dict[str, bytearray] = {"stdout": bytearray(), "stderr": bytearray()}
    total = 0
    deadline = time.monotonic() + timeout
    try:
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                process.kill()
                _ = process.wait()
                raise AgentScenarioError("task agent exceeded its timeout")
            for key, _ in selector.select(remaining):
                chunk = os.read(key.fd, min(4096, MAX_TRACE_BYTES - total + 1))
                if not chunk:
                    _ = selector.unregister(key.fileobj)
                    continue
                total += len(chunk)
                if total > MAX_TRACE_BYTES:
                    process.kill()
                    _ = process.wait()
                    raise AgentScenarioError(
                        "task-agent trace exceeded the bounded size"
                    )
                streams[cast(str, key.data)].extend(chunk)
        returncode = process.wait(timeout=max(0.0, deadline - time.monotonic()))
    except subprocess.TimeoutExpired as exc:
        process.kill()
        _ = process.wait()
        raise AgentScenarioError("task agent exceeded its timeout") from exc
    finally:
        selector.close()
    return returncode, bytes(streams["stdout"]), bytes(streams["stderr"])


def run_agent_scenario(
    command: Sequence[str],
    *,
    fixture_repository: str | Path,
    mold_bundle: str | Path,
    cook_bundle: str | Path,
    responses: str | Path,
    output: str | Path,
    timeout: float = 300.0,
) -> TranscriptReport:
    """Execute an agent and require a structurally valid final transcript."""
    if not command:
        raise AgentScenarioError("an OMP task-agent command is required")
    repository = Path(fixture_repository).resolve()
    if not repository.is_dir():
        raise AgentScenarioError("fixture repository does not exist")
    mold = Path(mold_bundle).resolve()
    cook = Path(cook_bundle).resolve()
    if not mold.is_file() or not cook.is_file():
        raise AgentScenarioError("both generated skill bundles are required")
    harness_responses = _load_responses(Path(responses))
    environment = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", str(Path.home())),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "MOLD_COOK_FIXTURE_REPOSITORY": str(repository),
        "MOLD_COOK_MOLD_BUNDLE": str(mold),
        "MOLD_COOK_COOK_BUNDLE": str(cook),
        "MOLD_COOK_TEST_ROOT": str(Path(__file__).resolve().parents[2]),
        "MOLD_COOK_HARNESS_RESPONSES": json.dumps(harness_responses, sort_keys=True),
    }
    returncode, stdout, stderr = _run_bounded(
        command,
        cwd=repository,
        env=environment,
        timeout=timeout,
    )
    if returncode != 0:
        raise AgentScenarioError(
            f"task agent exited {returncode}: {stderr.decode(errors='replace')[-2000:]}"
        )
    try:
        decoded_trace = cast(object, json.loads(stdout.decode("utf-8")))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AgentScenarioError("task agent did not emit a JSON transcript") from exc
    if not isinstance(decoded_trace, Mapping):
        raise AgentScenarioError("task agent transcript must be an object")
    trace = cast(Mapping[str, object], decoded_trace)
    try:
        report = check_transcript(trace)
    except TranscriptCheckError as exc:
        raise AgentScenarioError(f"unsafe task-agent transcript: {exc}") from exc
    if not report.artifact_refs:
        raise AgentScenarioError("task-agent transcript has no consumer artifact")
    pointer = (repository / report.artifact_refs[-1]).resolve()
    if repository not in pointer.parents:
        raise AgentScenarioError("consumer artifact escapes the fixture repository")
    if not pointer.is_file():
        raise AgentScenarioError(
            "task-agent transcript names a pointer it did not create"
        )
    accepted_code, _accepted_stdout, accepted_stderr = _run_bounded(
        [
            sys.executable,
            str(cook),
            "accept",
            str(pointer),
            "--artifact-root",
            str(repository / "artifacts"),
        ],
        cwd=repository,
        env=environment,
        timeout=timeout,
    )
    if accepted_code != 0:
        raise AgentScenarioError(
            "task-agent artifact failed real Cook acceptance: "
            + accepted_stderr.decode(errors="replace")[-2000:]
        )
    destination = Path(output)
    _ = destination.parent.mkdir(parents=True, exist_ok=True)
    _ = destination.write_text(
        json.dumps(decoded_trace, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mold-cook-agent-driver")
    _ = parser.add_argument("--fixture-repository", required=True, type=Path)
    _ = parser.add_argument("--mold-bundle", required=True, type=Path)
    _ = parser.add_argument("--cook-bundle", required=True, type=Path)
    _ = parser.add_argument("--responses", required=True, type=Path)
    _ = parser.add_argument("--output", required=True, type=Path)
    _ = parser.add_argument("command", nargs="+")
    parsed = parser.parse_args(argv)
    command = cast(list[str], parsed.command)
    try:
        report = run_agent_scenario(
            command,
            fixture_repository=cast(Path, parsed.fixture_repository),
            mold_bundle=cast(Path, parsed.mold_bundle),
            cook_bundle=cast(Path, parsed.cook_bundle),
            responses=cast(Path, parsed.responses),
            output=cast(Path, parsed.output),
        )
    except AgentScenarioError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"scenario": report.scenario, "mode": report.mode}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
