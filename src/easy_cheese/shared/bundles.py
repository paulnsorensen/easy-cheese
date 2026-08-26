"""Find the pure-Python sources one skill archive must contain.

Two sets are staged into a skill's zipapp:

- First-party sources: every module reachable by a breadth-first import walk
  from the skill's `commands` entrypoint, restricted to
  `easy_cheese`/`easy_cheese_schemas`.
- Vendored trees: whole pinned dependency packages (attr, attrs, cattr,
  cattrs, typing_extensions), staged in full rather than walked, because
  reachability inside a vendored tree is not tracked. Every vendored module
  is still scanned so its own imports can be validated against a fixed
  table of declared optional imports: cattrs's preconf modules import
  third-party serializers unconditionally, but cattrs/__init__.py never
  imports preconf, so those modules are unreachable unless a first-party
  module imports one explicitly — and that explicit import is rejected.

Invariants:
- Only the owning skill's namespace may enter the closure; a sibling skill's
  package can never be pulled in, even via a deferred or relative import.
- Every reached name must resolve to a staged first-party module, a stdlib
  module, a generated fallback module, or a vendored root/declared optional
  import — anything else raises.
- No staged module may have a native (.so/.pyd/.dylib) sibling or member;
  zipimport cannot load native extensions from inside a zipapp.
- The vendored set is a fixed, audited table, not an inferred walk;
  requirements-vendor.txt pins the exact versions it describes.
- Vendored METADATA/dist-info is never staged (the glob is *.py only), so
  attr/__init__.py's lazily-resolved __version__ would raise
  PackageNotFoundError if ever exercised inside a built archive.
- The closure is sorted by archive path.
"""

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
# Each key is an import root, not a distribution: requirements-vendor.txt pins
# distributions by version, and one distribution can provide multiple import
# roots (the attrs wheel provides both `attr` and `attrs`; the cattrs wheel
# provides both `cattr` and `cattrs`). The value is the closure of sibling
# roots that importing this root pulls in, each staged as a whole tree.
_VENDORED_CLOSURES = {
    "attr": ("attr",),
    "attrs": ("attr", "attrs"),
    "cattr": ("attr", "attrs", "cattr", "cattrs", "typing_extensions"),
    "cattrs": ("attr", "attrs", "cattrs", "typing_extensions"),
    "typing_extensions": ("typing_extensions",),
}
_VENDORED_ROOTS = frozenset(
    root for closure in _VENDORED_CLOSURES.values() for root in closure
)
# Declared optional imports for vendored modules: cattrs's preconf modules
# import third-party serializers behind a try/except, none of which are
# staged, plus version-guarded stdlib backports (exceptiongroup pre-3.11,
# annotationlib pre-3.14). Audited against the real vendor/ tree;
# test_vendored_scan_matches_declared_optional_imports binds this table to
# `just vendor` output so drift raises instead of silently passing.
# annotationlib is interpreter-dependent: required on CI's pinned Python
# 3.12 (stdlib only since 3.14), invisible there — the binding holds
# because CI pins 3.12.
_VENDORED_OPTIONAL_IMPORTS: dict[str, tuple[str, ...]] = {
    "attr._compat": ("annotationlib",),
    "cattrs._compat": ("exceptiongroup",),
    "cattrs.preconf.bson": ("bson",),
    "cattrs.preconf.cbor2": ("cbor2",),
    "cattrs.preconf.msgpack": ("msgpack",),
    "cattrs.preconf.msgspec": ("msgspec",),
    "cattrs.preconf.orjson": ("orjson",),
    "cattrs.preconf.pyyaml": ("yaml",),
    "cattrs.preconf.tomlkit": ("tomlkit",),
    "cattrs.preconf.tomllib": ("tomli", "tomli_w"),
    "cattrs.preconf.ujson": ("ujson",),
    "typing_extensions": ("annotationlib",),
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


@dataclass(frozen=True)
class _ImportReference:
    name: str
    is_attribute_reference: bool


def _import_references(source: _BundleSource) -> tuple[_ImportReference, ...]:
    tree = ast.parse(
        source.source.read_text(encoding="utf-8"), filename=str(source.source)
    )
    package = source.module if source.is_package else source.module.rpartition(".")[0]
    references: list[_ImportReference] = []
    # Walk nested scopes so deferred imports are bundled without executing the module.
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            references.extend(
                _ImportReference(alias.name, is_attribute_reference=False)
                for alias in node.names
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
        references.append(_ImportReference(imported, is_attribute_reference=False))
        references.extend(
            _ImportReference(f"{imported}.{alias.name}", is_attribute_reference=True)
            for alias in node.names
            if alias.name != "*"
        )
    return tuple(references)


class _FirstPartySources:
    """Import-walked index of easy_cheese/easy_cheese_schemas modules."""

    def __init__(self, sources: tuple[_BundleSource, ...]) -> None:
        self._sources = {source.module: source for source in sources}
        if len(self._sources) != len(sources):
            raise ValueError("duplicate module in bundle source roots")

    @classmethod
    def load(cls, source_root: Path) -> _FirstPartySources:
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

    def source_for(self, module: str) -> _BundleSource | None:
        return self._sources.get(module)

    def contains(self, module: str) -> bool:
        return module in self._sources

    def has_descendant(self, package: str) -> bool:
        prefix = f"{package}."
        return any(module.startswith(prefix) for module in self._sources)


class _VendoredSources:
    """Whole pinned dependency trees, staged in full and validated by import scan.

    Every staged .py file is kept, including tests.py-style modules; only
    __pycache__ directories are filtered.
    """

    def __init__(
        self, sources: tuple[_BundleSource, ...], dependency_root: Path
    ) -> None:
        self._sources = {source.module: source for source in sources}
        if len(self._sources) != len(sources):
            raise ValueError(
                "duplicate module in vendored source roots:"
                " a vendored root ships both root.py and root/__init__.py"
            )
        self._dependency_root = dependency_root
        self._validate_imports()

    @classmethod
    def load(cls, dependency_root: Path) -> _VendoredSources:
        sources: list[_BundleSource] = []
        for root_name in sorted(_VENDORED_ROOTS):
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
                if "__pycache__" in relative.parts:
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
                    )
                )
        return cls(tuple(sources), dependency_root)

    def _validate_imports(self) -> None:
        for source in self._sources.values():
            for reference in _import_references(source):
                if reference.is_attribute_reference:
                    continue
                root = reference.name.split(".", 1)[0]
                if root in _STDLIB_MODULES or root in _VENDORED_ROOTS:
                    continue
                if root in _VENDORED_OPTIONAL_IMPORTS.get(source.module, ()):
                    continue
                raise ValueError(
                    f"undeclared vendored import in {source.module}: {reference.name}"
                )

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
        base = self._dependency_root / root
        for suffix in _NATIVE_SUFFIXES:
            # Exact-suffix file: root.so
            if base.with_name(f"{base.name}{suffix}").is_file():
                return True
            # ABI-tagged glob: root.cpython-312-darwin.so
            if next(base.parent.glob(f"{base.name}.*{suffix}"), None) is not None:
                return True
        # Recursive dir scan: root/ ships a native member anywhere in its tree.
        return base.is_dir() and any(
            path.suffix in _NATIVE_SUFFIXES
            for path in base.rglob("*")
            if path.is_file()
        )


