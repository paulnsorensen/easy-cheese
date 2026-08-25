#!/usr/bin/env python3
"""Build one self-contained .pyz per skill: only that skill's scripts plus the
shared/scripts modules they actually import.

Sources live outside the shipped skill dirs — skill scripts in src/<skill>/, the
shared library in shared/scripts/. Each bundle is assembled from just what the
skill needs (shared deps computed by scanning imports) and deployed to
skills/<skill>/scripts/<skill>.pyz. No skill ships another skill's code, and a
shared module is vendored only into the bundles that import it — keeping the
total shipped footprint O(scripts), not O(skills × scripts).
"""

from __future__ import annotations

import argparse
import ast
import importlib
import importlib.util
import shutil
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

import vendor_deps

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
SHARED_SCRIPTS = REPO_ROOT / "shared" / "scripts"

PHASE_REGISTRY_MODULE = "_compiled_phase_registry.py"
PHASE_REGISTRY_SOURCE = SRC_ROOT / "easy_cheese_schemas" / PHASE_REGISTRY_MODULE
PHASE_CONTRACT_SOURCE = SRC_ROOT / "easy_cheese_schemas" / "phase_contracts.py"
SCHEMA_CATALOG_SOURCE = SRC_ROOT / "easy_cheese_schemas" / "_schema_catalog.py"
SCHEMA_CONTRACT_SOURCE = SRC_ROOT / "easy_cheese_schemas" / "contracts.py"
DOCUMENT_RULES_MODULE = "_document_rules.py"
DOCUMENT_RULES_SOURCE = (
    SRC_ROOT / "easy_cheese" / "skills" / "mold" / DOCUMENT_RULES_MODULE
)
SHARED_MODULES = {p.stem for p in SHARED_SCRIPTS.glob("*.py")}
ZIP_TIMESTAMP = (1980, 1, 2, 0, 0, 0)
# Pinned so the compressed bytes depend only on the zlib build, never on
# zipfile's default drifting. Compressed output still differs between stock
# zlib and zlib-ng, so CI's rebuild is the authority on the committed bundles;
# if that ever bites, switching this file back to ZIP_STORED is a one-liner.
ZIP_COMPRESSLEVEL = 9


@dataclass(frozen=True)
class Shared:
    """A subcommand sourced from a shared/scripts/ module rather than a
    src/<skill>/ script, so one file backs the subcommand across every skill
    that registers it — no per-skill copy to keep in sync."""

    filename: str


