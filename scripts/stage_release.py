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
import os
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_pyz  # noqa: E402  (sibling module in scripts/)

REPO_ROOT = Path(__file__).resolve().parents[1]
SHARED_DIR = REPO_ROOT / "shared"

# A reference to a markdown asset under repo-root shared/, with any number of
# leading `../` segments. The char class excludes `/`, so `shared/scripts/x.py`
# (Python, already bundled into the .pyz) never matches — only flat
# `shared/<name>.md` docs do.
_SHARED_MD_REF = re.compile(r"(?:\.\./)*shared/([A-Za-z0-9._-]+\.md)")

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


def _skill_markdown(skill_dir: Path) -> list[Path]:
    """The authored markdown a skill ships: SKILL.md + every references/*.md."""
    files = [skill_dir / "SKILL.md"]
    refs = skill_dir / "references"
    if refs.is_dir():
        files.extend(sorted(refs.glob("*.md")))
    return [f for f in files if f.is_file()]


def _rewrite_shared_refs(path: Path, skill_dir: Path) -> None:
    """Rewrite every `(../)*shared/<name>.md` reference in ``path`` to a path
    relative to ``path`` itself, pointing at the skill-local vendored copy at
    ``skill_dir/shared/<name>.md``. Works for SKILL.md (-> `shared/x.md`),
    references/*.md (-> `../shared/x.md`), and the vendored docs themselves
    (-> `x.md`)."""
    text = path.read_text(encoding="utf-8")

    def repl(match: re.Match[str]) -> str:
        target = skill_dir / "shared" / match.group(1)
        return Path(os.path.relpath(target, path.parent)).as_posix()

    rewritten = _SHARED_MD_REF.sub(repl, text)
    if rewritten != text:
        path.write_text(rewritten, encoding="utf-8")


def _vendor_shared_assets(out: Path) -> None:
    """Make each skill's repo-root `shared/*.md` references resolve post-install.

    `gh skill install` ships only `skills/<name>/`, so repo-root `shared/` docs
    a SKILL.md cites (handoff-gate.md, formatting.md) vanish on install. Copy
    each referenced doc into `skills/<name>/shared/` and rewrite the references
    to skill-relative paths. Python `shared/scripts/*.py` is excluded — it is
    already vendored into the .pyz by build_pyz."""
    skills_root = out / "skills"
    for skill_dir in sorted(p for p in skills_root.iterdir() if p.is_dir()):
        authored = _skill_markdown(skill_dir)
        needed: set[str] = set()
        for md in authored:
            needed.update(_SHARED_MD_REF.findall(md.read_text(encoding="utf-8")))
        if not needed:
            continue
        vendor_dir = skill_dir / "shared"
        vendor_dir.mkdir(exist_ok=True)
        for name in sorted(needed):
            src = SHARED_DIR / name
            if not src.is_file():
                raise SystemExit(
                    f"stage_release: {skill_dir.name} references shared/{name} "
                    "but no such file exists under shared/"
                )
            shutil.copy2(src, vendor_dir / name)
        # Rewrite both the authored prose and the vendored docs (a vendored doc
        # may cross-reference a sibling shared doc that now sits beside it).
        for md in authored + [vendor_dir / n for n in sorted(needed)]:
            _rewrite_shared_refs(md, skill_dir)


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

    # Vendor referenced shared/*.md docs into each skill so their references
    # resolve post-install (repo-root shared/ is never shipped).
    _vendor_shared_assets(out)

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
