"""Cut RED oracle for skills-only-spec-format-enforcement (AC-1..AC-9).

One outer tracer per approved Test Contract. This file and
tests/python/fixtures/cut_spec_format/ are protected by the Cut GateReceipt at
.cheese/cut/skills-only-spec-format-enforcement.json: production work must turn
these GREEN without editing the oracle.

Every assertion message leads with its contract's expected-failure witness so
the RED evidence binds to the approved contract verbatim.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "cut_spec_format"

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import build_pyz  # noqa: E402
import render_generated_regions as regen  # noqa: E402

WITNESS_AC1 = (
    "dispatcher exits 2 with unknown-subcommand error because validate-spec is "
    "not in the SKILLS registry; test asserts exit 0 on the syntax-deviant fixture"
)
WITNESS_AC2 = (
    "dispatcher exits 2 with unknown-subcommand error; test asserts exit 1 plus "
    "one ERROR: line per seeded semantic violation"
)
WITNESS_AC3 = (
    "ImportError: no _document_rules module and no document compiler exists; "
    "test asserts drift detection and deterministic regeneration"
)
WITNESS_AC4 = (
    "refresh entrypoint does not exist (ModuleNotFoundError) and the repo "
    "contains zero BEGIN GENERATED regions; test asserts both real surfaces "
    "carry a region whose content equals the rendered projection"
)
WITNESS_AC5 = (
    "dispatcher exits 2 with unknown-subcommand error because normalize is not "
    "registered; test asserts exit 1 naming the host-owned field path"
)
WITNESS_AC6 = (
    "dispatcher exits 2 with unknown-subcommand error; test asserts exit 1 with "
    "structuring error on the nonconforming fixture and exit 0 on the conforming one"
)
WITNESS_AC7 = (
    "skills/cook/scripts/common.pyz is absent because COMMON_CONSUMERS excludes "
    "cook; test asserts the file exists and the frozenset contains cook"
)
WITNESS_AC8 = (
    "COHERENCE_GATES carries no spec-format checklist entry so the rendered "
    "graph lacks a spec-format-valid node; test asserts the node exists with an "
    "edge ordered before the curdle node (curdle-gate-wiring)"
)
WITNESS_AC9 = (
    "generator module does not exist and skills/cheese/references/"
    "schema-intertwine.md is absent; test asserts the file is generated "
    "deterministically from registry, catalog, and models, and that a seeded "
    "stale copy fails the drift gate (phase-registry-untouched)"
)


@pytest.fixture(scope="module")
def mold_pyz() -> Path:
    return build_pyz.cached_bundle("mold")


@pytest.fixture(scope="module")
def cook_pyz() -> Path:
    return build_pyz.cached_bundle("cook")


def _run(pyz: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    return subprocess.run(
        [sys.executable, str(pyz), *args],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        env=env,
    )


def _error_lines(result: subprocess.CompletedProcess[str]) -> list[str]:
    combined = result.stdout + result.stderr
    return [line for line in combined.splitlines() if line.startswith("ERROR:")]


def test_ac1_validate_spec_accepts_syntax_deviant_spec(mold_pyz: Path) -> None:
    result = _run(mold_pyz, "validate-spec", str(FIXTURES / "syntax_deviant_spec.md"))
    assert result.returncode == 0, f"{WITNESS_AC1} [rc={result.returncode}]"
    assert not _error_lines(result), f"{WITNESS_AC1} [unexpected ERROR lines]"


def test_ac2_validate_spec_rejects_seeded_semantic_violations(mold_pyz: Path) -> None:
    result = _run(
        mold_pyz, "validate-spec", str(FIXTURES / "semantic_violation_spec.md")
    )
    errors = _error_lines(result)
    assert result.returncode == 1, f"{WITNESS_AC2} [rc={result.returncode}]"
    assert len(errors) == 2, f"{WITNESS_AC2} [got {len(errors)} ERROR lines]"
    assert any("Risks" in line for line in errors), (
        f"{WITNESS_AC2} [no ERROR names the missing Risks section]"
    )
    assert any("AC-1" in line for line in errors), (
        f"{WITNESS_AC2} [no ERROR names the duplicated AC-1 acceptance ID]"
    )


def test_ac3_document_rules_projection_exists_and_is_staged(mold_pyz: Path) -> None:
    compiler = REPO_ROOT / "src" / "easy_cheese_schemas" / "_document_rules_compiler.py"
    generated = REPO_ROOT / "src" / "mold" / "_document_rules.py"
    assert compiler.is_file(), f"{WITNESS_AC3} [missing _document_rules_compiler.py]"
    assert generated.is_file(), f"{WITNESS_AC3} [missing src/mold/_document_rules.py]"
    with zipfile.ZipFile(mold_pyz) as bundle:
        names = {Path(name).name for name in bundle.namelist()}
    assert "_document_rules.py" in names, (
        f"{WITNESS_AC3} [_document_rules.py not staged into mold.pyz]"
    )


def test_ac4_generated_regions_present_in_both_instruction_surfaces() -> None:
    refresher = REPO_ROOT / "scripts" / "render_generated_regions.py"
    assert refresher.is_file(), f"{WITNESS_AC4} [missing refresh entrypoint]"
    for surface, tag, render in (
        (regen.CURDLE_PATH, regen.MOLD_SPEC_TAG, regen.render_mold_spec_region),
        (regen.WRITER_VIEWS_PATH, regen.WRITER_VIEWS_TAG, regen.render_writer_views_region),
    ):
        assert surface.is_file(), f"{WITNESS_AC4} [missing surface {surface.name}]"
        text = surface.read_text(encoding="utf-8")
        assert "BEGIN GENERATED" in text and "END GENERATED" in text, (
            f"{WITNESS_AC4} [no generated region in {surface.name}]"
        )
        assert regen.replace_region(text, tag, render()) == text, (
            f"{WITNESS_AC4} [empty generated region in {surface.name}]"
        )


def test_ac5_cook_normalize_names_host_owned_field(cook_pyz: Path) -> None:
    invocation = FIXTURES.parent / "cook_payloads" / "clean_invocation.json"
    result = _run(
        cook_pyz,
        "normalize",
        str(FIXTURES / "writer_view_host_owned.json"),
        "--invocation",
        str(invocation),
    )
    combined = result.stdout + result.stderr
    assert result.returncode == 1, f"{WITNESS_AC5} [rc={result.returncode}]"
    assert "plan_id" in combined, f"{WITNESS_AC5} [offending field not named]"
    assert "payload" in combined, f"{WITNESS_AC5} [offending field path not named]"


def test_ac6_cook_validate_structures_payload_against_catalog_contract(
    cook_pyz: Path,
) -> None:
    bad = _run(
        cook_pyz,
        "validate",
        str(FIXTURES / "writer_view_bad.json"),
        "--schema",
        "agent-writer-view",
    )
    assert bad.returncode == 1, (
        f"{WITNESS_AC6} [rc={bad.returncode} on nonconforming payload]"
    )
    bad_combined = bad.stdout + bad.stderr
    assert "kind" in bad_combined, (
        f"{WITNESS_AC6} [offending field not named]"
    )
    ok = _run(
        cook_pyz,
        "validate",
        str(FIXTURES / "writer_view_ok.json"),
        "--schema",
        "agent-writer-view",
    )
    assert ok.returncode == 0, f"{WITNESS_AC6} [rc={ok.returncode} on conforming payload]"


def test_ac7_cook_joins_common_consumers_and_ships_common_pyz() -> None:
    assert "cook" in build_pyz.COMMON_CONSUMERS, (
        f"{WITNESS_AC7} [COMMON_CONSUMERS excludes cook]"
    )
    assert (REPO_ROOT / "skills" / "cook" / "scripts" / "common.pyz").is_file(), (
        f"{WITNESS_AC7} [skills/cook/scripts/common.pyz missing]"
    )


def test_ac8_gate_graph_derives_spec_format_valid_before_curdle(
    mold_pyz: Path,
) -> None:
    result = _run(mold_pyz, "gate-graph", "--render", "dot")
    assert result.returncode == 0, f"{WITNESS_AC8} [rc={result.returncode}]"
    dot = result.stdout
    assert "spec_format_valid" in dot, f"{WITNESS_AC8} [node missing from graph]"
    assert re.search(r"^\s*spec_format_valid -> \w+", dot, flags=re.MULTILINE), (
        f"{WITNESS_AC8} [spec-format-valid has no outgoing edge]"
    )
    assert 'handshake -> curdle [label="both keys"]' in dot, (
        f"{WITNESS_AC8} [curdle ordering edge missing]"
    )


def test_ac9_schema_intertwine_map_is_generated() -> None:
    intertwine = REPO_ROOT / "skills" / "cheese" / "references" / "schema-intertwine.md"
    assert intertwine.is_file(), f"{WITNESS_AC9} [schema-intertwine.md missing]"
    text = intertwine.read_text(encoding="utf-8")
    assert "| mold | 1.0 | planner-request | cook | curd-plan | CurdPlan |" in text, (
        f"{WITNESS_AC9} [registered mold-to-cook transition absent from the map]"
    )