# skill -> {subcommand: source}. A plain string names a src/<skill>/ script;
# Shared(...) names a shared/scripts/ module reused across skills. Subcommands
# keep each script's stem verbatim; the staged module name underscores it.
SKILLS: dict[str, dict[str, str | Shared]] = {
    "melt": {
        "batch-resolve": "batch-resolve.py",
        "conflict-pick": "conflict-pick.py",
        "conflict-summary": "conflict-summary.py",
        "detect-squash-residue": "detect-squash-residue.py",
        "lockfile-resolve": "lockfile-resolve.py",
    },
    "affinage": {
        "pr-status": "pr-status.py",
        "post-reply": "post-reply.py",
        "age-route": "fanout/age_route_cli.py",
        "review-surface": "fanout/review_surface_cli.py",
    },
    "mold": {
        "artifact-path": Shared("artifact_path.py"),
        "curd-count": "curd-count.py",
        "gate-graph": "gate-graph.py",
        "render_html": Shared("html_report_cli.py"),
        "taste-test": "taste_test.py",
        "validate-spec": "validate-spec.py",
    },
    "briesearch": {
        "artifact-path": Shared("artifact_path.py"),
        "ground-check": "ground_check.py",
    },
    # normalize and validate are one module: cook_cli.py reads the verb off
    # argv[0], the way wheypoint.py does for commit|resolve|show|lint.
    "cook": {
        "artifact-path": Shared("artifact_path.py"),
        "worktree": Shared("worktree.py"),
        "normalize": "cook_cli.py",
        "validate": "cook_cli.py",
    },
    "cut": {"red-gate": "red_gate.py"},
    # argv[0], the way hallouminate_setup.py already does for global|local|doctor.
    "wheypoint": {
        "commit": "wheypoint.py",
        "resolve": "wheypoint.py",
        "show": "wheypoint.py",
        "lint": "wheypoint.py",
    },
    "easy-cheese-setup": {
        "global": Shared("hallouminate_setup.py"),
        "local": Shared("hallouminate_setup.py"),
        "doctor": Shared("hallouminate_setup.py"),
    },
    "age": {
        "html-report": "age-html-report.py",
        "age-route": "fanout/age_route_cli.py",
        "review-surface": "fanout/review_surface_cli.py",
    },
    "hard-cheese": {
        "append-attempt": "append-attempt.py",
        "freshness-check": "freshness-check.py",
    },
    "pasteurize": {
        "debug-tag-sweep": "debug-tag-sweep.py",
        "repro-rerun": "repro-rerun.py",
        "pasteurize-route": "fanout/pasteurize_route_cli.py",
    },
    "press": {
        "press-route": "fanout/press_route_cli.py",
        "red-gate": "cut/red_gate.py",
    },
    "cure": {},
    # /ultracook drives the fan-out engine (formerly /cheese-factory); its
    # sources live in the mode-neutral src/fanout/ dir (see SRC_DIRS).
    "ultracook": {
        "artifact-path": Shared("artifact_path.py"),
        "baseline": "baseline.py",
        "phase_decision": "phase_decision.py",
        "mode": "mode.py",
        "worktree": Shared("worktree.py"),
        "milknado": "milknado.py",
        "validate_decomposition": "validate_decomposition.py",
        "validate_manifest": "validate_manifest.py",
        "validate_pr_plan": "validate_pr_plan.py",
        "manifest_update": "manifest_update.py",
        "wiring_topo_sort": "wiring_topo_sort.py",
        "pr_plan_to_branches": "pr_plan_to_branches.py",
        "age-route": "fanout/age_route_cli.py",
        "curd-block": "fanout/curd_block.py",
    },
}

# A skill whose scripts live in a src dir named differently from the skill.
# /ultracook drives the neutral src/fanout/ engine rather than a src/ultracook/.
SRC_DIRS: dict[str, str] = {"ultracook": "fanout"}

# Cross-skill source modules a bundle needs beyond its own src dir, staged as
# plain importable modules (not subcommands). mold/curd-count imports the
# canonical PARALLEL_THRESHOLD from src/fanout/mode.py — one source file,
# vendored into both the mold and ultracook bundles.
EXTRA_MODULES: dict[str, list[tuple[str, str]]] = {
    "mold": [("fanout", "mode.py")],
    "cut": [
        ("easy_cheese/skills/mold", "taste_test.py"),
    ],
    "age": [
        ("fanout", "age_route.py"),
        ("fanout", "review_surface.py"),
    ],
    "affinage": [
        ("fanout", "age_route.py"),
        ("fanout", "review_surface.py"),
    ],
    "pasteurize": [("fanout", "pasteurize_route.py")],
    "press": [
        ("fanout", "press_route.py"),
        ("cut", "cut_assertion_probe.py"),
        ("cut", "gate_receipts.py"),
        ("easy_cheese/skills/mold", "taste_test.py"),
    ],
}

# Whole directory trees (and the odd single-file module) staged verbatim into a
# bundle. The import scanner above only resolves flat sibling modules, so a real
# package's membership is declared here rather than discovered.
#
# Bundles that execute typed workflow or GateReceipt contracts carry the complete
# easy_cheese_schemas package and its vendored attrs/cattrs dependencies. Keep
# ownership explicit so each consumer imports the canonical implementation.
PACKAGE_TREES: dict[str, list[Path]] = {
    "cook": [SRC_ROOT / "easy_cheese_schemas"],
    "cut": [SRC_ROOT / "easy_cheese_schemas"],
    "press": [SRC_ROOT / "easy_cheese_schemas"],
    "ultracook": [SRC_ROOT / "easy_cheese_schemas"],
    # wheypoint's whole runtime is typed against the Wheypoint schemas, so it is
    # another real consumer rather than a bundle carrying dead weight.
    "wheypoint": [SRC_ROOT / "easy_cheese_schemas"],
}


