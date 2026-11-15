"""Doctrine-topology conformance: the one-skill/one-launcher boundary rules.

Easy Cheese's landed doctrine forbids naming a shared common.pyz or any
retired archive, copying another skill's sources into a skill's own tree,
naming another skill's launcher, and flattening the src/ runtime roots. These
tests fabricate each violation and assert scripts/runtime_gates.py (or, where
no runtime checker exists, the repo's own layout) rejects it. A checked-in
archive file itself is `wedge check`'s rule.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import runtime_gates  # noqa: E402


def _scan(root: Path, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    monkeypatch.setattr(runtime_gates, "REPO_ROOT", root)
    return runtime_gates.check_skill_references()


def _skill(root: Path, name: str) -> Path:
    skill_dir = root / "skills" / name
    (skill_dir / "scripts").mkdir(parents=True)
    return skill_dir


def test_common_pyz_mentions_are_flagged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Docs still naming the retired shared bundle are a doctrine violation."""
    _ = (_skill(tmp_path, "demo") / "SKILL.md").write_text(
        "Shared helpers live in common.pyz.\n"
    )

    violations = _scan(tmp_path, monkeypatch)

    assert any("obsolete shared bundle common.pyz" in v for v in violations)


def test_retired_archive_tokens_are_flagged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A skill's own source naming any .pyz signals code or docs copied from the
    retired archive era, or from another skill's tree."""
    _ = (_skill(tmp_path, "demo") / "scripts" / "helper.py").write_text(
        "# copied from other-skill.pyz's helper module\n"
    )

    violations = _scan(tmp_path, monkeypatch)

    assert any("references foreign archive other-skill.pyz" in v for v in violations)


def test_cross_skill_launcher_reference_is_flagged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A skill may invoke only its own launcher."""
    _ = (_skill(tmp_path, "demo") / "SKILL.md").write_text(
        "Run `python3 skills/cook/scripts/cook paths list`.\n"
    )

    violations = _scan(tmp_path, monkeypatch)

    assert any("references cook's launcher, not its own scripts/demo" in v for v in violations)


def test_mismatched_launcher_path_is_flagged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _ = (_skill(tmp_path, "cook") / "SKILL.md").write_text(
        "Run `python3 skills/other-skill/scripts/cook paths list`.\n"
    )

    violations = _scan(tmp_path, monkeypatch)

    assert any("which is not that skill's launcher" in v for v in violations)


def test_own_launcher_reference_is_flagged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _ = (_skill(tmp_path, "cook") / "SKILL.md").write_text(
        "Run python3 skills/cook/scripts/cook paths list or scripts/cook paths.\\n"
    )

    violations = _scan(tmp_path, monkeypatch)

    assert any("obsolete extensionless launcher" in v for v in violations)



def test_dot_resource_is_not_a_launcher(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scripts = _skill(tmp_path, "mold") / "scripts"
    _ = (scripts / "mold.dot").write_text("digraph mold {}\n")

    assert _scan(tmp_path, monkeypatch) == []


def test_canonical_archive_directory_mismatch_is_flagged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _ = (_skill(tmp_path, "cook") / "SKILL.md").write_text(
        "Run skills/other/scripts/cook.pyz.\n"
    )

    violations = _scan(tmp_path, monkeypatch)

    assert any("not that skill's archive" in v for v in violations)


def test_dotted_own_archive_reference_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _ = (_skill(tmp_path, "cook") / "SKILL.md").write_text(
        "Run skills/cook/scripts/cook.pyz.\n"
    )

    assert _scan(tmp_path, monkeypatch) == []


def test_own_archive_reference_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _ = (_skill(tmp_path, "cook") / "SKILL.md").write_text(
        "Run skills/cook/scripts/cook.pyz.\n"
    )

    assert _scan(tmp_path, monkeypatch) == []


def test_source_tree_has_no_flat_runtime_roots() -> None:
    """Every runtime source lives under src/easy_cheese/{skills,shared,cli} or
    src/easy_cheese_schemas; nothing else may sit at the src/ or
    src/easy_cheese root (the doctrine the reference gate exists to keep honest).
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
    assert easy_cheese_children <= {"__init__.py", "skills", "shared", "cli"}
