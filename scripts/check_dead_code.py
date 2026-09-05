"""Owner-qualified semantic classifier over Vulture's scanner API.

Wraps Vulture 2.16's scan and accepts findings only in narrow, owner-qualified
categories; everything else is reported and fails the gate. Whitelist-free --
no checked-in symbol list; exceptions are explicit owner-qualified identities.
"""
from __future__ import annotations

import ast
import contextlib
import importlib
import io
import sys
import tokenize
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, TypedDict, cast, override

from vulture.config import InputError  # pyright: ignore[reportMissingTypeStubs]
from vulture.core import ExitCode  # pyright: ignore[reportMissingTypeStubs]

REPO_ROOT = Path(__file__).resolve().parent.parent
_SCHEMA_PREFIX = "src/easy_cheese_schemas/"


class _UnusedItem(Protocol):
    filename: Path
    first_lineno: int
    name: str
    typ: str

    def get_report(self) -> str: ...


class _VultureLike(Protocol):
    exit_code: int

    def scavenge(self, paths: Sequence[str], exclude: Sequence[str] | None = None) -> None: ...  # noqa: V107

    def get_unused_code(
        self, min_confidence: int = 0, sort_by_size: bool = False  # noqa: V107
    ) -> list[_UnusedItem]: ...


class _VultureConfig(TypedDict):
    verbose: bool  # noqa: V107
    ignore_names: list[str]  # noqa: V107
    ignore_decorators: list[str]  # noqa: V107
    paths: list[str]  # noqa: V107
    exclude: list[str]  # noqa: V107
    min_confidence: int  # noqa: V107
    sort_by_size: bool  # noqa: V107


# vulture ships no type stubs; its untyped params would otherwise propagate
# Unknown through every downstream use of the scanner API.
_Vulture = cast(Callable[..., _VultureLike], getattr(importlib.import_module("vulture"), "Vulture"))
_make_config = cast(
    Callable[[list[str]], _VultureConfig],
    getattr(importlib.import_module("vulture.config"), "make_config"),
)

# base names are matched via each file's own import map (see _import_map),
# resolved to "module.Name" and compared against these fully-qualified pairs:
_QUALIFIED_CALLBACK_OVERRIDES = {
    ("urllib.request.HTTPRedirectHandler", "redirect_request"),
    ("html.parser.HTMLParser", "handle_starttag"),
    ("html.parser.HTMLParser", "handle_data"),
    ("html.parser.HTMLParser", "handle_endtag"),
    ("urllib.request.HTTPSHandler", "https_open"),
}


@dataclass(frozen=True, slots=True)
class _Finding:
    path: Path
    first_line: int
    name: str
    typ: str
    report: str


def _findings(items: Sequence[_UnusedItem]) -> tuple[_Finding, ...]:
    findings: list[_Finding] = []
    for i in items:
        path = Path(i.filename)
        if path.is_absolute():
            with contextlib.suppress(ValueError):
                path = path.relative_to(REPO_ROOT)
        findings.append(_Finding(path, i.first_lineno, i.name, i.typ, i.get_report()))
    return tuple(findings)


class _ImportMap(dict[str, str]):
    def __init__(self) -> None:
        super().__init__()
        self.bindings: dict[str, list[tuple[int, str | None]]] = {}

    def bind(self, name: str, line: int, qualified: str | None) -> None:
        self.bindings.setdefault(name, []).append((line, qualified))
        if qualified is None:
            _ = self.pop(name, None)
        else:
            self[name] = qualified


def _bound_names(target: ast.AST) -> tuple[str, ...]:
    if isinstance(target, ast.Name):
        return (target.id,)
    if isinstance(target, (ast.Tuple, ast.List)):
        return tuple(name for elt in target.elts for name in _bound_names(elt))
    if isinstance(target, ast.Starred):
        return _bound_names(target.value)
    return ()


