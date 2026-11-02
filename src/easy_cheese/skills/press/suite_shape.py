"""Report test-shape findings for the Python tests that changed after a base revision.

Press runs this check before its handoff. The result is a receipt, not a gate:
Press fixes each finding in the tests that it wrote, or records why the finding
stands. Only new test functions are checked; tests that exist at the base stay
out of scope.
"""

from __future__ import annotations

import ast
import math
import re
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal

import fromargs

from easy_cheese.shared.git_utils import run_git

DEFAULT_ROW_CAP = 8
_PRESS_FILE = re.compile(r"test_press_(\w+)\.py|test_(\w+)_press\.py")
_PROCESS_CALLS = frozenset({
    "subprocess.run", "subprocess.Popen", "subprocess.call",
    "subprocess.check_call", "subprocess.check_output", "os.system",
})
_COLLECTION_WRAPPERS = frozenset({"sorted", "list", "tuple", "set"})
_COLLECTION_VIEWS = frozenset({"items", "keys", "values"})

TestNode = ast.FunctionDef | ast.AsyncFunctionDef
Kind = Literal[
    "press-file-beside-base", "rows-over-cap", "range-trials",
    "cross-product-over-cap", "subprocess-per-row", "repeated-ac-marker",
]


@dataclass(frozen=True)
class Finding:
    kind: Kind
    path: str
    line: int
    test: str
    detail: str


@dataclass(frozen=True)
class _Revision:
    """One readable tree: a revision, or the working tree when `name` is None."""

    root: Path
    name: str | None

    def read(self, path: str) -> str | None:
        if self.name is None:
            file = self.root / path
            return file.read_text(encoding="utf-8") if file.is_file() else None
        return _git(self.root, ["show", f"{self.name}:{path}"])


def _git(root: Path, args: list[str]) -> str | None:
    result = run_git(args, cwd=root)
    return result.stdout if result.returncode == 0 else None


def _verified_revision(root: Path, revision: str) -> str:
    if revision.startswith("-") or _git(root, ["rev-parse", "--verify", "--quiet", f"{revision}^{{tree}}"]) is None:
        raise fromargs.CliError(f"not a revision in this repository: {revision!r}")
    return revision


def _is_test_file(path: str) -> bool:
    name = PurePosixPath(path).name
    return name.endswith(".py") and (name.startswith("test_") or name.endswith("_test.py"))


def _changed_test_files(root: Path, base: str, head: str | None) -> list[tuple[str, str]]:
    """Return `(status, path)` for each added or modified test file."""
    diff = _git(root, ["diff", "--name-status", "--no-renames", base, *([head] if head else []), "--"])
    if diff is None:
        raise fromargs.CliError(f"git diff failed for base {base!r}")
    entries = [tuple(line.split("\t", 1)) for line in diff.splitlines() if line]
    if head is None:
        untracked = _git(root, ["ls-files", "--others", "--exclude-standard"]) or ""
        entries += [("A", path) for path in untracked.splitlines() if path]
    changed = [(status[0], path) for status, path in entries if status[0] in "AM" and _is_test_file(path)]
    return sorted(changed, key=lambda entry: entry[1])


def _tests(module: ast.Module) -> Iterator[tuple[str, TestNode]]:
    for node in module.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
            yield node.name, node
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name.startswith("test"):
                    yield f"{node.name}.{item.name}", item


def _parametrize_values(test: TestNode) -> list[ast.expr]:
    values: list[ast.expr] = []
    for decorator in test.decorator_list:
        if isinstance(decorator, ast.Call) and ast.unparse(decorator.func).endswith("mark.parametrize"):
            keyword = next((item.value for item in decorator.keywords if item.arg == "argvalues"), None)
            argument = decorator.args[1] if len(decorator.args) > 1 else keyword
            if argument is not None:
                values.append(argument)
    return values


