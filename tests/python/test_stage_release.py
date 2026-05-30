"""The staged release tree is exactly the shippable surface: every skill carries
its built <skill>.pyz and its SKILL.md, no raw .py sources leak in, and dev-only
scaffolding (src/, shared/, scripts/, tests/, docs/, .github/) is left behind.
These are the invariants that, when violated silently, shipped the empty v0.5.1.
"""

from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import build_pyz  # noqa: E402
import stage_release  # noqa: E402


@pytest.fixture(scope="module")
def staged(tmp_path_factory) -> Path:
    return stage_release.stage(tmp_path_factory.mktemp("release") / "tree")


def test_every_skill_ships_its_bundle(staged: Path) -> None:
    for skill in build_pyz.SKILLS:
        pyz = staged / "skills" / skill / "scripts" / f"{skill}.pyz"
        assert pyz.is_file(), f"missing bundle for {skill}"
        # A real zipapp, not an empty placeholder: it carries the dispatcher.
        with zipfile.ZipFile(pyz) as zf:
            assert "__main__.py" in zf.namelist()


def test_skill_metadata_ships(staged: Path) -> None:
    for skill in build_pyz.SKILLS:
        assert (staged / "skills" / skill / "SKILL.md").is_file()


def test_no_raw_python_under_skills(staged: Path) -> None:
    """The release ships the .pyz, never the loose .py — the whole point of the
    src/ relocation. A stray .py here means a skill leaked its sources."""
    stray = sorted(p.relative_to(staged) for p in (staged / "skills").rglob("*.py"))
    assert stray == [], f"raw python leaked into release: {stray}"


@pytest.mark.parametrize("dev_dir", ["src", "shared", "scripts", "tests", "docs", ".github"])
def test_dev_scaffolding_excluded(staged: Path, dev_dir: str) -> None:
    assert not (staged / dev_dir).exists(), f"{dev_dir}/ must not ship in a release"


def test_top_level_metadata_present(staged: Path) -> None:
    assert (staged / "README.md").is_file()
    assert (staged / "LICENSE").is_file()


@pytest.mark.parametrize("danger", ["/", str(REPO_ROOT), str(REPO_ROOT.parent)])
def test_stage_refuses_to_wipe_dangerous_paths(danger: str) -> None:
    """rmtree on --out must never touch the filesystem root, the repo, or an
    ancestor — accidental data loss is the irreversible failure mode here."""
    with pytest.raises(SystemExit, match="refusing to wipe"):
        stage_release.stage(Path(danger))


def test_verify_rejects_missing_bundle(tmp_path: Path) -> None:
    """_verify is the publish gate — it must reject a tree whose bundles are absent."""
    fake = tmp_path / "tree"
    (fake / "skills" / "affinage").mkdir(parents=True)
    (fake / "skills" / "affinage" / "SKILL.md").write_text("# affinage\n")
    with pytest.raises(SystemExit, match="missing bundle"):
        stage_release._verify(fake)


# Any `shared/<...>` reference in shipped markdown, with leading `../` segments.
# Broader than the stager's vendoring regex on purpose: the reachability test
# must also catch a non-`.md`, non-`scripts/` shared ref that was never vendored.
_ANY_SHARED_REF = re.compile(r"(?:\.\./)*shared/([A-Za-z0-9._/-]+)")


def test_shared_doc_refs_resolve_in_staged_tree(staged: Path) -> None:
    """The issue's core requirement: an installed skill must reach every path
    its SKILL.md (or references/) invokes. Every `shared/…` reference in shipped
    markdown — excluding `shared/scripts/*` (bundled into the .pyz) — must
    resolve to a real file inside that skill's own directory, with no link
    escaping the skill dir."""
    skills = staged / "skills"
    problems: list[str] = []
    for md in sorted(skills.rglob("*.md")):
        skill_root = (skills / md.relative_to(skills).parts[0]).resolve()
        for match in _ANY_SHARED_REF.finditer(md.read_text(encoding="utf-8")):
            ref, sub = match.group(0), match.group(1)
            if sub.startswith("scripts/"):
                continue  # Python helpers ride the .pyz, not the file tree.
            target = (md.parent / ref).resolve()
            rel = md.relative_to(staged)
            if not target.is_file():
                problems.append(f"{rel} -> {ref} (missing)")
            elif skill_root != target and skill_root not in target.parents:
                problems.append(f"{rel} -> {ref} (escapes {skill_root.name}/)")
    assert not problems, "unresolved shared/ refs in staged tree:\n" + "\n".join(problems)


def test_vendor_missing_shared_doc_fails_loud(tmp_path: Path) -> None:
    """If a SKILL.md cites a shared/<name>.md that does not exist under shared/,
    vendoring must fail loud at stage time rather than silently ship a skill
    whose reference dangles post-install."""
    tree = tmp_path / "tree"
    skill = tree / "skills" / "ghost"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "See [the gate](../../shared/does-not-exist.md).\n", encoding="utf-8"
    )
    with pytest.raises(SystemExit, match="no such file exists under shared/"):
        stage_release._vendor_shared_assets(tree)


def test_referenced_shared_docs_are_vendored(staged: Path) -> None:
    """A skill that cites shared/handoff-gate.md / shared/formatting.md must get
    a vendored copy beside it, and its SKILL.md must point at the skill-local
    path (no surviving `../../shared/` escape)."""
    cook_skill = staged / "skills" / "cook"
    skill_md = (cook_skill / "SKILL.md").read_text(encoding="utf-8")
    assert "shared/formatting.md" in skill_md  # still references it
    assert "../../shared/formatting.md" not in skill_md  # but rewritten
    assert (cook_skill / "shared" / "formatting.md").is_file()