def _import_map(module: ast.Module) -> _ImportMap:
    out = _ImportMap()

    class _WalrusBindings(ast.NodeVisitor):
        @override
        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            return

        @override
        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            return

        @override
        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            return

        @override
        def visit_Lambda(self, node: ast.Lambda) -> None:  # noqa: V105
            return

        @override  # noqa: V105
        def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
            for name in _bound_names(node.target):
                out.bind(name, node.lineno, None)
            self.generic_visit(node.value)

    def visit_statements(statements: list[ast.stmt]) -> None:
        for node in statements:
            _WalrusBindings().visit(node)
            if isinstance(node, ast.ImportFrom) and node.module:
                for alias in node.names:
                    out.bind(alias.asname or alias.name, node.lineno, f"{node.module}.{alias.name}")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    bound = alias.asname or alias.name.split(".")[0]
                    out.bind(bound, node.lineno, alias.name if alias.asname else bound)
            elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    for name in _bound_names(target):
                        out.bind(name, node.lineno, None)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                out.bind(node.name, node.lineno, None)
                continue

            # Module-level control flow can bind names; do not enter function/class bodies.
            if isinstance(node, ast.If):
                visit_statements(node.body)
                visit_statements(node.orelse)
            elif isinstance(node, (ast.For, ast.AsyncFor, ast.While)):
                if isinstance(node, (ast.For, ast.AsyncFor)):
                    for name in _bound_names(node.target):
                        out.bind(name, node.lineno, None)
                visit_statements(node.body)
                visit_statements(node.orelse)
            elif isinstance(node, (ast.With, ast.AsyncWith)):
                for item in node.items:
                    if item.optional_vars:
                        for name in _bound_names(item.optional_vars):
                            out.bind(name, node.lineno, None)
                visit_statements(node.body)
            elif isinstance(node, ast.Try):
                visit_statements(node.body)
                for handler in node.handlers:
                    if handler.name:
                        out.bind(handler.name, handler.lineno, None)
                    visit_statements(handler.body)
                visit_statements(node.orelse)
                visit_statements(node.finalbody)

    visit_statements(module.body)
    return out


def _resolve_expr(expr: ast.expr, imports: Mapping[str, str], lineno: int | None = None) -> str | None:
    if isinstance(expr, ast.Name):
        if isinstance(imports, _ImportMap) and lineno is not None:
            candidates = [qualified for line, qualified in imports.bindings.get(expr.id, []) if line <= lineno]
            if not candidates or candidates[-1] is None:
                return None
            return candidates[-1]
        return imports.get(expr.id)
    if isinstance(expr, ast.Attribute):
        parent = _resolve_expr(expr.value, imports, lineno)
        return f"{parent}.{expr.attr}" if parent else None
    return None


def _resolve_base(base: ast.expr, imports: Mapping[str, str], lineno: int | None = None) -> str | None:
    return _resolve_expr(base, imports, lineno)


def _is_enum_base(resolved: str | None) -> bool:
    return resolved == "enum.Enum"


_TYPED_DICT_BASES = {"typing.TypedDict", "typing_extensions.TypedDict"}
_PROTOCOL_BASES = {"typing.Protocol", "typing_extensions.Protocol"}
_OVERRIDE_DECORATORS = {"typing.override", "typing_extensions.override"}