def _range_length(arguments: list[ast.expr]) -> int | None:
    bounds = [item.value for item in arguments if isinstance(item, ast.Constant) and type(item.value) is int]
    if not 1 <= len(arguments) <= 3 or len(bounds) != len(arguments) or (len(bounds) == 3 and bounds[2] == 0):
        return None
    return len(range(*bounds))


def _row_count(values: ast.expr, literals: dict[str, int]) -> int | None:
    match values:
        case ast.List(elts=items) | ast.Tuple(elts=items) | ast.Set(elts=items):
            return len(items)
        case ast.Dict(keys=keys):
            return len(keys)
        case ast.Name(id=name):
            return literals.get(name)
        case ast.Call(func=ast.Name(id="range"), args=arguments):
            return _range_length(arguments)
        case ast.Call(func=ast.Name(id=wrapper), args=[inner]) if wrapper in _COLLECTION_WRAPPERS:
            return _row_count(inner, literals)
        case ast.Call(func=ast.Attribute(value=inner, attr=view), args=[]) if view in _COLLECTION_VIEWS:
            return _row_count(inner, literals)
        case _:
            return None


def _is_range(values: ast.expr) -> bool:
    return isinstance(values, ast.Call) and isinstance(values.func, ast.Name) and values.func.id == "range"


def _module_literals(module: ast.Module) -> dict[str, int]:
    """Map each module-level name bound to a collection literal to its length."""
    sizes: dict[str, int] = {}
    for node in module.body:
        match node:
            case ast.Assign(targets=[ast.Name(id=name)], value=value) | ast.AnnAssign(
                target=ast.Name(id=name), value=value
            ) if value is not None:
                if (count := _row_count(value, sizes)) is not None:
                    sizes[name] = count
            case _:
                pass
    return sizes


def _starts_process(node: ast.AST, helpers: dict[str, TestNode], *, follow: bool = True) -> bool:
    """Return whether `node`, or a module helper that it calls, starts a process."""
    for child in ast.walk(node):
        if isinstance(child, ast.Attribute) and ast.unparse(child) == "sys.executable":
            return True
        if isinstance(child, ast.Call):
            called = ast.unparse(child.func)
            if called in _PROCESS_CALLS:
                return True
            if follow and called in helpers and _starts_process(helpers[called], helpers, follow=False):
                return True
    return False


def _markers(test: TestNode, marker: str) -> list[str]:
    return [
        argument.value
        for decorator in test.decorator_list
        if isinstance(decorator, ast.Call) and ast.unparse(decorator.func).endswith(f"mark.{marker}")
        for argument in decorator.args
        if isinstance(argument, ast.Constant) and isinstance(argument.value, str)
    ]


def _test_findings(
    path: str, name: str, test: TestNode, literals: dict[str, int], helpers: dict[str, TestNode], row_cap: int
) -> Iterator[Finding]:
    values = _parametrize_values(test)
    rows = [_row_count(item, literals) for item in values]
    for item, count in zip(values, rows):
        if _is_range(item) and (count is None or count > row_cap):
            trials = "an unknown number of" if count is None else str(count)
            yield Finding("range-trials", path, test.lineno, name, f"parametrize over range runs {trials} trials")
        elif count is not None and count > row_cap:
            yield Finding("rows-over-cap", path, test.lineno, name, f"{count} rows, cap {row_cap}")
    known = [count for count in rows if count is not None]
    cases = math.prod(known)
    if len(rows) > 1 and len(known) == len(rows) and cases > row_cap:
        product = " x ".join(map(str, known))
        yield Finding("cross-product-over-cap", path, test.lineno, name, f"{product} = {cases} cases, cap {row_cap}")
    if cases > 1 and _starts_process(test, helpers):
        yield Finding("subprocess-per-row", path, test.lineno, name, f"starts a process for each of {cases} cases")


def _new_tests(module: ast.Module, old: ast.Module) -> Iterator[tuple[str, TestNode]]:
    existing = {name for name, _ in _tests(old)}
    return ((name, test) for name, test in _tests(module) if name not in existing)