VENDORED_DEP_BUNDLES = ("cook", "cut", "press", "ultracook", "wheypoint")


def vendored_dep_trees() -> list[Path]:
    """Every top-level entry `just vendor` unpacked, in a stable order."""
    vendor_deps.require_populated("build_pyz")
    return sorted(
        path
        for path in vendor_deps.VENDOR_ROOT.iterdir()
        if path.name not in {"__pycache__", vendor_deps.STAMP.name}
    )


SHARED_COMMANDS: dict[str, str] = {
    "slugify": "slugify.py",
    "write_handoff_artifact": "write_handoff_artifact.py",
    "read_handoff_slug": "read_handoff_slug.py",
    "findings_cli": "findings_cli.py",
    "gates_cli": "gates_cli.py",
    "paths_cli": "paths_cli.py",
    "handoff_cli": "handoff_cli.py",
    "render_html": "html_report_cli.py",
}
SHARED_COMMAND_CONSUMERS = frozenset({"age", "cook", "cure", "ultracook"})

_CACHE: dict[str, Path] = {}


def _phase_compiler():
    """Load the source-only compiler without importing the generated module."""
    package_entry = str(SRC_ROOT / "easy_cheese_schemas")
    if package_entry not in sys.path:
        sys.path.insert(0, package_entry)
    from _phase_registry_compiler import compile_phase_files_to_source

    return compile_phase_files_to_source


def _compiled_phase_registry_source() -> str:
    """Compile authored phase YAML into the portable runtime data module."""
    declarations = sorted(REPO_ROOT.glob("skills/*/phase-contract.yaml"))
    return _phase_compiler()(declarations)


def _schema_catalog_compiler():
    """Load the source-only catalog compiler without runtime projections."""
    package_entry = str(SRC_ROOT / "easy_cheese_schemas")
    if package_entry not in sys.path:
        sys.path.insert(0, package_entry)
    from _schema_catalog_compiler import collect, render

    return collect, render


def _schema_contract_module() -> ModuleType:
    """Load a fresh contracts module so every build sees current markers."""
    vendor_deps.require_populated("schema catalog compiler")
    vendor_entry = str(vendor_deps.VENDOR_ROOT)
    if vendor_entry not in sys.path:
        sys.path.insert(0, vendor_entry)
    module = ModuleType("_build_schema_contracts")
    module.__file__ = str(SCHEMA_CONTRACT_SOURCE)
    sys.modules[module.__name__] = module
    source = SCHEMA_CONTRACT_SOURCE.read_bytes()
    exec(
        compile(source, str(SCHEMA_CONTRACT_SOURCE), "exec"),
        module.__dict__,
    )
    return module


def _compiled_schema_catalog_source() -> str:
    """Compile the marker-derived schema catalog from the live contracts."""
    collect, render = _schema_catalog_compiler()
    return render(collect(_schema_contract_module()))


def _document_rules_compiler():
    """Load the source-only document-rules compiler without runtime projections."""
    package_entry = str(SRC_ROOT / "easy_cheese_schemas")
    added = package_entry not in sys.path
    if added:
        sys.path.insert(0, package_entry)
    try:
        from _document_rules_compiler import collect, render
    finally:
        if added:
            sys.path.remove(package_entry)

    return collect, render


def _compiled_document_rules_source() -> str:
    """Compile the marker-derived mold-spec document rules from the live contracts."""
    collect, render = _document_rules_compiler()
    return render(collect(_schema_contract_module()))


def _checked_in_generated_file_bytes(
    expected_source: str,
    source: Path,
    *,
    artifact_name: str,
) -> bytes:
    """Require a tracked generated file to match its source authority."""
    expected = expected_source.encode("utf-8")
    try:
        actual = source.read_bytes()
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"checked-in {artifact_name} is missing: {source}"
        ) from exc
    if actual != expected:
        try:
            regeneration_target = source.relative_to(REPO_ROOT)
        except ValueError:
            regeneration_target = source
        raise RuntimeError(
            f"checked-in {artifact_name} is stale; regenerate {regeneration_target}"
        )
    return actual


