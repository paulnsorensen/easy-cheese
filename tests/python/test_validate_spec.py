"""Direct-invocation and pyz-dispatcher coverage for src/mold/validate-spec.py
(curd-ssfe-2).

Exercises the dispatcher argv contract (`validate-spec <spec-path>`) that
mold.pyz's `__main__.py` dispatches, at both entry-point seams: the direct
script (fast local seam) and the built mold.pyz (the seam AC-1/AC-2 declare).
Covers the committed lenient syntax-repair classes and the strict
semantic-rejection rules.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = REPO_ROOT / "src" / "mold" / "validate-spec.py"
BASE_SPEC = (
    REPO_ROOT / "tests" / "python" / "fixtures" / "spec_format" / "valid_spec.md"
).read_text(encoding="utf-8")

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import build_pyz  # noqa: E402


def _run_direct(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(VALIDATOR), str(path)],
        capture_output=True,
        text=True,
    )


def _run_pyz(path: Path) -> subprocess.CompletedProcess[str]:
    mold_pyz = build_pyz.cached_bundle("mold")
    return subprocess.run(
        [sys.executable, str(mold_pyz), "validate-spec", str(path)],
        capture_output=True,
        text=True,
    )


@pytest.fixture(params=[_run_direct, _run_pyz], ids=["direct-script", "mold-pyz"])
def _run(request: pytest.FixtureRequest):
    return request.param


def _error_lines(result: subprocess.CompletedProcess[str]) -> list[str]:
    combined = result.stdout + result.stderr
    return [line for line in combined.splitlines() if line.startswith("ERROR:")]


def _write(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


# --- lenient syntax-repair classes (AC-1 half) ---------------------------


def test_valid_spec_fixture_is_accepted(tmp_path: Path, _run) -> None:
    path = _write(tmp_path, "spec.md", BASE_SPEC)
    result = _run(path)
    assert result.returncode == 0
    assert not _error_lines(result)


def test_lenient_heading_case_is_repaired(tmp_path: Path, _run) -> None:
    text = BASE_SPEC.replace("## Problem", "## PROBLEM", 1)
    path = _write(tmp_path, "spec.md", text)
    result = _run(path)
    assert result.returncode == 0
    assert not _error_lines(result)


def test_lenient_heading_trailing_punctuation_is_repaired(tmp_path: Path, _run) -> None:
    text = BASE_SPEC.replace("## Goals\n", "## Goals.\n", 1)
    path = _write(tmp_path, "spec.md", text)
    result = _run(path)
    assert result.returncode == 0
    assert not _error_lines(result)


def test_lenient_table_cell_whitespace_is_repaired(tmp_path: Path, _run) -> None:
    text = BASE_SPEC.replace(
        "| AC-1 | validate-spec CLI |",
        "|   AC-1   |  validate-spec CLI  |",
        1,
    )
    path = _write(tmp_path, "spec.md", text)
    result = _run(path)
    assert result.returncode == 0
    assert not _error_lines(result)


def test_lenient_fence_dialect_is_repaired(tmp_path: Path, _run) -> None:
    text = BASE_SPEC.replace("```pseudocode", "~~~pseudocode", 1).replace(
        "```\n\n## Risks", "~~~\n\n## Risks", 1
    )
    assert "~~~pseudocode" in text and "~~~\n\n## Risks" in text
    path = _write(tmp_path, "spec.md", text)
    result = _run(path)
    assert result.returncode == 0
    assert not _error_lines(result)


@pytest.mark.parametrize("fence", ["```", "~~~"])
def test_fenced_fake_heading_and_table_rows_are_invisible_to_detection(
    tmp_path: Path, _run, fence: str
) -> None:
    """A fenced fake '## Risks' heading and fenced '|' rows must not satisfy or
    corrupt section/table detection: with the real Risks section removed, the
    fenced impostor must not count, so the spec is still rejected for the
    genuinely missing Risks section."""
    text = BASE_SPEC.replace(
        "## Risks\n\n- None beyond the usual validator-drift risk.\n\n", "", 1
    )
    text = text.replace(
        "## Interface sketches",
        f"## Interface sketches\n\n{fence}\n## Risks\n\n"
        f"| fake | row | that | should | not | count | anywhere |\n{fence}",
        1,
    )
    path = _write(tmp_path, "spec.md", text)
    result = _run(path)
    errors = _error_lines(result)
    assert result.returncode == 1
    assert any("Risks" in line for line in errors)


# --- strict semantic-rejection rules (AC-2 half) --------------------------


def test_missing_required_section_is_rejected(tmp_path: Path, _run) -> None:
    text = BASE_SPEC.replace(
        "## Risks\n\n- None beyond the usual validator-drift risk.\n\n", "", 1
    )
    path = _write(tmp_path, "spec.md", text)
    result = _run(path)
    errors = _error_lines(result)
    assert result.returncode == 1
    assert len(errors) == 1
    assert "Risks" in errors[0]


def test_acceptance_id_absent_from_table_is_rejected(tmp_path: Path, _run) -> None:
    text = BASE_SPEC.replace(
        "| AC-2 | validate-spec CLI | pytest invoking the CLI as a subprocess "
        "| no validator exists yet | contract-matrix | v1 | row-a, row-b |\n",
        "",
        1,
    )
    path = _write(tmp_path, "spec.md", text)
    result = _run(path)
    errors = _error_lines(result)
    assert result.returncode == 1
    assert len(errors) == 1
    assert "AC-2" in errors[0]
    assert "absent" in errors[0]


def test_acceptance_id_duplicated_in_table_is_rejected(tmp_path: Path, _run) -> None:
    text = BASE_SPEC.replace(
        "- AC-2: WHEN the validator runs on a valid contract-matrix spec "
        "THE SYSTEM SHALL exit 0.\n",
        "",
        1,
    ).replace(
        "| AC-2 | validate-spec CLI | pytest invoking the CLI as a subprocess "
        "| no validator exists yet | contract-matrix | v1 | row-a, row-b |\n",
        "",
        1,
    ).replace(
        "| AC-1 | validate-spec CLI | pytest invoking the CLI as a subprocess "
        "| no validator exists yet | tracer | | |\n",
        "| AC-1 | validate-spec CLI | pytest invoking the CLI as a subprocess "
        "| no validator exists yet | tracer | | |\n"
        "| AC-1 | validate-spec CLI | pytest invoking the CLI as a subprocess "
        "| no validator exists yet | tracer | | |\n",
        1,
    )
    path = _write(tmp_path, "spec.md", text)
    result = _run(path)
    errors = _error_lines(result)
    assert result.returncode == 1
    assert len(errors) == 1
    assert "AC-1" in errors[0]
    assert "2 times" in errors[0]


def test_matrix_metadata_on_tracer_row_is_rejected(tmp_path: Path, _run) -> None:
    text = BASE_SPEC.replace(
        "- AC-2: WHEN the validator runs on a valid contract-matrix spec "
        "THE SYSTEM SHALL exit 0.\n",
        "",
        1,
    ).replace(
        "| AC-2 | validate-spec CLI | pytest invoking the CLI as a subprocess "
        "| no validator exists yet | contract-matrix | v1 | row-a, row-b |\n",
        "",
        1,
    ).replace(
        "| AC-1 | validate-spec CLI | pytest invoking the CLI as a subprocess "
        "| no validator exists yet | tracer | | |",
        "| AC-1 | validate-spec CLI | pytest invoking the CLI as a subprocess "
        "| no validator exists yet | tracer | v1 | |",
        1,
    )
    path = _write(tmp_path, "spec.md", text)
    result = _run(path)
    errors = _error_lines(result)
    assert result.returncode == 1
    assert len(errors) == 1
    assert "AC-1" in errors[0]
    assert "tracer" in errors[0]


def test_contract_matrix_row_missing_interface_version_is_rejected(
    tmp_path: Path, _run,
) -> None:
    text = BASE_SPEC.replace(
        "- AC-1: WHEN the validator runs on a valid tracer spec THE SYSTEM "
        "SHALL exit 0.\n",
        "",
        1,
    ).replace(
        "| AC-1 | validate-spec CLI | pytest invoking the CLI as a subprocess "
        "| no validator exists yet | tracer | | |\n",
        "",
        1,
    ).replace(
        "| AC-2 | validate-spec CLI | pytest invoking the CLI as a subprocess "
        "| no validator exists yet | contract-matrix | v1 | row-a, row-b |",
        "| AC-2 | validate-spec CLI | pytest invoking the CLI as a subprocess "
        "| no validator exists yet | contract-matrix | | row-a, row-b |",
        1,
    )
    path = _write(tmp_path, "spec.md", text)
    result = _run(path)
    errors = _error_lines(result)
    assert result.returncode == 1
    assert len(errors) == 1
    assert "AC-2" in errors[0]
    assert "contract-matrix" in errors[0]


def test_unknown_mode_value_is_rejected(tmp_path: Path, _run) -> None:
    text = BASE_SPEC.replace(
        "| AC-1 | validate-spec CLI | pytest invoking the CLI as a subprocess "
        "| no validator exists yet | tracer | | |",
        "| AC-1 | validate-spec CLI | pytest invoking the CLI as a subprocess "
        "| no validator exists yet | Tracer | | |",
        1,
    )
    path = _write(tmp_path, "spec.md", text)
    result = _run(path)
    errors = _error_lines(result)
    assert result.returncode == 1
    assert any("AC-1" in line and "Mode" in line for line in errors)


def test_six_cell_row_is_a_shape_error(tmp_path: Path, _run) -> None:
    text = BASE_SPEC.replace(
        "| AC-1 | validate-spec CLI | pytest invoking the CLI as a subprocess "
        "| no validator exists yet | tracer | | |",
        "| AC-1 | validate-spec CLI | pytest invoking the CLI as a subprocess "
        "| no validator exists yet | tracer | |",
        1,
    )
    path = _write(tmp_path, "spec.md", text)
    result = _run(path)
    errors = _error_lines(result)
    assert result.returncode == 1
    assert any("test-contracts-table-shape" in line for line in errors)


def test_missing_delimiter_row_is_a_shape_error(tmp_path: Path, _run) -> None:
    text = BASE_SPEC.replace(
        "| Acceptance ID | Interface referent | Outermost stable seam | Expected "
        "failure | Mode | Interface version | Matrix rows |\n"
        "| --- | --- | --- | --- | --- | --- | --- |\n",
        "| Acceptance ID | Interface referent | Outermost stable seam | Expected "
        "failure | Mode | Interface version | Matrix rows |\n",
        1,
    )
    path = _write(tmp_path, "spec.md", text)
    result = _run(path)
    errors = _error_lines(result)
    assert result.returncode == 1
    assert any("test-contracts-table-shape" in line for line in errors)


def test_duplicate_acceptance_heading_is_rejected(tmp_path: Path, _run) -> None:
    text = BASE_SPEC.replace(
        "## Test Contracts",
        "## Acceptance\n\n- AC-3: duplicate heading filler.\n\n## Test Contracts",
        1,
    )
    path = _write(tmp_path, "spec.md", text)
    result = _run(path)
    errors = _error_lines(result)
    assert result.returncode == 1
    assert any("duplicate-heading" in line and "acceptance" in line for line in errors)


def test_missing_frontmatter_is_rejected(tmp_path: Path, _run) -> None:
    end = BASE_SPEC.index("---", 3) + 3
    text = BASE_SPEC[end:].lstrip("\n")
    path = _write(tmp_path, "spec.md", text)
    result = _run(path)
    errors = _error_lines(result)
    assert result.returncode == 1
    assert any("gate-applicability-required" in line for line in errors)


def test_missing_gate_applicability_is_rejected(tmp_path: Path, _run) -> None:
    text = BASE_SPEC.replace(
        "gate_applicability:\n  disposition: red-required\n  work_class: behavior\n"
        "  ui_surface: non-browser\n",
        "",
        1,
    )
    path = _write(tmp_path, "spec.md", text)
    result = _run(path)
    errors = _error_lines(result)
    assert result.returncode == 1
    assert any("gate-applicability-required" in line for line in errors)


def test_underscore_not_applicable_is_rejected(tmp_path: Path, _run) -> None:
    text = BASE_SPEC.replace(
        "  disposition: red-required\n", "  disposition: not_applicable\n", 1
    )
    path = _write(tmp_path, "spec.md", text)
    result = _run(path)
    errors = _error_lines(result)
    assert result.returncode == 1
    assert any("gate-applicability-closed-class" in line and "disposition" in line for line in errors)


def test_unknown_work_class_is_rejected(tmp_path: Path, _run) -> None:
    text = BASE_SPEC.replace("  work_class: behavior\n", "  work_class: bogus\n", 1)
    path = _write(tmp_path, "spec.md", text)
    result = _run(path)
    errors = _error_lines(result)
    assert result.returncode == 1
    assert any("gate-applicability-closed-class" in line and "work_class" in line for line in errors)


def test_unknown_ui_surface_is_rejected(tmp_path: Path, _run) -> None:
    text = BASE_SPEC.replace("  ui_surface: non-browser\n", "  ui_surface: bogus\n", 1)
    path = _write(tmp_path, "spec.md", text)
    result = _run(path)
    errors = _error_lines(result)
    assert result.returncode == 1
    assert any("gate-applicability-closed-class" in line and "ui_surface" in line for line in errors)


def _isolated_gate_applicability_fixture(reason: str | None, rows: bool) -> str:
    text = BASE_SPEC.replace(
        "gate_applicability:\n  disposition: red-required\n  work_class: behavior\n"
        "  ui_surface: non-browser\n",
        "gate_applicability:\n  disposition: not-applicable\n  work_class: docs-only\n"
        "  ui_surface: not-applicable\n"
        + (f"  reason: {reason}\n" if reason else ""),
        1,
    )
    text = text.replace(
        "- AC-2: WHEN the validator runs on a valid contract-matrix spec "
        "THE SYSTEM SHALL exit 0.\n",
        "",
        1,
    )
    ac2_row = (
        "| AC-2 | validate-spec CLI | pytest invoking the CLI as a subprocess "
        "| no validator exists yet | contract-matrix | v1 | row-a, row-b |\n"
    )
    if rows:
        text = text.replace(ac2_row, "", 1)
    else:
        ac1_row = (
            "| AC-1 | validate-spec CLI | pytest invoking the CLI as a subprocess "
            "| no validator exists yet | tracer | | |\n"
        )
        text = text.replace(ac1_row, "", 1).replace(ac2_row, "", 1)
        text = text.replace(
            "- AC-1: WHEN the validator runs on a valid tracer spec THE SYSTEM "
            "SHALL exit 0.\n",
            "",
            1,
        )
    return text


def test_not_applicable_with_contracts_is_rejected(tmp_path: Path, _run) -> None:
    text = _isolated_gate_applicability_fixture(reason="closed, no CLI change", rows=True)
    path = _write(tmp_path, "spec.md", text)
    result = _run(path)
    errors = _error_lines(result)
    assert result.returncode == 1
    assert len(errors) == 1
    assert "not-applicable" in errors[0]
    assert "zero Test Contracts rows" in errors[0]


def test_not_applicable_without_reason_is_rejected(tmp_path: Path, _run) -> None:
    text = _isolated_gate_applicability_fixture(reason=None, rows=False)
    path = _write(tmp_path, "spec.md", text)
    result = _run(path)
    errors = _error_lines(result)
    assert result.returncode == 1
    assert len(errors) == 1
    assert "reason is required" in errors[0]


def test_multiple_violations_accumulate_in_one_run(tmp_path: Path, _run) -> None:
    text = BASE_SPEC.replace(
        "## Risks\n\n- None beyond the usual validator-drift risk.\n\n", "", 1
    ).replace(
        "| AC-1 | validate-spec CLI | pytest invoking the CLI as a subprocess "
        "| no validator exists yet | tracer | | |",
        "| AC-1 | validate-spec CLI | pytest invoking the CLI as a subprocess "
        "| no validator exists yet | tracer | v1 | |",
        1,
    ).replace(
        "| AC-2 | validate-spec CLI | pytest invoking the CLI as a subprocess "
        "| no validator exists yet | contract-matrix | v1 | row-a, row-b |",
        "| AC-2 | validate-spec CLI | pytest invoking the CLI as a subprocess "
        "| no validator exists yet | contract-matrix | | |",
        1,
    )
    path = _write(tmp_path, "spec.md", text)
    result = _run(path)
    errors = _error_lines(result)
    assert result.returncode == 1
    assert len(errors) == 3
    assert any("Risks" in line for line in errors)
    assert any("AC-1" in line and "tracer" in line for line in errors)
    assert any("AC-2" in line and "contract-matrix" in line for line in errors)
