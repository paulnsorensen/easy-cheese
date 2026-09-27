#!/usr/bin/env python3
"""Assemble the shippable release tree: each skill's SKILL.md, wedge launcher,
and lock, plus top-level project metadata. Everything a consumer does NOT
need — runtime sources (src/), build/test tooling, docs, CI config — is left
behind.

The release workflow commits this tree to the `release` branch and points the
version tag at it, so `gh skill install` (which reads the git tree at the tag)
pulls a minimal skill: the launcher and its lock, never the loose .py. The
launcher downloads the skill's content-addressed archive from the rolling
`wedge` release on first run; wedge.yml publishes that archive after every
merge to main, so this script builds nothing.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from collections.abc import Callable
from pathlib import Path
from typing import cast

sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime_gates  # noqa: E402  (sibling module in scripts/)

REPO_ROOT = Path(__file__).resolve().parents[1]

# Allowlist, not denylist: new dev scaffolding added to the repo stays out of
# releases by default. `skills` ships wholesale; metadata files ship if present.
SHIP = [
    "skills",
    "README.md",
    "LICENSE",
    "SECURITY.md",
    "CODE_OF_CONDUCT.md",
    ".claude-plugin",
]

# Build configuration and any stray local archive stay out of the tree.
SKILL_IGNORE = shutil.ignore_patterns("wedge.toml", "*.pyz")


def _copy(
    src: Path,
    dst: Path,
    *,
    ignore: Callable[[str, list[str]], set[str]] | None = None,
) -> None:
    if src.is_dir():
        _ = shutil.copytree(src, dst, ignore=ignore)
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        _ = shutil.copy2(src, dst)


def _guard_out(out: Path) -> None:
    """``stage`` wipes ``out`` with rmtree — refuse paths whose loss would be
    catastrophic: the filesystem root, the repo itself, or an ancestor of it."""
    resolved = out.resolve()
    if resolved == Path(resolved.anchor):
        raise SystemExit(f"stage_release: refusing to wipe filesystem root {resolved}")
    if resolved == REPO_ROOT or resolved in REPO_ROOT.parents:
        raise SystemExit(
            f"stage_release: refusing to wipe {resolved} (repo root or ancestor)"
        )


def stage(out: Path) -> Path:
    """Assemble the release tree at ``out`` (wiped first). Returns ``out``."""
    _guard_out(out)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    for rel in SHIP:
        src = REPO_ROOT / rel
        if src.exists():
            _copy(src, out / rel, ignore=SKILL_IGNORE if rel == "skills" else None)

    _verify(out)
    return out


def _verify(out: Path) -> None:
    """Fail loud if the staged tree is wrong — a broken release should never get
    silently published (the v0.5.1 failure mode)."""
    skills = out / "skills"
    if not any(skills.glob("*/SKILL.md")):
        raise SystemExit(f"stage_release: no skills found under {skills}")

    for skill in runtime_gates.SKILLS:
        launcher = skills / skill / "scripts" / skill
        lock = skills / skill / "scripts" / f"{skill}.wedge.json"
        if not launcher.is_file():
            raise SystemExit(f"stage_release: missing launcher {launcher}")
        if not lock.is_file():
            raise SystemExit(f"stage_release: missing lock {lock}")

    stray = sorted(
        str(p.relative_to(out))
        for pattern in ("*.py", "*.pyz")
        for p in skills.rglob(pattern)
    )
    if stray:
        raise SystemExit(
            "stage_release: raw .py sources and archives must not ship under skills/; found: "
            + ", ".join(stray)
        )


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Stage the shippable release tree.")
    _ = parser.add_argument(
        "--out", type=Path, required=True, help="Output directory (wiped first)."
    )
    args = parser.parse_args(argv[1:])
    out = stage(cast(Path, args.out))
    print(f"staged release tree at {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