def _checked_in_schema_catalog_bytes(expected_source: str) -> bytes:
    """Validate the checked-in schema catalog against its live authority."""
    return _checked_in_generated_file_bytes(
        expected_source,
        SCHEMA_CATALOG_SOURCE,
        artifact_name="schema catalog",
    )


def _checked_in_phase_registry_bytes(expected_source: str) -> bytes:
    """Validate the checked-in phase registry against its YAML authority."""
    return _checked_in_generated_file_bytes(
        expected_source,
        PHASE_REGISTRY_SOURCE,
        artifact_name="phase registry",
    )


def _checked_in_document_rules_bytes(expected_source: str) -> bytes:
    """Validate the checked-in mold-spec document rules against their live authority."""
    return _checked_in_generated_file_bytes(
        expected_source,
        DOCUMENT_RULES_SOURCE,
        artifact_name="document rules",
    )


def _schema_catalog_bytes_for(skills: list[str]) -> bytes | None:
    """Derive and validate the checked-in catalog once for a build batch."""
    if not any(
        skill in PACKAGE_TREES or skill in SHARED_COMMAND_CONSUMERS
        for skill in skills
    ):
        return None
    return _checked_in_schema_catalog_bytes(_compiled_schema_catalog_source())


def _document_rules_bytes_for(skills: list[str]) -> bytes | None:
    """Derive and validate the checked-in document rules once for a build batch."""
    if "mold" not in skills:
        return None
    return _checked_in_document_rules_bytes(_compiled_document_rules_source())


def _module_name(filename: str) -> str:
    return Path(filename).stem.replace("-", "_")


def _src_dir(skill: str) -> Path:
    """The src/ subdir a skill's scripts live in (usually the skill name)."""
    return SRC_ROOT / SRC_DIRS.get(skill, skill)


def _files(skill: str) -> dict[str, str | Shared]:
    files = dict(SKILLS[skill])
    if skill in SHARED_COMMAND_CONSUMERS:
        for command, filename in SHARED_COMMANDS.items():
            if command in files:
                raise ValueError(f"shared command collides in {skill}: {command}")
            files[command] = Shared(filename)
    return files


def _filename(source: str | Shared) -> str:
    return source.filename if isinstance(source, Shared) else source


def _source_path(skill: str, source: str | Shared) -> Path:
    """Resolve a subcommand's source file. Shared() modules live in
    shared/scripts/; a plain string containing
    a path separator is src/-relative (a cross-skill source, e.g. a fanout/
    module bundled into age/affinage/ultracook); any other plain string in a
    real skill lives in src/<skill>/."""
    if isinstance(source, Shared):
        return SHARED_SCRIPTS / _filename(source)
    if isinstance(source, str) and "/" in source:
        return SRC_ROOT / source
    return _src_dir(skill) / source


def _imported_top_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return names


def _local_skill_modules(skill: str) -> set[str]:
    """Non-registered local src/<skill>/*.py modules transitively imported by the skill."""
    skill_dir = _src_dir(skill)
    registered = {_module_name(_filename(src)) for src in _files(skill).values()}
    frontier: set[str] = set()
    for source in _files(skill).values():
        for name in _imported_top_names(_source_path(skill, source)):
            if name not in registered and (skill_dir / f"{name}.py").exists():
                frontier.add(name)
    resolved: set[str] = set()
    while frontier:
        name = frontier.pop()
        if name in resolved:
            continue
        resolved.add(name)
        for imp in _imported_top_names(skill_dir / f"{name}.py"):
            if (
                imp not in registered
                and imp not in resolved
                and (skill_dir / f"{imp}.py").exists()
            ):
                frontier.add(imp)
    return resolved


def needed_shared(skill: str) -> set[str]:
    """Shared modules transitively imported by the skill's scripts and local modules."""
    frontier: set[str] = set()
    for source in _files(skill).values():
        frontier |= _imported_top_names(_source_path(skill, source)) & SHARED_MODULES
    skill_dir = _src_dir(skill)
    for name in _local_skill_modules(skill):
        frontier |= _imported_top_names(skill_dir / f"{name}.py") & SHARED_MODULES
    for src_subdir, filename in EXTRA_MODULES.get(skill, []):
        frontier |= (
            _imported_top_names(SRC_ROOT / src_subdir / filename) & SHARED_MODULES
        )
    resolved: set[str] = set()
    while frontier:
        module = frontier.pop()
        if module in resolved:
            continue
        resolved.add(module)
        frontier |= (
            _imported_top_names(SHARED_SCRIPTS / f"{module}.py") & SHARED_MODULES
        ) - resolved
    return resolved


