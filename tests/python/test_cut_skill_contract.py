"""Contract tests for the first-class ``/cut`` skill.

These tests keep the prose contract executable where a runtime helper exists,
and keep documentation assertions scoped to the section that owns each
invariant. They intentionally do not bless a receipt by inspecting arbitrary
GateReceipt JSON: ``red-gate issue`` remains the writer boundary.
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from types import ModuleType


REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL = REPO_ROOT / "skills" / "cut" / "SKILL.md"
WORKFLOW = REPO_ROOT / "skills" / "cut" / "references" / "gate-workflow.md"
PRESSURE = REPO_ROOT / "skills" / "cut" / "references" / "pressure-eval.md"
CUT_ROOT = REPO_ROOT / "src" / "cut"


def _frontmatter(path: Path) -> dict[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines and lines[0] == "---", f"{path} must start with frontmatter"
    end = next((index for index, line in enumerate(lines[1:], start=1) if line == "---"), None)
    assert end is not None, f"{path} frontmatter is not closed"
    result: dict[str, str] = {}
    for line in lines[1:end]:
        if ":" not in line or line[:1].isspace():
            continue
        key, value = line.split(":", 1)
        result[key.strip()] = value.strip()
    return result


def _body(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    return parts[2] if len(parts) == 3 and parts[0].strip() == "" else text


def _section(path: Path, heading: str) -> str:
    body = _body(path)
    match = re.search(rf"^## {re.escape(heading)}\s*$", body, re.MULTILINE)
    assert match, f"{path} has no ## {heading} section"
    tail = body[match.end() :]
    next_heading = re.search(r"^## \S.*$", tail, re.MULTILINE)
    return tail[: next_heading.start()] if next_heading else tail


def _flat(text: str) -> str:
    return " ".join(text.split())


def _load_red_gate() -> ModuleType:
    sys.path.insert(0, str(CUT_ROOT))
    spec = importlib.util.spec_from_file_location("red_gate_cut_skill_contract", CUT_ROOT / "red_gate.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


red_gate = _load_red_gate()


def test_cut_frontmatter_is_first_class_and_triggerable() -> None:
    metadata = _frontmatter(SKILL)
    assert metadata["name"] == "cut"
    assert metadata["license"] == "MIT"
    description = metadata["description"]
    sentences = re.split(r"(?<=[.!?])\s+", description)
    assert sentences[0].startswith("Establishes protected, test-only RED evidence")
    assert sentences[1].startswith("Use when ")
    for trigger in ("/cut", "Mold", "Cook", "Pasteurize"):
        assert trigger in description


def test_cut_references_are_existing_one_level_links() -> None:
    body = _body(SKILL)
    links = set(re.findall(r"\]\(([^)]+)\)", body))
    assert {"references/gate-workflow.md", "references/pressure-eval.md"} <= links
    for relative in links:
        if relative.startswith("references/"):
            reference = SKILL.parent / relative
            assert reference.is_file(), relative
            first = next(line for line in reference.read_text(encoding="utf-8").splitlines() if line.strip())
            assert first.startswith("# "), relative
            nested_reference_links = re.findall(r"\]\((references/[^)]+)\)", reference.read_text(encoding="utf-8"))
            assert not nested_reference_links, f"{relative} creates a second reference hop"


def test_cut_contract_declares_the_public_callable_shape() -> None:
    contract = _section(SKILL, "Contract")
    assert re.search(r"cut\(spec_ref, reproduction\? = null, auto = false\) -> GateReceipt", contract)
    assert "Mold's approved `red-required` handoff" in contract
    assert "no valid receipt" in contract
    assert "contract_source: inferred" in contract
    assert "producer: cut" in contract
    assert "origin: adopted" in contract


def test_flow_orders_snapshot_pre_oracle_baseline_oracle_red_and_issue() -> None:
    flow = _flat(_section(SKILL, "Flow"))
    required_order = (
        "red-gate contracts <spec>",
        "Validate `gate_applicability`",
        "Choose the seam and declare the phase",
        "red-gate begin .cheese/cut/<slug>.plan.json",
        "Freeze the baseline evidence",
        "Copy the token's exact baseline command identities",
        "Write only the oracle",
        "Prove RED",
        "red-gate issue <candidate> --token .cheese/cut/<slug>.phase.json --out .cheese/cut/<slug>.json",
        "Handoff",
    )
    positions = [flow.index(marker) for marker in required_order]
    assert positions == sorted(positions)
    assert "Before creating or adopting a new oracle" in flow
    assert "freezes the full project snapshot" in flow
    assert "halts without a token" in flow
    assert "Baseline argv must exclude the protected RED-oracle paths or remain green" in flow
    assert "Collection, import, dependency, fixture, syntax, or other harness failures are not a behavioral RED." in flow

def test_receipt_invariants_are_section_local_and_exact() -> None:
    section = _flat(_section(SKILL, "Receipt invariants"))
    assert re.search(r"RED receipt has `producer: cut`", section)
    assert re.search(r"frozen pre-Cut `baseline_checks`", section)
    assert "Each `baseline_checks` entry is the broad project result captured before the oracle" in section
    assert all(field in section for field in ("id", "argv", "cwd", "observed_exit_code"))
    assert "immutable receipt evidence, not a Cook-owned recapture" in section
    assert re.search(r"Initial Cut receipts have\s+`guard_receipt_refs: \[\]`", section)
    assert re.search(r"Each ordinary\s+behavioral curd owns one tracer", section)
    assert re.search(
        r"contract matrix is allowed\s+only for a ratified/versioned interface",
        section,
    )
    assert "`interface_version` and unique `matrix_rows`" in section
    assert "exactly one `kind: contract` case for each named `matrix_row`" in section
    assert "active case origin remains `generated` or `adopted`" in section
    assert "do not create a RED-only commit" in section


def test_closed_na_rule_has_no_red_evidence() -> None:
    flow = _flat(_section(SKILL, "Flow"))
    assert re.search(
        r"`not-applicable` declaration.*?closed class.*?no RED contracts,\s*baseline checks, cases, protected files, guards, or receipt-level mode",
        flow,
        re.DOTALL,
    )
    workflow = _flat(_section(WORKFLOW, "Applicability closure"))
    for work_class in ("docs-only", "refactor-only", "test-only", "appearance-only"):
        assert re.search(rf"\| `not-applicable` \+ `{work_class}` \| Issue closed N/A", workflow)
    assert "no contracts, baseline checks, cases, protected files, guards, or gate mode" in workflow
    assert "red-gate issue" in workflow


def test_reproduction_adoption_preserves_cut_provenance() -> None:
    workflow = _flat(_section(WORKFLOW, "Inputs and provenance"))
    assert "user or Pasteurize" in workflow
    assert "`origin: adopted`" in workflow
    assert "approved seam" in workflow
    assert "argv list" in workflow
    assert "halt and name the ambiguity" in workflow


def test_runner_policy_rejects_silent_third_party_invention() -> None:
    runner = _flat(_section(WORKFLOW, "Runner and seam selection"))
    assert "target project's existing runner" in runner
    assert "Python 3.12 standard-library runner already present" in runner
    assert "explicit harness decision" in runner
    assert "Do not add pytest" in runner
    assert "functional UI is ordinary behavior" in runner
    assert "appearance-only UI is closed N/A" in runner


def test_dirty_worktree_and_production_safety_are_explicit() -> None:
    workflow = _flat(_section(WORKFLOW, "Evidence sequence"))
    assert "pre-existing dirty-worktree delta" in workflow
    assert "Write the smallest outer tracer" in workflow
    assert "Do not change production files" in workflow
    assert "Every observed exit code must be `0`" in workflow
    assert (
        "Any change other than a newly added exact protected test-side file is a Cut refusal"
        in workflow
    )
    refusal = _flat(_section(WORKFLOW, "Refusal matrix"))
    assert re.search(r"\| production digest changed during Cut \| halt; no successful receipt \|", refusal)
    assert re.search(r"\| dirty worktree has unrelated edits \| preserve them; add only test-side files; never commit \|", refusal)


def test_issue_boundary_forbids_raw_receipt_writes() -> None:
    for path in (SKILL, WORKFLOW):
        body = _body(path)
        assert "red-gate issue" in body
        assert not re.search(r"\bjson\.(?:dump|dumps)\b", body)
    flow = _section(SKILL, "Flow")
    assert re.search(r"`red-gate issue` is the only receipt writer", flow)
    assert re.search(r"Never hand-write or publish raw\s+GateReceipt JSON", flow, re.DOTALL)
    assert "short-lived candidate input" in _section(WORKFLOW, "Evidence sequence")


def test_handoff_and_auto_sync_boundaries_are_exact() -> None:
    handoff = _flat(_section(SKILL, "Handoff"))
    assert re.search(
        r"status: ok\s+next: cook\s+artifact: \.cheese/cut/<slug>\.json",
        handoff,
    )
    assert "The canonical receipt is the handoff's baseline carrier" in handoff
    assert "consume its frozen `baseline_checks` exactly" in handoff
    assert "must not overwrite or recapture them" in handoff
    assert "A blocked attempt uses `halt: <reason>`" in handoff
    auto = _flat(_section(WORKFLOW, "Auto and synchronous handoff"))
    assert "dispatches Cook once with the receipt pointer" in auto
    assert "does not dispatch Cook from inside the preflight" in auto
    assert "returns the validated `GateReceipt`" in auto


def test_discipline_has_iron_law_red_flags_and_rebuttals() -> None:
    discipline = _section(SKILL, "Discipline")
    assert re.search(r"\*\*Iron Law:\*\* No successful Cut RED receipt without", discipline)
    for flag in (
        "production code changed",
        "collection, import, fixture setup",
        "missing runner",
        "RED-only commit",
        "serialized directly as the published receipt",
        "called recursively",
    ):
        assert flag in discipline
    rows = [line for line in discipline.splitlines() if line.startswith("|")]
    assert any("collection crash" in row and "issue nothing" in row for row in rows)
    assert any("missing" in row and "explicit harness decision" in row for row in rows)
    assert any("hand-written receipt" in row and "red-gate issue" in row for row in rows)


def test_pressure_reference_is_linked_from_the_gate() -> None:
    pressure = _section(SKILL, "Pressure gate")
    assert "failing pre-skill pressure run" in pressure
    assert "references/pressure-eval.md" in pressure
    assert "AC-12" in pressure
    assert "test_cut_pressure_eval.py" in pressure
    assert PRESSURE.is_file()


def test_legacy_contract_inference_is_executable(tmp_path: Path) -> None:
    spec = tmp_path / "legacy.md"
    spec.write_text(
        """# Legacy behavior

