"""Behavioral tests for red-gate contract parsing and applicability closure."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from easy_cheese.shared.cut import red_gate

REPO_ROOT = Path(__file__).resolve().parents[2]


def _run_contracts(
    spec_path: Path, capsys: pytest.CaptureFixture[str]
) -> tuple[int, dict[str, object] | None, str]:
    code = red_gate.main(["contracts", str(spec_path)])
    captured = capsys.readouterr()
    payload = json.loads(captured.out) if captured.out else None
    return code, payload, captured.err


def test_approved_contracts_map_each_acceptance_id_once(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    spec = tmp_path / "approved.md"
    spec.write_text(
        """---
status: approved
gate_applicability:
  disposition: red-required
  work_class: behavior
---
# Behavior

## Acceptance Criteria
- AC-1: `api.create` rejects an invalid request.
- AC-2: `api.create` accepts a valid request.

## Test Contracts
| Acceptance | Interface referent | Outermost stable seam | Expected failure | Mode | Interface version | Matrix rows |
| --- | --- | --- | --- | --- | --- | --- |
| AC-1 | `api.create` | `api.create` | invalid request is rejected | tracer | | |
| AC-2 | `api.create` | `api.create` | valid request is accepted | contract-matrix | v1 | invalid<br>valid |
""",
        encoding="utf-8",
    )

    code, payload, error = _run_contracts(spec, capsys)

    assert code == 0, error
    assert payload is not None
    assert payload["disposition"] == "red"
    contracts = payload["contracts"]
    assert [contract["acceptance_id"] for contract in contracts] == ["AC-1", "AC-2"]
    assert [contract["contract_source"] for contract in contracts] == [
        "approved",
        "approved",
    ]
    assert [contract["mode"] for contract in contracts] == ["tracer", "contract-matrix"]


def test_contract_plan_excludes_green_guards(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    spec = tmp_path / "guarded.md"
    spec.write_text(
        """---
source: mold-handshake
gate_applicability:
  disposition: red-required
  work_class: behavior
  ui_surface: non-browser
---
# Guarded behavior

## Acceptance
- AC-1: new behavior.
- AC-2: existing behavior remains unchanged.

## Test Contracts
| Acceptance | Interface | Seam | Expected failure | Mode |
| --- | --- | --- | --- | --- |
| AC-1 | `api.new` | public API | new behavior is absent | tracer |
| AC-2 | `api.existing` | committed snapshot | existing behavior changes | guard |
""",
        encoding="utf-8",
    )

    code, payload, error = _run_contracts(spec, capsys)

    assert code == 0, error
    assert payload is not None
    assert payload["disposition"] == "red"
    assert [
        (contract["acceptance_id"], contract["mode"])
        for contract in payload["contracts"]
    ] == [("AC-1", "tracer")]


def test_guard_only_red_required_is_rejected_with_one_actionable_problem(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    spec = tmp_path / "guard-only.md"
    spec.write_text(
        """---
source: mold-handshake
gate_applicability:
  disposition: red-required
  work_class: behavior
  ui_surface: non-browser
---
# Guard-only behavior

## Acceptance
- AC-1: existing behavior remains unchanged.
- AC-2: another preservation invariant remains unchanged.

## Test Contracts
| Acceptance | Interface | Seam | Expected failure | Mode |
| --- | --- | --- | --- | --- |
| AC-1 | `api.existing` | committed snapshot | existing behavior changes | guard |
| AC-2 | `api.other` | committed snapshot | another behavior changes | guard |
""",
        encoding="utf-8",
    )

    plan = red_gate._parse_spec(spec)
    assert plan.disposition is red_gate.GateDisposition.RED
    assert plan.contracts == ()
    assert plan.problems == (red_gate.RED_REQUIRED_EXECUTABLE_PROBLEM,)

    code, payload, error = _run_contracts(spec, capsys)

    assert code == 1
    assert payload is None
    assert error.splitlines() == [
        f"ERROR: {red_gate.RED_REQUIRED_EXECUTABLE_PROBLEM}"
    ]

    with pytest.raises(red_gate.GateValidationError) as failure:
        red_gate.parse_gate_applicability(spec)
    assert failure.value.problems == (red_gate.RED_REQUIRED_EXECUTABLE_PROBLEM,)


def test_approved_contract_row_can_cover_multiple_acceptance_ids(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    spec = tmp_path / "grouped.md"
    spec.write_text(
        """---
gate_applicability:
  disposition: red-required
  work_class: behavior
---
# Grouped behavior

## Acceptance Criteria
- AC-1: first behavior.
- AC-2: second behavior.

## Test Contracts
| Acceptance | Interface referent | Outermost stable seam | Expected failure | Mode | Interface version | Matrix rows |
| --- | --- | --- | --- | --- | --- | --- |
| AC-1, AC-2 | `api.read` | `api.read` | grouped witness | contract-matrix | v2 | found<br>missing |
""",
        encoding="utf-8",
    )

    code, payload, error = _run_contracts(spec, capsys)

    assert code == 0, error
    assert payload is not None
    assert [contract["acceptance_id"] for contract in payload["contracts"]] == [
        "AC-1",
        "AC-2",
    ]


def test_approved_red_required_rejects_table_ids_without_acceptance_ids(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    spec = tmp_path / "missing-acceptance-ids.md"
    spec.write_text(
        """---
status: approved
gate_applicability:
  disposition: red-required
  work_class: behavior
---
# Missing acceptance IDs

## Acceptance
The behavior is described here without a stable identifier.

