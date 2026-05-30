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
import zipapp
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
SHARED_SCRIPTS = REPO_ROOT / "shared" / "scripts"
SHARED_MODULES = {p.stem for p in SHARED_SCRIPTS.glob("*.py")}


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
    "cheese-factory": {
        "artifact-path": Shared("artifact_path.py"),
        "pr_plan_to_branches": "pr_plan_to_branches.py",
        "validate_decomposition": "validate_decomposition.py",
        "validate_manifest": "validate_manifest.py",
        "validate_pr_plan": "validate_pr_plan.py",
    },
    "affinage": {"pr-status": "pr-status.py", "post-reply": "post-reply.py"},
    "mold": {
        "artifact-path": Shared("artifact_path.py"),
        "curd-count": "curd-count.py",
    },
    "briesearch": {"artifact-path": Shared("artifact_path.py")},
    "cook": {"artifact-path": Shared("artifact_path.py")},
}

_CACHE: dict[str, Path] = {}


def _module_name(filename: str) -> str:
    return filename[:-3].replace("-", "_")


def _filename(source: str | Shared) -> str:
    return source.filename if isinstance(source, Shared) else source


def _source_path(skill: str, source: str | Shared) -> Path:
    if isinstance(source, Shared):
        return SHARED_SCRIPTS / source.filename
    return SRC_ROOT / skill / source


def _imported_top_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return names


def needed_shared(skill: str) -> set[str]:
    """Shared modules transitively imported by the skill's scripts."""
    frontier: set[str] = set()
    for source in SKILLS[skill].values():
        frontier |= _imported_top_names(_source_path(skill, source)) & SHARED_MODULES
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


def build_bundle(skill: str, target: Path) -> Path:
    """Build ``skill``'s bundle at ``target`` (a .pyz path). Returns it."""
    target.parent.mkdir(parents=True, exist_ok=True)
    files = SKILLS[skill]
    sub_to_module = {sub: _module_name(_filename(src)) for sub, src in files.items()}
    with tempfile.TemporaryDirectory() as td:
        stage = Path(td)
        for module in needed_shared(skill):
            shutil.copy(SHARED_SCRIPTS / f"{module}.py", stage / f"{module}.py")
        for source in files.values():
            shutil.copy(_source_path(skill, source), stage / f"{_module_name(_filename(source))}.py")
        (stage / "__main__.py").write_text(_dispatcher_source(sub_to_module))
        zipapp.create_archive(stage, target=target, interpreter="/usr/bin/env python3")
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
    unknown = [s for s in args.skills if s not in SKILLS]
    if unknown:
        parser.error(f"unknown skill(s): {', '.join(unknown)}; known: {', '.join(SKILLS)}")
    for skill in args.skills or list(SKILLS):
        if args.out_dir is not None:
            target = args.out_dir / f"{skill}.pyz"
            print(f"built {build_bundle(skill, target)}")
        else:
            target = REPO_ROOT / "skills" / skill / "scripts" / f"{skill}.pyz"
            print(f"deployed {build_bundle(skill, target)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
