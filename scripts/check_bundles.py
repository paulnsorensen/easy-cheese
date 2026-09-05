#!/usr/bin/env python3
"""Check every committed .pyz still matches its sources, by content.

Two currency modes, selected with `--against {head,index}` (default head):

- `head` (CI): run after `build_pyz.py` has rebuilt the working tree from a
  HEAD checkout; compares each rebuilt bundle against the copy committed at
  HEAD.
- `index` (local/pre-commit): materializes the staged index into an
  isolated detached worktree, rebuilds every bundle there, and compares
  against the staged blob. The real working tree and index are never
  touched. Catches a staged source change whose regenerated bundle was
  never staged.

The comparison uses per-member content signatures rather than raw archive bytes.
Shiv assembles deterministic wheel members, but ZIP metadata and interpreter
paths can vary between toolchains. Host-specific fields are canonicalized; a
source edit that never made it into the committed bundle still fails this gate.

Every .pyz must carry Shiv's runtime markers; other zipapp formats are rejected.
"""

from __future__ import annotations

import argparse
import ast
import contextlib
import functools
import hashlib
import io
import json
import re
import subprocess
import sys
import tempfile
import zipfile
from collections.abc import Callable, Generator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast, override

REPO_ROOT = Path(__file__).resolve().parents[1]
BUNDLE_GLOB = "skills/*/scripts/*.pyz"

SHIV_RUNTIME_MEMBERS = frozenset(
    {
        "_bootstrap/__init__.py",
        "_bootstrap/environment.py",
        "_bootstrap/filelock.py",
        "_bootstrap/interpreter.py",
        "__main__.py",
        "environment.json",
    }
)


def _validate_shiv_names(names: set[str]) -> None:
    missing = sorted(SHIV_RUNTIME_MEMBERS - names)
    if missing:
        raise ValueError(f"not a Shiv archive: missing {', '.join(missing)}")
    if not any(name.startswith("site-packages/") for name in names):
        raise ValueError("not a Shiv archive: missing site-packages/")


def _site_packages_members(
    infos: Sequence[zipfile.ZipInfo],
) -> list[zipfile.ZipInfo]:
    return sorted(
        [
            info
            for info in infos
            if info.filename.startswith("site-packages/")
            and not info.filename.endswith("/")
            and not info.filename.endswith(".pyc")
        ],
        key=lambda info: info.filename,
    )


def _site_packages_hashes(
    infos: Sequence[zipfile.ZipInfo],
    read: Callable[[zipfile.ZipInfo], bytes],
) -> tuple[str, str]:
    """Return raw and canonical site-packages hashes in one traversal."""
    raw_digest = hashlib.sha256()
    canonical_digest = hashlib.sha256()
    for info in _site_packages_members(infos):
        data = read(info)
        relative = info.filename.removeprefix("site-packages/")
        raw_digest.update(data)
        raw_digest.update(relative.encode())
        if info.filename.endswith(".dist-info/RECORD"):
            continue
        if info.filename.startswith("site-packages/bin/"):
            data = _canonical_wrapper(data)
        canonical_digest.update(data)
        canonical_digest.update(relative.encode())
    return raw_digest.hexdigest(), canonical_digest.hexdigest()


NATIVE_SUFFIXES = frozenset({".so", ".pyd", ".dylib"})

# First-party namespaces: the only sources this gate audits for import closure.
# Third-party wheels ship their own optional/extra integrations (e.g. cattrs'
# preconf converters for bson/cbor2/msgpack); those are pip's contract to keep
# consistent, not ours, and scanning them produces false positives for imports
# that are never exercised by any first-party code path.
FIRST_PARTY_PREFIXES = ("easy_cheese/", "easy_cheese_schemas/")


def native_members(archive: zipfile.ZipFile) -> list[str]:
    """Native/compiled members (.so/.pyd/.dylib) shipped in the archive."""
    return sorted(
        name
        for name in archive.namelist()
        if name.startswith("site-packages/")
        and Path(name).suffix.lower() in NATIVE_SUFFIXES
    )


