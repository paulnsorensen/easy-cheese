"""The staged release tree is exactly the shippable surface: every skill carries
its built <skill>.pyz and its SKILL.md, no raw .py sources leak in, and dev-only
scaffolding (src/, shared/, scripts/, tests/, docs/, .github/) is left behind.
These are the invariants that, when violated silently, shipped the empty v0.5.1.
"""

from __future__ import annotations

import json
import sys
import subprocess
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import build_pyz  # noqa: E402
import stage_release  # noqa: E402
from ref_extraction import relative_md_refs  # noqa: E402
from easy_cheese.shared.handoffs import canonical_bytes  # noqa: E402
from tests.schemas.python.test_handoff_contracts import (  # noqa: E402
    repaired_writer_text,
    writer_and_invocation,
)


@pytest.fixture(scope="module")
def staged(tmp_path_factory) -> Path:
    return stage_release.stage(tmp_path_factory.mktemp("release") / "tree")


def test_release_batch_derives_and_reuses_schema_catalog_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    compiled_calls = 0
    validated_calls = 0
    validated_catalog: bytes | None = None
    catalog_values: list[bytes | None] = []
    compile_catalog = build_pyz._compiled_schema_catalog_source
    validate_catalog = build_pyz._checked_in_schema_catalog_bytes
    build_bundle = build_pyz.build_bundle

    def compile_once() -> str:
        nonlocal compiled_calls
        compiled_calls += 1
        return compile_catalog()

    def validate_once(source: str) -> bytes:
        nonlocal validated_calls, validated_catalog
        validated_calls += 1
        validated_catalog = validate_catalog(source)
        return validated_catalog

    def build_with_catalog(
        skill: str,
        target: Path,
        *,
        schema_catalog_bytes: bytes | None = None,
        document_rules_bytes: bytes | None = None,
    ) -> Path:
        catalog_values.append(schema_catalog_bytes)
        return build_bundle(
            skill,
            target,
            schema_catalog_bytes=schema_catalog_bytes,
            document_rules_bytes=document_rules_bytes,
        )

    monkeypatch.setattr(build_pyz, "_compiled_schema_catalog_source", compile_once)
    monkeypatch.setattr(build_pyz, "_checked_in_schema_catalog_bytes", validate_once)
    monkeypatch.setattr(build_pyz, "build_bundle", build_with_catalog)

    stage_release.stage(tmp_path / "release")

    assert compiled_calls == 1
    assert validated_calls == 1
    assert len(catalog_values) == len(build_pyz.SKILLS)
    assert validated_catalog == build_pyz.SCHEMA_CATALOG_SOURCE.read_bytes()
    assert all(value is validated_catalog for value in catalog_values)


def test_every_skill_ships_its_bundle(staged: Path) -> None:
    for skill in build_pyz.SKILLS:
        pyz = staged / "skills" / skill / "scripts" / f"{skill}.pyz"
        assert pyz.is_file(), f"missing bundle for {skill}"
        # A real zipapp, not an empty placeholder: it carries the dispatcher.
        with zipfile.ZipFile(pyz) as zf:
            assert "__main__.py" in zf.namelist()


@pytest.mark.parametrize("skill", ["mold", "cook"])
def test_staged_layout_bundles_dispatch_in_isolation(
    staged: Path, skill: str, tmp_path: Path
) -> None:
    pyz = staged / "skills" / skill / "scripts" / f"{skill}.pyz"
    result = subprocess.run(
        [sys.executable, "-I", "-S", str(pyz), "--help"],
        cwd=tmp_path,
        env={"PATH": "", "PYTHONPATH": "/does/not/exist"},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "contract" in result.stdout


def test_staged_mold_cook_contract_round_trip_is_isolated(
    staged: Path, tmp_path: Path
) -> None:
    """Published staged Mold output must be consumable by staged Cook alone."""
    writer, invocation = writer_and_invocation(tmp_path)
    writer_path = tmp_path / "writer.jsonish"
    invocation_path = tmp_path / "invocation.json"
    writer_path.write_text(repaired_writer_text(writer), encoding="utf-8")
    invocation_path.write_bytes(canonical_bytes(invocation.to_mapping()))
    environment = {"PATH": "", "PYTHONPATH": "/does/not/exist"}
    mold = staged / "skills" / "mold" / "scripts" / "mold.pyz"
    cook = staged / "skills" / "cook" / "scripts" / "cook.pyz"

    produced = subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            str(mold),
            "contract",
            "publish",
            "--writer-view",
            str(writer_path),
            "--invocation",
            str(invocation_path),
            "--operation-id",
            "staged-round-trip",
        ],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
    )
    assert produced.returncode == 0, produced.stdout + produced.stderr
    pointer_path = tmp_path / "pointers" / "staged-round-trip.json"
    assert json.loads(produced.stdout) == json.loads(pointer_path.read_text())

    consumed = subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            str(cook),
            "contract",
            "accept",
            "--pointer",
            str(pointer_path),
        ],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
    )
    assert consumed.returncode == 0, consumed.stdout + consumed.stderr
    assert json.loads(consumed.stdout)["plan_id"] == "plan-1"


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
)


def test_moved_cheese_kernel_docs_ship_with_zero_vendoring(staged: Path) -> None:
    """The four shared docs move with the wholesale skills/ copy — no dedicated
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


def test_release_workflow_pins_checkout_to_v7_0_0() -> None:
    workflow = (REPO_ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")

    assert "actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0 # v7.0.0" in workflow
