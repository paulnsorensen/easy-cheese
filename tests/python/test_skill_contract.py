"""Skill↔bundle contract oracle (Cut RED evidence for pyz-pipeline-contracts).

Asserts strict equality between skill-markdown `<bundle>.pyz <subcommand>`
references and the build_pyz registries (AC-2), the ships-as banner on every
individually registered source file (AC-7), and a pure-Python src/ tree after
the Astro site moves to website/ (AC-8). Derived from build_pyz.SKILLS — there
is no hand-copied registry here.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "shared" / "scripts"))
import build_pyz  # noqa: E402

WITNESS_EQUALITY = (
    "On main the equality assertion fails: 12 registered subcommands, "
    "including press.pyz red-gate, have no skill-markdown reference"
)
WITNESS_BANNERS = (
    "On main the banner test fails: src/age/age-html-report.py has no "
    "ships-as header line"
)
WITNESS_SRC_PURITY = (
    "On main the assertion that src/ contains no Astro sources fails: "
    "src/components/Sidebar.astro exists"
)

_REFERENCE = re.compile(r"\b([a-z][a-z0-9_-]*)\.pyz\s+([A-Za-z_][A-Za-z0-9_-]*)")
_BANNER = re.compile(r"^# ships-as: \S+\.pyz")
_BANNER_WINDOW = 5


def registered_subcommands() -> frozenset[tuple[str, str]]:
    """Every (bundle, subcommand) pair the build registries declare."""
    pairs = {
        (skill, sub)
        for skill, subs in build_pyz.SKILLS.items()
        for sub in subs
    }
    pairs |= {(build_pyz.COMMON, sub) for sub in build_pyz.COMMON_SUBCOMMANDS}
    return frozenset(pairs)


def referenced_subcommands() -> frozenset[tuple[str, str]]:
    """Every (bundle, subcommand) invocation referenced in skills/**/*.md."""
    bundles = {*build_pyz.SKILLS, build_pyz.COMMON}
    referenced = set()
    for markdown in sorted((REPO_ROOT / "skills").rglob("*.md")):
        for match in _REFERENCE.finditer(markdown.read_text(encoding="utf-8")):
            if match.group(1) in bundles:
                referenced.add((match.group(1), match.group(2)))
    return frozenset(referenced)


def registered_source_files() -> frozenset[Path]:
    """Every individually registered source file the registries name.

    SKILLS and COMMON_SUBCOMMANDS entries resolve through build_pyz's own
    staging resolution; EXTRA_MODULES entries are src/-relative. PACKAGE_TREES
    stage whole directories and are deliberately out of scope: only files the
    registries name one-by-one carry a ships-as banner.
    """
    files = {
        build_pyz._source_path(skill, source)
        for skill, subs in build_pyz.SKILLS.items()
        for source in subs.values()
    }
    files |= {
        build_pyz._source_path(build_pyz.COMMON, source)
        for source in build_pyz.COMMON_SUBCOMMANDS.values()
    }
    files |= {
        build_pyz.SRC_ROOT / src_subdir / filename
        for entries in build_pyz.EXTRA_MODULES.values()
        for src_subdir, filename in entries
    }
    return frozenset(files)


def _fmt(pairs: frozenset[tuple[str, str]]) -> str:
    return "\n".join(f"  {bundle}.pyz {sub}" for bundle, sub in sorted(pairs))


def test_registry_equals_prose() -> None:
    registered = registered_subcommands()
    referenced = referenced_subcommands()
    unreferenced = registered - referenced
    unregistered = referenced - registered
    detail = (
        f"registered but never referenced in skills markdown:\n{_fmt(unreferenced)}\n"
        f"referenced in skills markdown but not registered:\n{_fmt(unregistered)}"
    )
    assert not unreferenced and not unregistered, f"{WITNESS_EQUALITY}\n{detail}"


def test_source_banners() -> None:
    missing = []
    for source in sorted(registered_source_files()):
        head = source.read_text(encoding="utf-8").splitlines()[:_BANNER_WINDOW]
        if not any(_BANNER.match(line) for line in head):
            missing.append(source.relative_to(REPO_ROOT).as_posix())
    detail = "\n".join(f"  {path}" for path in missing)
    assert not missing, f"{WITNESS_BANNERS}\nmissing ships-as banner:\n{detail}"


def test_src_is_pure_python() -> None:
    src = REPO_ROOT / "src"
    offenders = [path.relative_to(REPO_ROOT).as_posix() for path in src.rglob("*.astro")]
    for name in ("components", "pages", "styles", "content", "sidebar.mjs", "content.config.ts"):
        if (src / name).exists():
            offenders.append(f"src/{name}")
    detail = "\n".join(f"  {path}" for path in sorted(set(offenders)))
    assert not offenders, f"{WITNESS_SRC_PURITY}\nAstro sources still in src/:\n{detail}"