def _dispatcher_source(sub_to_module: dict[str, str]) -> str:
    choices = "|".join(sorted(sub_to_module))
    return (
        "import runpy\n"
        "import sys\n"
        "\n"
        f"SUBCOMMANDS = {sub_to_module!r}\n"
        "\n"
        "if len(sys.argv) < 2 or sys.argv[1] not in SUBCOMMANDS:\n"
        f"    sys.stderr.write('usage: <pyz> {{{choices}}} [args...]\\n')\n"
        "    sys.exit(2)\n"
        "\n"
        "_name = sys.argv[1]\n"
        "sys.argv = [_name, *sys.argv[2:]]\n"
        "runpy.run_module(SUBCOMMANDS[_name], run_name='__main__')\n"
    )


def _write_zipapp(source: Path, target: Path) -> None:
    with target.open("wb") as pyz:
        pyz.write(b"#!/usr/bin/env python3\n")
        with zipfile.ZipFile(pyz, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            staged = sorted(
                (p.relative_to(source).as_posix(), p)
                for p in source.rglob("*")
                if p.is_file()
            )
            for name, staged_file in staged:
                info = zipfile.ZipInfo(name, date_time=ZIP_TIMESTAMP)
                info.create_system = 3
                info.external_attr = 0o644 << 16
                archive.writestr(
                    info,
                    staged_file.read_bytes(),
                    compress_type=zipfile.ZIP_DEFLATED,
                    compresslevel=ZIP_COMPRESSLEVEL,
                )
    target.chmod(0o755)


def _build_bundle(
    skill: str,
    target: Path,
    *,
    schema_catalog_bytes: bytes | None,
    document_rules_bytes: bytes | None = None,
) -> Path:
    """Build ``skill`` with catalog bytes validated by the batch boundary."""
    files = _files(skill)
    sub_to_module = {sub: _module_name(_filename(src)) for sub, src in files.items()}
    catalog_bytes = schema_catalog_bytes
    registry_bytes = None
    if skill in SHARED_COMMAND_CONSUMERS | {"cook", "ultracook", "wheypoint"}:
        registry_source = _compiled_phase_registry_source()
        registry_bytes = _checked_in_phase_registry_bytes(registry_source)
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        stage = Path(td)
        for module in sorted(needed_shared(skill)):
            if module in sub_to_module.values():
                continue  # already staged below as a shared subcommand
            shutil.copy(SHARED_SCRIPTS / f"{module}.py", stage / f"{module}.py")
        if "paths" in needed_shared(skill):
            package = stage / "easy_cheese" / "shared"
            package.mkdir(parents=True, exist_ok=True)
            for init in (stage / "easy_cheese" / "__init__.py", package / "__init__.py"):
                init.write_text("", encoding="utf-8")
            shutil.copy(
                SRC_ROOT / "easy_cheese" / "shared" / "paths.py",
                package / "paths.py",
            )
        for source in files.values():
            shutil.copy(
                _source_path(skill, source),
                stage / f"{_module_name(_filename(source))}.py",
            )
        skill_dir = _src_dir(skill)
        for name in sorted(_local_skill_modules(skill)):
            shutil.copy(skill_dir / f"{name}.py", stage / f"{name}.py")
        for src_subdir, filename in EXTRA_MODULES.get(skill, []):
            shutil.copy(SRC_ROOT / src_subdir / filename, stage / filename)
        trees = list(PACKAGE_TREES.get(skill, []))
        if skill in VENDORED_DEP_BUNDLES:
            trees.extend(vendored_dep_trees())
        for tree in trees:
            if tree.is_dir():
                # __pycache__ is skipped: importing the package from source (the
                # test suite does) would otherwise leak host-specific .pyc bytes
                # into the archive and break the rebuild byte-compare.
                shutil.copytree(
                    tree,
                    stage / tree.name,
                    ignore=shutil.ignore_patterns(
                        "__pycache__",
                        "_phase_registry_compiler.py",
                        "_schema_catalog_compiler.py",
                        "_document_rules_compiler.py",
                    ),
                )
            else:
                shutil.copy(tree, stage / tree.name)
        if skill in PACKAGE_TREES:
            catalog_paths = (stage / "easy_cheese_schemas" / "_schema_catalog.py",)
        elif skill in SHARED_COMMAND_CONSUMERS:
            catalog_paths = (stage / "_schema_catalog.py",)
        else:
            catalog_paths = ()
        if catalog_bytes is not None:
            for catalog_path in catalog_paths:
                catalog_path.write_bytes(catalog_bytes)
        if registry_bytes is not None:
            if skill in SHARED_COMMAND_CONSUMERS and skill not in PACKAGE_TREES:
                shutil.copy(PHASE_CONTRACT_SOURCE, stage / "phase_contracts.py")
                (stage / PHASE_REGISTRY_MODULE).write_bytes(registry_bytes)
            else:
                package_registry = stage / "easy_cheese_schemas" / PHASE_REGISTRY_MODULE
                package_registry.write_bytes(registry_bytes)
        if skill == "mold" and document_rules_bytes is not None:
            (stage / DOCUMENT_RULES_MODULE).write_bytes(document_rules_bytes)
        (stage / "__main__.py").write_text(
            _dispatcher_source(sub_to_module), encoding="utf-8"
        )
        _write_zipapp(stage, target)
    return target


def build_bundle(
    skill: str,
    target: Path,
    *,
    schema_catalog_bytes: bytes | None = None,
    document_rules_bytes: bytes | None = None,
) -> Path:
    """Build one bundle from its owning layout."""
    if skill in {"mold", "cook"}:
        return build_layout_bundle(
            skill,
            target,
            schema_catalog_bytes=schema_catalog_bytes,
            document_rules_bytes=document_rules_bytes,
        )
    kwargs = {
        "schema_catalog_bytes": (
            schema_catalog_bytes
            if schema_catalog_bytes is not None
            else _schema_catalog_bytes_for([skill])
        )
    }
    if document_rules_bytes is not None:
        kwargs["document_rules_bytes"] = document_rules_bytes
    return _build_bundle(skill, target, **kwargs)


def cached_bundle(skill: str) -> Path:
    """Build ``skill``'s bundle once per process (to a temp dir) and reuse it.
    Used by the test conftests so the suite imports from the bundled artifact."""
    if skill not in _CACHE or not _CACHE[skill].exists():
        out = Path(tempfile.mkdtemp(prefix=f"ec-pyz-{skill}-"))
        _CACHE[skill] = build_bundle(skill, out / f"{skill}.pyz")
    return _CACHE[skill]


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Build per-skill .pyz bundles.")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Build bundles here instead of deploying into each skill's scripts/ dir.",
    )
    parser.add_argument("skills", nargs="*", help="Skills to build (default: all).")
    args = parser.parse_args(argv[1:])
    known = set(SKILLS)
    unknown = [skill for skill in args.skills if skill not in known]
    if unknown:
        parser.error(
            f"unknown skill(s): {', '.join(unknown)}; known: {', '.join(sorted(known))}"
        )
    real = args.skills or list(SKILLS)
    catalog_bytes = _schema_catalog_bytes_for(real)
    document_rules_bytes = _document_rules_bytes_for(real)

    if args.out_dir is not None:
        for skill in real:
            target = args.out_dir / f"{skill}.pyz"
            if skill in {"mold", "cook"}:
                built = build_layout_bundle(skill, target, schema_catalog_bytes=catalog_bytes, document_rules_bytes=document_rules_bytes)
            else:
                built = _build_bundle(
                    skill,
                    target,
                    schema_catalog_bytes=catalog_bytes,
                    document_rules_bytes=document_rules_bytes,
                )
            print("built", built)
        return 0

    for skill in real:
        target = REPO_ROOT / "skills" / skill / "scripts" / f"{skill}.pyz"
        if skill in {"mold", "cook"}:
            built = build_layout_bundle(skill, target, schema_catalog_bytes=catalog_bytes, document_rules_bytes=document_rules_bytes)
        else:
            built = _build_bundle(
                skill,
                target,
                schema_catalog_bytes=catalog_bytes,
                document_rules_bytes=document_rules_bytes,
            )
        print("deployed", built)
    return 0




