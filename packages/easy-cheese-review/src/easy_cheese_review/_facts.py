"""Compute the compat, dependencies, tests, and scope facts for a change.

The facts read two trees: `head` (the changed tree) and an optional `base`.
All paths are POSIX paths relative to the tree root. A changed path that is a
symbolic link, that leaves its tree, or that is not a regular file is skipped,
so the scan never reads a file outside the tree.
"""

from __future__ import annotations

import ast
import posixpath
import re
import sys
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path, PurePosixPath

from easy_cheese_review._model import Fact

JsonObject = dict[str, object]

PYTHON_SUFFIXES = frozenset({".py"})
SCRIPT_SUFFIXES = frozenset({".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"})
CODE_SUFFIXES = PYTHON_SUFFIXES | SCRIPT_SUFFIXES

_TEST_DIRS = frozenset({"tests", "test", "__tests__", "spec", "specs"})
_TEST_FILE = re.compile(r"^test_.+\.py$|^.+_test\.py$|^conftest\.py$|^.+\.(test|spec)\.[cm]?[jt]sx?$")
_TEST_AFFIX = re.compile(r"^test_|_test$")

# Each manifest maps to the lockfiles that pin it, in order of preference.
MANIFEST_LOCKFILES: Mapping[str, tuple[str, ...]] = {
    "pyproject.toml": ("uv.lock", "poetry.lock", "pdm.lock"),
    "Pipfile": ("Pipfile.lock",),
    "requirements.in": ("requirements.txt",),
    "package.json": ("pnpm-lock.yaml", "package-lock.json", "yarn.lock", "bun.lock", "bun.lockb"),
    "Cargo.toml": ("Cargo.lock",),
    "go.mod": ("go.sum",),
    "Gemfile": ("Gemfile.lock",),
}
LOCKFILES = frozenset(lock for locks in MANIFEST_LOCKFILES.values() for lock in locks)

_NODE_BUILTINS = frozenset(
    {
        "assert", "async_hooks", "buffer", "child_process", "cluster", "console", "crypto",
        "dgram", "diagnostics_channel", "dns", "events", "fs", "http", "http2", "https",
        "inspector", "module", "net", "os", "path", "perf_hooks", "process", "punycode",
        "querystring", "readline", "repl", "stream", "string_decoder", "timers", "tls",
        "tty", "url", "util", "v8", "vm", "worker_threads", "zlib",
    }
)
_SCRIPT_SOURCE = re.compile(r"""(?:\bfrom\s*|^\s*import\s*)["']([^"']+)["']""")
_EXPORT_CLAUSE = re.compile(r"\{([^}]*)\}")
# `export * from "m"` (group 2) or `export * as ns from "m"` (groups 1 and 2).
_EXPORT_STAR = re.compile(r"""^export\s+\*\s+(?:as\s+([\w$]+)\s+)?from\s+(['"][^'"]+['"])""")


def normalize_changed(changed: Iterable[str]) -> list[str]:
    """Validate changed paths as relative POSIX paths, without duplicates.

    Git never reports an absolute path or a `..` segment, so either one is a
    caller error. A backslash is a legal character in a POSIX file name.
    """
    seen: dict[str, None] = {}
    for raw in changed:
        path = PurePosixPath(raw)
        if not raw or path.is_absolute() or ".." in path.parts:
            raise ValueError(f"changed path must be relative and inside the tree: {raw!r}")
        seen.setdefault(path.as_posix(), None)
    return list(seen)


def tree_files(root: Path, changed: Sequence[str], suffixes: frozenset[str]) -> list[str]:
    """Return the changed paths that are regular files inside `root`."""
    resolved_root = root.resolve()
    kept: list[str] = []
    for path in changed:
        if PurePosixPath(path).suffix not in suffixes:
            continue
        candidate = root / path
        if candidate.is_symlink() or not candidate.is_file():
            continue
        if not candidate.resolve().is_relative_to(resolved_root):
            continue
        kept.append(path)
    return kept


# --- tests ---------------------------------------------------------------


def is_test_path(path: str) -> bool:
    parts = PurePosixPath(path).parts
    return any(part in _TEST_DIRS for part in parts[:-1]) or bool(_TEST_FILE.match(parts[-1]))


def _subject(path: str) -> str:
    """Return the name a source file and its test file share."""
    pure = PurePosixPath(path)
    stem = pure.name.split(".")[0]
    if stem in {"__init__", "index"}:
        stem = pure.parent.name
    return _TEST_AFFIX.sub("", stem).lstrip("_").lower()


def _covers(test_subject: str, source_subject: str) -> bool:
    """A test covers a source when its subject equals or ends with `_<source>`."""
    return test_subject == source_subject or test_subject.endswith("_" + source_subject)


