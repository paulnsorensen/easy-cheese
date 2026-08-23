"""Drift gate for the generated schema/type-block regions.

Covers scripts/render_generated_regions.py: on-disk regions must equal a
fresh render, both named surfaces must carry a non-empty generated region,
and a seeded stale copy must be detected as drift. Also covers
schema-intertwine.md (wholly generated, byte-idempotent) and asserts the
phase-registry sources stay untouched (phase-registry-untouched invariant).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "render_generated_regions.py"

sys.path.insert(0, str(SCRIPT.parent))
import render_generated_regions as regen  # noqa: E402


def test_curdle_region_matches_fresh_render() -> None:
    text = regen.CURDLE_PATH.read_text(encoding="utf-8")
    expected = regen.replace_region(text, regen.MOLD_SPEC_TAG, regen.render_mold_spec_region())
    assert text == expected


def test_writer_views_region_matches_fresh_render() -> None:
    text = regen.WRITER_VIEWS_PATH.read_text(encoding="utf-8")
    expected = regen.replace_region(
        text, regen.WRITER_VIEWS_TAG, regen.render_writer_views_region()
    )
    assert text == expected


def test_both_surfaces_carry_a_non_empty_generated_region() -> None:
    for path in (regen.CURDLE_PATH, regen.WRITER_VIEWS_PATH):
        text = path.read_text(encoding="utf-8")
        assert "BEGIN GENERATED" in text and "END GENERATED" in text
        region = text.split("BEGIN GENERATED", 1)[1].split("END GENERATED", 1)[0]
        assert region.strip().strip("->").strip()


def _prepared_stale_tree(tmp_path: Path) -> Path:
    tree = tmp_path / "repo"
    shutil.copytree(
        REPO_ROOT,
        tree,
        symlinks=True,
        ignore=shutil.ignore_patterns(".git", "__pycache__", ".venv"),
    )
    return tree


def test_seeded_stale_region_copy_is_detected_as_drift(tmp_path: Path) -> None:
    tree = _prepared_stale_tree(tmp_path)
    stale = tree / "skills" / "mold" / "references" / "curdle.md"
    text = stale.read_text(encoding="utf-8")
    stale.write_text(
        regen.replace_region(text, regen.MOLD_SPEC_TAG, "document mold-spec { stale }\n"),
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, str(tree / "scripts" / "render_generated_regions.py"), "--check"],
        cwd=tree,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "curdle.md" in result.stderr


def test_intertwine_generator_runs_twice_byte_identical_and_matches_checked_in() -> None:
    first = regen.render_schema_intertwine()
    second = regen.render_schema_intertwine()
    assert first == second
    assert first == regen.INTERTWINE_PATH.read_text(encoding="utf-8")


def test_intertwine_seeded_stale_copy_is_detected_as_drift(tmp_path: Path) -> None:
    tree = _prepared_stale_tree(tmp_path)
    stale = tree / "skills" / "cheese" / "references" / "schema-intertwine.md"
    stale.write_text("stale content\n", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(tree / "scripts" / "render_generated_regions.py"), "--check"],
        cwd=tree,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "schema-intertwine.md" in result.stderr


def test_intertwine_mentions_registered_planner_result_transition() -> None:
    text = regen.INTERTWINE_PATH.read_text(encoding="utf-8")
    assert "planner-result" in text


def test_phase_registry_sources_are_untouched() -> None:
    result = subprocess.run(
        [
            "git",
            "diff",
            "--stat",
            "--",
            "src/easy_cheese_schemas/_phase_registry_compiler.py",
            "src/easy_cheese_schemas/_compiled_phase_registry.py",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout == ""