# Doctrine layout API for migrated skill packages.
LAYOUT_PACKAGE_ROOT = SRC_ROOT / "easy_cheese"
_NATIVE_SUFFIXES = {".so", ".pyd", ".dylib"}


def _compile_layout_commands(skill: str, root: Path | None = None) -> dict[str, str]:
    """Compile command decorators from a layout skill entrypoint."""
    package_root = root or LAYOUT_PACKAGE_ROOT
    source = package_root / "skills" / skill / "commands.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    commands: dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        for decorator in node.decorator_list:
            if (
                isinstance(decorator, ast.Call)
                and isinstance(decorator.func, ast.Name)
                and decorator.func.id == "bundle_command"
                and len(decorator.args) == 1
                and isinstance(decorator.args[0], ast.Constant)
                and isinstance(decorator.args[0].value, str)
            ):
                name = decorator.args[0].value
                if name in commands:
                    raise ValueError(f"duplicate command declaration: {name}")
                commands[name] = node.name
    if not commands:
        raise ValueError(f"no bundle commands declared for {skill}")
    compiled = dict(sorted(commands.items()))
    if package_root.resolve() == LAYOUT_PACKAGE_ROOT.resolve():
        shared_entry = str(SHARED_SCRIPTS)
        added_shared = shared_entry not in sys.path
        if added_shared:
            sys.path.insert(0, shared_entry)
        try:
            module = importlib.import_module(f"easy_cheese.skills.{skill}.commands")
        finally:
            if added_shared:
                sys.path.remove(shared_entry)
        from easy_cheese.shared.bundle_commands import (
            compile_bundle_commands,
            validate_generated_region,
        )

        if compile_bundle_commands(module.__name__) != compiled:
            raise ValueError(f"runtime command registry drift for {skill}")
        guidance = REPO_ROOT / "skills" / skill
        guidance /= (
            "references/bundle-commands.md" if skill == "cook" else "SKILL.md"
        )
        validate_generated_region(
            guidance.read_text(encoding="utf-8"), module.__name__
        )
    return compiled



