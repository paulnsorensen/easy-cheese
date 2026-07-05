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

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
SHARED_SCRIPTS = REPO_ROOT / "shared" / "scripts"
SHARED_MODULES = {p.stem for p in SHARED_SCRIPTS.glob("*.py")}
ZIP_TIMESTAMP = (1980, 1, 2, 0, 0, 0)


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
    "affinage": {"pr-status": "pr-status.py", "post-reply": "post-reply.py"},
    "mold": {
        "artifact-path": Shared("artifact_path.py"),
        "curd-count": "curd-count.py",
        "gate-graph": "gate-graph.py",
    },
    "briesearch": {
        "artifact-path": Shared("artifact_path.py"),
        "ground-check": "ground_check.py",
    },
    "cook": {"artifact-path": Shared("artifact_path.py")},
    "hard-cheese": {
        "append-attempt": "append-attempt.py",
        "freshness-check": "freshness-check.py",
    },
    "pasteurize": {
        "debug-tag-sweep": "debug-tag-sweep.py",
        "repro-rerun": "repro-rerun.py",
    },
    # /ultracook drives the fan-out engine (formerly /cheese-factory); its
    # sources live in the mode-neutral src/fanout/ dir (see SRC_DIRS).
    "ultracook": {
        "artifact-path": Shared("artifact_path.py"),
        "phase_decision": "phase_decision.py",
        "mode": "mode.py",
        "worktree": "worktree.py",
        "milknado": "milknado.py",
        "validate_decomposition": "validate_decomposition.py",
        "validate_manifest": "validate_manifest.py",
        "validate_pr_plan": "validate_pr_plan.py",
        "manifest_update": "manifest_update.py",
        "wiring_topo_sort": "wiring_topo_sort.py",
        "pr_plan_to_branches": "pr_plan_to_branches.py",
    },
}

# A skill whose scripts live in a src dir named differently from the skill.
# /ultracook drives the neutral src/fanout/ engine rather than a src/ultracook/.
SRC_DIRS: dict[str, str] = {"ultracook": "fanout"}

# Cross-skill source modules a bundle needs beyond its own src dir, staged as
# plain importable modules (not subcommands). mold/curd-count imports the
# canonical PARALLEL_THRESHOLD from src/fanout/mode.py — one source file,
# vendored into both the mold and ultracook bundles.
EXTRA_MODULES: dict[str, list[tuple[str, str]]] = {"mold": [("fanout", "mode.py")]}

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
}
# Wave 1: consumer skills receive common.pyz
COMMON_CONSUMERS: frozenset[str] = frozenset({"cure", "age", "ultracook"})

_CACHE: dict[str, Path] = {}


def _module_name(filename: str) -> str:
    return filename[:-3].replace("-", "_")


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
    common-bundle subcommand live in shared/scripts/; a plain string in a real
    skill lives in src/<skill>/."""
    if isinstance(source, Shared) or skill == COMMON:
        return SHARED_SCRIPTS / _filename(source)
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
            if imp not in registered and imp not in resolved and (skill_dir / f"{imp}.py").exists():
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
        frontier |= _imported_top_names(SRC_ROOT / src_subdir / filename) & SHARED_MODULES
    resolved: set[str] = set()
    while frontier:
        module = frontier.pop()
        if module in resolved:
            continue
        resolved.add(module)
        frontier |= (_imported_top_names(SHARED_SCRIPTS / f"{module}.py") & SHARED_MODULES) - resolved
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
        with zipfile.ZipFile(pyz, "w", compression=zipfile.ZIP_STORED) as archive:
            for staged_file in sorted(source.iterdir(), key=lambda p: p.name):
                info = zipfile.ZipInfo(staged_file.name, date_time=ZIP_TIMESTAMP)
                info.create_system = 3
                info.external_attr = 0o644 << 16
                archive.writestr(info, staged_file.read_bytes())
    target.chmod(0o755)


def build_bundle(skill: str, target: Path) -> Path:
    """Build ``skill``'s bundle at ``target`` (a .pyz path). Returns it."""
    target.parent.mkdir(parents=True, exist_ok=True)
    files = _files(skill)
    sub_to_module = {sub: _module_name(_filename(src)) for sub, src in files.items()}
    with tempfile.TemporaryDirectory() as td:
        stage = Path(td)
        for module in sorted(needed_shared(skill)):
            if module in sub_to_module.values():
                continue  # already staged below as a subcommand (common bundle)
            shutil.copy(SHARED_SCRIPTS / f"{module}.py", stage / f"{module}.py")
        for source in files.values():
            shutil.copy(_source_path(skill, source), stage / f"{_module_name(_filename(source))}.py")
        if skill != COMMON:
            skill_dir = _src_dir(skill)
            for name in sorted(_local_skill_modules(skill)):
                shutil.copy(skill_dir / f"{name}.py", stage / f"{name}.py")
        for src_subdir, filename in EXTRA_MODULES.get(skill, []):
            shutil.copy(SRC_ROOT / src_subdir / filename, stage / filename)
        (stage / "__main__.py").write_text(_dispatcher_source(sub_to_module), encoding="utf-8")
        _write_zipapp(stage, target)
    return target


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
    # Consumer-only skills (age/cure/press) have no own bundle but receive
    # common.pyz, so they are valid targets even though they are not in SKILLS.
    known = {*SKILLS, COMMON, *COMMON_CONSUMERS}
    unknown = [s for s in args.skills if s not in known]
    if unknown:
        parser.error(f"unknown skill(s): {', '.join(unknown)}; known: {', '.join(sorted(known))}")
    targets = args.skills or [*SKILLS, COMMON]
    real = [s for s in targets if s in SKILLS]  # only skills that ship their own .pyz
    want_common = COMMON in targets or any(s in COMMON_CONSUMERS for s in targets)
    consumers = _common_consumers(targets, explicit=bool(args.skills))

    if args.out_dir is not None:
        for skill in real:
            print(f"built {build_bundle(skill, args.out_dir / f'{skill}.pyz')}")
        if want_common:
            print(f"built {build_bundle(COMMON, args.out_dir / 'common.pyz')}")
        return 0

    for skill in real:
        print(f"deployed {build_bundle(skill, REPO_ROOT / 'skills' / skill / 'scripts' / f'{skill}.pyz')}")
    if want_common:
        # Build once, then fan the same artifact out to each consuming skill so
        # every skill ships self-contained — common has no skill dir of its own.
        with tempfile.TemporaryDirectory() as td:
            common = build_bundle(COMMON, Path(td) / "common.pyz")
            for consumer in sorted(consumers):
                dest = REPO_ROOT / "skills" / consumer / "scripts" / "common.pyz"
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(common, dest)
                print(f"deployed {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
