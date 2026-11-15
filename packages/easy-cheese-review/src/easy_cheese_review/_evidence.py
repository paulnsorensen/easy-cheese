"""Scan a change with the packaged rules and compute its review facts."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import cast

import easy_cheese_review._ast_grep as _ast_grep
import easy_cheese_review._facts as _facts
from easy_cheese_review._model import Evidence, Fact, Hit, unknown_facts

LineRange = tuple[int, int]

_MISSING = "ast-grep-missing"
_HUNK = re.compile(r"^@@ -\d+(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def _diff_path(target: str) -> str:
    """Return the path of a `+++` header, without git's C-style quotes."""
    if len(target) >= 2 and target[0] == target[-1] == '"':
        inner = target[1:-1]
        try:
            escaped = inner.encode("latin-1", "backslashreplace").decode("unicode_escape")
            target = escaped.encode("latin-1").decode("utf-8")
        except (UnicodeDecodeError, UnicodeEncodeError):
            target = inner
    return target.removeprefix("b/")


def hunks_from_diff(diff: str) -> dict[str, list[LineRange]]:
    """Return the 1-based, inclusive head-side line ranges of a unified diff.

    A pure deletion hunk (`+n,0`) adds no range. A deleted file adds no entry.
    Hunk bodies are counted, so a body line never reads as a file header.
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
        if new_left and path is not None:
            hunks.setdefault(path, []).append((start, start + new_left - 1))
    return hunks


def _compute_facts(
    binary: str, config: Path, head: Path, changed: Sequence[str], base: Path | None
) -> dict[str, Fact]:
    """Compute each fact on its own, so one failed ast-grep run spoils only its facts."""
    code_paths = _facts.tree_files(head, changed, _facts.CODE_SUFFIXES)
    results: dict[str, Fact] = {"tests": _facts.tests_fact(code_paths)}
    no_base = Fact("unknown", {"reason": "no base tree"})
    try:
        head_imports = _ast_grep.imports(binary, config, head, code_paths)
    except _ast_grep.AstGrepError as exc:
        failed = Fact("unknown", {"reason": f"ast-grep {exc}"})
        results["scope"] = failed
        results["dependencies"] = failed if base is not None else no_base
    else:
        results["scope"] = _facts.scope_fact(code_paths, head_imports)
        if base is None:
            results["dependencies"] = no_base
        else:
            try:
                base_imports = _ast_grep.imports(binary, config, base, ["."])
            except _ast_grep.AstGrepError as exc:
                results["dependencies"] = Fact("unknown", {"reason": f"ast-grep {exc}"})
            else:
                results["dependencies"] = _facts.dependencies_fact(head, changed, head_imports, base_imports)
    if base is None:
        results["compat"] = no_base
    else:
        base_paths = _facts.tree_files(base, changed, _facts.CODE_SUFFIXES)
        try:
            before = _ast_grep.outline(binary, config, base, base_paths, "exports")
            after = _ast_grep.outline(binary, config, head, code_paths, "exports")
        except _ast_grep.AstGrepError as exc:
            results["compat"] = Fact("unknown", {"reason": f"ast-grep {exc}"})
        else:
            results["compat"] = _facts.compat_fact(base_paths, before, after)
    return {name: results[name] for name in ("compat", "dependencies", "tests", "scope")}


def facts(
    head: Path,
    changed: Iterable[str],
    *,
    base: Path | None = None,
    ast_grep: str | None = None,
) -> dict[str, Fact]:
    """Return the compat, dependencies, tests, and scope facts for a change.

    Every fact is `unknown` when ast-grep is not on PATH. A failed ast-grep
    run makes only the facts that need it `unknown`. `compat` and
    `dependencies` are `unknown` when `base` is None.
    """
    paths = _facts.normalize_changed(changed)
    binary = _ast_grep.find_binary(ast_grep)
    if binary is None:
        return unknown_facts(_MISSING)
    with _ast_grep.packaged_config() as config:
        return _compute_facts(binary, config, head, paths, base)


def _on_changed_lines(hit: Hit, ranges: Sequence[LineRange]) -> bool:
    return any(hit.line <= end and start <= hit.end_line for start, end in ranges)


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
    file. Without ast-grep, the result is `failed:ast-grep-missing`, no hits,
    and every fact `unknown`.
    """
    paths = _facts.normalize_changed(changed)
    binary = _ast_grep.find_binary(ast_grep)
    if binary is None:
        return Evidence(f"failed:{_MISSING}", (), unknown_facts(_MISSING))
    with _ast_grep.packaged_config() as config:
        code_paths = _facts.tree_files(head, paths, _facts.CODE_SUFFIXES)
        try:
            rows = _ast_grep.scan(binary, config, head, code_paths)
        except _ast_grep.AstGrepError as exc:
            return Evidence(f"failed:{exc}", (), unknown_facts(f"ast-grep {exc}"))
        hits = [hit for row in rows if (hit := _hit(row)) is not None]
        if hunks is not None:
            hits = [hit for hit in hits if _on_changed_lines(hit, hunks.get(hit.path, ()))]
        hits.sort(key=lambda hit: (hit.path, hit.line, hit.rule_id))
        return Evidence("ok", tuple(hits), _compute_facts(binary, config, head, paths, base))