## Test Contracts
| Acceptance | Interface referent | Outermost stable seam | Expected failure | Mode |
| --- | --- | --- | --- | --- |
| AC-1 | `api.read` | `api.read` | value is wrong before implementation | tracer |
""",
        encoding="utf-8",
    )

    code, payload, error = _run_contracts(spec, capsys)

    assert code == 1
    assert payload is None
    assert "acceptance-ids-required" in error


def test_legacy_contracts_are_inferred_without_approval(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    spec = tmp_path / "legacy.md"
    spec.write_text(
        """# Legacy behavior

## Acceptance Criteria
- AC-7: `legacy.run` emits the expected failure witness.
- AC-8: `legacy.run` preserves its caller-facing seam.
""",
        encoding="utf-8",
    )

    code, payload, error = _run_contracts(spec, capsys)

    assert code == 0, error
    assert payload is not None
    assert [contract["acceptance_id"] for contract in payload["contracts"]] == [
        "AC-7",
        "AC-8",
    ]
    assert all(
        contract["contract_source"] == "inferred" for contract in payload["contracts"]
    )
    assert all(contract["seam"] for contract in payload["contracts"])
    assert all(contract["expected_failure"] for contract in payload["contracts"])


def test_not_applicable_allows_acceptance_ids_without_contract_table(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    spec = tmp_path / "docs.md"
    spec.write_text(
        """---
gate_applicability:
  disposition: not-applicable
  work_class: docs-only
  reason: documentation-only change
---
# Documentation

## Acceptance Criteria
- AC-1: The guide describes the new command.
""",
        encoding="utf-8",
    )

    code, payload, error = _run_contracts(spec, capsys)

    assert code == 0, error
    assert payload is not None
    assert payload["disposition"] == "not-applicable"
    assert payload["contracts"] == []


def test_not_applicable_requires_reason(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    spec = tmp_path / "missing-reason.md"
    spec.write_text(
        """---
gate_applicability:
  disposition: not-applicable
  work_class: docs-only
---
# Documentation

## Acceptance Criteria
- AC-1: The guide describes the new command.
""",
        encoding="utf-8",
    )

    code, payload, error = _run_contracts(spec, capsys)

    assert code == 1
    assert payload is None
    assert "not-applicable-reason-required" in error


def test_contracts_reject_contradictory_not_applicable_declaration(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    spec = tmp_path / "contradictory.md"
    spec.write_text(
        """---
gate_applicability:
  disposition: not-applicable
  work_class: appearance-only
---
# Contradictory

## Acceptance Criteria
- AC-1: the interaction returns a changed value.

## Test Contracts
| Acceptance | Interface referent | Outermost stable seam | Expected failure | Mode |
| --- | --- | --- | --- | --- |
| AC-1 | `api.read` | `api.read` | value is wrong before implementation | tracer |
""",
        encoding="utf-8",
    )

    code, payload, error = _run_contracts(spec, capsys)

    assert code == 1
    assert payload is None
    assert "not-applicable-cannot-carry-test-contracts" in error


def test_contracts_reject_duplicate_and_missing_acceptance_rows(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    spec = tmp_path / "incomplete.md"
    spec.write_text(
        """---
gate_applicability:
  disposition: red-required
  work_class: behavior
---
# Incomplete

## Acceptance Criteria
- AC-1: first behavior.
- AC-2: second behavior.

## Test Contracts
| Acceptance | Interface referent | Outermost stable seam | Expected failure | Mode |
| --- | --- | --- | --- | --- |
| AC-1 | `api.read` | `api.read` | first witness | tracer |
| AC-1 | `api.read` | `api.read` | duplicate witness | tracer |
""",
        encoding="utf-8",
    )

    code, payload, error = _run_contracts(spec, capsys)

    assert code == 1
    assert payload is None
    assert "test-contract-acceptance-ids-not-unique" in error


def test_cut_reuses_mold_browser_surface_validation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    spec = tmp_path / "browser.md"
    spec.write_text(
        """---
source: agent-mini-spec
gate_applicability:
  disposition: red-required
  work_class: behavior
  ui_surface: browser
---
# Browser behavior

## Acceptance Criteria
- AC-1: the browser interaction succeeds.

## Test Contracts
| Acceptance | Interface referent | Outermost stable seam | Expected failure | Mode |
| --- | --- | --- | --- | --- |
| AC-1 | `internal helper` | `service boundary` | browser result differs | tracer |
""",
        encoding="utf-8",
    )

    code, payload, error = _run_contracts(spec, capsys)

    assert code == 1
    assert payload is None
    assert "browser-e2e-interface-required" in error
    assert "browser-e2e-seam-required" in error


def test_cut_accepts_mold_appearance_only_ui_as_not_applicable(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    spec = tmp_path / "appearance.md"
    spec.write_text(
        """---
source: agent-mini-spec
gate_applicability:
  disposition: not-applicable
  work_class: appearance-only
  ui_surface: not-applicable
  reason: visual styling only
---
# Appearance

## Acceptance Criteria
- AC-1: the existing surface uses the approved color.
""",
        encoding="utf-8",
    )

    code, payload, error = _run_contracts(spec, capsys)

    assert code == 0, error
    assert payload is not None
    assert payload["disposition"] == "not-applicable"
    assert payload["work_class"] == "appearance-only"
    assert payload["contracts"] == []


def test_cut_reuses_mold_disposition_validation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    spec = tmp_path / "invalid-disposition.md"
    spec.write_text(
        """---
gate_applicability:
  disposition: deferred
  work_class: docs-only
  reason: later
---
# Invalid
""",
        encoding="utf-8",
    )

    code, payload, error = _run_contracts(spec, capsys)

    assert code == 1
    assert payload is None
    assert "gate-applicability-invalid-disposition" in error
