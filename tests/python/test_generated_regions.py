"""Drift gate for the generated schema/type-block regions.

Covers scripts/render_generated_regions.py: on-disk regions must equal a
fresh render, both named surfaces must carry a non-empty generated region,
and a seeded stale copy must be detected as drift. Also covers
schema-intertwine.md (wholly generated, byte-idempotent) and asserts the
phase-registry sources stay untouched (phase-registry-untouched invariant).
"""

from __future__ import annotations

import hashlib
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
    for path, tag, render in (
        (regen.CURDLE_PATH, regen.MOLD_SPEC_TAG, regen.render_mold_spec_region),
        (regen.WRITER_VIEWS_PATH, regen.WRITER_VIEWS_TAG, regen.render_writer_views_region),
    ):
        text = path.read_text(encoding="utf-8")
        assert "BEGIN GENERATED" in text and "END GENERATED" in text
        assert regen.replace_region(text, tag, render()) == text


def _prepared_stale_tree(tmp_path: Path) -> Path:
    tree = tmp_path / "repo"
    shutil.copytree(
        REPO_ROOT,
        tree,
        symlinks=True,
        ignore=shutil.ignore_patterns(
            ".git",
            "__pycache__",
            ".venv",
            ".worktrees",
            "node_modules",
            "dist",
            ".release-preview",
            ".cheese",
        ),
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
    assert "DRIFT:" in result.stderr
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
    assert "DRIFT:" in result.stderr
    assert "schema-intertwine.md" in result.stderr


def test_intertwine_lists_a_real_registered_phase_transition_row() -> None:
    text = regen.INTERTWINE_PATH.read_text(encoding="utf-8")
    assert "| mold | 1.0 | planner-request | cook | curd-plan | CurdPlan |" in text


# Pinned sha256 digests of the phase-registry compiler and its compiled output.
# These sources must never be hand-touched as part of rendering the generated
# regions; the registry is regenerated deterministically from its own compiler,
# not from documentation. To legitimately update a pin, regenerate the
# registry through its own pipeline, review the diff, then recompute:
#   python3 -c "import hashlib; print(hashlib.sha256(open(PATH, 'rb').read()).hexdigest())"
_PHASE_REGISTRY_COMPILER_DIGEST = (
    "393f0dd5f084de9565b485767b933bab5a828a2907655c3e535c63666b87f61f"
)
_COMPILED_PHASE_REGISTRY_DIGEST = (
    "5fb1a336e8eb7ee23e5ab44916808341cf6adf972e92a14ac5521c66f41eec30"
)


def test_phase_registry_sources_are_untouched() -> None:
    for relative_path, expected_digest in (
        ("src/easy_cheese_schemas/_phase_registry_compiler.py", _PHASE_REGISTRY_COMPILER_DIGEST),
        ("src/easy_cheese_schemas/_compiled_phase_registry.py", _COMPILED_PHASE_REGISTRY_DIGEST),
    ):
        content = (REPO_ROOT / relative_path).read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        assert digest == expected_digest, (
            f"{relative_path} no longer matches its pinned digest; the "
            "phase-registry-untouched invariant requires this file be produced "
            "only by regenerating the registry through its own compiler, never "
            "hand-edited or touched incidentally by unrelated changes. If this "
            "change is a legitimate registry regeneration, update the pinned "
            "digest constant above."
        )
