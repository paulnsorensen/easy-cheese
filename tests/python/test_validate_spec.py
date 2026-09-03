"""Direct-invocation and pyz-dispatcher coverage for src/mold/validate-spec.py
(curd-ssfe-2).

Exercises the dispatcher argv contract (`validate-spec <spec-path>`) that
mold.pyz's `__main__.py` dispatches, at both entry-point seams: the direct
script (fast local seam) and the built mold.pyz (the seam AC-1/AC-2 declare).
Covers the committed lenient syntax-repair classes and the strict
semantic-rejection rules.
"""
from __future__ import annotations
import os
import subprocess
import sys
from pathlib import Path
from typing import Protocol, cast

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = (
    REPO_ROOT / "src" / "easy_cheese" / "skills" / "mold" / "validate_spec.py"
)
SPEC_FIXTURES = REPO_ROOT / "tests" / "python" / "fixtures" / "spec_format"
BASE_SPEC = (SPEC_FIXTURES / "valid_spec.md").read_text(encoding="utf-8")
LEGACY_SPEC = (SPEC_FIXTURES / "legacy_v013_spec.md").read_text(encoding="utf-8")
MINI_SPEC = (SPEC_FIXTURES / "valid_mini_spec.md").read_text(encoding="utf-8")
RED_MINI_SPEC = (
    SPEC_FIXTURES / "valid_red_required_mini_spec.md"
).read_text(encoding="utf-8")

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import build_pyz  # noqa: E402


class _RunFn(Protocol):
    def __call__(
        self, path: Path, *flags: str
    ) -> subprocess.CompletedProcess[str]:
        raise NotImplementedError


def _run_direct(path: Path, *flags: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(VALIDATOR), *flags, str(path)],
        capture_output=True,
        text=True,
    )


def _run_pyz(path: Path, *flags: str) -> subprocess.CompletedProcess[str]:
    mold_pyz = build_pyz.cached_bundle("mold")
    return subprocess.run(
        [sys.executable, str(mold_pyz), "validate-spec", *flags, str(path)],
        capture_output=True,
        text=True,
    )


@pytest.fixture(  # noqa: V103 -- registered under name="_run", injected by pytest
    params=[_run_direct, _run_pyz], ids=["direct-script", "mold-pyz"], name="_run"
)
def run_fixture(request: pytest.FixtureRequest) -> _RunFn:
    return cast(_RunFn, request.param)


def _error_lines(result: subprocess.CompletedProcess[str]) -> list[str]:
    combined = result.stdout + result.stderr
    return [line for line in combined.splitlines() if line.startswith("ERROR:")]


def _notice_lines(result: subprocess.CompletedProcess[str]) -> list[str]:
    combined = result.stdout + result.stderr
    return [line for line in combined.splitlines() if line.startswith("NOTICE:")]