## Acceptance Criteria
- AC-7: `legacy.run` emits the expected witness.
- AC-8: `legacy.run` preserves the caller seam.
""",
        encoding="utf-8",
    )
    plan = red_gate.parse_gate_applicability(spec)
    assert plan.disposition.value == "red"
    assert [contract.acceptance_id for contract in plan.contracts] == ["AC-7", "AC-8"]
    assert all(contract.contract_source == "inferred" for contract in plan.contracts)
    assert all(contract.seam and contract.expected_failure for contract in plan.contracts)


def test_closed_na_plan_is_executable_and_empty_of_red_contracts(tmp_path: Path) -> None:
    spec = tmp_path / "appearance.md"
    spec.write_text(
        """---
status: approved
gate_applicability:
  disposition: not-applicable
  work_class: appearance-only
  reason: appearance-only work item
---
# Appearance

No interaction or data behavior changes.
""",
        encoding="utf-8",
    )
    plan = red_gate.parse_gate_applicability(spec)
    assert plan.disposition.value == "not-applicable"
    assert plan.contracts == ()
    assert plan.not_applicable_reason == "appearance-only work item"


_LEGACY_MOLD_SPEC = """---
slug: retry-backoff-tuning
status: approved
---

# Retry backoff tuning

## Problem
Immediate retries cause storms.

