"""Run the ast-grep binary against the packaged rule configuration.

Every call passes `-c` with the packaged `sgconfig.yml`, so a config file or a
rule file in the scanned tree never takes effect. Paths go after `--`, so a
path that starts with `-` is never read as an option.
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import threading
from collections.abc import Generator, Iterator, Sequence
from contextlib import contextmanager, suppress
from importlib import resources
from pathlib import Path
from typing import IO, cast

JsonObject = dict[str, object]

_TIMEOUT_SECONDS = 120
# Path bytes per run. Each run stays far below the OS argument limit (ARG_MAX
# is 256 KiB on macOS and 2 MiB on Linux, and includes the environment).
_ARG_BYTE_BUDGET = 128 * 1024


class AstGrepError(RuntimeError):
    """An ast-grep run failed; the message is a short reason token."""


def find_binary(name: str | None) -> str | None:
    """Return the ast-grep executable path, or None when it is not on PATH."""
    return shutil.which(name or "ast-grep")


@contextmanager
def packaged_config() -> Generator[Path, None, None]:
    """Yield a file-system path to the packaged `rules/sgconfig.yml`."""
    with resources.as_file(resources.files(__package__) / "rules") as rules:
        yield rules / "sgconfig.yml"


def _kill(proc: subprocess.Popen[str]) -> None:
    """Stop the run and any child it started."""
    if proc.poll() is not None:
        return
    # The run can exit between the poll and the kill; that race is not an error.
    with suppress(OSError):
        if hasattr(os, "killpg"):
            os.killpg(proc.pid, signal.SIGKILL)
        else:
            proc.kill()


def _rows(binary: str, args: Sequence[str], cwd: Path) -> Iterator[JsonObject]:
    """Yield one JSON object per stdout line while ast-grep runs.

    The timeout bounds the whole run, also while the stream stays open. A failure
    raises after the stream ends, so a non-zero exit wins over bad JSON.
    """
    try:
        proc = subprocess.Popen(
            [binary, *args],
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            start_new_session=True,
        )
    except OSError:
        raise AstGrepError("exec-error") from None
    timed_out = threading.Event()

    def expire() -> None:
        timed_out.set()
        _kill(proc)

    timer = threading.Timer(_TIMEOUT_SECONDS, expire)
    timer.start()
    bad_json = False
    returncode = 0
    try:
        for line in cast(IO[str], proc.stdout):
            if bad_json or not line.strip():
                continue
            try:
                row = cast(object, json.loads(line))
            except json.JSONDecodeError:
                bad_json = True
                continue
            if isinstance(row, dict):
                yield cast(JsonObject, row)
            else:
                bad_json = True
        returncode = proc.wait()
    finally:
        _kill(proc)
        _ = proc.wait()
        timer.cancel()
        cast(IO[str], proc.stdout).close()
    if timed_out.is_set():
        raise AstGrepError("timeout")
    if returncode != 0:
        raise AstGrepError(f"exit-{returncode}")
    if bad_json:
        raise AstGrepError("bad-json")


def _batches(paths: Sequence[str]) -> Iterator[list[str]]:
    """Split `paths` into batches whose path bytes stay within the budget.

    A path larger than the budget goes alone. Input order is kept.
    """
    batch: list[str] = []
    size = 0
    for path in paths:
        cost = len(os.fsencode(path)) + 1
        if batch and size + cost > _ARG_BYTE_BUDGET:
            yield batch
            batch, size = [], 0
        batch.append(path)
        size += cost
    if batch:
        yield batch


def _batch_rows(
    binary: str, args: Sequence[str], cwd: Path, paths: Sequence[str]
) -> Iterator[JsonObject]:
    """Run `args` once per batch of `paths` and yield each row.

    Each batch goes after `--`, so a path is never read as an option.
    """
    for batch in _batches(paths):
        yield from _rows(binary, [*args, "--", *batch], cwd)


def scan(binary: str, config: Path, cwd: Path, paths: Sequence[str]) -> list[JsonObject]:
    """Run the packaged rules over `paths` and return one JSON object per hit."""
    args = ["scan", "-c", str(config), "--json=stream", "--include-metadata"]
    return list(_batch_rows(binary, args, cwd, paths))


def imports(binary: str, config: Path, cwd: Path, paths: Sequence[str]) -> dict[str, list[str]]:
    """Return the full text of every import statement, grouped by path.

    A path may be a directory; the result keys are file paths relative to `cwd`.
    The run keeps only the file and text of each row, never the whole row.
    """
    found: dict[str, list[str]] = {}
    if not paths:
        return found
    query = (resources.files(__package__) / "queries" / "imports.yml").read_text(encoding="utf-8")
    args = ["scan", "-c", str(config), "--inline-rules", query, "--json=stream"]
    for row in _batch_rows(binary, args, cwd, paths):
        rule_id = row.get("ruleId")
        path = row.get("file")
        text = row.get("text")
        if (
            isinstance(rule_id, str)
            and rule_id.startswith("import-")
            and isinstance(path, str)
            and isinstance(text, str)
        ):
            found.setdefault(path.removeprefix("./"), []).append(text)
    return found


def outline(
    binary: str, config: Path, cwd: Path, paths: Sequence[str], items: str
) -> dict[str, list[JsonObject]]:
    """Return the outline items (`exports` or `imports`) for each path."""
    found: dict[str, list[JsonObject]] = {path: [] for path in paths}
    args = ["-c", str(config), "outline", "--items", items, "--json=stream"]
    for row in _batch_rows(binary, args, cwd, paths):
        path = row.get("path")
        entries = row.get("items")
        if isinstance(path, str) and isinstance(entries, list):
            found[path] = [
                cast(JsonObject, item)
                for item in cast(list[object], entries)
                if isinstance(item, dict)
            ]
    return found
