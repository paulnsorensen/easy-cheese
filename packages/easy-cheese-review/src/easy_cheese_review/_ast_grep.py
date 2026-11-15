"""Run the ast-grep binary against the packaged rule configuration.

Every call passes `-c` with the packaged `sgconfig.yml`, so a config file or a
rule file in the scanned tree never takes effect. Paths go after `--`, so a
path that starts with `-` is never read as an option.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Generator, Sequence
from contextlib import contextmanager
from importlib import resources
from pathlib import Path
from typing import cast

JsonObject = dict[str, object]

_TIMEOUT_SECONDS = 120


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


def _run(binary: str, args: Sequence[str], cwd: Path) -> list[JsonObject]:
    try:
        completed = subprocess.run(
            [binary, *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise AstGrepError("timeout") from None
    except OSError:
        raise AstGrepError("exec-error") from None
    if completed.returncode != 0:
        raise AstGrepError(f"exit-{completed.returncode}")
    rows: list[JsonObject] = []
    for line in completed.stdout.splitlines():
        if not line.strip():
            continue
        try:
            row = cast(object, json.loads(line))
        except json.JSONDecodeError:
            raise AstGrepError("bad-json") from None
        if not isinstance(row, dict):
            raise AstGrepError("bad-json")
        rows.append(cast(JsonObject, row))
    return rows


def scan(binary: str, config: Path, cwd: Path, paths: Sequence[str]) -> list[JsonObject]:
    """Run the packaged rules over `paths` and return one JSON object per hit."""
    if not paths:
        return []
    args = ["scan", "-c", str(config), "--json=stream", "--include-metadata", "--", *paths]
    return _run(binary, args, cwd)


def imports(binary: str, config: Path, cwd: Path, paths: Sequence[str]) -> dict[str, list[str]]:
    """Return the full text of every import statement, grouped by path.

    A path may be a directory; the result keys are file paths relative to `cwd`.
    """
    if not paths:
        return {}
    query = (resources.files(__package__) / "queries" / "imports.yml").read_text(encoding="utf-8")
    args = ["scan", "-c", str(config), "--inline-rules", query, "--json=stream", "--", *paths]
    found: dict[str, list[str]] = {}
    for row in _run(binary, args, cwd):
        rule_id = row.get("ruleId")
        path = row.get("file")
        text = row.get("text")
        if isinstance(rule_id, str) and rule_id.startswith("import-") and isinstance(path, str) and isinstance(text, str):
            found.setdefault(path.removeprefix("./"), []).append(text)
    return found


def outline(
    binary: str, config: Path, cwd: Path, paths: Sequence[str], items: str
) -> dict[str, list[JsonObject]]:
    """Return the outline items (`exports` or `imports`) for each path."""
    if not paths:
        return {}
    args = ["-c", str(config), "outline", "--items", items, "--json=stream", "--", *paths]
    found: dict[str, list[JsonObject]] = {path: [] for path in paths}
    for row in _run(binary, args, cwd):
        path = row.get("path")
        entries = row.get("items")
        if isinstance(path, str) and isinstance(entries, list):
            found[path] = [
                cast(JsonObject, item)
                for item in cast(list[object], entries)
                if isinstance(item, dict)
            ]
    return found