def _parse(path: str, source: str) -> ast.Module:
    try:
        return ast.parse(source, filename=path)
    except SyntaxError as exc:
        raise fromargs.CliError(f"cannot parse {path}: {exc.msg} (line {exc.lineno})") from exc


def _beside_base(head: _Revision, path: str) -> Finding | None:
    match = _PRESS_FILE.fullmatch(PurePosixPath(path).name)
    if match is None:
        return None
    sibling = str(PurePosixPath(path).with_name(f"test_{match.group(1) or match.group(2)}.py"))
    if head.read(sibling) is None:
        return None
    return Finding("press-file-beside-base", path, 1, "", f"extend {sibling} instead")


def _marker_counts(head: _Revision, marker: str) -> Counter[str]:
    """Count each acceptance-marker value across every test file in `head`."""
    before: list[str] = ["--untracked"] if head.name is None else []
    after: list[str] = [] if head.name is None else [head.name]
    pattern = rf"mark\.{re.escape(marker)}\("
    grep = run_git(["grep", *before, "-n", "-E", "-e", pattern, *after, "--", "*.py"], cwd=head.root)
    if grep.returncode > 1:
        raise fromargs.CliError(f"git grep failed: {grep.stderr.strip()}")
    found = grep.stdout
    value = re.compile(rf"""mark\.{re.escape(marker)}\(\s*["']([^"']+)["']""")
    counts: Counter[str] = Counter()
    for line in found.splitlines():
        located = line.removeprefix(f"{head.name}:") if head.name else line
        path, _, content = located.partition(":")
        if _is_test_file(path):
            counts.update(value.findall(content))
    return counts


def suite_shape(
    *, base: str, head: str | None = None, row_cap: int = DEFAULT_ROW_CAP, marker: str = "ac"
) -> dict[str, object]:
    """Report test-shape findings for the new Python tests after a base revision.

    Parameters
    ----------
    base
        Revision that holds the existing tests, such as the Cook report's acceptance-evidence revision.
    head
        Revision to check. Omit it to check the working tree, untracked files included.
    row_cap
        Largest parametrize table, or product of stacked tables, that needs no written reason.
    marker
        Name of the pytest acceptance marker, as in `pytest.mark.<marker>("gh-1:AC-1")`.
    """
    if row_cap < 1:
        raise fromargs.CliError(f"row-cap must be 1 or more, got {row_cap}")
    top = _git(Path.cwd(), ["rev-parse", "--show-toplevel"])
    if top is None:
        raise fromargs.CliError("not inside a git work tree")
    root = Path(top.strip())
    tip = _Revision(root, None if head is None else _verified_revision(root, head))
    findings: list[Finding] = []
    marked: list[tuple[str, str, int, str]] = []
    for status, path in _changed_test_files(root, _verified_revision(root, base), tip.name):
        if status == "A" and (finding := _beside_base(tip, path)) is not None:
            findings.append(finding)
        module = _parse(path, tip.read(path) or "")
        old = _parse(path, _git(root, ["show", f"{base}:{path}"]) or "") if status == "M" else ast.Module([], [])
        literals = _module_literals(module)
        helpers = {node.name: node for node in module.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
        for name, test in _new_tests(module, old):
            findings.extend(_test_findings(path, name, test, literals, helpers, row_cap))
            marked.extend((path, name, test.lineno, value) for value in _markers(test, marker))
    counts = _marker_counts(tip, marker) if marked else Counter[str]()
    findings.extend(
        Finding("repeated-ac-marker", path, line, name, f"{value} is on {counts[value]} tests")
        for path, name, line, value in marked
        if counts[value] > 1
    )
    return {"base": base, "head": head or "worktree", "row_cap": row_cap, "clean": not findings, "findings": findings}


def build_app() -> fromargs.App:
    return fromargs.App(
        "test-shape",
        help="Report test-shape findings for the new Python tests after a base revision.",
        help_formatter="plain",
        default_command=suite_shape,
    )


def main(argv: list[str] | None = None) -> int:
    return build_app().run(argv)