@dataclass(frozen=True)
class _DependencyResolution:
    first_party: tuple[_BundleSource, ...] = ()
    vendored_roots: tuple[str, ...] = ()


class _ImportPolicy:
    def __init__(
        self,
        skill: str,
        sources: _FirstPartySources,
        vendored: _VendoredSources | None,
    ) -> None:
        self._sources = sources
        self._vendored = vendored
        self._owner_namespace = f"{_SKILLS_NAMESPACE}.{skill}"
        self._owner_prefix = f"{self._owner_namespace}."

    @classmethod
    def for_first_party_only(
        cls, skill: str, sources: _FirstPartySources
    ) -> _ImportPolicy:
        return cls(skill, sources, vendored=None)

    @classmethod
    def for_full_closure(
        cls, skill: str, sources: _FirstPartySources, vendored: _VendoredSources
    ) -> _ImportPolicy:
        return cls(skill, sources, vendored=vendored)

    def resolve(
        self, importer: _BundleSource, reference: _ImportReference
    ) -> _DependencyResolution:
        # Fixed precedence: ownership must reject before any lookup can
        # smuggle a sibling skill in; generated/stdlib/vendored short circuits
        # must all clear before the internal-root and native checks that
        # raise, so a resolvable import is never flagged ambient; the native
        # check runs last so every legitimate short circuit gets a chance to
        # clear the reference before a coincidental native sibling file
        # produces a false positive.
        name = reference.name
        # Ownership wins over lookup so another skill cannot enter this closure.
        if self._is_cross_skill_import(name):
            raise ValueError(f"cross-skill import in bundle: {name}")
        if candidate := self._sources.source_for(name):
            return _DependencyResolution(first_party=(candidate,))

        parent = name.rpartition(".")[0]
        if reference.is_attribute_reference and (
            self._sources.contains(parent) or parent in _GENERATED_MODULES
        ):
            return _DependencyResolution()

        root_name = name.split(".", 1)[0]
        if name in _GENERATED_MODULES or root_name in _STDLIB_MODULES:
            return _DependencyResolution()
        if root_name in _VENDORED_CLOSURES:
            if self._vendored is None:
                return _DependencyResolution()
            self._validate_vendored_reference(name, reference.is_attribute_reference)
            return _DependencyResolution(vendored_roots=_VENDORED_CLOSURES[root_name])
        if root_name in _INTERNAL_ROOTS:
            # Package imports have descendants but no indexed initializer source.
            if self._sources.has_descendant(name):
                return _DependencyResolution()
            raise ValueError(f"unresolved internal dependency: {name}")
        if not reference.is_attribute_reference and self._has_adjacent_native(
            importer.source, name
        ):
            raise ValueError(f"native ambient dependency in bundle: {name}")
        raise ValueError(f"ambient dependency in bundle: {name}")

    def _validate_vendored_reference(
        self, imported: str, is_attribute_reference: bool
    ) -> None:
        assert self._vendored is not None
        root = imported.split(".", 1)[0]
        closure = _VENDORED_CLOSURES[root]
        for required_root in closure:
            if not (
                self._vendored.contains(required_root)
                or self._vendored.has_descendant(required_root)
            ):
                raise ValueError(
                    f"vendored dependency tree is missing: {required_root}"
                )
            if self._vendored.has_native(required_root):
                raise ValueError(
                    f"native vendored dependency in bundle: {required_root}"
                )
        if not is_attribute_reference and not (
            self._vendored.contains(imported)
            or self._vendored.has_descendant(imported)
        ):
            raise ValueError(f"vendored submodule is missing: {imported}")
        # Module-level check: `import cattrs.preconf` doesn't reach preconf's
        # leaf modules (its __init__ imports none of them), so package-level
        # imports are not walked for descendants — only the exact imported
        # module name is checked. Vendored roots are excluded: their own
        # optional imports are version-guarded internally and safe to reach.
        if (
            not is_attribute_reference
            and imported not in _VENDORED_ROOTS
            and imported in _VENDORED_OPTIONAL_IMPORTS
        ):
            raise ValueError(
                f"vendored module has unstaged optional imports: {imported}"
            )

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


