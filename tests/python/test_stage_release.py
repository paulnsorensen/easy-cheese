"""The staged release tree is exactly the shippable surface: every skill carries
its built <skill>.pyz and its SKILL.md, no raw .py sources leak in, and dev-only
scaffolding (src/, shared/, scripts/, tests/, docs/, .github/) is left behind.
These are the invariants that, when violated silently, shipped the empty v0.5.1.
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import build_pyz  # noqa: E402
import stage_release  # noqa: E402
from ref_extraction import relative_md_refs  # noqa: E402


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




def test_relative_refs_resolve_in_staged_tree(staged: Path) -> None:
    """The sibling-skills-ship-wholesale layout means every relative markdown
    ref under skills/**/*.md must resolve from its own file's directory, with
    zero vendoring machinery required."""
    problems: list[str] = []
    for md in sorted((staged / "skills").rglob("*.md")):
        for ref in relative_md_refs(md.read_text(encoding="utf-8")):
            if not (md.parent / ref).resolve().is_file():
                problems.append(f"{md.relative_to(staged)} -> {ref}")
    assert not problems, "unresolved refs in staged tree:\n" + "\n".join(problems)


_MOVED_DOC_NAMES = (
    "formatting",
    "handoff-gate",
    "harness-portability",
    "optional-plugins",
    "skill-authoring",
)


def test_moved_cheese_kernel_docs_ship_with_zero_vendoring(staged: Path) -> None:
    """The five shared docs move with the wholesale skills/ copy — no dedicated
    vendoring step exists or is needed. Locks the ship location explicitly so a
    future denylist/exclude change to stage_release can't silently drop them
    while test_relative_refs_resolve_in_staged_tree stays green (that test only
    checks refs among files that DO ship, not that these specific docs shipped
    at all)."""
    refs_dir = staged / "skills" / "cheese" / "references"
    for name in _MOVED_DOC_NAMES:
        assert (refs_dir / f"{name}.md").is_file(), f"{name}.md missing from staged skills/cheese/references/"
    assert not (staged / "shared").exists()


def test_release_workflow_validates_staged_tree_after_transformations() -> None:
    workflow = (REPO_ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    stage = workflow.index("python3 scripts/stage_release.py")
    validate = workflow.index("gh skill publish --dry-run")
    publish = workflow.index("git init -q")

    assert stage < validate < publish
    assert "working-directory: ${{ runner.temp }}/release" in workflow[stage:validate]


def test_release_workflow_pins_checkout_to_v6_0_2() -> None:
    workflow = (REPO_ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")

    assert "actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6.0.2" in workflow