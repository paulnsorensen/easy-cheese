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


def _validate_shiv_archive(archive: zipfile.ZipFile) -> None:
    names = set(archive.namelist())
    missing = sorted(SHIV_RUNTIME_MEMBERS - names)
    if missing:
        raise ValueError(f"not a Shiv archive: missing {', '.join(missing)}")
    if not any(name.startswith("site-packages/") for name in names):
        raise ValueError("not a Shiv archive: missing site-packages/")


def _site_packages_hash(
    archive: zipfile.ZipFile,
    *,
    normalize_wrappers: bool,
    include_record: bool,
) -> str:
    digest = hashlib.sha256()
    members = sorted(
        [
            info
            for info in archive.infolist()
            if info.filename.startswith("site-packages/")
            and not info.filename.endswith("/")
            and not info.filename.endswith(".pyc")
            and (include_record or not info.filename.endswith(".dist-info/RECORD"))
        ],
        key=lambda info: info.filename,
    )
    for info in members:
        data = archive.read(info)
        if normalize_wrappers and info.filename.startswith("site-packages/bin/"):
            data = _canonical_wrapper(data)
        relative = info.filename.removeprefix("site-packages/")
        digest.update(data)
        digest.update(relative.encode())
    return digest.hexdigest()


NATIVE_SUFFIXES = frozenset({".so", ".pyd", ".dylib"})

# First-party namespaces: the only sources this gate audits for import closure.
# Third-party wheels ship their own optional/extra integrations (e.g. cattrs'
# preconf converters for bson/cbor2/msgpack); those are pip's contract to keep
# consistent, not ours, and scanning them produces false positives for imports
# that are never exercised by any first-party code path.
FIRST_PARTY_PREFIXES = ("easy_cheese/", "easy_cheese_schemas/")


def _native_members(archive: zipfile.ZipFile) -> list[str]:
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


def _archive_module_index(
    archive: zipfile.ZipFile,
) -> tuple[frozenset[str], frozenset[str]]:
    """(file relpaths, directory relpaths) under site-packages/, source only."""
    files: set[str] = set()
    dirs: set[str] = set()
    for name in archive.namelist():
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


def check_import_closure(archive: zipfile.ZipFile) -> list[str]:
    """Every first-party import must resolve inside this archive's own closure.

    Catches unresolved deferred/function-body imports, ambient site-package
    dependencies absent from the shipped wheel set, cross-skill imports
    (another skill's package is simply not present in this archive), and
    deferred imports named only as a `Command(name, "module:attr")` string in
    the Command-manifest dispatch mechanism.
    """
    files, dirs = _archive_module_index(archive)
    stdlib = frozenset(sys.stdlib_module_names)

    @functools.cache
    def exports(relpath: str) -> frozenset[str]:
        tree = ast.parse(archive.read(f"site-packages/{relpath}").decode("utf-8"))
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
        source = archive.read(f"site-packages/{relpath}").decode("utf-8")
        tree = ast.parse(source)
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
        problems.append(f"isolated execution referenced the repository path: {combined.strip()}")
    return problems


def _declared_command_names(archive: zipfile.ZipFile) -> list[str]:
    """Every `Command("name", ...)` literal declared by this archive's own sources."""
    names: set[str] = set()
    for name in archive.namelist():
        if not name.startswith("site-packages/") or not name.endswith(".py"):
            continue
        relpath = name.removeprefix("site-packages/")
        if not relpath.startswith(FIRST_PARTY_PREFIXES):
            continue
        tree = ast.parse(archive.read(name).decode("utf-8"))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
                continue
            if node.func.id != "Command" or not node.args:
                continue
            first = node.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                names.add(first.value)
    return sorted(names)


def check_command_dispatch(pyz: Path, archive: zipfile.ZipFile) -> list[str]:
    """Every declared command must actually import its handler module.

    A bare argv only reaches the dispatcher's own usage branch (exit 2), so
    no handler import ever runs; invoke each declared command with --help to
    force the same importlib.import_module the real dispatch path takes.
    """
    interpreter = _isolated_interpreter()
    problems: list[str] = []
    for name in _declared_command_names(archive):
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


def _canonical_environment(data: bytes, *, canonical_build_id: str) -> bytes:
    """Normalize Shiv's host timestamp and derive a portable cache ID."""
    environment = cast(dict[str, object], json.loads(data))
    _ = environment.pop("built_at", None)
    environment["build_id"] = canonical_build_id
    return json.dumps(environment, sort_keys=True, separators=(",", ":")).encode()


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


