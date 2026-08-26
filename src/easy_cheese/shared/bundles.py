"""Layout-derived bundle closure validation."""

from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path

_NATIVE_SUFFIXES = {".so", ".pyd", ".dylib"}
_PURE_EXTERNALS = {"attr", "attrs", "cattrs", "typing_extensions"}
_GENERATED_MODULES = {
    "_compiled_phase_registry",
    "_schema_catalog",
    "easy_cheese_schemas._compiled_phase_registry",
    "easy_cheese_schemas._schema_catalog",
}


def _package_root(root: Path) -> Path:
    candidate = root / "src" / "easy_cheese"
    return candidate if candidate.exists() else root


def bundle_name(skill: str) -> str:
    if not skill or "/" in skill or "\\" in skill:
        raise ValueError("invalid skill name")
    return f"{skill}.pyz"


def _module_name(path: Path, source_root: Path) -> str:
    parts = path.relative_to(source_root).with_suffix("").parts
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _modules(root: Path, shared_root: Path | None = None) -> dict[str, Path]:
    source_root = root.parent
    modules: dict[str, Path] = {}
    for package in (root, source_root / "easy_cheese_schemas"):
        if not package.exists():
            continue
        for path in package.rglob("*.py"):
            if path.name == "__init__.py":
                continue
            modules[_module_name(path, source_root)] = path
            if package.name == "easy_cheese_schemas" and path.parent == package:
                # Source-checkout helpers have flat fallback imports. Resolve
                # those aliases to packaged modules instead of vendoring copies.
                modules.setdefault(path.stem, path)
    if shared_root is not None and shared_root.is_dir():
        for path in shared_root.glob("*.py"):
            modules[path.stem] = path
    return modules


def _import_names(tree: ast.AST, module: str) -> tuple[str, ...]:
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


def minimal_closure(
    skill: str, root: Path, shared_root: Path | None = None
) -> tuple[Path, ...]:
    """Resolve one skill's reachable internal pure-Python modules."""
    root = _package_root(root)
    entrypoint = root / "skills" / skill / "commands.py"
    if not entrypoint.is_file():
        raise ValueError(f"unknown Python skill: {skill}")
    modules = _modules(root, shared_root)
    pending = [entrypoint]
    included: set[Path] = set()
    while pending:
        path = pending.pop()
        if path in included:
            continue
        if path.suffix in _NATIVE_SUFFIXES:
            raise ValueError(f"native module in bundle: {path.name}")
        included.add(path)
        if shared_root is not None and path.parent == shared_root:
            module = path.stem
        else:
            module = _module_name(path, root.parent)
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for name in _import_names(tree, module):
            if name.startswith("easy_cheese.skills.") and not name.startswith(
                f"easy_cheese.skills.{skill}"
            ):
                raise ValueError(f"cross-skill import in bundle: {name}")
            candidate = modules.get(name)
            if candidate is not None:
                pending.append(candidate)
                continue
            parent = name.rpartition(".")[0]
            if parent in modules or parent in _GENERATED_MODULES:
                continue
            root_name = name.split(".", 1)[0]
            if name in _GENERATED_MODULES or root_name in sys.stdlib_module_names:
                continue
            if root_name in _PURE_EXTERNALS:
                continue
            if root_name in {"easy_cheese", "easy_cheese_schemas"}:
                if any(module_name.startswith(name + ".") for module_name in modules):
                    continue
                raise ValueError(f"unresolved internal dependency: {name}")
            stem = name.rsplit(".", 1)[-1]
            if any(
                (path.parent / f"{stem}{suffix}").exists()
                for suffix in _NATIVE_SUFFIXES
            ):
                raise ValueError(f"native ambient dependency in bundle: {name}")
            raise ValueError(f"ambient dependency in bundle: {name}")
    return tuple(sorted(included))


__all__ = [
    "bundle_name",
    "minimal_closure",
]
