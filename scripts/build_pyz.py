#!/usr/bin/env python3
"""Build one self-contained .pyz bundling every skill-runtime Python module.

`easy-cheese.pyz` contains all of `shared/scripts` plus every consuming skill's
scripts, with a generated `__main__.py` subcommand dispatcher (`runpy`). Skills are
installed individually (`gh skill install`), so a single shared bundle has nowhere
to live that survives install — the one artifact is therefore copied into each
consuming skill's `scripts/` dir, leaving every skill self-contained. `shared/scripts`
stays the single source of truth: it is copied (never forked) into the bundle at
build time and resolved as ordinary intra-zip imports with no sys.path traversal.
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
BUNDLE_NAME = "easy-cheese.pyz"

# subcommand -> (skill, source script filename). Subcommands keep each script's
# stem verbatim (hyphens included); the staged module name underscores it. Every
# subcommand is unique across skills, so the dispatch namespace is flat.
TOOLS: dict[str, tuple[str, str]] = {
    "batch-resolve": ("melt", "batch-resolve.py"),
    "conflict-pick": ("melt", "conflict-pick.py"),
    "conflict-summary": ("melt", "conflict-summary.py"),
    "detect-squash-residue": ("melt", "detect-squash-residue.py"),
    "lockfile-resolve": ("melt", "lockfile-resolve.py"),
    "pr_plan_to_branches": ("cheese-factory", "pr_plan_to_branches.py"),
    "validate_decomposition": ("cheese-factory", "validate_decomposition.py"),
    "validate_manifest": ("cheese-factory", "validate_manifest.py"),
    "validate_pr_plan": ("cheese-factory", "validate_pr_plan.py"),
    "pr-status": ("affinage", "pr-status.py"),
    "curd-count": ("mold", "curd-count.py"),
}

# Skills whose SKILL.md invokes a subcommand and therefore ship a copy of the bundle.
DEPLOY_SKILLS = sorted({skill for skill, _ in TOOLS.values()})

_CACHED_BUNDLE: Path | None = None


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


def build_bundle(target: Path) -> Path:
    """Build the unified bundle at ``target`` (a .pyz path). Returns it."""
    target.parent.mkdir(parents=True, exist_ok=True)
    sub_to_module = {sub: _module_name(fn) for sub, (_, fn) in TOOLS.items()}
    with tempfile.TemporaryDirectory() as td:
        stage = Path(td)
        for py in SHARED_SCRIPTS.glob("*.py"):
            shutil.copy(py, stage / py.name)
        for skill, fn in TOOLS.values():
            shutil.copy(REPO_ROOT / "skills" / skill / "scripts" / fn, stage / f"{_module_name(fn)}.py")
        (stage / "__main__.py").write_text(_dispatcher_source(sub_to_module))
        zipapp.create_archive(stage, target=target, interpreter="/usr/bin/env python3")
    return target


def cached_bundle() -> Path:
    """Build the bundle once per process (to a temp dir) and reuse it. Used by the
    test conftests so the suite imports modules from the bundled artifact."""
    global _CACHED_BUNDLE
    if _CACHED_BUNDLE is None or not _CACHED_BUNDLE.exists():
        _CACHED_BUNDLE = build_bundle(Path(tempfile.mkdtemp(prefix="ec-pyz-")) / BUNDLE_NAME)
    return _CACHED_BUNDLE


def deploy() -> list[Path]:
    """Build once and copy the bundle into each consuming skill's scripts/ dir."""
    with tempfile.TemporaryDirectory() as td:
        built = build_bundle(Path(td) / BUNDLE_NAME)
        out: list[Path] = []
        for skill in DEPLOY_SKILLS:
            dest = REPO_ROOT / "skills" / skill / "scripts" / BUNDLE_NAME
            shutil.copy(built, dest)
            out.append(dest)
    return out


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Build the unified easy-cheese .pyz bundle.")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Build a single bundle here instead of deploying into each skill's scripts/ dir.",
    )
    args = parser.parse_args(argv[1:])
    if args.out_dir is not None:
        print(f"built {build_bundle(args.out_dir / BUNDLE_NAME)}")
    else:
        for dest in deploy():
            print(f"deployed {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
