"""Direct-invocation coverage for src/mold/validate-spec.py (curd-ssfe-2).

Exercises the dispatcher argv contract (`validate-spec <spec-path>`) that
curd-5's mold.pyz dispatcher will exec, invoking the script directly since
the dispatcher wiring itself lands later. Covers the committed lenient
syntax-repair classes and the strict semantic-rejection rules.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = REPO_ROOT / "src" / "mold" / "validate-spec.py"
BASE_SPEC = (
    REPO_ROOT / "tests" / "python" / "fixtures" / "spec_format" / "valid_spec.md"
).read_text(encoding="utf-8")


def _run(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(VALIDATOR), str(path)],
        capture_output=True,
        text=True,
    )


def _error_lines(result: subprocess.CompletedProcess[str]) -> list[str]:
    combined = result.stdout + result.stderr
    return [line for line in combined.splitlines() if line.startswith("ERROR:")]


def _write(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


# --- lenient syntax-repair classes (AC-1 half) ---------------------------


def test_valid_spec_fixture_is_accepted(tmp_path: Path) -> None:
    path = _write(tmp_path, "spec.md", BASE_SPEC)
    result = _run(path)
    assert result.returncode == 0
    assert not _error_lines(result)


def test_lenient_heading_case_is_repaired(tmp_path: Path) -> None:
    text = BASE_SPEC.replace("## Problem", "## PROBLEM", 1)
    path = _write(tmp_path, "spec.md", text)
    result = _run(path)
    assert result.returncode == 0
    assert not _error_lines(result)


def test_lenient_heading_trailing_punctuation_is_repaired(tmp_path: Path) -> None:
    text = BASE_SPEC.replace("## Goals\n", "## Goals.\n", 1)
    path = _write(tmp_path, "spec.md", text)
    result = _run(path)
    assert result.returncode == 0
    assert not _error_lines(result)


def test_lenient_table_cell_whitespace_is_repaired(tmp_path: Path) -> None:
    text = BASE_SPEC.replace(
        "| AC-1 | validate-spec CLI |",
        "|   AC-1   |  validate-spec CLI  |",
        1,
    )
    path = _write(tmp_path, "spec.md", text)
    result = _run(path)
    assert result.returncode == 0
    assert not _error_lines(result)


def test_lenient_fence_dialect_is_repaired(tmp_path: Path) -> None:
    text = BASE_SPEC.replace("```pseudocode", "~~~pseudocode", 1).replace(
        "```\n\n## Risks", "~~~\n\n## Risks", 1
    )
    assert "~~~pseudocode" in text and "~~~\n\n## Risks" in text
    path = _write(tmp_path, "spec.md", text)
    result = _run(path)
    assert result.returncode == 0
    assert not _error_lines(result)


# --- strict semantic-rejection rules (AC-2 half) --------------------------


def test_missing_required_section_is_rejected(tmp_path: Path) -> None:
    text = BASE_SPEC.replace(
        "## Risks\n\n- None beyond the usual validator-drift risk.\n\n", "", 1
    )
    path = _write(tmp_path, "spec.md", text)
    result = _run(path)
    errors = _error_lines(result)
    assert result.returncode == 1
    assert len(errors) == 1
    assert "Risks" in errors[0]


def test_acceptance_id_absent_from_table_is_rejected(tmp_path: Path) -> None:
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


def test_acceptance_id_duplicated_in_table_is_rejected(tmp_path: Path) -> None:
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


def test_matrix_metadata_on_tracer_row_is_rejected(tmp_path: Path) -> None:
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
    tmp_path: Path,
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


def test_not_applicable_with_contracts_is_rejected(tmp_path: Path) -> None:
    text = _isolated_gate_applicability_fixture(reason="closed, no CLI change", rows=True)
    path = _write(tmp_path, "spec.md", text)
    result = _run(path)
    errors = _error_lines(result)
    assert result.returncode == 1
    assert len(errors) == 1
    assert "not-applicable" in errors[0]
    assert "zero Test Contracts rows" in errors[0]


def test_not_applicable_without_reason_is_rejected(tmp_path: Path) -> None:
    text = _isolated_gate_applicability_fixture(reason=None, rows=False)
    path = _write(tmp_path, "spec.md", text)
    result = _run(path)
    errors = _error_lines(result)
    assert result.returncode == 1
    assert len(errors) == 1
    assert "reason is required" in errors[0]


def test_multiple_violations_accumulate_in_one_run(tmp_path: Path) -> None:
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