def _manifest(data: bytes) -> dict[str, tuple[int, int] | bytes]:
    """Source member name -> (CRC, uncompressed size).

    Shiv generates RECORD files and host-specific interpreter paths from the
    local toolchain. Execution configuration and wrapper bodies remain signals;
    only those host-dependent fields are canonicalized.
    """
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        _validate_shiv_archive(archive)
        environment = cast(
            dict[str, object], json.loads(archive.read("environment.json"))
        )
        stored_build_id = environment.get("build_id")
        raw_build_id = _site_packages_hash(
            archive, normalize_wrappers=False, include_record=True
        )
        if stored_build_id != raw_build_id:
            raise ValueError(
                f"Shiv build_id does not match site-packages contents: stored {stored_build_id!r}, expected {raw_build_id}"
            )
        canonical_build_id = _site_packages_hash(
            archive, normalize_wrappers=True, include_record=False
        )
        manifest: dict[str, tuple[int, int] | bytes] = {}
        for info in archive.infolist():
            if info.filename.endswith(".dist-info/RECORD"):
                continue
            if info.filename == "environment.json":
                manifest[info.filename] = _canonical_environment(
                    archive.read(info), canonical_build_id=canonical_build_id
                )
            elif info.filename.startswith("site-packages/bin/"):
                manifest[info.filename] = _canonical_wrapper(archive.read(info))
            else:
                manifest[info.filename] = (info.CRC, info.file_size)
        return manifest


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
        *(p for p in REPO_ROOT.glob("skills/*/scripts/*") if p.is_file() and p.suffix != ".pyz"),
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
                violations.append(f"{relative}: references obsolete shared bundle common.pyz")
            elif skill is not None and archive_name != skill:
                violations.append(
                    f"{relative}: references {archive_name}.pyz, not its own {skill}.pyz"
                )
    return violations


def _committed(path: Path) -> bytes | None:
    """The blob at HEAD, or None when the bundle is newly added."""
    result = subprocess.run(
        ["git", "show", f"HEAD:{path.as_posix()}"],
        cwd=REPO_ROOT,
        capture_output=True,
    )
    return result.stdout if result.returncode == 0 else None


def _staged(path: Path) -> bytes | None:
    """The blob staged in the index, or None when nothing is staged there."""
    result = subprocess.run(
        ["git", "show", f":{path.as_posix()}"],
        cwd=REPO_ROOT,
        capture_output=True,
    )
    return result.stdout if result.returncode == 0 else None


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
            _ = subprocess.run(
                [sys.executable, str(worktree / "scripts" / "build_pyz.py")],
                cwd=worktree,
                check=True,
            )
            yield worktree
        finally:
            _ = subprocess.run(
                ["git", "worktree", "remove", "--force", str(worktree)],
                cwd=REPO_ROOT,
                check=False,
            )


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
    args = list(argv)
    if not args:
        return "head"
    if len(args) == 2 and args[0] == "--against" and args[1] in ("head", "index"):
        return args[1]
    raise SystemExit("usage: check_bundles.py [--against {head,index}]")


def _run_checks(against: str, bundle_root: Path) -> int:
    stale: list[str] = []
    for path in sorted(REPO_ROOT.glob("skills/*/scripts/common.pyz")):
        stale.append(f"  {path.relative_to(REPO_ROOT)} (obsolete shared bundle)")
    for reference_problem in check_pyz_references():
        stale.append(f"  {reference_problem}")
    committed_of = _staged if against == "index" else _committed
    checked = 0
    for path in sorted(bundle_root.glob(BUNDLE_GLOB)):
        relative = path.relative_to(bundle_root)
        committed = committed_of(relative)
        checked += 1
        data = path.read_bytes()
        problems: list[str] = []
        try:
            rebuilt_manifest = _manifest(data)
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                problems += [f"    ! native member: {name}" for name in _native_members(archive)]
                problems += [f"    ! {p}" for p in check_import_closure(archive)]
                problems += [f"    ! {p}" for p in check_command_dispatch(path, archive)]
            problems += [f"    ! {p}" for p in check_isolated_execution(path)]
            if committed is None:
                print(f"new Shiv bundle, nothing to compare: {relative}")
                if problems:
                    stale.append(f"  {relative}\n" + "\n".join(problems))
                continue
            committed_manifest = _manifest(committed)
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

    print(f".pyz bundles are current ({checked} checked, by canonical member content).")
    return 0


def main(argv: Sequence[str] = ()) -> int:
    against = _parse_against(argv)
    if against == "index":
        with _staged_index_rebuild() as worktree:
            return _run_checks("index", worktree)
    return _run_checks("head", REPO_ROOT)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
