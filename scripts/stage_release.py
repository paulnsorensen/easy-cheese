#!/usr/bin/env python3
"""Assemble the shippable release tree: SKILL.md + one built <skill>.pyz per skill,
plus top-level project metadata. Everything a consumer does NOT need — raw script
sources (src/, shared/), build/test tooling, docs, CI config — is left behind.

The release workflow commits this tree to the `release` branch and points the
version tag at it, so `gh skill install` (which reads the git tree at the tag)
pulls a minimal, self-contained skill: the dispatching .pyz, never the loose .py.

Bundles are built straight into the staged tree via build_pyz.build_bundle, so
neither this script nor its test mutates the repo's working copy.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_pyz  # noqa: E402  (sibling module in scripts/)

REPO_ROOT = Path(__file__).resolve().parents[1]

# Allowlist, not denylist: new dev scaffolding added to the repo stays out of
# releases by default. `skills` ships wholesale (post-build); metadata files
# ship if present.
SHIP = [
    "skills",
    "README.md",
    "LICENSE",
    "SECURITY.md",
    "CODE_OF_CONDUCT.md",
    ".claude-plugin",
]


def _copy(src: Path, dst: Path) -> None:
    if src.is_dir():
        shutil.copytree(src, dst)
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def _guard_out(out: Path) -> None:
    """``stage`` wipes ``out`` with rmtree — refuse paths whose loss would be
    catastrophic: the filesystem root, the repo itself, or an ancestor of it."""
    resolved = out.resolve()
    if resolved == Path(resolved.anchor):
        raise SystemExit(f"stage_release: refusing to wipe filesystem root {resolved}")
    if resolved == REPO_ROOT or resolved in REPO_ROOT.parents:
        raise SystemExit(f"stage_release: refusing to wipe {resolved} (repo root or ancestor)")


def stage(out: Path) -> Path:
    """Build the release tree at ``out`` (wiped first). Returns ``out``."""
    _guard_out(out)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    for rel in SHIP:
        src = REPO_ROOT / rel
        if src.exists():
            _copy(src, out / rel)

    # Build each bundle directly into the staged skill dir — the only scripts a
    # released skill ships. Sources stay in the repo's src/ + shared/, unshipped.
    for skill in build_pyz.SKILLS:
        target = out / "skills" / skill / "scripts" / f"{skill}.pyz"
        build_pyz.build_bundle(skill, target)

    _verify(out)
    return out


def _verify(out: Path) -> None:
    """Fail loud if the staged tree is wrong — a broken release should never get
    silently published (the v0.5.1 failure mode)."""
    skills = out / "skills"
    if not any(skills.glob("*/SKILL.md")):
        raise SystemExit(f"stage_release: no skills found under {skills}")

    for skill in build_pyz.SKILLS:
        pyz = skills / skill / "scripts" / f"{skill}.pyz"
        if not pyz.is_file():
            raise SystemExit(f"stage_release: missing bundle {pyz}")

    stray = sorted(str(p.relative_to(out)) for p in skills.rglob("*.py"))
    if stray:
        raise SystemExit(
            "stage_release: raw .py sources must not ship under skills/; found: "
            + ", ".join(stray)
        )


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Stage the shippable release tree.")
    parser.add_argument("--out", type=Path, required=True, help="Output directory (wiped first).")
    args = parser.parse_args(argv[1:])
    out = stage(args.out)
    print(f"staged release tree at {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