def _dependency_module_index(name: str) -> dict[str, tuple[Path, Path]]:
    spec = importlib.util.find_spec(name)
    if spec is None or spec.origin is None:
        raise RuntimeError(f"approved dependency is unavailable: {name}")
    origin = Path(spec.origin)
    if origin.suffix in _NATIVE_SUFFIXES:
        raise RuntimeError(f"approved dependency resolves to native code: {name}")
    if not spec.submodule_search_locations:
        return {name: (origin, Path(f"{name}.py"))}
    package_root = Path(next(iter(spec.submodule_search_locations)))
    modules: dict[str, tuple[Path, Path]] = {}
    for source in sorted(package_root.rglob("*.py")):
        if "__pycache__" in source.parts or "tests" in source.parts:
            continue
        relative = source.relative_to(package_root)
        parts = relative.with_suffix("").parts
        module_parts = (name, *parts[:-1]) if parts[-1] == "__init__" else (name, *parts)
        modules[".".join(module_parts)] = (source, Path(name) / relative)
    return modules


def _source_imports(path: Path, module: str) -> set[str]:
    package = module if path.name == "__init__.py" else module.rpartition(".")[0]
    imports: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                target = "." * node.level + (node.module or "")
                imported = importlib.util.resolve_name(target, package)
            else:
                imported = node.module or ""
            if imported:
                imports.add(imported)
                imports.update(f"{imported}.{alias.name}" for alias in node.names)
    return imports