def _is_import_error_handler(handler: ast.ExceptHandler) -> bool:
    guard_names = {"ImportError", "ModuleNotFoundError"}
    if isinstance(handler.type, ast.Name):
        names = {handler.type.id}
    elif isinstance(handler.type, ast.Tuple):
        names = {item.id for item in handler.type.elts if isinstance(item, ast.Name)}
    else:
        names: set[str] = set()
    return bool(guard_names & names)


def _resolve_relative(package: str, level: int, module: str | None) -> str | None:
    """Absolute dotted name for a `from .[module] import ...` (level >= 1)."""
    bits = package.split(".") if package else []
    if level - 1 > len(bits):
        return None
    base = bits[: len(bits) - (level - 1)] if level > 1 else bits
    if module:
        base = [*base, *module.split(".")]
    return ".".join(base) if base else None


def _package_for(relpath: str) -> str:
    """The dotted `__package__` a module at this site-packages relpath sees."""
    parts = relpath.removesuffix(".py").split("/")
    return ".".join(parts[:-1])


class _ImportVisitor(ast.NodeVisitor):
    """Collect every runtime import, including deferred and guarded ones.

    Adapted from PR #460's closure resolver (ADR-003): here it verifies a
    *built* archive's own site-packages/, not a pre-build staging tree.
    """

    def __init__(self, package: str = "") -> None:
        self.package: str = package
        self.imports: set[tuple[str, bool]] = set()
        self.alternatives: list[tuple[_ImportVisitor, ...]] = []

    @classmethod
    def from_statements(
        cls, statements: list[ast.stmt], package: str = ""
    ) -> "_ImportVisitor":
        visitor = cls(package)
        for statement in statements:
            visitor.visit(statement)
        return visitor

    @override
    def visit_Import(self, node: ast.Import) -> None:
        self.imports.update((alias.name, False) for alias in node.names)

    @override
    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module
        if node.level != 0:
            module = _resolve_relative(self.package, node.level, node.module)
        if not module:
            return
        self.imports.update(
            (
                module if alias.name == "*" else f"{module}.{alias.name}",
                alias.name != "*",
            )
            for alias in node.names
        )

    @override
    def visit_Try(self, node: ast.Try) -> None:
        guarded = [
            handler for handler in node.handlers if _is_import_error_handler(handler)
        ]
        if not guarded:
            self.generic_visit(node)
            return
        self.alternatives.append(
            (
                self.from_statements(node.body, self.package),
                *(
                    self.from_statements(handler.body, self.package)
                    for handler in guarded
                ),
            )
        )
        for handler in node.handlers:
            if handler not in guarded:
                self.visit(handler)
        for statement in (*node.orelse, *node.finalbody):
            self.visit(statement)


def _unresolved_imports(
    visitor: _ImportVisitor,
    resolves: Callable[[str, bool], bool],
) -> set[str]:
    unresolved = {
        name for name, from_import in visitor.imports if not resolves(name, from_import)
    }
    for alternatives in visitor.alternatives:
        branch_problems = [
            _unresolved_imports(branch, resolves) for branch in alternatives
        ]
        if all(branch_problems):
            unresolved.update(*branch_problems)
    return unresolved


def _module_target_names(target: ast.expr | None) -> set[str]:
    if isinstance(target, ast.Name):
        return {target.id}
    if isinstance(target, (ast.List, ast.Tuple)):
        names: set[str] = set()
        for item in target.elts:
            names.update(_module_target_names(item))
        return names
    return set()


def _definite_module_bindings(statements: list[ast.stmt]) -> set[str]:
    """Names a module unconditionally binds at top level (best-effort)."""

    def sequence(nodes: list[ast.stmt]) -> set[str]:
        bindings: set[str] = set()
        for node in nodes:
            bindings.update(statement(node))
        return bindings

    def statement(node: ast.stmt) -> set[str]:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return {node.name}
        if isinstance(node, ast.Import):
            return {alias.asname or alias.name.split(".")[0] for alias in node.names}
        if isinstance(node, ast.ImportFrom):
            return {a.asname or a.name for a in node.names if a.name != "*"}
        if isinstance(node, ast.Assign):
            names: set[str] = set()
            for assign_target in node.targets:
                names.update(_module_target_names(assign_target))
            return names
        if isinstance(node, (ast.AnnAssign, ast.AugAssign)):
            return _module_target_names(node.target)
        if isinstance(node, ast.If):
            if isinstance(node.test, ast.Constant) and type(node.test.value) is bool:
                return sequence(node.body if node.test.value else node.orelse)
            if node.orelse:
                return sequence(node.body) & sequence(node.orelse)
            return set()
        if isinstance(node, ast.Try):
            normal = sequence(node.body) | sequence(node.orelse)
            paths = [normal] + [
                sequence(h.body) | ({h.name} if h.name else set())
                for h in node.handlers
            ]
            return paths[0].intersection(*paths[1:]) | sequence(node.finalbody)
        if isinstance(node, (ast.With, ast.AsyncWith)):
            with_names: set[str] = set()
            for item in node.items:
                with_names.update(_module_target_names(item.optional_vars))
            return sequence(node.body) | with_names
        return set()

    return sequence(statements)