def _write(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    _ = path.write_text(text, encoding="utf-8")
    return path


# --- lenient syntax-repair classes (AC-1 half) ---------------------------



def test_standalone_validator_falls_back_when_cattrs_is_missing(
    tmp_path: Path,
) -> None:
    spec_path = _write(tmp_path, "spec.md", BASE_SPEC)
    probe = """
import builtins
import importlib.util
import sys
from pathlib import Path

import attrs

real_import = builtins.__import__

def import_without_cattrs(name, *args, **kwargs):
    if name == "cattrs" or name.startswith("cattrs."):
        raise ModuleNotFoundError("No module named 'cattrs'", name="cattrs")
    return real_import(name, *args, **kwargs)

builtins.__import__ = import_without_cattrs
module_spec = importlib.util.spec_from_file_location("validate_spec", sys.argv[1])
assert module_spec is not None and module_spec.loader is not None
module = importlib.util.module_from_spec(module_spec)
sys.modules[module_spec.name] = module
module_spec.loader.exec_module(module)
errors, notice = module.validate(Path(sys.argv[2]), strict=True)
assert errors == [], errors
assert notice is None
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT / "src")
    result = subprocess.run(
        [sys.executable, "-c", probe, str(VALIDATOR), str(spec_path)],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, result.stderr

def test_valid_spec_fixture_is_accepted(tmp_path: Path, _run: _RunFn) -> None:
    path = _write(tmp_path, "spec.md", BASE_SPEC)
    result = _run(path)
    assert result.returncode == 0
    assert not _error_lines(result)


def test_lenient_heading_case_is_repaired(tmp_path: Path, _run: _RunFn) -> None:
    text = BASE_SPEC.replace("## Problem", "## PROBLEM", 1)
    path = _write(tmp_path, "spec.md", text)
    result = _run(path)
    assert result.returncode == 0
    assert not _error_lines(result)


def test_lenient_heading_trailing_punctuation_is_repaired(tmp_path: Path, _run: _RunFn) -> None:
    text = BASE_SPEC.replace("## Goals\n", "## Goals.\n", 1)
    path = _write(tmp_path, "spec.md", text)
    result = _run(path)
    assert result.returncode == 0
    assert not _error_lines(result)


def test_lenient_table_cell_whitespace_is_repaired(tmp_path: Path, _run: _RunFn) -> None:
    text = BASE_SPEC.replace(
        "| AC-1 | validate-spec CLI |",
        "|   AC-1   |  validate-spec CLI  |",
        1,
    )
    path = _write(tmp_path, "spec.md", text)
    result = _run(path)
    assert result.returncode == 0
    assert not _error_lines(result)


def test_lenient_fence_dialect_is_repaired(tmp_path: Path, _run: _RunFn) -> None:
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
    tmp_path: Path, _run: _RunFn, fence: str
) -> None:
    """A fenced fake '## Risks' heading and fenced '|' rows must not satisfy or
    corrupt section/table detection: with the real Risks section removed, the
    fenced impostor must not count, so the spec is still rejected for the
    genuinely missing Risks section."""
    text = BASE_SPEC.replace(
        "## Risks\n\n- No other validator drift risks apply.\n\n", "", 1
    )
    text = text.replace(
        "## Interface sketches",
        f"## Interface sketches\n\n{fence}\n## Risks\n\n" +
        f"| fake | row | that | should | not | count | anywhere |\n{fence}",
        1,
    )
    path = _write(tmp_path, "spec.md", text)
    result = _run(path)
    errors = _error_lines(result)
    assert result.returncode == 1
    assert any("Risks" in line for line in errors)


# --- strict semantic-rejection rules (AC-2 half) --------------------------


def test_missing_required_section_is_rejected(tmp_path: Path, _run: _RunFn) -> None:
    text = BASE_SPEC.replace(
        "## Risks\n\n- No other validator drift risks apply.\n\n", "", 1
    )
    path = _write(tmp_path, "spec.md", text)
    result = _run(path)
    errors = _error_lines(result)
    assert result.returncode == 1
    assert len(errors) == 1
    assert "Risks" in errors[0]


def test_acceptance_id_absent_from_table_is_rejected(tmp_path: Path, _run: _RunFn) -> None:
    text = BASE_SPEC.replace(
        "| AC-2 | validate-spec CLI | pytest calls the CLI as a subprocess " +
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


def test_acceptance_id_duplicated_in_table_is_rejected(tmp_path: Path, _run: _RunFn) -> None:
    text = BASE_SPEC.replace(
        "- AC-2: WHEN the validator runs on a valid contract-matrix spec " +
        "THE SYSTEM SHALL exit 0.\n",
        "",
        1,
    ).replace(
        "| AC-2 | validate-spec CLI | pytest calls the CLI as a subprocess " +
        "| no validator exists yet | contract-matrix | v1 | row-a, row-b |\n",
        "",
        1,
    ).replace(
        "| AC-1 | validate-spec CLI | pytest calls the CLI as a subprocess " +
        "| no validator exists yet | tracer | | |\n",
        "| AC-1 | validate-spec CLI | pytest calls the CLI as a subprocess " +
        "| no validator exists yet | tracer | | |\n" +
        "| AC-1 | validate-spec CLI | pytest calls the CLI as a subprocess " +
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


def test_matrix_metadata_on_tracer_row_is_rejected(tmp_path: Path, _run: _RunFn) -> None:
    text = BASE_SPEC.replace(
        "- AC-2: WHEN the validator runs on a valid contract-matrix spec " +
        "THE SYSTEM SHALL exit 0.\n",
        "",
        1,
    ).replace(
        "| AC-2 | validate-spec CLI | pytest calls the CLI as a subprocess " +
        "| no validator exists yet | contract-matrix | v1 | row-a, row-b |\n",
        "",
        1,
    ).replace(
        "| AC-1 | validate-spec CLI | pytest calls the CLI as a subprocess " +
        "| no validator exists yet | tracer | | |",
        "| AC-1 | validate-spec CLI | pytest calls the CLI as a subprocess " +
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
    tmp_path: Path, _run: _RunFn,
) -> None:
    text = BASE_SPEC.replace(
        "- AC-1: WHEN the validator runs on a valid tracer spec THE SYSTEM " +
        "SHALL exit 0.\n",
        "",
        1,
    ).replace(
        "| AC-1 | validate-spec CLI | pytest calls the CLI as a subprocess " +
        "| no validator exists yet | tracer | | |\n",
        "",
        1,
    ).replace(
        "| AC-2 | validate-spec CLI | pytest calls the CLI as a subprocess " +
        "| no validator exists yet | contract-matrix | v1 | row-a, row-b |",
        "| AC-2 | validate-spec CLI | pytest calls the CLI as a subprocess " +
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


def test_unknown_mode_value_is_rejected(tmp_path: Path, _run: _RunFn) -> None:
    text = BASE_SPEC.replace(
        "| AC-1 | validate-spec CLI | pytest calls the CLI as a subprocess " +
        "| no validator exists yet | tracer | | |",
        "| AC-1 | validate-spec CLI | pytest calls the CLI as a subprocess " +
        "| no validator exists yet | Tracer | | |",
        1,
    )
    path = _write(tmp_path, "spec.md", text)
    result = _run(path)
    errors = _error_lines(result)
    assert result.returncode == 1
    assert any("AC-1" in line and "Mode" in line for line in errors)


def test_six_cell_row_is_a_shape_error(tmp_path: Path, _run: _RunFn) -> None:
    text = BASE_SPEC.replace(
        "| AC-1 | validate-spec CLI | pytest calls the CLI as a subprocess " +
        "| no validator exists yet | tracer | | |",
        "| AC-1 | validate-spec CLI | pytest calls the CLI as a subprocess " +
        "| no validator exists yet | tracer | |",
        1,
    )
    path = _write(tmp_path, "spec.md", text)
    result = _run(path)
    errors = _error_lines(result)
    assert result.returncode == 1
    assert any("test-contracts-table-shape" in line for line in errors)


def test_missing_delimiter_row_is_a_shape_error(tmp_path: Path, _run: _RunFn) -> None:
    text = BASE_SPEC.replace(
        "| Acceptance ID | Interface referent | Outermost stable seam | Expected " +
        "failure | Mode | Interface version | Matrix rows |\n" +
        "| --- | --- | --- | --- | --- | --- | --- |\n",
        "| Acceptance ID | Interface referent | Outermost stable seam | Expected " +
        "failure | Mode | Interface version | Matrix rows |\n",
        1,
    )
    path = _write(tmp_path, "spec.md", text)
    result = _run(path)
    errors = _error_lines(result)
    assert result.returncode == 1
    assert any("test-contracts-table-shape" in line for line in errors)


def test_duplicate_acceptance_heading_is_rejected(tmp_path: Path, _run: _RunFn) -> None:
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


def test_missing_frontmatter_is_rejected(tmp_path: Path, _run: _RunFn) -> None:
    end = BASE_SPEC.index("---", 3) + 3
    text = BASE_SPEC[end:].lstrip("\n")
    path = _write(tmp_path, "spec.md", text)
    result = _run(path)
    errors = _error_lines(result)
    assert result.returncode == 1
    assert any("gate-applicability-required" in line for line in errors)


def test_missing_gate_applicability_is_rejected(tmp_path: Path, _run: _RunFn) -> None:
    text = BASE_SPEC.replace(
        "gate_applicability:\n  disposition: red-required\n  work_class: behavior\n" +
        "  ui_surface: non-browser\n",
        "",
        1,
    )
    path = _write(tmp_path, "spec.md", text)
    result = _run(path)
    errors = _error_lines(result)
    assert result.returncode == 1
    assert any("gate-applicability-required" in line for line in errors)


def test_underscore_not_applicable_is_rejected(tmp_path: Path, _run: _RunFn) -> None:
    text = BASE_SPEC.replace(
        "  disposition: red-required\n", "  disposition: not_applicable\n", 1
    )
    path = _write(tmp_path, "spec.md", text)
    result = _run(path)
    errors = _error_lines(result)
    assert result.returncode == 1
    assert any("gate-applicability-closed-class" in line and "disposition" in line for line in errors)


def test_unknown_work_class_is_rejected(tmp_path: Path, _run: _RunFn) -> None:
    text = BASE_SPEC.replace("  work_class: behavior\n", "  work_class: bogus\n", 1)
    path = _write(tmp_path, "spec.md", text)
    result = _run(path)
    errors = _error_lines(result)
    assert result.returncode == 1
    assert any("gate-applicability-closed-class" in line and "work_class" in line for line in errors)


def test_unknown_ui_surface_is_rejected(tmp_path: Path, _run: _RunFn) -> None:
    text = BASE_SPEC.replace("  ui_surface: non-browser\n", "  ui_surface: bogus\n", 1)
    path = _write(tmp_path, "spec.md", text)
    result = _run(path)
    errors = _error_lines(result)
    assert result.returncode == 1
    assert any("gate-applicability-closed-class" in line and "ui_surface" in line for line in errors)


def _isolated_gate_applicability_fixture(reason: str | None, rows: bool) -> str:
    text = BASE_SPEC.replace(
        "gate_applicability:\n  disposition: red-required\n  work_class: behavior\n" +
        "  ui_surface: non-browser\n",
        "gate_applicability:\n  disposition: not-applicable\n  work_class: docs-only\n" +
        "  ui_surface: not-applicable\n"
        + (f"  reason: {reason}\n" if reason else ""),
        1,
    )
    text = text.replace(
        "- AC-2: WHEN the validator runs on a valid contract-matrix spec " +
        "THE SYSTEM SHALL exit 0.\n",
        "",
        1,
    )
    ac2_row = (
        "| AC-2 | validate-spec CLI | pytest calls the CLI as a subprocess " +
        "| no validator exists yet | contract-matrix | v1 | row-a, row-b |\n"
    )
    if rows:
        return text.replace(ac2_row, "", 1)
    text = text.replace(
        "- AC-1: WHEN the validator runs on a valid tracer spec THE SYSTEM "
        + "SHALL exit 0.\n",
        "",
        1,
    )
    return _strip_test_contracts(text)


def test_not_applicable_with_contracts_is_rejected(tmp_path: Path, _run: _RunFn) -> None:
    text = _isolated_gate_applicability_fixture(reason="closed, no CLI change", rows=True)
    path = _write(tmp_path, "spec.md", text)
    result = _run(path)
    errors = _error_lines(result)
    assert result.returncode == 1
    assert len(errors) == 1
    assert "not-applicable" in errors[0]
    assert "requires no Test Contracts section" in errors[0]


def test_not_applicable_without_test_contracts_is_accepted(
    tmp_path: Path, _run: _RunFn
) -> None:
    text = _isolated_gate_applicability_fixture(
        reason="closed, no CLI change", rows=False
    )
    path = _write(tmp_path, "spec.md", text)
    for flags in ((), ("--strict",)):
        result = _run(path, *flags)
        assert result.returncode == 0, (flags, result.stderr)
        assert not _error_lines(result), flags


def test_not_applicable_without_reason_is_rejected(tmp_path: Path, _run: _RunFn) -> None:
    text = _isolated_gate_applicability_fixture(reason=None, rows=False)
    path = _write(tmp_path, "spec.md", text)
    result = _run(path)
    errors = _error_lines(result)
    assert result.returncode == 1
    assert len(errors) == 1
    assert "reason is required" in errors[0]


def test_multiple_violations_accumulate_in_one_run(tmp_path: Path, _run: _RunFn) -> None:
    text = BASE_SPEC.replace(
        "## Risks\n\n- No other validator drift risks apply.\n\n", "", 1
    ).replace(
        "| AC-1 | validate-spec CLI | pytest calls the CLI as a subprocess " +
        "| no validator exists yet | tracer | | |",
        "| AC-1 | validate-spec CLI | pytest calls the CLI as a subprocess " +
        "| no validator exists yet | tracer | v1 | |",
        1,
    ).replace(
        "| AC-2 | validate-spec CLI | pytest calls the CLI as a subprocess " +
        "| no validator exists yet | contract-matrix | v1 | row-a, row-b |",
        "| AC-2 | validate-spec CLI | pytest calls the CLI as a subprocess " +
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
    assert any(
        "AC-2" in line and "contract-matrix" in line for line in errors
    )


# --- v0.13 legacy acceptance on read, hardened-only on mint ---------------


def _strip_test_contracts(text: str) -> str:
    start = text.index("## Test Contracts")
    return text[:start] + text[text.index("## Interface sketches") :]


def test_legacy_v013_spec_is_accepted_on_read(tmp_path: Path, _run: _RunFn) -> None:
    path = _write(tmp_path, "spec.md", LEGACY_SPEC)
    result = _run(path)
    assert result.returncode == 0
    assert not _error_lines(result)
    assert _notice_lines(result) == [
        "NOTICE: legacy-spec-format this spec predates the current format "
        + "(no mold provenance marker, so Test Contracts, Grounding and "
        + "gate_applicability are not required); accepted on read — re-mint it "
        + f"with /mold to adopt them in {path}"
    ]


def test_legacy_v013_spec_is_rejected_under_strict_mint(
    tmp_path: Path, _run: _RunFn
) -> None:
    path = _write(tmp_path, "spec.md", LEGACY_SPEC)
    result = _run(path, "--strict")
    errors = _error_lines(result)
    assert result.returncode == 1
    assert not _notice_lines(result)
    assert any("spec-provenance-required" in line for line in errors)
    assert any(
        "missing-required-section" in line and "Test Contracts" in line
        for line in errors
    )
    assert any("gate-applicability-required" in line for line in errors)
    assert any(
        "missing-required-section" in line and "Grounding" in line for line in errors
    )
    assert any("grounding-probe-recorded" in line for line in errors)


def test_legacy_spec_grounding_content_is_still_validated(
    tmp_path: Path, _run: _RunFn
) -> None:
    text = LEGACY_SPEC.replace(
        "## Approach",
        "## Grounding\n\n| Probe | Outcome | Evidence |\n| --- | --- | --- |\n"
        + "| wiki | hit | adr/spec-format-enforcement-001.md |\n"
        + "| explorer | unavailable | |\n\n## Approach",
        1,
    )
    path = _write(tmp_path, "spec.md", text)
    result = _run(path)
    errors = _error_lines(result)
    assert result.returncode == 1
    assert len(errors) == 1
    assert "delegation-digest-recorded" in errors[0]
    assert "records no evidence" in errors[0]


def test_legacy_spec_still_fails_on_a_section_v013_required(
    tmp_path: Path, _run: _RunFn
) -> None:
    text = LEGACY_SPEC.replace("## Risks\n", "## Hazards\n", 1)
    path = _write(tmp_path, "spec.md", text)
    result = _run(path)
    errors = _error_lines(result)
    assert result.returncode == 1
    assert any(
        "missing-required-section" in line and "Risks" in line for line in errors
    )


def test_legacy_spec_test_contracts_content_is_still_validated(
    tmp_path: Path, _run: _RunFn
) -> None:
    text = LEGACY_SPEC.replace(
        "## Interface sketches",
        "## Test Contracts\n\n| Acceptance ID | Mode |\n| --- | --- |\n"
        + "| AC-1 | tracer |\n\n## Interface sketches",
        1,
    )
    path = _write(tmp_path, "spec.md", text)
    result = _run(path)
    errors = _error_lines(result)
    assert result.returncode == 1
    assert any("test-contracts-table-shape" in line for line in errors)


def test_hardened_spec_missing_test_contracts_is_rejected_on_read(
    tmp_path: Path, _run: _RunFn
) -> None:
    path = _write(tmp_path, "spec.md", _strip_test_contracts(BASE_SPEC))
    result = _run(path)
    errors = _error_lines(result)
    assert result.returncode == 1
    assert not _notice_lines(result)
    assert any(
        "missing-required-section" in line and "Test Contracts" in line
        for line in errors
    )


def test_documented_not_applicable_mini_spec_passes_strict_validation(
    tmp_path: Path, _run: _RunFn
) -> None:
    result = _run(_write(tmp_path, "mini-spec.md", MINI_SPEC), "--strict")
    assert result.returncode == 0, result.stderr
    assert not _error_lines(result)
    assert not _notice_lines(result)


def test_documented_red_required_mini_spec_passes_strict_validation(
    tmp_path: Path, _run: _RunFn
) -> None:
    result = _run(_write(tmp_path, "mini-spec.md", RED_MINI_SPEC), "--strict")
    assert result.returncode == 0, result.stderr
    assert not _error_lines(result)
    assert not _notice_lines(result)


def test_current_format_spec_reads_and_mints_without_a_legacy_notice(
    tmp_path: Path, _run: _RunFn
) -> None:
    path = _write(tmp_path, "spec.md", BASE_SPEC)
    for flags in ((), ("--strict",)):
        result = _run(path, *flags)
        assert result.returncode == 0, flags
        assert not _error_lines(result), flags
        assert not _notice_lines(result), flags


@pytest.mark.parametrize("flags", [(), ("--strict",)])
def test_nested_source_is_reported_without_a_traceback(
    tmp_path: Path, _run: _RunFn, flags: tuple[str, ...]
) -> None:
    text = LEGACY_SPEC.replace(
        "status: approved\n", "status: approved\nsource:\n  value: mold-handshake\n", 1
    )
    result = _run(_write(tmp_path, "spec.md", text), *flags)
    assert result.returncode == 1
    assert any("spec-provenance-invalid" in line for line in _error_lines(result))
    assert "Traceback" not in result.stderr


def test_legacy_scalar_gate_applicability_is_rejected(
    tmp_path: Path, _run: _RunFn
) -> None:
    text = LEGACY_SPEC.replace(
        "agent_introduced_scope: []\n",
        "agent_introduced_scope: []\ngate_applicability: garbage\n",
        1,
    )
    result = _run(_write(tmp_path, "spec.md", text))
    assert result.returncode == 1
    assert any(
        "gate-applicability-required" in line and "unparseable" in line
        for line in _error_lines(result)
    )


def test_spec_without_frontmatter_is_malformed_not_legacy(
    tmp_path: Path, _run: _RunFn
) -> None:
    end = BASE_SPEC.index("---", 3) + 3
    path = _write(tmp_path, "spec.md", BASE_SPEC[end:].lstrip("\n"))
    result = _run(path)
    assert result.returncode == 1
    assert not _notice_lines(result)
    assert any("gate-applicability-required" in line for line in _error_lines(result))


# --- grounding gate (#553) ----------------------------------------------

WIKI_ROW = (
    "| wiki | hit | adr/spec-format-enforcement-001.md — content-schema rules "
    "belong in the validator |\n"
)
EXPLORER_ROW = (
    "| explorer | unavailable | This fixture cannot use Hallouminate. It reads "
    "validate_spec.py directly. |\n"
)


def test_missing_grounding_section_is_rejected(tmp_path: Path, _run: _RunFn) -> None:
    start = BASE_SPEC.index("## Grounding")
    end = BASE_SPEC.index("## Approach")
    text = BASE_SPEC[:start] + BASE_SPEC[end:]
    path = _write(tmp_path, "spec.md", text)
    result = _run(path)
    errors = _error_lines(result)
    assert result.returncode == 1
    assert len(errors) == 3
    assert any("missing-required-section" in line and "Grounding" in line for line in errors)
    assert any("grounding-probe-recorded" in line and "'wiki'" in line for line in errors)
    assert any("delegation-digest-recorded" in line and "'explorer'" in line for line in errors)


@pytest.mark.parametrize(
    ("row", "rule", "probe"),
    [
        (WIKI_ROW, "grounding-probe-recorded", "wiki"),
        (EXPLORER_ROW, "delegation-digest-recorded", "explorer"),
    ],
)
def test_unrecorded_probe_is_rejected(
    tmp_path: Path, _run: _RunFn, row: str, rule: str, probe: str
) -> None:
    text = BASE_SPEC.replace(row, "", 1)
    assert row not in text
    path = _write(tmp_path, "spec.md", text)
    result = _run(path)
    errors = _error_lines(result)
    assert result.returncode == 1
    assert len(errors) == 1
    assert rule in errors[0]
    assert f"does not record the '{probe}' probe" in errors[0]


@pytest.mark.parametrize(
    ("row", "rule", "probe"),
    [
        (WIKI_ROW, "grounding-probe-recorded", "wiki"),
        (EXPLORER_ROW, "delegation-digest-recorded", "explorer"),
    ],
)
def test_duplicated_probe_is_rejected(
    tmp_path: Path, _run: _RunFn, row: str, rule: str, probe: str
) -> None:
    text = BASE_SPEC.replace(row, row + row, 1)
    path = _write(tmp_path, "spec.md", text)
    result = _run(path)
    errors = _error_lines(result)
    assert result.returncode == 1
    assert len(errors) == 1
    assert rule in errors[0]
    assert f"records the '{probe}' probe 2 times" in errors[0]


def test_unavailable_probe_without_evidence_is_rejected(
    tmp_path: Path, _run: _RunFn
) -> None:
    text = BASE_SPEC.replace(EXPLORER_ROW, "| explorer | unavailable | |\n", 1)
    path = _write(tmp_path, "spec.md", text)
    result = _run(path)
    errors = _error_lines(result)
    assert result.returncode == 1
    assert len(errors) == 1
    assert "delegation-digest-recorded" in errors[0]
    assert "records no evidence" in errors[0]


def test_unavailable_probe_with_evidence_is_accepted(tmp_path: Path, _run: _RunFn) -> None:
    text = BASE_SPEC.replace(
        WIKI_ROW, "| wiki | unavailable | hallouminate MCP not connected |\n", 1
    )
    path = _write(tmp_path, "spec.md", text)
    result = _run(path)
    assert result.returncode == 0
    assert not _error_lines(result)


def test_unknown_grounding_probe_is_rejected(tmp_path: Path, _run: _RunFn) -> None:
    text = BASE_SPEC.replace(WIKI_ROW, WIKI_ROW.replace("| wiki |", "| Wiki |", 1), 1)
    path = _write(tmp_path, "spec.md", text)
    result = _run(path)
    errors = _error_lines(result)
    assert result.returncode == 1
    assert len(errors) == 2
    assert any("grounding-probe-closed-class" in line and "'Wiki'" in line for line in errors)
    assert any("grounding-probe-recorded" in line for line in errors)


def test_unknown_grounding_outcome_is_rejected(tmp_path: Path, _run: _RunFn) -> None:
    text = BASE_SPEC.replace(WIKI_ROW, WIKI_ROW.replace("| hit |", "| skipped |", 1), 1)
    path = _write(tmp_path, "spec.md", text)
    result = _run(path)
    errors = _error_lines(result)
    assert result.returncode == 1
    assert len(errors) == 1
    assert "grounding-outcome-closed-class" in errors[0]
    assert "'skipped'" in errors[0]


def test_grounding_table_column_drift_is_a_shape_error(
    tmp_path: Path, _run: _RunFn
) -> None:
    text = BASE_SPEC.replace(
        "| Probe | Outcome | Evidence |", "| Probe | Outcome | Citation |", 1
    )
    path = _write(tmp_path, "spec.md", text)
    result = _run(path)
    errors = _error_lines(result)
    assert result.returncode == 1
    assert any("grounding-table-shape" in line for line in errors)
    assert any("grounding-probe-recorded" in line for line in errors)
    assert any("delegation-digest-recorded" in line for line in errors)


def test_not_applicable_spec_still_requires_grounding(
    tmp_path: Path, _run: _RunFn
) -> None:
    text = _isolated_gate_applicability_fixture(
        reason="closed, no CLI change", rows=False
    ).replace(WIKI_ROW, "", 1)
    path = _write(tmp_path, "spec.md", text)
    result = _run(path)
    errors = _error_lines(result)
    assert result.returncode == 1
    assert len(errors) == 1
    assert "grounding-probe-recorded" in errors[0]