def _copy_pure_python_dependencies(stage: Path, files: tuple[Path, ...]) -> None:
    approved = {"attrs", "attr", "cattrs", "typing_extensions"}
    indexes = {name: _dependency_module_index(name) for name in approved}
    modules = {module: source for index in indexes.values() for module, source in index.items()}
    pending: list[str] = []
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                pending.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                pending.append(node.module)
                pending.extend(f"{node.module}.{alias.name}" for alias in node.names)
    included: set[str] = set()
    while pending:
        imported = pending.pop()
        root_name = imported.split(".", 1)[0]
        if root_name not in approved:
            continue
        candidate = modules.get(imported)
        if candidate is None:
            continue
        if imported in included:
            continue
        included.add(imported)
        source, _destination = candidate
        pending.extend(_source_imports(source, imported))
    for module in sorted(included):
        source, relative = modules[module]
        destination = stage / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def _schema_package_initializer(root: Path) -> str:
    """Project only canonical version metadata into the isolated package."""
    source = root.parent / "easy_cheese_schemas" / "__init__.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "__version__"
            for target in node.targets
        ):
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                return f"__version__ = {node.value.value!r}\n"
    raise RuntimeError(f"canonical schema package version is missing: {source}")


def build_layout_bundle(
    skill: str,
    target: Path,
    root: Path | None = None,
    *,
    schema_catalog_bytes: bytes | None = None,
    document_rules_bytes: bytes | None = None,
) -> Path:
    """Build one same-named archive from the layout-derived transitive closure."""
    if target.name != f"{skill}.pyz":
        raise ValueError("archive name must match owning skill")
    root = root or LAYOUT_PACKAGE_ROOT
    package_entry = str(root.parent)
    if package_entry not in sys.path:
        sys.path.insert(0, package_entry)
    from easy_cheese.shared.bundles import minimal_closure

    files = minimal_closure(skill, root, SHARED_SCRIPTS)
    if skill in {"mold", "cook"} and schema_catalog_bytes is None:
        schema_catalog_bytes = _checked_in_schema_catalog_bytes(
            _compiled_schema_catalog_source()
        )
    if skill == "mold" and document_rules_bytes is None:
        document_rules_bytes = _checked_in_document_rules_bytes(
            _compiled_document_rules_source()
        )
    registry_bytes = _checked_in_phase_registry_bytes(_compiled_phase_registry_source())
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        stage = Path(td)
        for source in files:
            if source.is_relative_to(SHARED_SCRIPTS):
                relative = Path(source.name)
            else:
                relative = source.relative_to(root.parent)
            destination = stage / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        for package in (
            stage / "easy_cheese",
            stage / "easy_cheese" / "shared",
            stage / "easy_cheese" / "skills",
            stage / "easy_cheese" / "skills" / skill,
            stage / "easy_cheese_schemas",
        ):
            package.mkdir(parents=True, exist_ok=True)
            if package.name == "easy_cheese_schemas":
                (package / "__init__.py").write_text(
                    _schema_package_initializer(root), encoding="utf-8"
                )
            else:
                (package / "__init__.py").write_text("", encoding="utf-8")
        _copy_pure_python_dependencies(stage, files)
        schema_path = stage / "easy_cheese_schemas" / "_schema_catalog.py"
        if schema_catalog_bytes is not None:
            schema_path.parent.mkdir(parents=True, exist_ok=True)
            schema_path.write_bytes(schema_catalog_bytes)
        (stage / "easy_cheese_schemas" / PHASE_REGISTRY_MODULE).write_bytes(registry_bytes)
        if skill == "mold" and document_rules_bytes is not None:
            (stage / "easy_cheese" / "skills" / "mold" / DOCUMENT_RULES_MODULE).write_bytes(
                document_rules_bytes
            )
        commands = _compile_layout_commands(skill, root)
        (stage / "__main__.py").write_text(
            "# bundle_command generated layout dispatcher\n"
            "import sys\n"
            f"COMMANDS = {commands!r}\n"
            "from easy_cheese.shared.bundle_commands import dispatch\n"
            "from easy_cheese.skills.%s import commands\n"
            "raise SystemExit(dispatch(commands.__name__, sys.argv[1:], expected=COMMANDS))\n"
            % skill,
            encoding="utf-8",
        )
        _write_zipapp(stage, target)
    return target


if __name__ == "__main__":
    sys.exit(main(sys.argv))