def _resolve_first_party_closure(
    policy: _ImportPolicy, entrypoint: _BundleSource
) -> tuple[tuple[_BundleSource, ...], frozenset[str]]:
    pending = [entrypoint]
    included: set[_BundleSource] = set()
    vendored_roots: set[str] = set()
    while pending:
        source = pending.pop()
        if source in included:
            continue
        included.add(source)
        for reference in _import_references(source):
            resolution = policy.resolve(source, reference)
            pending.extend(resolution.first_party)
            vendored_roots.update(resolution.vendored_roots)
    return tuple(included), frozenset(vendored_roots)


def _entrypoint_source(skill: str, sources: _FirstPartySources) -> _BundleSource:
    module = f"{_SKILLS_NAMESPACE}.{skill}.commands"
    entrypoint = sources.source_for(module)
    if entrypoint is None:
        raise ValueError(f"unknown Python skill: {skill}")
    return entrypoint


def _resolve_bundle_sources(skill: str, source_root: Path) -> tuple[Path, ...]:
    """Resolve one skill's reachable internal pure-Python modules."""
    sources = _FirstPartySources.load(source_root)
    entrypoint = _entrypoint_source(skill, sources)
    policy = _ImportPolicy.for_first_party_only(skill, sources)
    included, _ = _resolve_first_party_closure(policy, entrypoint)
    ordered = sorted(included, key=lambda source: source.archive_path)
    return tuple(source.source for source in ordered)


def _resolve_bundle_closure(
    skill: str, source_root: Path, dependency_root: Path
) -> tuple[_BundleSource, ...]:
    """Resolve archive paths for the first-party closure and vendored dependency trees."""
    sources = _FirstPartySources.load(source_root)
    vendored = _VendoredSources.load(dependency_root)
    entrypoint = _entrypoint_source(skill, sources)
    policy = _ImportPolicy.for_full_closure(skill, sources, vendored)
    first_party, vendored_roots = _resolve_first_party_closure(policy, entrypoint)
    # Vendored trees are staged whole once a root is touched, not walked file by file.
    staged_vendored = vendored.sources_for_roots(tuple(sorted(vendored_roots)))
    return tuple(
        sorted(first_party + staged_vendored, key=lambda source: source.archive_path)
    )