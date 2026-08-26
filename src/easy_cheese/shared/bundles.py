"""Find the pure-Python sources one skill archive must contain."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from easy_cheese.shared.bundle_imports import _ImportReference, _import_references

_PACKAGE_NAME = "easy_cheese"
_SCHEMAS_PACKAGE_NAME = "easy_cheese_schemas"
_SKILLS_NAMESPACE = f"{_PACKAGE_NAME}.skills"
_SKILLS_PREFIX = f"{_SKILLS_NAMESPACE}."
_NATIVE_SUFFIXES = {".so", ".pyd", ".dylib"}
_APPROVED_DEPENDENCY_ROOTS = {
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


@dataclass(frozen=True)
class _BundleSource:
    module: str
    source: Path
    archive_path: PurePosixPath
    is_package: bool = False


class _ModuleIndex:
    def __init__(
        self,
        sources: tuple[_BundleSource, ...],
        *,
        native_root: Path | None = None,
    ) -> None:
        self._sources = {source.module: source for source in sources}
        if len(self._sources) != len(sources):
            raise ValueError("duplicate module in bundle source roots")
        self._native_root = native_root

    @classmethod
    def canonical(cls, source_root: Path) -> _ModuleIndex:
        sources: list[_BundleSource] = []
        for package_name in (_PACKAGE_NAME, _SCHEMAS_PACKAGE_NAME):
            package = source_root / package_name
            if not package.is_dir():
                continue
            for path in package.rglob("*.py"):
                # The archive builder stages package initializers separately.
                if path.name == "__init__.py":
                    continue
                relative = path.relative_to(source_root)
                sources.append(
                    _BundleSource(
                        ".".join(relative.with_suffix("").parts),
                        path,
                        PurePosixPath(*relative.parts),
                    )
                )
        return cls(tuple(sources))

    @classmethod
    def dependencies(cls, dependency_root: Path) -> _ModuleIndex:
        sources: list[_BundleSource] = []
        for root_name in sorted(_APPROVED_DEPENDENCY_ROOTS):
            module = dependency_root / f"{root_name}.py"
            if module.is_file():
                sources.append(
                    _BundleSource(root_name, module, PurePosixPath(module.name))
                )
            package = dependency_root / root_name
            if not package.is_dir():
                continue
            for path in package.rglob("*.py"):
                relative = path.relative_to(dependency_root)
                if any(part in {"__pycache__", "tests"} for part in relative.parts):
                    continue
                module_parts = relative.with_suffix("").parts
                is_package = module_parts[-1] == "__init__"
                if is_package:
                    module_parts = module_parts[:-1]
                sources.append(
                    _BundleSource(
                        ".".join(module_parts),
                        path,
                        PurePosixPath(*relative.parts),
                        is_package,
                    )
                )
        return cls(tuple(sources), native_root=dependency_root)

    def source_for(self, module: str) -> _BundleSource | None:
        return self._sources.get(module)

    def contains(self, module: str) -> bool:
        return module in self._sources

    def has_descendant(self, package: str) -> bool:
        prefix = f"{package}."
        return any(module.startswith(prefix) for module in self._sources)

    def has_native(self, module: str) -> bool:
        if self._native_root is None:
            return False
        base = self._native_root.joinpath(*module.split("."))
        for suffix in _NATIVE_SUFFIXES:
            if base.with_suffix(suffix).is_file():
                return True
            if (base / f"__init__{suffix}").is_file():
                return True
            if next(base.parent.glob(f"{base.name}.*{suffix}"), None) is not None:
                return True
            if next(base.glob(f"__init__.*{suffix}"), None) is not None:
                return True
        return False


class _ImportPolicy:
    def __init__(
        self,
        skill: str,
        sources: _ModuleIndex,
        dependencies: _ModuleIndex | None = None,
    ) -> None:
        self._sources = sources
        self._dependencies = dependencies
        self._owner_namespace = f"{_SKILLS_NAMESPACE}.{skill}"
        self._owner_prefix = f"{self._owner_namespace}."

    def dependency_source(
        self, importer: _BundleSource, reference: _ImportReference
    ) -> _BundleSource | None:
        name = reference.name
        # Ownership wins over lookup so another skill cannot enter this closure.
        if self._is_cross_skill_import(name):
            raise ValueError(f"cross-skill import in bundle: {name}")
        if candidate := self._sources.source_for(name):
            return candidate

        root_name = name.split(".", 1)[0]
        if root_name in _APPROVED_DEPENDENCY_ROOTS:
            return self._approved_dependency(reference)
        if self._has_adjacent_native(importer.source, name):
            raise ValueError(f"native ambient dependency in bundle: {name}")

        parent = name.rpartition(".")[0]
        if not reference.requires_module and (
            self._sources.contains(parent) or parent in _GENERATED_MODULES
        ):
            return None
        if name in _GENERATED_MODULES or root_name in _STDLIB_MODULES:
            return None
        if root_name in _INTERNAL_ROOTS:
            # Package imports have descendants but no indexed initializer source.
            if self._sources.has_descendant(name):
                return None
            raise ValueError(f"unresolved internal dependency: {name}")
        raise ValueError(f"ambient dependency in bundle: {name}")

    def _approved_dependency(self, reference: _ImportReference) -> _BundleSource | None:
        if self._dependencies is None:
            return None
        name = reference.name
        if candidate := self._dependencies.source_for(name):
            return candidate
        if self._dependencies.has_native(name):
            raise ValueError(f"native approved dependency in bundle: {name}")
        parent = name.rpartition(".")[0]
        if not reference.requires_module and self._dependencies.contains(parent):
            return None
        if self._dependencies.has_descendant(name):
            return None
        raise ValueError(f"approved dependency is unavailable: {name}")

    def _is_cross_skill_import(self, name: str) -> bool:
        return name.startswith(_SKILLS_PREFIX) and not (
            name == self._owner_namespace or name.startswith(self._owner_prefix)
        )

    @staticmethod
    def _has_adjacent_native(importer: Path, module: str) -> bool:
        stem = module.rsplit(".", 1)[-1]
        for suffix in _NATIVE_SUFFIXES:
            if (importer.parent / f"{stem}{suffix}").is_file():
                return True
            if next(importer.parent.glob(f"{stem}.*{suffix}"), None) is not None:
                return True
        return False


class _ClosureResolver:
    def __init__(self, policy: _ImportPolicy, entrypoint: _BundleSource) -> None:
        self._policy = policy
        self._pending = [entrypoint]
        self._included: set[_BundleSource] = set()

    def resolve(self) -> tuple[_BundleSource, ...]:
        while self._pending:
            source = self._pending.pop()
            if source in self._included:
                continue
            self._included.add(source)
            for reference in _import_references(
                source.source, source.module, is_package=source.is_package
            ):
                dependency = self._policy.dependency_source(source, reference)
                if dependency is not None:
                    self._pending.append(dependency)
        return tuple(sorted(self._included, key=lambda source: source.archive_path))


def _entrypoint_source(skill: str, sources: _ModuleIndex) -> _BundleSource:
    module = f"{_SKILLS_NAMESPACE}.{skill}.commands"
    entrypoint = sources.source_for(module)
    if entrypoint is None:
        raise ValueError(f"unknown Python skill: {skill}")
    return entrypoint


def _resolve_bundle_sources(skill: str, source_root: Path) -> tuple[Path, ...]:
    """Resolve one skill's reachable internal pure-Python modules."""
    sources = _ModuleIndex.canonical(source_root)
    entrypoint = _entrypoint_source(skill, sources)
    closure = _ClosureResolver(_ImportPolicy(skill, sources), entrypoint).resolve()
    return tuple(source.source for source in closure)


def _resolve_bundle_closure(
    skill: str, source_root: Path, dependency_root: Path
) -> tuple[_BundleSource, ...]:
    """Resolve archive paths for canonical and vendored Python sources."""
    sources = _ModuleIndex.canonical(source_root)
    dependencies = _ModuleIndex.dependencies(dependency_root)
    entrypoint = _entrypoint_source(skill, sources)
    policy = _ImportPolicy(skill, sources, dependencies)
    return _ClosureResolver(policy, entrypoint).resolve()
