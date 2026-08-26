"""Layout-derived bundle closure validation."""

from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path

_PACKAGE_NAME = "easy_cheese"
_SCHEMAS_PACKAGE_NAME = "easy_cheese_schemas"
_SKILLS_NAMESPACE = f"{_PACKAGE_NAME}.skills"
_SKILLS_PREFIX = f"{_SKILLS_NAMESPACE}."
_NATIVE_SUFFIXES = {".so", ".pyd", ".dylib"}
_ALLOWED_UNBUNDLED_EXTERNAL_ROOTS = {
    "attr",
    "attrs",
    "cattrs",
    "typing_extensions",
}
# Bare names remain while schema sources retain common.pyz fallback imports.
_GENERATED_MODULES = {
    "_compiled_phase_registry",
    "_schema_catalog",
    f"{_SCHEMAS_PACKAGE_NAME}._compiled_phase_registry",
    f"{_SCHEMAS_PACKAGE_NAME}._schema_catalog",
}
_INTERNAL_ROOTS = frozenset({_PACKAGE_NAME, _SCHEMAS_PACKAGE_NAME})
_STDLIB_MODULES = sys.stdlib_module_names


def _module_name(path: Path, source_root: Path) -> str:
    return ".".join(path.relative_to(source_root).with_suffix("").parts)


def _modules(source_root: Path) -> dict[str, Path]:
    modules: dict[str, Path] = {}
    for package_name in (_PACKAGE_NAME, _SCHEMAS_PACKAGE_NAME):
        package = source_root / package_name
        if not package.is_dir():
            continue
        for path in package.rglob("*.py"):
            if path.name != "__init__.py":
                modules[_module_name(path, source_root)] = path
    return modules


def _import_names(path: Path, module: str) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    package = module.rpartition(".")[0]
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
            continue
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.level:
            target = "." * node.level + (node.module or "")
            try:
                imported = importlib.util.resolve_name(target, package)
            except (ImportError, ValueError) as exc:
                raise ValueError(f"invalid relative import in {module}") from exc
        else:
            imported = node.module or ""
        if imported:
            names.append(imported)
            names.extend(f"{imported}.{alias.name}" for alias in node.names)
    return tuple(names)


class _ClosureResolver:
    def __init__(self, source_root: Path, skill: str, entrypoint: Path) -> None:
        self._source_root = source_root
        self._modules = _modules(source_root)
        self._pending = [entrypoint]
        self._included: set[Path] = set()
        self._owner_namespace = f"{_SKILLS_NAMESPACE}.{skill}"
        self._owner_prefix = f"{self._owner_namespace}."

    def resolve(self) -> tuple[Path, ...]:
        while self._pending:
            path = self._pending.pop()
            if path in self._included:
                continue
            self._included.add(path)
            module = _module_name(path, self._source_root)
            for name in _import_names(path, module):
                self._classify_import(path, name)
        return tuple(sorted(self._included))


    def _classify_import(self, path: Path, name: str) -> None:
        if self._is_cross_skill_import(name):
            raise ValueError(f"cross-skill import in bundle: {name}")
        candidate = self._modules.get(name)
        if candidate is not None:
            self._pending.append(candidate)
            return
        parent = name.rpartition(".")[0]
        if parent in self._modules or parent in _GENERATED_MODULES:
            return
        root_name = name.split(".", 1)[0]
        if name in _GENERATED_MODULES or root_name in _STDLIB_MODULES:
            return
        if root_name in _ALLOWED_UNBUNDLED_EXTERNAL_ROOTS:
            return
        if root_name in _INTERNAL_ROOTS:
            if any(module_name.startswith(name + ".") for module_name in self._modules):
                return
            raise ValueError(f"unresolved internal dependency: {name}")
        stem = name.rsplit(".", 1)[-1]
        if any(
            (path.parent / f"{stem}{suffix}").exists() for suffix in _NATIVE_SUFFIXES
        ):
            raise ValueError(f"native ambient dependency in bundle: {name}")
        raise ValueError(f"ambient dependency in bundle: {name}")

    def _is_cross_skill_import(self, name: str) -> bool:
        return name.startswith(_SKILLS_PREFIX) and not (
            name == self._owner_namespace or name.startswith(self._owner_prefix)
        )


def _resolve_bundle_sources(skill: str, source_root: Path) -> tuple[Path, ...]:
    """Resolve one skill's reachable internal pure-Python modules."""
    package_root = source_root / _PACKAGE_NAME
    entrypoint = package_root / "skills" / skill / "commands.py"
    if not entrypoint.is_file():
        raise ValueError(f"unknown Python skill: {skill}")
    return _ClosureResolver(source_root, skill, entrypoint).resolve()
