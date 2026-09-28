"""The staged release tree contains one executable archive per Python skill."""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import runtime_gates  # noqa: E402
import stage_release  # noqa: E402
from ref_extraction import relative_md_refs  # noqa: E402  # pyright: ignore[reportImplicitRelativeImport]


@pytest.fixture(scope="module")
def staged(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    yield stage_release.stage(tmp_path_factory.mktemp("release") / "tree")


def _fake_tree(root: Path, *, without_archive: str | None = None) -> Path:
    """A minimal tree that passes _verify unless one archive is withheld."""
    for skill in runtime_gates.SKILLS:
        scripts = root / "skills" / skill / "scripts"
        scripts.mkdir(parents=True)
        _ = (root / "skills" / skill / "SKILL.md").write_text(f"# {skill}\n")
        if skill != without_archive:
            archive = scripts / f"{skill}.pyz"
            _ = archive.write_bytes(b"#!/usr/bin/env python3\n")
            archive.chmod(0o755)
    return root


def test_every_skill_ships_its_archive(staged: Path) -> None:
    for skill in runtime_gates.SKILLS:
        archive = staged / "skills" / skill / "scripts" / f"{skill}.pyz"
        assert archive.is_file(), f"missing archive for {skill}"
        assert archive.stat().st_mode & 0o111, f"archive for {skill} is not executable"


def test_skill_metadata_ships(staged: Path) -> None:
    for skill in runtime_gates.SKILLS:
        assert (staged / "skills" / skill / "SKILL.md").is_file()
    assert (staged / "skills/mold/scripts/mold.dot").is_file()


def test_no_source_or_build_config_under_skills(staged: Path) -> None:
    stray = sorted(
        str(p.relative_to(staged))
        for pattern in ("*.py", "wedge.toml")
        for p in (staged / "skills").rglob(pattern)
    )
    assert stray == [], f"build inputs leaked into release: {stray}"


@pytest.mark.parametrize("dev_dir", ["src", "shared", "scripts", "tests", "docs", ".github"])
def test_dev_scaffolding_excluded(staged: Path, dev_dir: str) -> None:
    assert not (staged / dev_dir).exists(), f"{dev_dir}/ must not ship in a release"


def test_top_level_metadata_present(staged: Path) -> None:
    assert (staged / "README.md").is_file()
    assert (staged / "LICENSE").is_file()


@pytest.mark.parametrize("danger", ["/", str(REPO_ROOT), str(REPO_ROOT.parent)])
def test_stage_refuses_to_wipe_dangerous_paths(danger: str) -> None:
    """rmtree on --out must never touch the filesystem root, the repo, or an
    ancestor: accidental data loss is the irreversible failure mode here."""
    with pytest.raises(SystemExit, match="refusing to wipe"):
        _ = stage_release.stage(Path(danger))


def test_verify_rejects_missing_archive(tmp_path: Path) -> None:
    """_verify is the publish gate; it must reject a tree without an archive."""
    fake = tmp_path / "tree"
    (fake / "skills" / "affinage").mkdir(parents=True)
    _ = (fake / "skills" / "affinage" / "SKILL.md").write_text("# affinage\n")
    with pytest.raises(SystemExit, match="missing archive"):
        stage_release._verify(fake)  # pyright: ignore[reportPrivateUsage]


def test_verify_rejects_missing_skill_archive(tmp_path: Path) -> None:
    fake = _fake_tree(tmp_path / "tree", without_archive="cook")
    with pytest.raises(SystemExit, match=r"missing archive .*cook\.pyz"):
        stage_release._verify(fake)  # pyright: ignore[reportPrivateUsage]


def test_verify_rejects_stray_source(tmp_path: Path) -> None:
    fake = _fake_tree(tmp_path / "tree")
    _ = (fake / "skills" / "cook" / "scripts" / "helper.py").write_bytes(b"x")
    with pytest.raises(SystemExit, match="unexpected generated artifacts"):
        stage_release._verify(fake)  # pyright: ignore[reportPrivateUsage]



@pytest.mark.parametrize(
    ("relative", "message"),
    [
        ("skills/cook/scripts/cook", "unexpected generated artifacts"),
        ("skills/cook/scripts/cook.wedge.json", "unexpected generated artifacts"),
        ("skills/cook/scripts/extra.pyz", "unexpected generated artifacts"),
    ],
)
def test_verify_rejects_legacy_or_extra_artifacts(
    tmp_path: Path, relative: str, message: str
) -> None:
    fake = _fake_tree(tmp_path / "tree")
    artifact = fake / relative
    artifact.parent.mkdir(parents=True, exist_ok=True)
    _ = artifact.write_bytes(b"legacy")
    with pytest.raises(SystemExit, match=message):
        stage_release._verify(fake)  # pyright: ignore[reportPrivateUsage]


def test_verify_accepts_a_complete_tree(tmp_path: Path) -> None:
    stage_release._verify(_fake_tree(tmp_path / "tree"))  # pyright: ignore[reportPrivateUsage]


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
)


def test_moved_cheese_kernel_docs_ship_with_zero_vendoring(staged: Path) -> None:
    """The four shared docs move with the wholesale skills/ copy; no dedicated
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


def test_release_workflow_builds_nothing() -> None:
    """Archives come from the wedge release the merge-to-main job fills, so the
    tag workflow installs no build tooling and runs no build."""
    workflow = (REPO_ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert "requirements-build.txt" not in workflow
    assert "build_pyz" not in workflow
    assert "shiv" not in workflow.lower()


def test_release_workflow_pins_checkout_to_v7_0_1() -> None:
    workflow = (REPO_ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")

    assert "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1" in workflow
