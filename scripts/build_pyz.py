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
DOCUMENT_RULES_SOURCE = SRC_ROOT / "mold" / DOCUMENT_RULES_MODULE
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
    "cook": {
        "artifact-path": Shared("artifact_path.py"),
        "worktree": Shared("worktree.py"),
    },
    "cut": {"red-gate": "red_gate.py"},
    # All four subcommands are one module: wheypoint.py reads the subcommand off
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
        ("mold", "taste_test.py"),
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
        ("mold", "taste_test.py"),
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
    "common": [SRC_ROOT / "easy_cheese_schemas"],
    "cook": [SRC_ROOT / "easy_cheese_schemas"],
    "cut": [SRC_ROOT / "easy_cheese_schemas"],
    "press": [SRC_ROOT / "easy_cheese_schemas"],
    "ultracook": [SRC_ROOT / "easy_cheese_schemas"],
    # wheypoint's whole runtime is typed against the Wheypoint schemas, so it is
    # another real consumer rather than a bundle carrying dead weight.
    "wheypoint": [SRC_ROOT / "easy_cheese_schemas"],
}


VENDORED_DEP_BUNDLES = ("common", "cook", "cut", "press", "ultracook", "wheypoint")


def vendored_dep_trees() -> list[Path]:
    """Every top-level entry `just vendor` unpacked, in a stable order."""
    vendor_deps.require_populated("build_pyz")
    return sorted(
        path
        for path in vendor_deps.VENDOR_ROOT.iterdir()
        if path.name not in {"__pycache__", vendor_deps.STAMP.name}
    )


# The "common" bundle ships cross-cutting CLI entrypoints sourced from
# shared/scripts/ (not src/<skill>/). It has no skill dir of its own; instead a
# copy is fanned out into every consuming skill's scripts/ dir so each skill
# stays self-contained after `gh skill install`.
COMMON = "common"
COMMON_SUBCOMMANDS: dict[str, str] = {
    "slugify": "slugify.py",
    "write_handoff_artifact": "write_handoff_artifact.py",
    "read_handoff_slug": "read_handoff_slug.py",
    "findings_cli": "findings_cli.py",
    "gates_cli": "gates_cli.py",
    "paths_cli": "paths_cli.py",
    "handoff_cli": "handoff_cli.py",
    "render_html": "html_report_cli.py",
}
# Wave 1: consumer skills receive common.pyz
COMMON_CONSUMERS: frozenset[str] = frozenset({"cure", "age", "ultracook"})

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
    if not any(skill in PACKAGE_TREES for skill in skills):
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
    return COMMON_SUBCOMMANDS if skill == COMMON else SKILLS[skill]


def _common_consumers(targets: list[str], *, explicit: bool) -> frozenset[str]:
    """Which consumer skills receive common.pyz for this build request.

    A full build (no explicit targets) or an explicit ``common`` build fans out
    to every consumer; an explicit skill list fans only to the consumers named.
    """
    if not explicit or COMMON in targets:
        return COMMON_CONSUMERS
    return frozenset(s for s in targets if s in COMMON_CONSUMERS)


def _filename(source: str | Shared) -> str:
    return source.filename if isinstance(source, Shared) else source