def _function_args(func: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[ast.arg, ...]:
    args = func.args
    optional = [args.vararg] if args.vararg else []
    optional += [args.kwarg] if args.kwarg else []
    return (*args.posonlyargs, *args.args, *args.kwonlyargs, *optional)


def _ann_assign_matches(item: ast.stmt, finding: _Finding) -> bool:
    return (
        isinstance(item, ast.AnnAssign)
        and isinstance(item.target, ast.Name)
        and item.target.id == finding.name
        and item.lineno == finding.first_line
    )


def _is_attrs_decorated(class_def: ast.ClassDef, imports: Mapping[str, str]) -> bool:
    for dec in class_def.decorator_list:
        head = dec.func if isinstance(dec, ast.Call) else dec
        if _resolve_expr(head, imports, class_def.lineno) in {"attrs.define", "attrs.frozen", "attrs.attrs"}:
            return True
    return False


def _has_definition_noqa(
    finding: _Finding, module: ast.Module, source_path: Path
) -> bool:
    if finding.typ not in {"function", "method"}:
        return False
    try:
        source = source_path.read_text(encoding="utf-8")
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except (OSError, SyntaxError, tokenize.TokenError):
        return False
    for node in ast.walk(module):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or node.name != finding.name:
            continue
        decorator_line = node.decorator_list[0].lineno if node.decorator_list else node.lineno
        if finding.first_line != decorator_line and finding.first_line != node.lineno:
            continue
        start = next(
            (index for index, token in enumerate(tokens)
             if token.type == tokenize.NAME and token.string == "def" and token.start[0] == node.lineno),
            None,
        )
        if start is None:
            continue
        depth = 0
        for index, token in enumerate(tokens[start:], start):
            if token.type == tokenize.COMMENT and token.string == "# noqa: V103":
                return True
            if token.type == tokenize.OP:
                if token.string in "([{":
                    depth += 1
                elif token.string in ")]}":
                    depth = max(0, depth - 1)
                elif token.string == ":" and depth == 0:
                    next_token = tokens[index + 1] if index + 1 < len(tokens) else None
                    while next_token is not None and next_token.type not in {tokenize.NEWLINE, tokenize.ENDMARKER}:
                        if next_token.type == tokenize.COMMENT and next_token.string == "# noqa: V103":
                            return True
                        index += 1
                        next_token = tokens[index + 1] if index + 1 < len(tokens) else None
                    break
        return False
    return False


def _accepted_reason(finding: _Finding, module: ast.Module, imports: dict[str, str]) -> str | None:
    schema_owned = finding.path.as_posix().startswith(_SCHEMA_PREFIX)
    for node in ast.walk(module):
        if not isinstance(node, ast.ClassDef):
            continue
        if finding.typ == "method":
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == finding.name and item.lineno == finding.first_line:
                    for base in node.bases:
                        resolved = _resolve_base(base, imports, node.lineno)
                        if resolved and any(
                            resolved == qualified and method == finding.name
                            for qualified, method in _QUALIFIED_CALLBACK_OVERRIDES
                        ):
                            return "exact callback override"
                if (
                    isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and item.name == finding.name
                    and finding.first_line in {item.lineno, *(d.lineno for d in item.decorator_list)}
                    and any(
                        _resolve_expr(decorator, imports, item.lineno) in _OVERRIDE_DECORATORS
                        for decorator in item.decorator_list
                    )
                ):
                    return "@override framework hook"
        if finding.typ == "variable":
            bases_resolved = {_resolve_base(base, imports, node.lineno) for base in node.bases}
            if bases_resolved & _TYPED_DICT_BASES and any(
                _ann_assign_matches(item, finding) for item in node.body
            ):
                return "TypedDict field declaration"
            if bases_resolved & _PROTOCOL_BASES:
                if any(_ann_assign_matches(item, finding) for item in node.body):
                    return "Protocol member declaration"
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and any(
                        arg.arg == finding.name and arg.lineno == finding.first_line
                        for arg in _function_args(item)
                    ):
                        return "Protocol method parameter"
        if finding.typ == "variable" and schema_owned:
            for item in node.body:
                target_line = None
                if isinstance(item, ast.Assign) and len(item.targets) == 1 and isinstance(item.targets[0], ast.Name) and item.targets[0].id == finding.name:
                    target_line = item.lineno
                elif isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name) and item.target.id == finding.name:
                    target_line = item.lineno
                if target_line != finding.first_line:
                    continue
                is_enum = any(_is_enum_base(_resolve_base(b, imports, node.lineno)) for b in node.bases)
                if is_enum or _is_attrs_decorated(node, imports):
                    return "enum member or attrs field owned by easy_cheese_schemas"
    if finding.typ == "function":
        for node in ast.walk(module):
            if not (isinstance(node, ast.FunctionDef) and node.name == finding.name):
                continue
            start_line = node.decorator_list[0].lineno if node.decorator_list else node.lineno
            if start_line != finding.first_line:
                continue
            for dec in node.decorator_list:
                if isinstance(dec, ast.Call) and _resolve_expr(dec.func, imports, node.lineno) == "pytest.fixture":
                    if any(kw.arg == "autouse" and isinstance(kw.value, ast.Constant) and kw.value.value is True for kw in dec.keywords):
                        return "autouse pytest fixture"
    return None


def main(argv: Sequence[str] | None = None) -> int:
    try:
        config = _make_config(list(argv) if argv is not None else sys.argv[1:])
    except InputError as err:
        print(err, file=sys.stderr)
        return ExitCode.InvalidCmdlineArguments.value

    vult = _Vulture(
        verbose=config["verbose"],
        ignore_names=config["ignore_names"],
        ignore_decorators=config["ignore_decorators"],
    )
    vult.scavenge(config["paths"], exclude=config["exclude"])
    if vult.exit_code == ExitCode.InvalidInput:
        return ExitCode.InvalidInput.value

    findings = _findings(
        vult.get_unused_code(
            min_confidence=config["min_confidence"], sort_by_size=config["sort_by_size"]
        )
    )
    unclassified: list[_Finding] = []
    module_cache: dict[Path, tuple[ast.Module | None, dict[str, str]]] = {}
    for finding in findings:
        if finding.path not in module_cache:
            source_path = finding.path if finding.path.is_absolute() else REPO_ROOT / finding.path
            try:
                tree = ast.parse(source_path.read_text(encoding="utf-8"))
            except (OSError, SyntaxError):
                module_cache[finding.path] = (None, {})
            else:
                module_cache[finding.path] = (tree, _import_map(tree))
        module, imports = module_cache[finding.path]
        source_path = finding.path if finding.path.is_absolute() else REPO_ROOT / finding.path
        if module is not None and _has_definition_noqa(finding, module, source_path):
            continue
        if module is not None and _accepted_reason(finding, module, imports):
            continue
        unclassified.append(finding)

    for finding in unclassified:
        print(finding.report)
    return ExitCode.DeadCode.value if unclassified else ExitCode.NoDeadCode.value


if __name__ == "__main__":
    raise SystemExit(main())