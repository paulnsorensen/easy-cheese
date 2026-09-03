"""Doctrine-topology conformance: the one-skill/one-bundle boundary rules.

Easy Cheese's landed doctrine forbids reintroducing a shared common.pyz,
copying another skill's sources into a skill's own tree, and flattening the
src/ runtime roots. These tests fabricate each violation and assert the
enforcement in scripts/check_bundles.py (or, where no runtime checker exists,
the repo's own layout) rejects it.

Whole-package staging markers (nested dirs, .dist-info metadata) are already
guarded by tests/python/test_build_pyz_tree_staging.py against real builds;
not duplicated here.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts import check_bundles

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_common_pyz_reintroduction_fails_the_bundle_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A resurrected skills/*/scripts/common.pyz must fail the gate outright."""
    bundle_dir = tmp_path / "skills" / "demo" / "scripts"
    bundle_dir.mkdir(parents=True)
    _ = (bundle_dir / "common.pyz").write_bytes(b"stale-shared-bundle")
    monkeypatch.setattr(check_bundles, "REPO_ROOT", tmp_path)

    assert check_bundles.main() == 1
    output = capsys.readouterr().out
    assert "obsolete shared bundle" in output


def test_check_pyz_references_flags_common_pyz_mentions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Docs still naming the retired shared bundle are a doctrine violation."""
    skill_dir = tmp_path / "skills" / "demo"
    skill_dir.mkdir(parents=True)
    _ = (skill_dir / "SKILL.md").write_text("Shared helpers live in common.pyz.\n")
    monkeypatch.setattr(check_bundles, "REPO_ROOT", tmp_path)

    violations = check_bundles.check_pyz_references()
    assert any("obsolete shared bundle common.pyz" in v for v in violations)


def test_check_pyz_references_flags_cross_skill_source_copying(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A skill's own source naming a sibling skill's .pyz signals its code
    (or docs) leaked in from another skill's tree, which check_import_closure
    cannot see since it only audits one archive at a time.
    """
    demo_scripts = tmp_path / "skills" / "demo" / "scripts"
    demo_scripts.mkdir(parents=True)
    _ = (demo_scripts / "helper.py").write_text(
        "# copied from other-skill.pyz's helper module\n"
    )
    monkeypatch.setattr(check_bundles, "REPO_ROOT", tmp_path)

    violations = check_bundles.check_pyz_references()
    assert any(
        "other-skill.pyz, not its own demo.pyz" in v for v in violations
    )


def test_source_tree_has_no_flat_runtime_roots() -> None:
    """Every runtime source lives under src/easy_cheese/{skills,shared} or
    src/easy_cheese_schemas; nothing else may sit at the src/ or
    src/easy_cheese root (the doctrine this bundle-currency gate exists to
    keep honest).
    """
    src_root = REPO_ROOT / "src"
    ignored = {"__pycache__"}
    assert {
        path.name for path in src_root.iterdir() if path.name not in ignored
    } == {"easy_cheese", "easy_cheese_schemas"}
    easy_cheese_children = {
        path.name
        for path in (src_root / "easy_cheese").iterdir()
        if path.name not in ignored
    }
    assert easy_cheese_children <= {"__init__.py", "skills", "shared"}