def _module_index_from_names(
    names: set[str],
) -> tuple[frozenset[str], frozenset[str]]:
    """(file relpaths, directory relpaths) under site-packages/, source only."""
    files: set[str] = set()
    dirs: set[str] = set()
    for name in names:
        if not name.startswith("site-packages/") or name.startswith(
            "site-packages/bin/"
        ):
            continue
        relative = name.removeprefix("site-packages/")
        if not relative or relative.endswith("/"):
            continue
        if ".dist-info/" in relative or ".data/" in relative:
            continue
        files.add(relative)
        parts = relative.split("/")
        for depth in range(1, len(parts)):
            dirs.add("/".join(parts[:depth]))
    return frozenset(files), frozenset(dirs)


def _command_module_targets(tree: ast.Module) -> set[str]:
    """Module half of every `Command(name, "module:attr")` call in this tree.

    bundle_commands.dispatch resolves these via importlib at runtime, off a
    static string a plain import/from-import scan never sees (AC-7 finding 1).
    """
    targets: set[str] = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
            continue
        if node.func.id != "Command":
            continue
        args = [a for a in node.args if isinstance(a, ast.Constant)]
        if len(args) < 2 or not isinstance(args[1].value, str):
            continue
        module, separator, attribute = args[1].value.partition(":")
        if separator and module and attribute:
            targets.add(module)
    return targets


def _check_import_closure(analysis: _ArchiveAnalysis) -> list[str]:
    """Every first-party import must resolve inside this archive's own closure.

    Catches unresolved deferred/function-body imports, ambient site-package
    dependencies absent from the shipped wheel set, cross-skill imports
    (another skill's package is simply not present in this archive), and
    deferred imports named only as a `Command(name, "module:attr")` string in
    the Command-manifest dispatch mechanism.
    """
    files, dirs = analysis.files, analysis.dirs
    stdlib = frozenset(sys.stdlib_module_names)

    @functools.cache
    def exports(relpath: str) -> frozenset[str]:
        tree = analysis.module_tree(relpath)
        return frozenset(_definite_module_bindings(tree.body))

    def resolves(name: str, from_import: bool) -> bool:
        parts = name.split(".")
        if parts[0] in stdlib:
            return True
        if from_import and len(parts) >= 2:
            imported = "/".join(parts[:-1])
            module = f"{imported}.py"
            if module in files:
                return parts[-1] in exports(module)
            package_init = f"{imported}/__init__.py"
            if package_init in files:
                child = f"{imported}/{parts[-1]}"
                return (
                    f"{child}.py" in files
                    or child in dirs
                    or parts[-1] in exports(package_init)
                )
        package = parts[0]
        if package in dirs:
            if len(parts) == 1:
                return f"{package}/__init__.py" in files
            current = package
            for part in parts[1:-1]:
                current = f"{current}/{part}"
                if current not in dirs or f"{current}/__init__.py" not in files:
                    return False
            leaf = parts[-1]
            child = f"{current}/{leaf}"
            if f"{child}.py" in files or child in dirs:
                return True
            init = f"{current}/__init__.py"
            return init in files and leaf in exports(init)
        flat = f"{parts[0]}.py"
        if flat in files:
            return len(parts) == 1 or (
                from_import and len(parts) == 2 and parts[1] in exports(flat)
            )
        return False

    problems: list[str] = []
    for relpath in sorted(files):
        if not relpath.endswith(".py"):
            continue
        if not relpath.startswith(FIRST_PARTY_PREFIXES):
            continue
        tree = analysis.module_tree(relpath)
        visitor = _ImportVisitor(_package_for(relpath))
        visitor.visit(tree)
        for name in sorted(_unresolved_imports(visitor, resolves)):
            problems.append(f"unresolved import {name!r} in site-packages/{relpath}")
        for name in sorted(_command_module_targets(tree)):
            if not resolves(name, False):
                problems.append(
                    f"unresolved Command target {name!r} in site-packages/{relpath}"
                )
    return problems


