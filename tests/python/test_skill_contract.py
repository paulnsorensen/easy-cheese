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
WITNESS_COMMON_CONSUMERS = (
    "a common.pyz markdown reference must name a COMMON_CONSUMERS skill"
)

_REFERENCE = re.compile(r"\b([a-z][a-z0-9_-]*)\.pyz\s+([A-Za-z_][A-Za-z0-9_-]*)")
_BANNER = re.compile(r"^# ships-as:")
_BANNER_BUNDLES = re.compile(r"([a-z][a-z0-9_-]*)\.pyz")
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


def _banner_bundles(source: Path) -> frozenset[str]:
    for line in source.read_text(encoding="utf-8").splitlines()[:_BANNER_WINDOW]:
        if _BANNER.match(line):
            return frozenset(_BANNER_BUNDLES.findall(line))
    return frozenset()


def _staged_bundles(source: Path) -> frozenset[str]:
    bundles: set[str] = set()
    for skill, subs in build_pyz.SKILLS.items():
        for src in subs.values():
            if build_pyz._source_path(skill, src) == source:
                bundles.add(skill)
    for src in build_pyz.COMMON_SUBCOMMANDS.values():
        if build_pyz._source_path(build_pyz.COMMON, src) == source:
            bundles.add(build_pyz.COMMON)
    for skill, entries in build_pyz.EXTRA_MODULES.items():
        for src_subdir, filename in entries:
            if build_pyz.SRC_ROOT / src_subdir / filename == source:
                bundles.add(skill)
    for skill in build_pyz.SKILLS:
        skill_dir = build_pyz._src_dir(skill)
        if (
            source.parent == skill_dir
            and source.stem in build_pyz._local_skill_modules(skill)
        ):
            bundles.add(skill)
    return frozenset(bundles)


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


def test_common_consumers_cover_prose() -> None:
    consumers: set[str] = set()
    skills_root = REPO_ROOT / "skills"
    for markdown in sorted(skills_root.rglob("*.md")):
        if re.search(
            r"\bcommon\.pyz\s+[A-Za-z_]",
            markdown.read_text(encoding="utf-8"),
        ):
            consumers.add(markdown.relative_to(skills_root).parts[0])
    missing = consumers - build_pyz.COMMON_CONSUMERS
    detail = "\n".join(f"  {skill}" for skill in sorted(missing))
    assert not missing, f"{WITNESS_COMMON_CONSUMERS}\n{detail}"


def test_source_banners() -> None:
    missing = []
    drifted = []
    for source in sorted(registered_source_files()):
        claimed = _banner_bundles(source)
        rel = source.relative_to(REPO_ROOT).as_posix()
        if not claimed:
            missing.append(rel)
            continue
        staged = _staged_bundles(source)
        if claimed != staged:
            drifted.append(
                f"  {rel}: banner={sorted(claimed)} staged={sorted(staged)}"
            )
    detail = "\n".join(
        ["missing ships-as banner:", *(f"  {path}" for path in missing)]
        + (["banner/stage mismatch:", *drifted] if drifted else [])
    )
    assert not missing and not drifted, f"{WITNESS_BANNERS}\n{detail}"


def test_src_is_pure_python() -> None:
    src = REPO_ROOT / "src"
    offenders = [path.relative_to(REPO_ROOT).as_posix() for path in src.rglob("*.astro")]
    for name in ("components", "pages", "styles", "content", "sidebar.mjs", "content.config.ts"):
        if (src / name).exists():
            offenders.append(f"src/{name}")
    detail = "\n".join(f"  {path}" for path in sorted(set(offenders)))
    assert not offenders, f"{WITNESS_SRC_PURITY}\nAstro sources still in src/:\n{detail}"
