"""Find the pure-Python sources one skill archive must contain."""

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


# Build the index only from canonical source packages; never consult sys.path.
class _SourceModules:
    def __init__(self, source_root: Path) -> None:
        self._source_root = source_root
        self._paths = self._index()

    def module_name(self, path: Path) -> str:
        return ".".join(path.relative_to(self._source_root).with_suffix("").parts)

    def source_for(self, module: str) -> Path | None:
        return self._paths.get(module)

    def contains(self, module: str) -> bool:
        return module in self._paths

    def has_descendant(self, package: str) -> bool:
        prefix = f"{package}."
        return any(module.startswith(prefix) for module in self._paths)

    @staticmethod
    def has_adjacent_native(importer: Path, module: str) -> bool:
        stem = module.rsplit(".", 1)[-1]
        return any(
            (importer.parent / f"{stem}{suffix}").exists()
            for suffix in _NATIVE_SUFFIXES
        )

    def _index(self) -> dict[str, Path]:
        paths: dict[str, Path] = {}
        for package_name in (_PACKAGE_NAME, _SCHEMAS_PACKAGE_NAME):
            package = self._source_root / package_name
            if not package.is_dir():
                continue
            for path in package.rglob("*.py"):
                # The archive builder stages package initializers separately.
                if path.name != "__init__.py":
                    paths[self.module_name(path)] = path
        return paths


def _import_names(path: Path, module: str) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    package = module.rpartition(".")[0]
    names: list[str] = []
    # Walk nested scopes so deferred imports are bundled without executing the module.
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


class _ImportPolicy:
    def __init__(self, skill: str, sources: _SourceModules) -> None:
        self._sources = sources
        self._owner_namespace = f"{_SKILLS_NAMESPACE}.{skill}"
        self._owner_prefix = f"{self._owner_namespace}."

    def dependency_source(self, importer: Path, name: str) -> Path | None:
        # Ownership wins over lookup so another skill cannot enter this closure.
        if self._is_cross_skill_import(name):
            raise ValueError(f"cross-skill import in bundle: {name}")
        if candidate := self._sources.source_for(name):
            return candidate
        parent = name.rpartition(".")[0]
        if self._sources.contains(parent) or parent in _GENERATED_MODULES:
            return None
        root_name = name.split(".", 1)[0]
        if name in _GENERATED_MODULES or root_name in _STDLIB_MODULES:
            return None
        if root_name in _ALLOWED_UNBUNDLED_EXTERNAL_ROOTS:
            return None
        if root_name in _INTERNAL_ROOTS:
            # Package imports have descendants but no indexed initializer source.
            if self._sources.has_descendant(name):
                return None
            raise ValueError(f"unresolved internal dependency: {name}")
        if self._sources.has_adjacent_native(importer, name):
            raise ValueError(f"native ambient dependency in bundle: {name}")
        raise ValueError(f"ambient dependency in bundle: {name}")

    def _is_cross_skill_import(self, name: str) -> bool:
        return name.startswith(_SKILLS_PREFIX) and not (
            name == self._owner_namespace or name.startswith(self._owner_prefix)
        )


class _ClosureResolver:
    def __init__(
        self,
        sources: _SourceModules,
        policy: _ImportPolicy,
        entrypoint: Path,
    ) -> None:
        self._sources = sources
        self._policy = policy
        self._pending = [entrypoint]
        self._included: set[Path] = set()

    def resolve(self) -> tuple[Path, ...]:
        while self._pending:
            path = self._pending.pop()
            if path in self._included:
                continue
            self._included.add(path)
            module = self._sources.module_name(path)
            for name in _import_names(path, module):
                dependency = self._policy.dependency_source(path, name)
                if dependency is not None:
                    self._pending.append(dependency)
        return tuple(sorted(self._included))


def _resolve_bundle_sources(skill: str, source_root: Path) -> tuple[Path, ...]:
    """Resolve one skill's reachable internal pure-Python modules."""
    package_root = source_root / _PACKAGE_NAME
    entrypoint = package_root / "skills" / skill / "commands.py"
    if not entrypoint.is_file():
        raise ValueError(f"unknown Python skill: {skill}")
    sources = _SourceModules(source_root)
    policy = _ImportPolicy(skill, sources)
    return _ClosureResolver(sources, policy, entrypoint).resolve()