def check_import_closure(archive: zipfile.ZipFile) -> list[str]:
    """Check first-party imports against one parsed archive analysis."""
    return _check_import_closure(
        _ArchiveAnalysis.from_archive(archive, parse_first_party=True)
    )


def _isolated_interpreter() -> str:
    """The base system interpreter, bypassing any active venv's site-packages.

    A venv resolves via pyvenv.cfg, not PYTHONPATH/VIRTUAL_ENV env vars, so
    stripping those env vars alone still leaks the venv's own site-packages
    (e.g. yaml resolving from .venv inside a run). Switching to the base
    executable sidesteps the venv prefix entirely.
    """
    if sys.prefix != sys.base_prefix:
        return cast(str, getattr(sys, "_base_executable"))
    return sys.executable


def _import_failure_problems(combined: str) -> list[str]:
    """Uncaught-exception signals only; excludes REPO_ROOT, which a handler's
    own --help usage banner legitimately prints (its own invocation path).
    """
    problems: list[str] = []
    if "ModuleNotFoundError" in combined or "ImportError" in combined:
        problems.append(f"failed to resolve imports: {combined.strip()}")
    if "Traceback (most recent call last)" in combined:
        problems.append(f"raised: {combined.strip()}")
    return problems


def check_isolated_execution(pyz: Path) -> list[str]:
    """Run the built archive from a scratch cwd with no PYTHONPATH or repo path.

    Proves the archive is self-contained: no reliance on the repository
    checkout, its cwd, an ambient PYTHONPATH, or a host venv's site-packages
    to resolve its own imports.
    """
    interpreter = _isolated_interpreter()
    with tempfile.TemporaryDirectory(prefix="easy-cheese-isolated-") as scratch:
        result = subprocess.run(
            [interpreter, "-I", str(pyz)],
            cwd=scratch,
            capture_output=True,
            text=True,
        )
    combined = result.stdout + result.stderr
    problems = [f"isolated execution {p}" for p in _import_failure_problems(combined)]
    if str(REPO_ROOT) in combined:
        problems.append(
            f"isolated execution referenced the repository path: {combined.strip()}"
        )
    return problems


def _literal_name(node: ast.expr | None) -> str | None:
    """The string value of one literal argument, or None."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _decorated_command_names(tree: ast.Module) -> set[str]:
    """Every `@bundle_command("name")` declaration in one source tree.

    Most manifests declare commands with `@bundle_command` plus
    `derive_command` rather than a `Command(...)` literal, so a literal-only
    scan finds no commands in those archives.
    """
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        for decorator in node.decorator_list:
            if not (
                isinstance(decorator, ast.Call)
                and isinstance(decorator.func, ast.Name)
                and decorator.func.id == "bundle_command"
                and decorator.args
            ):
                continue
            name = _literal_name(decorator.args[0])
            if name is not None:
                names.add(name)
    return names


def _declared_command_names_from_trees(
    trees: Sequence[ast.Module],
) -> list[str]:
    """Every command name declared in first-party source trees.

    Covers both declaration forms: the `Command("name", ...)` literal and the
    `@bundle_command("name")` decorator.
    """
    names: set[str] = set()
    for tree in trees:
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
                continue
            if node.func.id != "Command" or not node.args:
                continue
            name = _literal_name(node.args[0])
            if name is not None:
                names.add(name)
        names |= _decorated_command_names(tree)
    return sorted(names)


def _check_command_dispatch(pyz: Path, command_names: Sequence[str]) -> list[str]:
    """Every declared command must actually import its handler module.

    A bare argv only reaches the dispatcher's own usage branch (exit 2), so
    no handler import ever runs; invoke each declared command with --help to
    force the same importlib.import_module the real dispatch path takes.
    """
    interpreter = _isolated_interpreter()
    problems: list[str] = []
    for name in command_names:
        with tempfile.TemporaryDirectory(prefix="easy-cheese-isolated-") as scratch:
            result = subprocess.run(
                [interpreter, "-I", str(pyz), name, "--help"],
                cwd=scratch,
                capture_output=True,
                text=True,
            )
        combined = result.stdout + result.stderr
        problems.extend(
            f"command {name!r} {p}" for p in _import_failure_problems(combined)
        )
    return problems


def _canonical_environment_values(
    environment: dict[str, object], *, canonical_build_id: str
) -> bytes:
    """Normalize Shiv's host timestamp and derive a portable cache ID."""
    normalized = dict(environment)
    _ = normalized.pop("built_at", None)
    normalized["build_id"] = canonical_build_id
    return json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode()