def tests_fact(code_paths: Sequence[str]) -> Fact:
    """Report changed source files that have no matching test file in head.

    `code_paths` holds the changed code files that exist in head, so a deleted
    test never counts as coverage.
    """
    sources = [path for path in code_paths if not is_test_path(path)]
    tested = {_subject(path) for path in code_paths if is_test_path(path)}
    untested = [
        path for path in sources if not any(_covers(test, _subject(path)) for test in tested)
    ]
    return Fact("yes" if untested else "no", {"untested": untested, "sources": len(sources)})


# --- compat --------------------------------------------------------------


def _export_names(path: str, items: Iterable[JsonObject]) -> set[str]:
    """Return the public names a module exports, as an importer sees them."""
    python = _is_python(path)
    names: set[str] = set()
    for item in items:
        name = item.get("name")
        if item.get("isExported") is not True or not isinstance(name, str):
            continue
        if python and name.startswith("_"):
            continue
        signature = item.get("signature")
        signature = signature if isinstance(signature, str) else ""
        if not python and signature.startswith("export default"):
            names.add("default")
        elif item.get("symbolType") == "module":
            names |= _export_statement_names(signature)
        else:
            names.add(name)
    return names


def _export_statement_names(signature: str) -> set[str]:
    if star := _EXPORT_STAR.match(signature):
        alias = star.group(1)
        return {alias if alias else f"* from {star.group(2)}"}
    clause = _EXPORT_CLAUSE.search(signature)
    if clause is None:
        return set()
    names: set[str] = set()
    for part in clause.group(1).split(","):
        alias = part.split(" as ")[-1].strip().removeprefix("type ").strip()
        if alias:
            names.add(alias)
    return names


def compat_fact(
    base_paths: Sequence[str],
    before: Mapping[str, list[JsonObject]],
    after: Mapping[str, list[JsonObject]],
) -> Fact:
    """Report exported names that the base files have and the head files lack.

    Test modules are not an import surface, so their names never count.
    """
    removed: list[JsonObject] = []
    for path in base_paths:
        if is_test_path(path):
            continue
        gone = _export_names(path, before.get(path, [])) - _export_names(path, after.get(path, []))
        removed.extend({"path": path, "name": name} for name in sorted(gone))
    return Fact("yes" if removed else "no", {"removed": removed})


# --- import parsing ------------------------------------------------------


