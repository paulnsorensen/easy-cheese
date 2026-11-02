"""Report test-shape findings for the Python tests that changed after a base revision.

Press runs this check before its handoff. The result is a receipt, not a gate:
Press fixes each finding in the tests that it wrote, or records why the finding
stands. A new test function is checked in full. A test that exists at the base
is reported only for a finding that it did not have at the base.
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
    "subprocess.run", "subprocess.Popen", "subprocess.call", "subprocess.check_call",
    "subprocess.check_output", "subprocess.getoutput", "subprocess.getstatusoutput",
    "os.system", "os.popen", "asyncio.create_subprocess_exec", "asyncio.create_subprocess_shell",
})
_PROCESS_MODULES = frozenset(name.partition(".")[0] for name in _PROCESS_CALLS)
_TRIAL_NAMES = frozenset({"trial", "trials", "attempt", "iteration", "repeat", "_"})
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


def _changed_test_files(root: Path, base: str, head: str | None) -> list[tuple[str, str, str | None]]:
    """Return `(status, path, base_path)` for each added, modified, or renamed test file.

    `base_path` names the file at the base. It is None for an added file.
    """
    diff = _git(root, ["diff", "--name-status", "-z", "--find-renames", base, *([head] if head else []), "--"])
    if diff is None:
        raise fromargs.CliError(f"git diff failed for base {base!r}")
    fields = iter(diff.split("\0"))
    entries: list[tuple[str, str, str | None]] = []
    for status in fields:
        path = next(fields, "")
        if status.startswith("R"):
            entries.append(("R", next(fields, ""), path))
        elif status in ("A", "M"):
            entries.append((status, path, path if status == "M" else None))
    if head is None:
        untracked = _git(root, ["ls-files", "-z", "--others", "--exclude-standard"]) or ""
        entries += [("A", path, None) for path in untracked.split("\0") if path]
    return sorted((entry for entry in entries if _is_test_file(entry[1])), key=lambda entry: entry[1])


def _tests(module: ast.Module) -> Iterator[tuple[str, TestNode]]:
    for node in module.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
            yield node.name, node
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name.startswith("test"):
                    yield f"{node.name}.{item.name}", item


def _argument(decorator: ast.Call, position: int, keyword: str) -> ast.expr | None:
    if len(decorator.args) > position:
        return decorator.args[position]
    return next((item.value for item in decorator.keywords if item.arg == keyword), None)


def _argnames(names: ast.expr | None) -> frozenset[str]:
    if isinstance(names, ast.Constant) and isinstance(names.value, str):
        return frozenset(part.strip() for part in names.value.split(","))
    if isinstance(names, (ast.List, ast.Tuple)):
        return frozenset(item.value for item in names.elts if isinstance(item, ast.Constant) and isinstance(item.value, str))
    return frozenset()


def _tables(test: TestNode) -> list[tuple[frozenset[str], ast.expr]]:
    """Return the argument names and the values of each parametrize table on `test`."""
    tables: list[tuple[frozenset[str], ast.expr]] = []
    for decorator in test.decorator_list:
        if isinstance(decorator, ast.Call) and ast.unparse(decorator.func).endswith("mark.parametrize"):
            values = _argument(decorator, 1, "argvalues")
            if values is not None:
                tables.append((_argnames(_argument(decorator, 0, "argnames")), values))
    return tables


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
            pass
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


def _process_imports(module: ast.Module) -> dict[str, str]:
    """Map each local name that a module-level import binds to a process module or a launch call."""
    names: dict[str, str] = {}
    for node in module.body:
        if isinstance(node, ast.Import):
            names.update((alias.asname or alias.name, alias.name) for alias in node.names if alias.name in _PROCESS_MODULES)
        elif isinstance(node, ast.ImportFrom) and node.module in _PROCESS_MODULES:
            names.update((alias.asname or alias.name, f"{node.module}.{alias.name}") for alias in node.names)
    return names


@dataclass(frozen=True)
class _Scope:
    """The module-level names that a test can refer to."""

    literals: dict[str, int]
    helpers: dict[str, TestNode]
    imports: dict[str, str]

    @classmethod
    def of(cls, module: ast.Module) -> _Scope:
        helpers = {node.name: node for node in module.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
        return cls(_module_literals(module), helpers, _process_imports(module))


def _mentions_interpreter(node: ast.AST, names: frozenset[str]) -> bool:
    return any(
        (isinstance(child, ast.Attribute) and ast.unparse(child) == "sys.executable")
        or (isinstance(child, ast.Name) and child.id in names)
        for child in ast.walk(node)
    )


def _interpreter_names(node: ast.AST) -> frozenset[str]:
    """Return the local names that `node` binds to a value holding `sys.executable`."""
    return frozenset(
        target.id
        for child in ast.walk(node)
        if isinstance(child, ast.Assign) and _mentions_interpreter(child.value, frozenset())
        for target in child.targets
        if isinstance(target, ast.Name)
    )


def _passes_interpreter(call: ast.Call, names: frozenset[str]) -> bool:
    """Return whether `call` receives `sys.executable`, directly or through a local name, as a launcher argv does."""
    arguments = [*call.args, *(keyword.value for keyword in call.keywords)]
    return any(_mentions_interpreter(argument, names) for argument in arguments)


def _starts_process(node: ast.AST, scope: _Scope, *, follow: bool = True) -> bool:
    """Return whether `node`, or a module helper that it calls, starts a process."""
    names = _interpreter_names(node)
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        called = ast.unparse(child.func)
        head, dot, rest = called.partition(".")
        if scope.imports.get(head, head) + dot + rest in _PROCESS_CALLS or _passes_interpreter(child, names):
            return True
        if follow and called in scope.helpers and _starts_process(scope.helpers[called], scope, follow=False):
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


def _test_findings(path: str, name: str, test: TestNode, scope: _Scope, row_cap: int) -> Iterator[Finding]:
    tables = _tables(test)
    rows = [_row_count(values, scope.literals) for _, values in tables]
    for (names, values), count in zip(tables, rows):
        if _is_range(values) and (count is None or count > row_cap or not names.isdisjoint(_TRIAL_NAMES)):
            trials = "an unknown number of" if count is None else str(count)
            yield Finding("range-trials", path, test.lineno, name, f"parametrize over range runs {trials} trials")
        elif count is not None and count > row_cap:
            yield Finding("rows-over-cap", path, test.lineno, name, f"{count} rows, cap {row_cap}")
    known = [count for count in rows if count is not None]
    cases = math.prod(known)
    if len(rows) > 1 and len(known) == len(rows) and cases > row_cap:
        product = " x ".join(map(str, known))
        yield Finding("cross-product-over-cap", path, test.lineno, name, f"{product} = {cases} cases, cap {row_cap}")
    unknown = len(known) < len(rows)
    if (cases > 1 or unknown) and _starts_process(test, scope):
        each = "each case" if unknown else f"each of {cases} cases"
        yield Finding("subprocess-per-row", path, test.lineno, name, f"starts a process for {each}")


def _parse(path: str, source: str) -> ast.Module:
    try:
        return ast.parse(source, filename=path)
    except SyntaxError as exc:
        raise fromargs.CliError(f"cannot parse {path}: {exc.msg} (line {exc.lineno})") from exc


def _file_findings(
    path: str, module: ast.Module, old: ast.Module, row_cap: int, marker: str
) -> tuple[list[Finding], list[tuple[str, str, int, str]]]:
    """Return the shape findings and the added acceptance markers of the tests in one changed file.

    A test that `old` also holds keeps only the findings and markers that it did not have in `old`.
    """
    scope, old_scope, old_tests = _Scope.of(module), _Scope.of(old), dict(_tests(old))
    findings: list[Finding] = []
    marked: list[tuple[str, str, int, str]] = []
    for name, test in _tests(module):
        found = list(_test_findings(path, name, test, scope, row_cap))
        markers = _markers(test, marker)
        if (previous := old_tests.get(name)) is not None:
            seen = Counter((item.kind, item.detail) for item in _test_findings(path, name, previous, old_scope, row_cap))
            kept: list[Finding] = []
            for item in found:
                if seen[item.kind, item.detail] > 0:
                    seen[item.kind, item.detail] -= 1
                else:
                    kept.append(item)
            found = kept
            markers = [value for value in markers if value not in _markers(previous, marker)]
        findings.extend(found)
        marked.extend((path, name, test.lineno, value) for value in markers)
    return findings, marked


def _beside_base(head: _Revision, path: str) -> Finding | None:
    match = _PRESS_FILE.fullmatch(PurePosixPath(path).name)
    if match is None:
        return None
    sibling = str(PurePosixPath(path).with_name(f"test_{match.group(1) or match.group(2)}.py"))
    if head.read(sibling) is None:
        return None
    return Finding("press-file-beside-base", path, 1, "", f"extend {sibling} instead")


def _marker_counts(head: _Revision, marker: str) -> Counter[str]:
    """Count the tests in `head` that carry each acceptance-marker value."""
    before: list[str] = ["--untracked"] if head.name is None else []
    after: list[str] = [] if head.name is None else [head.name]
    pattern = rf"mark\.{re.escape(marker)}\("
    grep = run_git(["grep", *before, "-l", "-z", "-E", "-e", pattern, *after, "--", "*.py"], cwd=head.root)
    if grep.returncode > 1:
        raise fromargs.CliError(f"git grep failed: {grep.stderr.strip()}")
    counts: Counter[str] = Counter()
    for entry in grep.stdout.split("\0"):
        path = entry.removeprefix(f"{head.name}:") if head.name else entry
        if not _is_test_file(path):
            continue
        try:
            module = ast.parse(head.read(path) or "", filename=path)
        except SyntaxError:
            continue
        for _, test in _tests(module):
            counts.update(set(_markers(test, marker)))
    return counts


def suite_shape(
    *, base: str, head: str | None = None, row_cap: int = DEFAULT_ROW_CAP, marker: str = "ac"
) -> dict[str, object]:
    """Report test-shape findings for the Python tests that changed after a base revision.

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
    for status, path, base_path in _changed_test_files(root, _verified_revision(root, base), tip.name):
        if status == "A" and (finding := _beside_base(tip, path)) is not None:
            findings.append(finding)
        module = _parse(path, tip.read(path) or "")
        old_source = _git(root, ["show", f"{base}:{base_path}"]) if base_path else None
        old = _parse(base_path, old_source) if base_path and old_source else ast.Module([], [])
        file_findings, file_markers = _file_findings(path, module, old, row_cap, marker)
        findings.extend(file_findings)
        marked.extend(file_markers)
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
        help="Report test-shape findings for the Python tests that changed after a base revision.",
        help_formatter="plain",
        default_command=suite_shape,
    )


def main(argv: list[str] | None = None) -> int:
    return build_app().run(argv)