def _canonical_wrapper(data: bytes) -> bytes:
    """Normalize only the interpreter token, retaining shebang arguments."""

    def replace(match: re.Match[bytes]) -> bytes:
        line = match.group(0)
        command_line = line[2:]
        if command_line.startswith(b"/usr/bin/env "):
            command_line = command_line[len(b"/usr/bin/env ") :]
        token, separator, args = command_line.partition(b" ")
        executable = token.rsplit(b"/", 1)[-1]
        if not re.fullmatch(rb"python(?:\d+(?:\.\d+)*)?", executable):
            return line
        suffix = separator + args
        return b"#!<python>" + suffix

    return re.sub(rb"(?m)^#![^\n]*", replace, data, count=1)


@dataclass
class _ArchiveAnalysis:
    archive: zipfile.ZipFile
    infos: tuple[zipfile.ZipInfo, ...]
    names: frozenset[str]
    files: frozenset[str]
    dirs: frozenset[str]
    native_members: tuple[str, ...]
    info_by_name: dict[str, zipfile.ZipInfo]
    member_data: dict[int, bytes] = field(default_factory=dict)
    module_trees: dict[str, ast.Module] = field(default_factory=dict)
    command_names: tuple[str, ...] = ()
    manifest: dict[str, tuple[int, int] | bytes] | None = None

    @classmethod
    def from_archive(
        cls,
        archive: zipfile.ZipFile,
        *,
        validate_shiv: bool = False,
        parse_first_party: bool = False,
    ) -> "_ArchiveAnalysis":
        infos = tuple(archive.infolist())
        names = frozenset(info.filename for info in infos)
        if validate_shiv:
            _validate_shiv_names(set(names))
        files, dirs = _module_index_from_names(set(names))
        analysis = cls(
            archive=archive,
            infos=infos,
            names=names,
            files=files,
            dirs=dirs,
            native_members=tuple(native_members(archive)),
            info_by_name={info.filename: info for info in infos},
        )
        if validate_shiv:
            raw_build_id, canonical_build_id = _site_packages_hashes(
                infos, analysis.read
            )
            environment = cast(
                dict[str, object], json.loads(analysis.read("environment.json"))
            )
            stored_build_id = environment.get("build_id")
            if stored_build_id != raw_build_id:
                raise ValueError(
                    f"Shiv build_id does not match site-packages contents: stored {stored_build_id!r}, expected {raw_build_id}"
                )
            manifest: dict[str, tuple[int, int] | bytes] = {}
            for info in infos:
                if info.filename.endswith(".dist-info/RECORD"):
                    continue
                if info.filename == "environment.json":
                    manifest[info.filename] = _canonical_environment_values(
                        environment, canonical_build_id=canonical_build_id
                    )
                elif info.filename.startswith("site-packages/bin/"):
                    manifest[info.filename] = _canonical_wrapper(analysis.read(info))
                else:
                    manifest[info.filename] = (info.CRC, info.file_size)
            analysis.manifest = manifest
        if parse_first_party:
            analysis._parse_first_party()
        return analysis

    def read(self, member: str | zipfile.ZipInfo) -> bytes:
        info = (
            member
            if isinstance(member, zipfile.ZipInfo)
            else self.info_by_name.get(member)
        )
        if info is None:
            return self.archive.read(member)
        key = id(info)
        if key not in self.member_data:
            self.member_data[key] = self.archive.read(info)
        return self.member_data[key]

    def module_tree(self, relpath: str) -> ast.Module:
        if relpath not in self.module_trees:
            self.module_trees[relpath] = ast.parse(
                self.read(f"site-packages/{relpath}").decode("utf-8")
            )
        return self.module_trees[relpath]

    def _parse_first_party(self) -> None:
        for info in self.infos:
            name = info.filename
            if not name.startswith("site-packages/") or not name.endswith(".py"):
                continue
            relpath = name.removeprefix("site-packages/")
            if not relpath.startswith(FIRST_PARTY_PREFIXES):
                continue
            self.module_trees[relpath] = ast.parse(self.read(info).decode("utf-8"))
        self.command_names = tuple(
            _declared_command_names_from_trees(self._dispatcher_trees())
        )

    def _dispatcher_trees(self) -> tuple[ast.Module, ...]:
        """The parsed trees that declare this archive's own command manifest.

        Shiv records the dispatcher module in `environment.json`. An archive
        also ships other skills' command modules, so a scan of every tree
        would declare commands this archive does not dispatch. Archives
        without `environment.json` fall back to every parsed tree.
        """
        if "environment.json" not in self.names:
            return tuple(self.module_trees.values())
        environment = cast(
            dict[str, object], json.loads(self.read("environment.json"))
        )
        entry_point = environment.get("entry_point")
        if not isinstance(entry_point, str):
            return ()
        module = entry_point.partition(":")[0]
        relpath = module.replace(".", "/") + ".py"
        tree = self.module_trees.get(relpath)
        return () if tree is None else (tree,)


