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
