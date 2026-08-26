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
_INIT_MODULE_NAME = "__init__"
_INIT_NAME = f"{_INIT_MODULE_NAME}.py"
_NATIVE_SUFFIXES = {".so", ".pyd", ".dylib"}
_ALLOWED_UNBUNDLED_EXTERNAL_ROOTS = {
    "attr",
    "attrs",
    "cattrs",
    "typing_extensions",
}
_GENERATED_MODULES = {
    "_compiled_phase_registry",
    "_schema_catalog",
    f"{_SCHEMAS_PACKAGE_NAME}._compiled_phase_registry",
    f"{_SCHEMAS_PACKAGE_NAME}._schema_catalog",
}
_INTERNAL_ROOTS = frozenset({_PACKAGE_NAME, _SCHEMAS_PACKAGE_NAME})
_STDLIB_MODULES = sys.stdlib_module_names


def _package_root(root: Path) -> Path:
    candidate = root / "src" / _PACKAGE_NAME
    return candidate if candidate.exists() else root


def _module_name(path: Path, source_root: Path) -> str:
    parts = path.relative_to(source_root).with_suffix("").parts
    if parts[-1] == _INIT_MODULE_NAME:
        parts = parts[:-1]
    return ".".join(parts)


def _modules(root: Path, shared_root: Path | None = None) -> dict[str, Path]:
    source_root = root.parent
    modules: dict[str, Path] = {}
    for package in (root, source_root / _SCHEMAS_PACKAGE_NAME):
        if not package.exists():
            continue
        for path in package.rglob("*.py"):
            if path.name == _INIT_NAME:
                continue
            modules[_module_name(path, source_root)] = path
            if package.name == _SCHEMAS_PACKAGE_NAME and path.parent == package:
                # Source-checkout helpers have flat fallback imports. Resolve
                # those aliases to packaged modules instead of vendoring copies.
                modules.setdefault(path.stem, path)
    if shared_root is not None and shared_root.is_dir():
        for path in shared_root.glob("*.py"):
            modules[path.stem] = path
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
    def __init__(
        self, root: Path, skill: str, shared_root: Path | None, entrypoint: Path
    ) -> None:
        self._root = root
        self._shared_root = shared_root
        self._modules = _modules(root, shared_root)
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
            module = self._module_name(path)
            for name in _import_names(path, module):
                self._classify_import(path, name)
        return tuple(sorted(self._included))

    def _module_name(self, path: Path) -> str:
        if self._shared_root is not None and path.parent == self._shared_root:
            return path.stem
        return _module_name(path, self._root.parent)

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
            (path.parent / f"{stem}{suffix}").exists()
            for suffix in _NATIVE_SUFFIXES
        ):
            raise ValueError(f"native ambient dependency in bundle: {name}")
        raise ValueError(f"ambient dependency in bundle: {name}")

    def _is_cross_skill_import(self, name: str) -> bool:
        return name.startswith(_SKILLS_PREFIX) and not (
            name == self._owner_namespace or name.startswith(self._owner_prefix)
        )


def minimal_closure(
    skill: str, root: Path, shared_root: Path | None = None
) -> tuple[Path, ...]:
    """Resolve one skill's reachable internal pure-Python modules."""
    root = _package_root(root)
    entrypoint = root / "skills" / skill / "commands.py"
    if not entrypoint.is_file():
        raise ValueError(f"unknown Python skill: {skill}")
    return _ClosureResolver(root, skill, shared_root, entrypoint).resolve()


__all__ = [
    "minimal_closure",
]