def bundle_manifest(data: bytes) -> dict[str, tuple[int, int] | bytes]:
    """Source member name -> (CRC, uncompressed size)."""
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        analysis = _ArchiveAnalysis.from_archive(archive, validate_shiv=True)
    if analysis.manifest is None:
        raise ValueError("Shiv archive manifest was not computed")
    return analysis.manifest


_PYZ_REFERENCE = re.compile(r"[\w-]+\.pyz")

# ultracook is a retired skill: its SKILL.md documents that no ultracook.pyz
# is published and that runtime moved into cook.pyz, purely as retirement
# prose (see skills/ultracook/SKILL.md's "What did not move" section) -- not
# an instruction for any code path to invoke another skill's archive.
_RETIRED_REDIRECT_SKILLS = frozenset({"ultracook"})

# This file is the scan's own implementation: its stale-shared-bundle glob
# legitimately names the retired common.pyz, which would otherwise trip its
# own "references obsolete shared bundle" rule.
_SELF_PATH = Path(__file__).resolve()


def _owning_skill(path: Path) -> str | None:
    """The skill a file may reference its own .pyz for, or None if none applies."""
    parts = path.relative_to(REPO_ROOT).parts
    if parts[0] == "skills":
        return parts[1]
    if parts[:3] == ("src", "easy_cheese", "skills"):
        return parts[3].replace("_", "-")
    if parts[:4] == ("website", "content", "docs", "skills") and len(parts) == 5:
        return path.stem
    return None


def _pyz_reference_roots() -> list[Path]:
    return [
        *REPO_ROOT.glob("skills/**/*.md"),
        *(
            p
            for p in REPO_ROOT.glob("skills/*/scripts/*")
            if p.is_file() and p.suffix != ".pyz"
        ),
        *(
            p
            for p in (REPO_ROOT / "src").rglob("*")
            if p.is_file() and "__pycache__" not in p.parts
        ),
        *REPO_ROOT.glob("website/content/docs/**/*.md"),
        *(p for p in (REPO_ROOT / "scripts").glob("*.py") if p.resolve() != _SELF_PATH),
    ]


def check_pyz_references() -> list[str]:
    """Skill docs and sources may only name their own .pyz archive.

    A skill's docs or source naming another skill's bundle is either a stale
    doc (the skill was renamed/merged) or a real cross-skill import that
    check_import_closure cannot see (it only audits one archive at a time).
    """
    violations: list[str] = []
    for path in sorted(set(_pyz_reference_roots())):
        skill = _owning_skill(path)
        if skill in _RETIRED_REDIRECT_SKILLS:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for match in _PYZ_REFERENCE.finditer(text):
            archive_name = match.group(0).removesuffix(".pyz")
            relative = path.relative_to(REPO_ROOT)
            if archive_name == "common":
                violations.append(
                    f"{relative}: references obsolete shared bundle common.pyz"
                )
            elif skill is not None and archive_name != skill:
                violations.append(
                    f"{relative}: references {archive_name}.pyz, not its own {skill}.pyz"
                )
    return violations