## Goals
- Retries back off exponentially with jitter.

## Required cases
- `retry.send` waits exponentially longer between attempts.
- `retry.send` stops after three attempts and surfaces the final error.
- A successful attempt short-circuits the remaining retries.

## Approach
Wrap the transport send in a bounded backoff helper.
"""


def test_mold_legacy_required_cases_spec_infers_contracts(tmp_path: Path) -> None:
    """gh#401: an approved legacy Mold spec (narrative Goals + Required cases,
    no acceptance IDs, no declaration, no Test Contracts table) must still
    parse into an executable red plan."""
    spec = tmp_path / "legacy-mold.md"
    spec.write_text(_LEGACY_MOLD_SPEC, encoding="utf-8")
    plan = red_gate.parse_gate_applicability(spec)
    assert plan.disposition.value == "red"
    assert [contract.acceptance_id for contract in plan.contracts] == [
        "AC-1",
        "AC-2",
        "AC-3",
    ]
    assert all(contract.contract_source == "inferred" for contract in plan.contracts)
    assert plan.contracts[0].interface == "retry.send"
    assert all(
        contract.seam and contract.expected_failure for contract in plan.contracts
    )


def test_mold_legacy_spec_passes_red_gate_contracts_cli(tmp_path: Path) -> None:
    """gh#401 integration: the exact Cook-preflight command must succeed on
    the legacy Mold shape through the built cut bundle."""
    import build_pyz

    spec = tmp_path / "legacy-mold.md"
    spec.write_text(_LEGACY_MOLD_SPEC, encoding="utf-8")
    bundle = build_pyz.cached_bundle("cut")
    proc = subprocess.run(
        [sys.executable, str(bundle), "red-gate", "contracts", str(spec)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["disposition"] == "red"
    assert [row["acceptance_id"] for row in payload["contracts"]] == [
        "AC-1",
        "AC-2",
        "AC-3",
    ]