def _source_path(skill: str, source: str | Shared) -> Path:
    """Resolve a subcommand's source file. Shared() modules and every
    common-bundle subcommand live in shared/scripts/; a plain string containing
    a path separator is src/-relative (a cross-skill source, e.g. a fanout/
    module bundled into age/affinage/ultracook); any other plain string in a
    real skill lives in src/<skill>/."""
    if isinstance(source, Shared) or skill == COMMON:
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
    if skill == COMMON:
        return set()
    skill_dir = _src_dir(skill)
    registered = {_module_name(_filename(src)) for src in SKILLS[skill].values()}
    frontier: set[str] = set()
    for source in SKILLS[skill].values():
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
    if skill != COMMON:
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
    if skill in {COMMON, "cook", "ultracook", "wheypoint"}:
        registry_source = _compiled_phase_registry_source()
        registry_bytes = _checked_in_phase_registry_bytes(registry_source)
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        stage = Path(td)
        for module in sorted(needed_shared(skill)):
            if module in sub_to_module.values():
                continue  # already staged below as a subcommand (common bundle)
            shutil.copy(SHARED_SCRIPTS / f"{module}.py", stage / f"{module}.py")
        for source in files.values():
            shutil.copy(
                _source_path(skill, source),
                stage / f"{_module_name(_filename(source))}.py",
            )
        if skill != COMMON:
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
        if skill == COMMON:
            catalog_paths = (
                stage / "_schema_catalog.py",
                stage / "easy_cheese_schemas" / "_schema_catalog.py",
            )
        elif skill in PACKAGE_TREES:
            catalog_paths = (stage / "easy_cheese_schemas" / "_schema_catalog.py",)
        else:
            catalog_paths = ()
        if catalog_bytes is not None:
            for catalog_path in catalog_paths:
                catalog_path.write_bytes(catalog_bytes)
        if registry_bytes is not None:
            if skill == COMMON:
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


def build_bundle(skill: str, target: Path) -> Path:
    """Build one bundle after deriving and validating its generated catalog."""
    return _build_bundle(
        skill,
        target,
        schema_catalog_bytes=_schema_catalog_bytes_for([skill]),
        document_rules_bytes=_document_rules_bytes_for([skill]),
    )


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
    # Consumer-only skills (age/cure) have no own bundle but receive common.pyz,
    # so they are valid targets even though they are not in SKILLS.
    known = {*SKILLS, COMMON, *COMMON_CONSUMERS}
    unknown = [skill for skill in args.skills if skill not in known]
    if unknown:
        parser.error(
            f"unknown skill(s): {', '.join(unknown)}; known: {', '.join(sorted(known))}"
        )
    targets = args.skills or [*SKILLS, COMMON]
    real = [s for s in targets if s in SKILLS]  # only skills that ship their own .pyz
    want_common = COMMON in targets or any(s in COMMON_CONSUMERS for s in targets)
    consumers = _common_consumers(targets, explicit=bool(args.skills))
    batch_skills = [*real, COMMON] if want_common else real
    catalog_bytes = _schema_catalog_bytes_for(batch_skills)
    document_rules_bytes = _document_rules_bytes_for(batch_skills)

    if args.out_dir is not None:
        for skill in real:
            print(
                "built",
                _build_bundle(
                    skill,
                    args.out_dir / f"{skill}.pyz",
                    schema_catalog_bytes=catalog_bytes,
                    document_rules_bytes=document_rules_bytes,
                ),
            )
        if want_common:
            print(
                "built",
                _build_bundle(
                    COMMON,
                    args.out_dir / "common.pyz",
                    schema_catalog_bytes=catalog_bytes,
                    document_rules_bytes=document_rules_bytes,
                ),
            )
        return 0

    for skill in real:
        print(
            "deployed",
            _build_bundle(
                skill,
                REPO_ROOT / "skills" / skill / "scripts" / f"{skill}.pyz",
                schema_catalog_bytes=catalog_bytes,
                document_rules_bytes=document_rules_bytes,
            ),
        )
    if want_common:
        # Build once, then fan the same artifact out to each consuming skill so
        # every skill ships self-contained — common has no skill dir of its own.
        with tempfile.TemporaryDirectory() as td:
            common = _build_bundle(
                COMMON,
                Path(td) / "common.pyz",
                schema_catalog_bytes=catalog_bytes,
                document_rules_bytes=document_rules_bytes,
            )
            for consumer in sorted(consumers):
                dest = REPO_ROOT / "skills" / consumer / "scripts" / "common.pyz"
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(common, dest)
                print(f"deployed {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
