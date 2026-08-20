"""Skill↔bundle contract oracle (Cut RED evidence for pyz-pipeline-contracts).

Asserts strict equality between skill-markdown `<bundle>.pyz <subcommand>`
references and the build_pyz registries (AC-2), the ships-as banner on every
individually registered source file (AC-7), and a Python-plus-docs src/ tree
after the Astro site moves to website/ (AC-8). Derived from build_pyz.SKILLS — there
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


def referenced_invocations() -> frozenset[tuple[str, str, str]]:
    """Every (skill, bundle, subcommand) invocation in skills/**/*.md."""
    bundles = {*build_pyz.SKILLS, build_pyz.COMMON}
    referenced = set()
    skills_root = REPO_ROOT / "skills"
    for markdown in sorted(skills_root.rglob("*.md")):
        skill = markdown.relative_to(skills_root).parts[0]
        for match in _REFERENCE.finditer(markdown.read_text(encoding="utf-8")):
            if match.group(1) in bundles:
                referenced.add((skill, match.group(1), match.group(2)))
    return frozenset(referenced)


def referenced_subcommands() -> frozenset[tuple[str, str]]:
    """Every (bundle, subcommand) invocation referenced in skills/**/*.md."""
    return frozenset(
        (bundle, subcommand)
        for _, bundle, subcommand in referenced_invocations()
    )


def registered_source_banners() -> dict[Path, tuple[str, ...]]:
    """Exact ships-as entries for every individually registered source file."""
    entries: dict[Path, list[str]] = {}

    def add(source: Path, entry: str) -> None:
        entries.setdefault(source, []).append(entry)

    for skill, subcommands in build_pyz.SKILLS.items():
        for subcommand, source in subcommands.items():
            add(build_pyz._source_path(skill, source), f"{skill}.pyz {subcommand}")
    for subcommand, source in build_pyz.COMMON_SUBCOMMANDS.items():
        add(
            build_pyz._source_path(build_pyz.COMMON, source),
            f"{build_pyz.COMMON}.pyz {subcommand}",
        )
    for skill, modules in build_pyz.EXTRA_MODULES.items():
        for src_subdir, filename in modules:
            add(build_pyz.SRC_ROOT / src_subdir / filename, f"{skill}.pyz (module)")
    return {source: tuple(values) for source, values in entries.items()}


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


def test_common_consumers_cover_references() -> None:
    referenced = {
        skill
        for skill, bundle, _ in referenced_invocations()
        if bundle == build_pyz.COMMON
    }
    missing = referenced - build_pyz.COMMON_CONSUMERS
    detail = "\n".join(f"  {skill}" for skill in sorted(missing))
    assert not missing, f"common.pyz references from non-consumers:\n{detail}"


def test_source_banners() -> None:
    mismatches = []
    for source, entries in sorted(registered_source_banners().items()):
        expected = f"# ships-as: {' '.join(entries)}"
        head = source.read_text(encoding="utf-8").splitlines()[:_BANNER_WINDOW]
        actual = next((line for line in head if line.startswith("# ships-as:")), None)
        if actual != expected:
            path = source.relative_to(REPO_ROOT).as_posix()
            mismatches.append(f"  {path}: expected {expected!r}, got {actual!r}")
    detail = "\n".join(mismatches)
    assert not mismatches, f"{WITNESS_BANNERS}\nships-as mismatch:\n{detail}"


def test_src_contains_only_python_and_docs() -> None:
    src = REPO_ROOT / "src"
    offenders = [path.relative_to(REPO_ROOT).as_posix() for path in src.rglob("*.astro")]
    for name in ("components", "pages", "styles", "content", "sidebar.mjs", "content.config.ts"):
        if (src / name).exists():
            offenders.append(f"src/{name}")
    detail = "\n".join(f"  {path}" for path in sorted(set(offenders)))
    assert not offenders, f"{WITNESS_SRC_PURITY}\nAstro sources still in src/:\n{detail}"
