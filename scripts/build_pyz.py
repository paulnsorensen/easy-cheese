#!/usr/bin/env python3
"""Build self-contained .pyz bundles for skills that consume shared/scripts.

Each consuming skill ships one ``<skill>.pyz`` whose entry point is a generated
``__main__.py`` dispatcher: the first argument selects a subcommand and the rest
are forwarded to that tool's existing ``main``. ``shared/scripts`` stays the
single source of truth; it is copied (never forked) into the staging dir before
``zipapp`` archives it, so the bundle resolves ``from git_utils import ...`` and
friends as ordinary intra-zip imports with no sys.path traversal.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
import zipapp
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SHARED_SCRIPTS = REPO_ROOT / "shared" / "scripts"

# skill -> {subcommand: source script filename}. Subcommands keep the script's
# stem verbatim (hyphens included); the staged module name underscores it.
CONSUMERS: dict[str, dict[str, str]] = {
    "melt": {
        "batch-resolve": "batch-resolve.py",
        "conflict-pick": "conflict-pick.py",
        "conflict-summary": "conflict-summary.py",
        "detect-squash-residue": "detect-squash-residue.py",
        "lockfile-resolve": "lockfile-resolve.py",
    },
    "cheese-factory": {
        "pr_plan_to_branches": "pr_plan_to_branches.py",
        "validate_decomposition": "validate_decomposition.py",
        "validate_manifest": "validate_manifest.py",
        "validate_pr_plan": "validate_pr_plan.py",
    },
}


def _module_name(filename: str) -> str:
    return filename[:-3].replace("-", "_")


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


def build_skill(skill: str, out_dir: Path | None = None) -> Path:
    """Build ``<skill>.pyz``. Writes to ``out_dir`` if given, else the skill's
    own ``scripts/`` directory. Returns the archive path."""
    files = CONSUMERS[skill]
    skill_scripts = REPO_ROOT / "skills" / skill / "scripts"
    dest = out_dir if out_dir is not None else skill_scripts
    dest.mkdir(parents=True, exist_ok=True)
    sub_to_module = {sub: _module_name(fn) for sub, fn in files.items()}
    with tempfile.TemporaryDirectory() as td:
        stage = Path(td)
        for py in SHARED_SCRIPTS.glob("*.py"):
            shutil.copy(py, stage / py.name)
        for fn in files.values():
            shutil.copy(skill_scripts / fn, stage / f"{_module_name(fn)}.py")
        (stage / "__main__.py").write_text(_dispatcher_source(sub_to_module))
        target = dest / f"{skill}.pyz"
        zipapp.create_archive(stage, target=target, interpreter="/usr/bin/env python3")
    return target


def build_all(out_dir: Path | None = None) -> list[Path]:
    return [build_skill(skill, out_dir) for skill in CONSUMERS]


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Build .pyz bundles for shared-consuming skills.")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Write bundles here instead of each skill's scripts/ dir.",
    )
    parser.add_argument("skills", nargs="*", help="Skills to build (default: all).")
    args = parser.parse_args(argv[1:])
    unknown = [s for s in args.skills if s not in CONSUMERS]
    if unknown:
        parser.error(f"unknown skill(s): {', '.join(unknown)}; known: {', '.join(CONSUMERS)}")
    for skill in args.skills or list(CONSUMERS):
        print(f"built {build_skill(skill, args.out_dir)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