def _baseline_blobs(against: str, paths: Sequence[Path]) -> dict[Path, bytes]:
    """Read every baseline bundle blob through one Git batch process."""
    if not paths:
        return {}
    prefix = ":" if against == "index" else "HEAD:"
    requests = [f"{prefix}{path.as_posix()}" for path in paths]
    result = subprocess.run(
        ["git", "cat-file", "--batch"],
        cwd=REPO_ROOT,
        input=("\n".join(requests) + "\n").encode(),
        capture_output=True,
    )
    if result.returncode != 0:
        raise ValueError(
            "git cat-file --batch failed: " + result.stderr.decode(errors="replace").strip()
        )

    blobs: dict[Path, bytes] = {}
    output = result.stdout
    offset = 0
    for path in paths:
        line_end = output.find(b"\n", offset)
        if line_end < 0:
            raise ValueError("git cat-file --batch returned malformed output")
        header = output[offset:line_end].split()
        offset = line_end + 1
        if len(header) >= 2 and header[1] == b"missing":
            continue
        if len(header) != 3 or header[1] != b"blob":
            raise ValueError("git cat-file --batch returned a non-blob object")
        try:
            size = int(header[2])
        except ValueError as exc:
            raise ValueError("git cat-file --batch returned an invalid size") from exc
        end = offset + size
        if output[end : end + 1] != b"\n":
            raise ValueError("git cat-file --batch returned truncated data")
        blobs[path] = output[offset:end]
        offset = end + 1
    return blobs


@contextlib.contextmanager
def _staged_index_rebuild() -> Generator[Path]:
    """Materialize the staged index into an isolated detached worktree,
    rebuild every bundle there, and yield the worktree root with the
    rebuilt bundles on disk.

    `git write-tree` snapshots the index exactly as staged, `git
    commit-tree` wraps that snapshot as a throwaway parentless commit, and
    `git worktree add --detach` checks it out into a scratch directory that
    `build_pyz.py` can rebuild from -- it resolves its own root from its own
    `__file__`, so running the worktree's copy naturally scopes the rebuild
    there. The real working tree and index are never touched, so a Shiv
    rebuild that is not byte-reproducible, or a build failure, can never
    strand this check mid-mutation.
    """
    tree = subprocess.run(
        ["git", "write-tree"], cwd=REPO_ROOT, capture_output=True, check=True, text=True
    ).stdout.strip()
    commit = subprocess.run(
        ["git", "commit-tree", tree, "-m", "check_bundles: staged index snapshot"],
        cwd=REPO_ROOT,
        capture_output=True,
        check=True,
        text=True,
    ).stdout.strip()
    with tempfile.TemporaryDirectory(prefix="easy-cheese-index-rebuild-") as scratch:
        worktree = Path(scratch) / "worktree"
        _ = subprocess.run(
            ["git", "worktree", "add", "--detach", "--quiet", str(worktree), commit],
            cwd=REPO_ROOT,
            check=True,
        )
        try:
            build_command = [sys.executable, str(worktree / "scripts" / "build_pyz.py")]
            runtime_requirements = worktree / "requirements" / "runtime.txt"
            build_requirements = worktree / "requirements-build.txt"
            if runtime_requirements.is_file() and build_requirements.is_file():
                build_command = [
                    "uv",
                    "run",
                    "--no-project",
                    "--with-requirements",
                    str(runtime_requirements),
                    "--with-requirements",
                    str(build_requirements),
                    "python3",
                    str(worktree / "scripts" / "build_pyz.py"),
                ]
            _ = subprocess.run(build_command, cwd=worktree, check=True)
            yield worktree
        finally:
            removal = subprocess.run(
                ["git", "worktree", "remove", "--force", str(worktree)],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
            )
            if removal.returncode != 0:
                detail = removal.stderr.strip()
                message = f"could not remove the temporary worktree: {detail}"
                # Never mask the error that caused the early exit.
                if sys.exception() is None:
                    raise ValueError(message)
                print(f"::warning::{message}", file=sys.stderr)


