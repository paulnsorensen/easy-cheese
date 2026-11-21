"""Scan a change with the packaged rules and compute its review facts."""

from __future__ import annotations

import os
import re
from collections.abc import Callable, Generator, Iterable, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import TypeVar, cast

import easy_cheese_review._ast_grep as _ast_grep
import easy_cheese_review._facts as _facts
from easy_cheese_review._model import FACT_NAMES, Evidence, Fact, FactValue, Hit, Skipped

LineRange = tuple[int, int]

# Files above this size are not scanned: one generated or vendored file must
# not cost unbounded ast-grep time and memory.
MAX_FILE_BYTES = 1024 * 1024

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


def _split(root: Path, paths: Sequence[str], limit: int) -> tuple[list[str], dict[str, int]]:
    """Split `paths` into the files within `limit` bytes and the sizes of the others."""
    kept: list[str] = []
    oversized: dict[str, int] = {}
    for path in paths:
        size = (root / path).stat().st_size
        if size > limit:
            oversized[path] = size
        else:
            kept.append(path)
    return kept, oversized


def _oversized_in_tree(root: Path, limit: int) -> dict[str, int]:
    """Return the size of each file under `root` that ast-grep parses and that is above `limit`.

    Like the ast-grep directory walk, the walk skips hidden entries and links.
    """
    found: dict[str, int] = {}
    for folder, dirs, files in os.walk(root):
        dirs[:] = [name for name in dirs if not name.startswith(".")]
        for name in files:
            candidate = Path(folder, name)
            if name.startswith(".") or candidate.suffix not in _facts.SCAN_SUFFIXES:
                continue
            if candidate.is_symlink() or not candidate.is_file():
                continue
            size = candidate.stat().st_size
            if size > limit:
                found[candidate.relative_to(root).as_posix()] = size
    return found


def _unless_skipped(fact: Fact, doubtful: FactValue, skipped: Iterable[str]) -> Fact:
    """Return `unknown` when `fact` is `doubtful` and a skipped file can change that answer."""
    names = sorted(skipped)
    if fact.value == doubtful and names:
        return Fact("unknown", {"reason": "file-too-large", "skipped": names})
    return fact


def _compute_facts(
    binary: str | None, config: Path, head: Path, changed: Sequence[str], base: Path | None, limit: int
) -> tuple[dict[str, Fact], tuple[Skipped, ...], list[str]]:
    """Compute each fact on its own, so one failed ast-grep run spoils only its facts.

    Return the facts, the skipped files, and the head code files within `limit`.
    No ast-grep run reads a file above `limit` bytes. A skip makes a fact
    `unknown` only when the missing file can change its value:

    - `tests` pairs file names and reads no file, so it never changes.
    - `scope`: a missing import can only join groups, so `yes` becomes `unknown`.
    - `compat`: a changed file skipped in either tree is not compared, so
      `no` becomes `unknown`.
    - `dependencies`: a skipped head file can hide a new import, so `no`
      becomes `unknown`. A skipped base file can hide a known import, so a
      `yes` that rests only on `added_imports` becomes `unknown`.
    """

    def imports(root: Path, paths: Sequence[str], exclude: Sequence[str] = ()) -> dict[str, list[str]]:
        return _ast_grep.imports(_require(binary), config, root, paths, exclude)

    def exports(root: Path, paths: Sequence[str]) -> dict[str, list[_ast_grep.JsonObject]]:
        return _ast_grep.outline(_require(binary), config, root, paths, "exports")

    code_paths = _facts.tree_files(head, changed, _facts.CODE_SUFFIXES)
    head_kept, head_over = _split(head, code_paths, limit)
    skipped = [Skipped("head", path, size) for path, size in head_over.items()]
    head_imports = _guarded(lambda: imports(head, head_kept))
    computed: dict[str, Fact] = {"tests": _facts.tests_fact(code_paths)}
    if isinstance(head_imports, Fact):
        computed["scope"] = head_imports
    else:
        computed["scope"] = _unless_skipped(_facts.scope_fact(code_paths, head_imports), "yes", head_over)
    if base is None:
        computed["compat"] = computed["dependencies"] = Fact("unknown", {"reason": "no base tree"})
    else:
        base_paths = _facts.tree_files(base, changed, _facts.CODE_SUFFIXES)
        base_kept, base_over = _split(base, base_paths, limit)
        tree_over = _oversized_in_tree(base, limit) | base_over
        skipped.extend(Skipped("base", path, size) for path, size in tree_over.items())
        unread = set(base_over) | (set(head_over) & set(base_paths))
        compared = [path for path in base_kept if path not in unread]
        compat = _guarded(
            lambda: _facts.compat_fact(compared, exports(base, compared), exports(head, head_kept))
        )
        computed["compat"] = _unless_skipped(compat, "no", unread)
        if isinstance(head_imports, Fact):
            computed["dependencies"] = head_imports
        else:
            base_imports = _guarded(lambda: imports(base, ["."], sorted(tree_over)))
            computed["dependencies"] = (
                base_imports
                if isinstance(base_imports, Fact)
                else _dependencies(head, changed, head_imports, base_imports, head_over, tree_over)
            )
    ordered = tuple(sorted(skipped, key=lambda item: (item.tree, item.path)))
    return {name: computed[name] for name in FACT_NAMES}, ordered, head_kept


