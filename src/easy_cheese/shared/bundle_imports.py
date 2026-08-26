"""Extract imports that execute on the supported bundle runtime."""

from __future__ import annotations

import ast
import importlib.util
from dataclasses import dataclass
from pathlib import Path

# Closure targets the project's minimum runtime, not the interpreter building it.
_TARGET_VERSION = (3, 12, 0, "final", 0)


@dataclass(frozen=True)
class _ImportReference:
    name: str
    requires_module: bool


class _ImportWalker(ast.NodeVisitor):
    def __init__(self, module: str, *, is_package: bool) -> None:
        self._module = module
        self._package = module if is_package else module.rpartition(".")[0]
        self.references: list[_ImportReference] = []
        self._conditions: dict[str, bool] = {}

    def visit_Import(self, node: ast.Import) -> None:
        self.references.extend(
            _ImportReference(alias.name, True) for alias in node.names
        )

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        imported = self._resolve_from(node)
        if not imported:
            return
        self.references.append(_ImportReference(imported, True))
        # A from-import name may be a submodule or an attribute of its parent.
        self.references.extend(
            _ImportReference(f"{imported}.{alias.name}", False)
            for alias in node.names
            if alias.name != "*"
        )

    def visit_Assign(self, node: ast.Assign) -> None:
        condition = self._condition(node.value)
        for target in node.targets:
            if not isinstance(target, ast.Name):
                continue
            if condition is None:
                self._conditions.pop(target.id, None)
            else:
                self._conditions[target.id] = condition
        self.generic_visit(node)

    def visit_If(self, node: ast.If) -> None:
        condition = self._condition(node.test)
        if condition is not None:
            for statement in node.body if condition else node.orelse:
                self.visit(statement)
            return

        # Unknown branches contribute imports, but not facts used to prune later code.
        conditions = self._conditions.copy()
        for statement in node.body:
            self.visit(statement)
        self._conditions = conditions.copy()
        for statement in node.orelse:
            self.visit(statement)
        self._conditions = conditions

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_nested_scope(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_nested_scope(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._visit_nested_scope(node)

    def _visit_nested_scope(self, node: ast.AST) -> None:
        conditions = self._conditions.copy()
        self.generic_visit(node)
        self._conditions = conditions

    def _resolve_from(self, node: ast.ImportFrom) -> str:
        if not node.level:
            return node.module or ""
        target = "." * node.level + (node.module or "")
        try:
            return importlib.util.resolve_name(target, self._package)
        except (ImportError, ValueError) as exc:
            raise ValueError(f"invalid relative import in {self._module}") from exc

    def _condition(self, node: ast.expr) -> bool | None:
        if isinstance(node, ast.Constant) and isinstance(node.value, bool):
            return node.value
        if isinstance(node, ast.Name) and node.id in self._conditions:
            return self._conditions[node.id]
        if self._is_type_checking(node):
            return False
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            condition = self._condition(node.operand)
            return None if condition is None else not condition
        if not isinstance(node, ast.Compare) or len(node.ops) != 1:
            return None
        left = self._version_value(node.left)
        right = self._version_value(node.comparators[0])
        if left is None or right is None:
            return None
        return self._compare(left, node.ops[0], right)

    @staticmethod
    def _is_type_checking(node: ast.expr) -> bool:
        return (isinstance(node, ast.Name) and node.id == "TYPE_CHECKING") or (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "typing"
            and node.attr == "TYPE_CHECKING"
        )

    @classmethod
    def _version_value(cls, node: ast.expr) -> tuple[object, ...] | None:
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "sys"
            and node.attr == "version_info"
        ):
            return _TARGET_VERSION
        if isinstance(node, ast.Tuple):
            values: list[object] = []
            for item in node.elts:
                if not isinstance(item, ast.Constant):
                    return None
                values.append(item.value)
            return tuple(values)
        if (
            isinstance(node, ast.Subscript)
            and cls._version_value(node.value) == _TARGET_VERSION
            and isinstance(node.slice, ast.Slice)
            and node.slice.lower is None
            and isinstance(node.slice.upper, ast.Constant)
            and isinstance(node.slice.upper.value, int)
            and node.slice.step is None
        ):
            return _TARGET_VERSION[: node.slice.upper.value]
        return None

    @staticmethod
    def _compare(
        left: tuple[object, ...], operator: ast.cmpop, right: tuple[object, ...]
    ) -> bool | None:
        if isinstance(operator, ast.Eq):
            return left == right
        if isinstance(operator, ast.NotEq):
            return left != right
        if isinstance(operator, ast.Lt):
            return left < right
        if isinstance(operator, ast.LtE):
            return left <= right
        if isinstance(operator, ast.Gt):
            return left > right
        if isinstance(operator, ast.GtE):
            return left >= right
        return None


def _import_references(
    path: Path, module: str, *, is_package: bool = False
) -> tuple[_ImportReference, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    walker = _ImportWalker(module, is_package=is_package)
    walker.visit(tree)
    return tuple(walker.references)
