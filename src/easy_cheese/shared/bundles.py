"""Find the pure-Python sources one skill archive must contain."""

from __future__ import annotations

import ast
import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

_PACKAGE_NAME = "easy_cheese"
_SCHEMAS_PACKAGE_NAME = "easy_cheese_schemas"
_SKILLS_NAMESPACE = f"{_PACKAGE_NAME}.skills"
_SKILLS_PREFIX = f"{_SKILLS_NAMESPACE}."
_NATIVE_SUFFIXES = {".so", ".pyd", ".dylib"}
# These are distribution-level closures, not inferred third-party import graphs.
# requirements-vendor.txt pins the exact versions this table describes.
_VENDORED_CLOSURES = {
    "attr": ("attr",),
    "attrs": ("attr", "attrs"),
    "cattrs": ("attr", "attrs", "cattrs", "typing_extensions"),
    "typing_extensions": ("typing_extensions",),
}
_VENDORED_ROOTS = frozenset(
    root for closure in _VENDORED_CLOSURES.values() for root in closure
)
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
    scan_imports: bool = True


@dataclass(frozen=True)
class _ImportReference:
    name: str
    requires_module: bool


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
        for root_name in sorted(_VENDORED_ROOTS):
            module = dependency_root / f"{root_name}.py"
            if module.is_file():
                sources.append(
                    _BundleSource(
                        root_name,
                        module,
                        PurePosixPath(module.name),
                        scan_imports=False,
                    )
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
                        is_package=is_package,
                        scan_imports=False,
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

    def sources_for_roots(self, roots: tuple[str, ...]) -> tuple[_BundleSource, ...]:
        return tuple(
            source
            for module, source in self._sources.items()
            if any(module == root or module.startswith(f"{root}.") for root in roots)
        )

    def has_native(self, root: str) -> bool:
        if self._native_root is None:
            return False
        base = self._native_root / root
        for suffix in _NATIVE_SUFFIXES:
            if base.with_suffix(suffix).is_file():
                return True
            if next(base.parent.glob(f"{base.name}.*{suffix}"), None) is not None:
                return True
        return base.is_dir() and any(
            path.suffix in _NATIVE_SUFFIXES
            for path in base.rglob("*")
            if path.is_file()
        )


def _import_references(source: _BundleSource) -> tuple[_ImportReference, ...]:
    tree = ast.parse(
        source.source.read_text(encoding="utf-8"), filename=str(source.source)
    )
    package = source.module if source.is_package else source.module.rpartition(".")[0]
    references: list[_ImportReference] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            references.extend(
                _ImportReference(alias.name, True) for alias in node.names
            )
            continue
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.level:
            target = "." * node.level + (node.module or "")
            try:
                imported = importlib.util.resolve_name(target, package)
            except (ImportError, ValueError) as exc:
                raise ValueError(f"invalid relative import in {source.module}") from exc
        else:
            imported = node.module or ""
        if not imported:
            continue
        references.append(_ImportReference(imported, True))
        references.extend(
            _ImportReference(f"{imported}.{alias.name}", False)
            for alias in node.names
            if alias.name != "*"
        )
    return tuple(references)


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

    def dependency_sources(
        self, importer: _BundleSource, reference: _ImportReference
    ) -> tuple[_BundleSource, ...]:
        name = reference.name
        if self._is_cross_skill_import(name):
            raise ValueError(f"cross-skill import in bundle: {name}")
        if candidate := self._sources.source_for(name):
            return (candidate,)

        root_name = name.split(".", 1)[0]
        if root_name in _VENDORED_CLOSURES:
            return self._vendored_sources(name, reference.requires_module)
        if self._has_adjacent_native(importer.source, name):
            raise ValueError(f"native ambient dependency in bundle: {name}")

        parent = name.rpartition(".")[0]
        if not reference.requires_module and (
            self._sources.contains(parent) or parent in _GENERATED_MODULES
        ):
            return ()
        if name in _GENERATED_MODULES or root_name in _STDLIB_MODULES:
            return ()
        if root_name in _INTERNAL_ROOTS:
            if self._sources.has_descendant(name):
                return ()
            raise ValueError(f"unresolved internal dependency: {name}")
        raise ValueError(f"ambient dependency in bundle: {name}")

    def _vendored_sources(
        self, imported: str, requires_module: bool
    ) -> tuple[_BundleSource, ...]:
        if self._dependencies is None:
            return ()
        root = imported.split(".", 1)[0]
        closure = _VENDORED_CLOSURES[root]
        if not (
            self._dependencies.contains(root) or self._dependencies.has_descendant(root)
        ):
            raise ValueError(f"approved dependency is unavailable: {root}")
        for required_root in closure:
            if not (
                self._dependencies.contains(required_root)
                or self._dependencies.has_descendant(required_root)
            ):
                raise ValueError(f"approved dependency is unavailable: {required_root}")
            if self._dependencies.has_native(required_root):
                raise ValueError(
                    f"native approved dependency in bundle: {required_root}"
                )
        if requires_module and not (
            self._dependencies.contains(imported)
            or self._dependencies.has_descendant(imported)
        ):
            raise ValueError(f"approved dependency is unavailable: {imported}")
        return self._dependencies.sources_for_roots(closure)

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
            if not source.scan_imports:
                continue
            for reference in _import_references(source):
                self._pending.extend(self._policy.dependency_sources(source, reference))
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
    """Resolve archive paths for canonical and fixed vendored dependency trees."""
    sources = _ModuleIndex.canonical(source_root)
    dependencies = _ModuleIndex.dependencies(dependency_root)
    entrypoint = _entrypoint_source(skill, sources)
    policy = _ImportPolicy(skill, sources, dependencies)
    return _ClosureResolver(policy, entrypoint).resolve()