def _dependencies(
    head: Path,
    changed: Sequence[str],
    head_imports: Mapping[str, list[str]],
    base_imports: Mapping[str, list[str]],
    head_over: Mapping[str, int],
    base_over: Mapping[str, int],
) -> Fact:
    """Return the `dependencies` fact, `unknown` where a skipped file can change it."""
    fact = _facts.dependencies_fact(head, changed, head_imports, base_imports)
    fact = _unless_skipped(fact, "no", head_over)
    if fact.detail.get("manifests") or fact.detail.get("lockfiles"):
        return fact
    return _unless_skipped(fact, "yes", base_over)


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
    max_file_bytes: int = MAX_FILE_BYTES,
) -> dict[str, Fact]:
    """Return the compat, dependencies, tests, and scope facts for a change.

    A missing ast-grep binary fails like a failed ast-grep run: only the
    facts that need ast-grep (`compat`, `dependencies`, `scope`) are
    `unknown`, with the reason. `tests` needs no ast-grep and stays known.
    `compat` and `dependencies` are `unknown` when `base` is None.
    No ast-grep run reads a file larger than `max_file_bytes`; a fact that
    such a file can change is `unknown` with the reason `file-too-large`.
    """
    with _setup(changed, ast_grep) as (paths, binary, config):
        return _compute_facts(binary, config, head, paths, base, max_file_bytes)[0]

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
    max_file_bytes: int = MAX_FILE_BYTES,
) -> Evidence:
    """Run the packaged rule pack over the changed files of `head`.

    The rules load only through `-c` on the packaged config. When `hunks` is
    given, a hit survives only when its lines overlap a changed range of its
    file. A changed file with no entry in `hunks` counts as changed in full,
    so git output with no hunk for it (a binary diff) hides none of its hits.
    A failed hit scan, a missing ast-grep binary included, gives
    `failed:<reason>` and no hits; the facts are still computed as in `facts`.
    A file larger than `max_file_bytes` is not scanned and is in `skipped`.
    """
    with _setup(changed, ast_grep) as (paths, binary, config):
        computed, skipped, head_kept = _compute_facts(binary, config, head, paths, base, max_file_bytes)
        try:
            rows = _ast_grep.scan(_require(binary), config, head, head_kept)
        except _ast_grep.AstGrepError as exc:
            return Evidence(f"failed:{exc}", (), computed, skipped)
        hits = [hit for row in rows if (hit := _hit(row)) is not None]
        if hunks is not None:
            hits = [hit for hit in hits if _on_changed_lines(hit, hunks)]
        hits.sort(key=lambda hit: (hit.path, hit.line, hit.rule_id))
        return Evidence("ok", tuple(hits), computed, skipped)