def _describe(
    rebuilt: dict[str, tuple[int, int] | bytes],
    committed: dict[str, tuple[int, int] | bytes],
) -> list[str]:
    problems: list[str] = []
    for name in sorted(set(rebuilt) - set(committed)):
        problems.append(f"    + {name} (built, not in the committed bundle)")
    for name in sorted(set(committed) - set(rebuilt)):
        problems.append(f"    - {name} (committed, no longer built)")
    for name in sorted(set(rebuilt) & set(committed)):
        if rebuilt[name] != committed[name]:
            problems.append(f"    ~ {name} (content differs)")
    return problems


def _parse_against(argv: Sequence[str]) -> str:
    parser = argparse.ArgumentParser(
        prog="check_bundles.py",
        description="Check every committed .pyz still matches its sources, by content.",
    )
    _ = parser.add_argument(
        "--against",
        choices=("head", "index"),
        default="head",
        help="compare against HEAD or the staged index (default: head)",
    )
    return cast(str, parser.parse_args(argv).against)


def _run_checks(against: str, bundle_root: Path) -> int:
    stale: list[str] = []
    for path in sorted(REPO_ROOT.glob("skills/*/scripts/common.pyz")):
        stale.append(f"  {path.relative_to(REPO_ROOT)} (obsolete shared bundle)")
    for reference_problem in check_pyz_references():
        stale.append(f"  {reference_problem}")
    paths = [
        path
        for path in sorted(bundle_root.glob(BUNDLE_GLOB))
        if path.name != "common.pyz"
    ]
    relatives = [path.relative_to(bundle_root) for path in paths]
    baseline = _baseline_blobs(against, relatives)
    compared = sum(1 for relative in relatives if baseline.get(relative) is not None)
    new = len(relatives) - compared
    for path, relative in zip(paths, relatives, strict=True):
        committed = baseline.get(relative)
        data = path.read_bytes()
        problems: list[str] = []
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                analysis = _ArchiveAnalysis.from_archive(
                    archive, validate_shiv=True, parse_first_party=True
                )
                if analysis.manifest is None:
                    raise ValueError("Shiv archive manifest was not computed")
                rebuilt_manifest = analysis.manifest
                problems += [
                    f"    ! native member: {name}" for name in analysis.native_members
                ]
                problems += [f"    ! {p}" for p in _check_import_closure(analysis)]
                problems += [
                    f"    ! {p}"
                    for p in _check_command_dispatch(path, analysis.command_names)
                ]
            problems += [f"    ! {p}" for p in check_isolated_execution(path)]
            if committed is None:
                print(f"new Shiv bundle, nothing to compare: {relative}")
                if problems:
                    stale.append(f"  {relative}\n" + "\n".join(problems))
                continue
            with zipfile.ZipFile(io.BytesIO(committed)) as archive:
                committed_analysis = _ArchiveAnalysis.from_archive(
                    archive, validate_shiv=True
                )
                if committed_analysis.manifest is None:
                    raise ValueError("Shiv archive manifest was not computed")
                committed_manifest = committed_analysis.manifest
            problems += _describe(rebuilt_manifest, committed_manifest)
        except (ValueError, KeyError, json.JSONDecodeError, zipfile.BadZipFile) as exc:
            problems.append(f"    ! bundle metadata invalid: {exc}")
        if problems:
            stale.append(f"  {relative}\n" + "\n".join(problems))

    if stale:
        print(
            "::error::.pyz bundles are invalid or stale; run 'python3 scripts/build_pyz.py' and commit the generated skills/*/scripts/*.pyz files."
        )
        print("\n".join(stale))
        return 1

    summary = f"{compared} compared against the baseline"
    if new:
        summary += f", {new} new"
    print(f".pyz bundles are current ({summary}, by canonical member content).")
    return 0


def main(argv: Sequence[str] = ()) -> int:
    against = _parse_against(argv)
    try:
        if against == "index":
            with _staged_index_rebuild() as worktree:
                return _run_checks("index", worktree)
        return _run_checks("head", REPO_ROOT)
    except ValueError as exc:
        print(f"::error::could not read the baseline bundles: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