def _python_imports(text: str) -> list[tuple[str, tuple[str, ...]]]:
    """Return (module, imported names) pairs; a relative module keeps its dots."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    found: list[tuple[str, tuple[str, ...]]] = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            found.extend((alias.name, ()) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = "." * node.level + (node.module or "")
            found.append((module, tuple(alias.name for alias in node.names)))
    return found


def _script_imports(text: str) -> list[str]:
    return [match.group(1) for match in _SCRIPT_SOURCE.finditer(text)]


def _package_of(path: str, module: str) -> str | None:
    """Return the distribution-level name an import names, or None when local."""
    if PurePosixPath(path).suffix in PYTHON_SUFFIXES:
        if module.startswith("."):
            return None
        return module.split(".")[0]
    if module.startswith((".", "/", "#", "~/", "@/")):
        return None
    if module.startswith("node:"):
        return module
    parts = module.split("/")
    return "/".join(parts[:2]) if module.startswith("@") else parts[0]


def _is_python(path: str) -> bool:
    return PurePosixPath(path).suffix in PYTHON_SUFFIXES


def _is_third_party(head: Path, path: str, package: str) -> bool:
    if _is_python(path):
        if package in sys.stdlib_module_names:
            return False
        # A local package sits beside the importing file, in an ancestor
        # folder, or in the `src/` folder of an ancestor.
        folder = PurePosixPath(path).parent
        roots = [root for ancestor in (folder, *folder.parents) for root in (ancestor, ancestor / "src")]
        return not any(
            (head / root / f"{package}.py").is_file() or (head / root / package).is_dir()
            for root in roots
        )
    return not (package.startswith("node:") or package in _NODE_BUILTINS)


def _packages(path: str, texts: Iterable[str]) -> set[str]:
    python = _is_python(path)
    modules: list[str] = []
    for text in texts:
        if python:
            modules.extend(module for module, _ in _python_imports(text))
        else:
            modules.extend(_script_imports(text))
    return {package for module in modules if (package := _package_of(path, module))}


# --- dependencies --------------------------------------------------------


def _pinning_lockfile(head: Path, manifest: str) -> str | None:
    pure = PurePosixPath(manifest)
    folders = [pure.parent] if pure.parent == PurePosixPath(".") else [pure.parent, PurePosixPath(".")]
    for folder in folders:
        for lock in MANIFEST_LOCKFILES[pure.name]:
            candidate = (folder / lock).as_posix()
            if (head / candidate).is_file():
                return candidate
    return None


def dependencies_fact(
    head: Path,
    changed: Sequence[str],
    head_imports: Mapping[str, list[str]],
    base_imports: Mapping[str, list[str]],
) -> Fact:
    """Report manifest and lockfile changes and new third-party imports.

    `base_imports` covers the whole base tree, so a module that any base file
    imports is not new.
    """
    manifests = [path for path in changed if PurePosixPath(path).name in MANIFEST_LOCKFILES]
    lockfiles = [path for path in changed if PurePosixPath(path).name in LOCKFILES]
    unpaired: list[JsonObject] = []
    for manifest in manifests:
        lock = _pinning_lockfile(head, manifest)
        if lock is not None and lock not in changed:
            unpaired.append({"manifest": manifest, "lockfile": lock})

    known: set[tuple[bool, str]] = set()
    for path, texts in base_imports.items():
        python = _is_python(path)
        known |= {(python, package) for package in _packages(path, texts)}
    added: list[JsonObject] = []
    for path, texts in sorted(head_imports.items()):
        for package in sorted(_packages(path, texts)):
            if (_is_python(path), package) not in known and _is_third_party(head, path, package):
                added.append({"path": path, "module": package})

    value = "yes" if manifests or lockfiles or added else "no"
    detail: JsonObject = {
        "added_imports": added,
        "manifests": manifests,
        "lockfiles": lockfiles,
        "unpaired": unpaired,
    }
    return Fact(value, detail)


# --- scope ---------------------------------------------------------------


def _dotted(path: str) -> str:
    pure = PurePosixPath(path).with_suffix("")
    if pure.name == "__init__":
        pure = pure.parent
    return ".".join(pure.parts)


def _python_targets(path: str, texts: Iterable[str], nodes: Sequence[str]) -> set[str]:
    dotted = {node: _dotted(node) for node in nodes if PurePosixPath(node).suffix in PYTHON_SUFFIXES}
    targets: set[str] = set()
    for text in texts:
        for module, names in _python_imports(text):
            stripped = module.lstrip(".")
            level = len(module) - len(stripped)
            if level:
                anchor = PurePosixPath(path).parent
                for _ in range(level - 1):
                    anchor = anchor.parent
                prefix = ".".join(part for part in (*anchor.parts, stripped) if part and part != ".")
            else:
                prefix = stripped
            candidates = {prefix, *(f"{prefix}.{name}" if prefix else name for name in names)}
            for candidate in filter(None, candidates):
                exact = {node for node, node_dotted in dotted.items() if node_dotted == candidate}
                # A relative import names exactly one module. An absolute import
                # can omit a source root such as `src`, so a unique suffix
                # match also counts; an ambiguous one joins nothing.
                suffix = {node for node, node_dotted in dotted.items() if node_dotted.endswith("." + candidate)}
                if exact:
                    targets |= exact
                elif not level and len(suffix) == 1:
                    targets |= suffix
    return targets


def _script_targets(path: str, texts: Iterable[str], nodes: Sequence[str]) -> set[str]:
    folder = PurePosixPath(path).parent.as_posix()
    node_set = set(nodes)
    targets: set[str] = set()
    for text in texts:
        for module in _script_imports(text):
            if not module.startswith("."):
                continue
            joined = posixpath.normpath(posixpath.join(folder, module))
            stem = re.sub(r"\.[cm]?jsx?$", "", joined)
            candidates = {joined, *(stem + suffix for suffix in SCRIPT_SUFFIXES)}
            candidates |= {f"{joined}/index{suffix}" for suffix in SCRIPT_SUFFIXES}
            targets |= candidates & node_set
    return targets


def scope_fact(nodes: Sequence[str], head_imports: Mapping[str, list[str]]) -> Fact:
    """Group the changed code files into connected components of the import graph."""
    parent = {node: node for node in nodes}

    def find(node: str) -> str:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    for path, texts in head_imports.items():
        if path not in parent:
            continue
        if PurePosixPath(path).suffix in PYTHON_SUFFIXES:
            targets = _python_targets(path, texts, nodes)
        else:
            targets = _script_targets(path, texts, nodes)
        for target in targets:
            parent[find(path)] = find(target)

    groups: dict[str, list[str]] = {}
    for node in nodes:
        groups.setdefault(find(node), []).append(node)
    ordered = sorted((sorted(group) for group in groups.values()), key=lambda group: group[0])
    return Fact("yes" if len(ordered) > 1 else "no", {"groups": ordered})
