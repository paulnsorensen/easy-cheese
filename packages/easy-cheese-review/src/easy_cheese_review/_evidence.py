"""Scan a change with the packaged rules and compute its review facts."""

from __future__ import annotations

import re
from collections.abc import Callable, Generator, Iterable, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import TypeVar, cast

import easy_cheese_review._ast_grep as _ast_grep
import easy_cheese_review._facts as _facts
from easy_cheese_review._model import FACT_NAMES, Evidence, Fact, Hit

LineRange = tuple[int, int]

_T = TypeVar("_T")

_HUNK = re.compile(r"^@@ -\d+(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
# git's C-style quoting: a named escape, or one byte as three octal digits.
_ESCAPE = re.compile(rb'\\([0-7]{3}|[abtnvfr"\\])')
_NAMED = {b"a": 7, b"b": 8, b"t": 9, b"n": 10, b"v": 11, b"f": 12, b"r": 13, b'"': 34, b"\\": 92}


def _unescape(match: re.Match[bytes]) -> bytes:
    token = match.group(1)
    return bytes([_NAMED[token] if len(token) == 1 else int(token, 8)])


def _diff_path(target: str) -> str:
    """Return the path of a `+++` header, without git's C-style quotes.

    The escapes are undone on the UTF-8 bytes, so a name works whether git
    writes non-ASCII bytes raw (`core.quotePath=false`) or as octal escapes.
    """
    if len(target) >= 2 and target[0] == target[-1] == '"':
        raw = _ESCAPE.sub(_unescape, target[1:-1].encode("utf-8", "surrogateescape"))
        target = raw.decode("utf-8", "surrogateescape")
    return target.removeprefix("b/")


def hunks_from_diff(diff: str) -> dict[str, list[LineRange]]:
    """Return the 1-based, inclusive head-side line ranges of a unified diff.

    A pure deletion hunk (`+n,0`) adds the lines on each side of the cut,
    `max(n, 1)` through `n + 1`, so a hit that the deletion creates survives.
    A deleted file adds no entry. Hunk bodies are counted, so a body line
    never reads as a file header.
    """
    hunks: dict[str, list[LineRange]] = {}
    path: str | None = None
    old_left = new_left = 0
    for line in diff.splitlines():
        if old_left > 0 or new_left > 0:
            tag = line[:1]
            if tag == "+":
                new_left -= 1
            elif tag == "-":
                old_left -= 1
            elif tag != "\\":
                old_left -= 1
                new_left -= 1
            continue
        if line.startswith("+++ "):
            target = line[4:].split("\t", 1)[0]
            path = None if target == "/dev/null" else _diff_path(target)
            continue
        match = _HUNK.match(line)
        if match is None:
            continue
        old_left = 1 if match.group(1) is None else int(match.group(1))
        start = int(match.group(2))
        new_left = 1 if match.group(3) is None else int(match.group(3))
        if path is not None:
            span = (start, start + new_left - 1) if new_left else (max(start, 1), start + 1)
            hunks.setdefault(path, []).append(span)
    return hunks


def _require(binary: str | None) -> str:
    """Return the ast-grep path, or fail like a run when it is not on PATH."""
    if binary is None:
        raise _ast_grep.AstGrepError("ast-grep-missing")
    return binary


def _guarded(compute: Callable[[], _T]) -> _T | Fact:
    """Run one ast-grep step; a failure becomes an `unknown` fact with its reason."""
    try:
        return compute()
    except _ast_grep.AstGrepError as exc:
        return Fact("unknown", {"reason": f"ast-grep {exc}"})


def _compute_facts(
    binary: str | None, config: Path, head: Path, changed: Sequence[str], base: Path | None
) -> dict[str, Fact]:
    """Compute each fact on its own, so one failed ast-grep run spoils only its facts."""

    def imports(root: Path, paths: Sequence[str]) -> dict[str, list[str]]:
        return _ast_grep.imports(_require(binary), config, root, paths)

    def exports(root: Path, paths: Sequence[str]) -> dict[str, list[_ast_grep.JsonObject]]:
        return _ast_grep.outline(_require(binary), config, root, paths, "exports")

    code_paths = _facts.tree_files(head, changed, _facts.CODE_SUFFIXES)
    head_imports = _guarded(lambda: imports(head, code_paths))
    computed: dict[str, Fact] = {"tests": _facts.tests_fact(code_paths)}
    if isinstance(head_imports, Fact):
        computed["scope"] = head_imports
    else:
        computed["scope"] = _facts.scope_fact(code_paths, head_imports)
    if base is None:
        computed["compat"] = computed["dependencies"] = Fact("unknown", {"reason": "no base tree"})
    else:
        base_paths = _facts.tree_files(base, changed, _facts.CODE_SUFFIXES)
        computed["compat"] = _guarded(
            lambda: _facts.compat_fact(base_paths, exports(base, base_paths), exports(head, code_paths))
        )
        if isinstance(head_imports, Fact):
            computed["dependencies"] = head_imports
        else:
            computed["dependencies"] = _guarded(
                lambda: _facts.dependencies_fact(head, changed, head_imports, imports(base, ["."]))
            )
    return {name: computed[name] for name in FACT_NAMES}


@contextmanager
def _setup(
    changed: Iterable[str], ast_grep: str | None
) -> Generator[tuple[list[str], str | None, Path], None, None]:
    """Yield the checked changed paths, the ast-grep path or None, and the packaged config."""
    paths = _facts.normalize_changed(changed)
    with _ast_grep.packaged_config() as config:
        yield paths, _ast_grep.find_binary(ast_grep), config


def facts(
    head: Path,
    changed: Iterable[str],
    *,
    base: Path | None = None,
    ast_grep: str | None = None,
) -> dict[str, Fact]:
    """Return the compat, dependencies, tests, and scope facts for a change.

    A missing ast-grep binary fails like a failed ast-grep run: only the
    facts that need ast-grep (`compat`, `dependencies`, `scope`) are
    `unknown`, with the reason. `tests` needs no ast-grep and stays known.
    `compat` and `dependencies` are `unknown` when `base` is None.
    """
    with _setup(changed, ast_grep) as (paths, binary, config):
        return _compute_facts(binary, config, head, paths, base)


def _on_changed_lines(hit: Hit, hunks: Mapping[str, Sequence[LineRange]]) -> bool:
    """Return whether a hit overlaps a changed range; a file with no entry is changed in full."""
    ranges = hunks.get(hit.path)
    return ranges is None or any(hit.line <= end and start <= hit.end_line for start, end in ranges)


def _mapping(value: object) -> Mapping[str, object]:
    return cast(Mapping[str, object], value) if isinstance(value, dict) else {}


def _hit(row: Mapping[str, object]) -> Hit | None:
    metadata = _mapping(row.get("metadata"))
    span = _mapping(row.get("range"))
    rule_id, path, message = row.get("ruleId"), row.get("file"), row.get("message")
    dimension, base = metadata.get("dimension"), metadata.get("base")
    first, last = _mapping(span.get("start")).get("line"), _mapping(span.get("end")).get("line")
    if not (
        isinstance(rule_id, str)
        and isinstance(path, str)
        and isinstance(message, str)
        and isinstance(dimension, str)
        and isinstance(base, str)
        and isinstance(first, int)
        and isinstance(last, int)
    ):
        return None
    # ast-grep lines are 0-based; evidence lines are 1-based like a diff.
    return Hit(rule_id, dimension, base, path.removeprefix("./"), first + 1, last + 1, message)


def scan(
    head: Path,
    changed: Iterable[str],
    *,
    base: Path | None = None,
    hunks: Mapping[str, Sequence[LineRange]] | None = None,
    ast_grep: str | None = None,
) -> Evidence:
    """Run the packaged rule pack over the changed files of `head`.

    The rules load only through `-c` on the packaged config. When `hunks` is
    given, a hit survives only when its lines overlap a changed range of its
    file. A changed file with no entry in `hunks` counts as changed in full,
    so git output with no hunk for it (a binary diff) hides none of its hits.
    A failed hit scan, a missing ast-grep binary included, gives
    `failed:<reason>` and no hits; the facts are still computed as in `facts`.
    """
    with _setup(changed, ast_grep) as (paths, binary, config):
        code_paths = _facts.tree_files(head, paths, _facts.CODE_SUFFIXES)
        computed = _compute_facts(binary, config, head, paths, base)
        try:
            rows = _ast_grep.scan(_require(binary), config, head, code_paths)
        except _ast_grep.AstGrepError as exc:
            return Evidence(f"failed:{exc}", (), computed)
        hits = [hit for row in rows if (hit := _hit(row)) is not None]
        if hunks is not None:
            hits = [hit for hit in hits if _on_changed_lines(hit, hunks)]
        hits.sort(key=lambda hit: (hit.path, hit.line, hit.rule_id))
        return Evidence("ok", tuple(hits), computed)
