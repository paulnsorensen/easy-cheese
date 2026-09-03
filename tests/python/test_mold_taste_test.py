"""Behavioral tests for Mold's applicability and fork-taste gate."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, cast

import pytest

if TYPE_CHECKING:
    from easy_cheese.shared.taste_test import (  # noqa: V104 -- names used only in quoted Protocol annotations
        ApplicabilityError as _ApplicabilityError,
        ForkTasteVerdict as _ForkTasteVerdict,
        NotApplicable as _NotApplicable,
        RedRequired as _RedRequired,
        TasteGateResult as _TasteGateResult,
        TasteTestError as _TasteTestError,
        TestContract as _TestContract,
    )

REPO_ROOT = Path(__file__).resolve().parents[2]
TASTE_SOURCE = REPO_ROOT / "src" / "easy_cheese" / "shared" / "taste_test.py"


class _MoldTasteTestModule(Protocol):
    REFLECTIONS: tuple[str, ...]
    NOT_APPLICABLE_REFLECTIONS: tuple[str, ...]
    RED_REQUIRED_EXECUTABLE_PROBLEM: str
    TestContract: type["_TestContract"]
    RedRequired: type["_RedRequired"]
    NotApplicable: type["_NotApplicable"]
    TasteTestError: type["_TasteTestError"]
    ApplicabilityError: type["_ApplicabilityError"]

    def draft_sha256(self, draft: object) -> str: ...
    def taste_test(
        self,
        draft: object,
        decision_ledger: object,
        reviewer_verdict: "Mapping[str, object] | _ForkTasteVerdict",
        *,
        correction_round: int = ...,
    ) -> "_ForkTasteVerdict": ...
    def validate_fork_taste(
        self,
        draft: object,
        decision_ledger: object,
        reviewer_verdict: "Mapping[str, object] | _ForkTasteVerdict",
        *,
        correction_round: int = ...,
    ) -> "_ForkTasteVerdict": ...
    def decomposition_gate(
        self, verdict: "_ForkTasteVerdict", *, correction_round: int = ...
    ) -> "_TasteGateResult": ...
    def parse_gate_applicability(
        self, spec: object, *, require_ui_surface: bool = ...
    ) -> "_RedRequired | _NotApplicable": ...
    def required_reflections(self, spec: object) -> tuple[str, ...]: ...
    def auto_handoff(
        self,
        spec_ref: str | Path,
        applicability: "_RedRequired | _NotApplicable",
        metadata: Mapping[str, object] | None = ...,
    ) -> dict[str, object]: ...
    def main(self, argv: list[str]) -> int: ...


@pytest.fixture(scope="module")
def taste() -> _MoldTasteTestModule:
    spec = importlib.util.spec_from_file_location("mold_taste_test", TASTE_SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return cast("_MoldTasteTestModule", cast(object, module))


DRAFT = """# Draft

## Approach
F-1 outer tracer; F-2 browser seam

## Interface sketches
F-1 outer tracer; F-2 browser seam

## Acceptance
F-1 outer tracer; F-2 browser seam

## Test Contracts
F-1 outer tracer; F-2 browser seam
"""
LEDGER = [
    {
        "id": "F-1",
        "decision": "outer tracer",
        "status": "settled",
        "consequential": True,
    },
    {
        "id": "F-2",
        "decision": "browser seam",
        "status": "settled",
        "consequential": True,
    },
    {"id": "F-open", "decision": "not chosen", "status": "open", "consequential": True},
    {
        "id": "F-minor",
        "decision": "cosmetic",
        "status": "settled",
        "consequential": False,
    },
]


def verdict(taste: _MoldTasteTestModule, draft: str = DRAFT) -> dict[str, object]:
    return {
        "draft_sha256": taste.draft_sha256(draft),
        "verdict": "pass",
        "forks": [
            {
                "id": "F-1",
                "decision": "outer tracer",
                "reflected_in": list(taste.REFLECTIONS),
            },
            {
                "id": "F-2",
                "decision": "browser seam",
                "reflected_in": list(taste.REFLECTIONS),
            },
        ],
        "contradictions": [],
        "orphaned_decisions": [],
        "unsupported_assumptions": [],
        "acceptance_gaps": [],
    }


def red_spec() -> str:
    return """---
source: mold-handshake
gate_applicability:
  disposition: red-required
  work_class: behavior
  ui_surface: non-browser
---
# A behavior

## Acceptance
- AC-1: WHEN called THE SYSTEM SHALL return the result
- AC-2: WHEN empty THE SYSTEM SHALL reject the input

## Test Contracts
| Acceptance ID | Interface | Outer seam | Deterministic expected failure | Mode | Interface version | Matrix rows |
| --- | --- | --- | --- | --- | --- | --- |
| AC-1 | public call | existing service boundary | assert result is returned | tracer | | |
| AC-2 | public call | existing service boundary | assert empty input is rejected | contract-matrix | v1 | empty<br>non-empty |
"""


def test_pass_requires_digest_and_every_settled_consequential_fork(
    taste: _MoldTasteTestModule,
) -> None:
    result = taste.taste_test(DRAFT, LEDGER, verdict(taste))
    assert result.passed
    assert result.draft_sha256 == hashlib.sha256(DRAFT.encode()).hexdigest()
    gate = taste.decomposition_gate(result)
    assert gate.allowed and not gate.halted


def test_taste_gate_blocks_source_less_draft_without_ui_surface(
    taste: _MoldTasteTestModule,
) -> None:
    draft = (
        """---
gate_applicability:
  disposition: red-required
  work_class: behavior
---
"""
        + DRAFT
    )
    result = taste.taste_test(draft, LEDGER, verdict(taste, draft))
    assert not result.passed
    assert (
        "gate-applicability:gate-applicability-ui-surface-required"
        in result.acceptance_gaps
    )


def test_taste_gate_requires_applicability_for_mold_handshake_source(
    taste: _MoldTasteTestModule,
) -> None:
    draft = "---\nsource: mold-handshake\n---\n" + DRAFT
    result = taste.taste_test(draft, LEDGER, verdict(taste, draft))
    assert not result.passed
    assert (
        "gate-applicability:gate-applicability-declaration-required"
        in result.acceptance_gaps
    )


def test_taste_gate_requires_applicability_for_agent_mini_spec_source(
    taste: _MoldTasteTestModule,
) -> None:
    draft = "---\nsource: agent-mini-spec\n---\n" + DRAFT
    result = taste.taste_test(draft, LEDGER, verdict(taste, draft))
    assert not result.passed
    assert (
        "gate-applicability:gate-applicability-declaration-required"
        in result.acceptance_gaps
    )


def test_taste_gate_keeps_missing_applicability_compatibility_for_legacy_spec(
    taste: _MoldTasteTestModule,
) -> None:
    draft = "---\nslug: legacy-spec\n---\n" + DRAFT
    result = taste.taste_test(draft, LEDGER, verdict(taste, draft))
    assert result.passed


def test_each_settled_fork_requires_all_reflection_locations(
    taste: _MoldTasteTestModule,
) -> None:
    partial = verdict(taste)
    forks = partial["forks"]
    assert isinstance(forks, list)
    forks = cast(list[object], forks)
    first = forks[0]
    assert isinstance(first, dict)
    first = cast(dict[str, object], first)
    first["reflected_in"] = ["approach"]
    result = taste.taste_test(DRAFT, LEDGER, partial)
    assert not result.passed
    assert {
        "missing-reflection:F-1:interface",
        "missing-reflection:F-1:acceptance",
        "missing-reflection:F-1:test-contract",
    } <= set(result.acceptance_gaps)


NOT_APPLICABLE_DRAFT = """---
source: mold-handshake
gate_applicability:
  disposition: not-applicable
  work_class: docs-only
  ui_surface: not-applicable
  reason: documentation-only change
---
# Docs draft

## Approach
F-1 outer tracer; F-2 browser seam

## Interface sketches
F-1 outer tracer; F-2 browser seam

## Acceptance
F-1 outer tracer; F-2 browser seam
"""


def _verdict_with(
    taste: _MoldTasteTestModule, draft: str, reflections: tuple[str, ...]
) -> dict[str, object]:
    payload = verdict(taste, draft)
    forks = cast(list[dict[str, object]], payload["forks"])
    for fork in forks:
        fork["reflected_in"] = list(reflections)
    return payload


def test_not_applicable_spec_owes_only_the_three_reachable_reflections(
    taste: _MoldTasteTestModule,
) -> None:
    assert taste.required_reflections(NOT_APPLICABLE_DRAFT) == (
        "approach",
        "interface",
        "acceptance",
    )
    assert taste.NOT_APPLICABLE_REFLECTIONS == ("approach", "interface", "acceptance")


def test_not_applicable_spec_passes_without_a_test_contract_reflection(
    taste: _MoldTasteTestModule,
) -> None:
    result = taste.taste_test(
        NOT_APPLICABLE_DRAFT,
        LEDGER,
        _verdict_with(
            taste, NOT_APPLICABLE_DRAFT, taste.NOT_APPLICABLE_REFLECTIONS
        ),
    )
    assert result.acceptance_gaps == ()
    assert result.passed
    assert taste.decomposition_gate(result).allowed


def test_not_applicable_spec_still_owes_the_other_three_reflections(
    taste: _MoldTasteTestModule,
) -> None:
    result = taste.taste_test(
        NOT_APPLICABLE_DRAFT,
        LEDGER,
        _verdict_with(taste, NOT_APPLICABLE_DRAFT, ("approach",)),
    )
    assert not result.passed
    assert {
        "missing-reflection:F-1:interface",
        "missing-reflection:F-1:acceptance",
        "missing-reflection:F-2:interface",
        "missing-reflection:F-2:acceptance",
    } <= set(result.acceptance_gaps)
    assert not any(
        gap.endswith(":test-contract") for gap in result.acceptance_gaps
    )


def test_red_required_spec_keeps_the_four_reflection_contract(
    taste: _MoldTasteTestModule,
) -> None:
    draft = red_spec().replace(
        "## Acceptance\n",
        "## Approach\nF-1 outer tracer\n\n## Interface sketches\nF-1 outer tracer\n\n## Acceptance\n",
    )
    ledger = [LEDGER[0]]
    payload = _verdict_with(taste, draft, ("approach", "interface", "acceptance"))
    payload["forks"] = [cast(list[dict[str, object]], payload["forks"])[0]]
    assert taste.required_reflections(draft) == taste.REFLECTIONS
    result = taste.taste_test(draft, ledger, payload)
    assert not result.passed
    assert "missing-reflection:F-1:test-contract" in result.acceptance_gaps


def test_missing_reviewer_fork_reopens_the_named_ledger_fork(
    taste: _MoldTasteTestModule,
) -> None:
    partial = verdict(taste)
    forks = partial["forks"]
    assert isinstance(forks, list)
    del forks[0]
    result = taste.taste_test(DRAFT, LEDGER, partial)
    assert result.reopened_forks == ("F-1",)


def test_fresh_context_verdict_is_required(taste: _MoldTasteTestModule) -> None:
    with pytest.raises(TypeError):
        taste.taste_test(DRAFT, LEDGER)  # pyright: ignore[reportCallIssue]
    with pytest.raises(TypeError):
        taste.validate_fork_taste(DRAFT, LEDGER)  # pyright: ignore[reportCallIssue]
    with pytest.raises(taste.TasteTestError):
        _ = taste.taste_test(DRAFT, LEDGER, None)  # pyright: ignore[reportArgumentType]


def test_cli_requires_verdict_file(taste: _MoldTasteTestModule, tmp_path: Path) -> None:
    draft = tmp_path / "draft.md"
    ledger = tmp_path / "ledger.json"
    _ = draft.write_text(DRAFT, encoding="utf-8")
    _ = ledger.write_text(json.dumps(LEDGER), encoding="utf-8")
    with pytest.raises(SystemExit) as exc_info:
        _ = taste.main(["--draft", str(draft), "--ledger", str(ledger)])
    assert exc_info.value.code == 2


def test_stale_digest_is_a_blocker_before_decomposition(taste: _MoldTasteTestModule) -> None:
    stale = verdict(taste)
    stale["draft_sha256"] = "0" * 64
    result = taste.taste_test(DRAFT, LEDGER, stale)
    assert not result.passed
    assert "stale-draft-digest" in result.acceptance_gaps
    assert not taste.decomposition_gate(result).allowed


def test_partial_verdict_shape_is_rejected(taste: _MoldTasteTestModule) -> None:
    partial = verdict(taste)
    del partial["acceptance_gaps"]
    with pytest.raises(taste.TasteTestError, match="invalid-verdict-shape"):
        _ = taste.taste_test(DRAFT, LEDGER, partial)


def test_contradictions_orphans_assumptions_and_gaps_reject_pass(
    taste: _MoldTasteTestModule,
) -> None:
    blocked = verdict(taste)
    blocked["contradictions"] = ["F-1 chooses two incompatible seams"]
    blocked["orphaned_decisions"] = ["F-orphan"]
    blocked["unsupported_assumptions"] = ["the browser is always available"]
    blocked["acceptance_gaps"] = ["AC-2 has no witness"]
    result = taste.taste_test(DRAFT, LEDGER, blocked)
    assert not result.passed
    assert result.reopened_forks == ("F-1",)
    assert not taste.decomposition_gate(result).allowed


def test_third_failed_verdict_halts_after_two_corrections(taste: _MoldTasteTestModule) -> None:
    blocked = verdict(taste)
    blocked["verdict"] = "fail"
    blocked["acceptance_gaps"] = ["named fork needs correction"]
    result = taste.taste_test(DRAFT, LEDGER, blocked)
    assert not taste.decomposition_gate(result, correction_round=0).halted
    assert not taste.decomposition_gate(result, correction_round=1).halted
    final = taste.decomposition_gate(result, correction_round=2)
    assert final.halted and not final.allowed


def test_applicability_requires_complete_contracts_and_allows_closed_na(
    taste: _MoldTasteTestModule,
) -> None:
    applicability = taste.parse_gate_applicability(red_spec())
    assert isinstance(applicability, taste.RedRequired)
    assert [contract.acceptance_id for contract in applicability.contracts] == [
        "AC-1",
        "AC-2",
    ]
    matrix = applicability.contracts[1]
    assert matrix.interface_version == "v1"
    assert matrix.matrix_rows == ("empty", "non-empty")

    not_applicable = taste.parse_gate_applicability(
        """---
gate_applicability:
  disposition: not-applicable
  work_class: docs-only
  reason: documentation-only change
---
# Docs
"""
    )
    assert isinstance(not_applicable, taste.NotApplicable)
    assert not not_applicable.contracts


def test_applicability_keeps_green_guards_outside_cut_contracts(
    taste: _MoldTasteTestModule,
) -> None:
    spec = red_spec().replace(
        "| AC-2 | public call | existing service boundary | assert empty input is rejected | contract-matrix | v1 | empty<br>non-empty |",
        "| AC-2 | public call | existing service boundary | existing behavior remains byte-identical | guard | | |",
    )

    applicability = taste.parse_gate_applicability(spec)
    assert isinstance(applicability, taste.RedRequired)
    assert [
        (contract.acceptance_id, contract.mode)
        for contract in applicability.contracts
    ] == [("AC-1", "tracer"), ("AC-2", "guard")]


def test_guard_only_red_required_is_rejected_before_cut_handoff(
    taste: _MoldTasteTestModule,
) -> None:
    spec = red_spec()
    spec = spec.replace(
        "| AC-1 | public call | existing service boundary | assert result is returned | tracer | | |",
        "| AC-1 | public call | existing service boundary | existing behavior remains byte-identical | guard | | |",
    ).replace(
        "| AC-2 | public call | existing service boundary | assert empty input is rejected | contract-matrix | v1 | empty<br>non-empty |",
        "| AC-2 | public call | existing service boundary | existing behavior remains byte-identical | guard | | |",
    )

    with pytest.raises(taste.ApplicabilityError) as error:
        _ = taste.parse_gate_applicability(spec)
    assert error.value.problems == (taste.RED_REQUIRED_EXECUTABLE_PROBLEM,)
    guard = taste.TestContract(
        acceptance_id="AC-1",
        interface="public call",
        seam="committed snapshot",
        expected_failure="existing behavior changes",
        mode="guard",
    )
    with pytest.raises(taste.ApplicabilityError) as constructor_error:
        _ = taste.RedRequired("behavior", (guard,))
    assert constructor_error.value.problems == (
        taste.RED_REQUIRED_EXECUTABLE_PROBLEM,
    )


    result = taste.taste_test(
        spec,
        [],
        {
            "draft_sha256": taste.draft_sha256(spec),
            "verdict": "pass",
            "forks": [],
            "contradictions": [],
            "orphaned_decisions": [],
            "unsupported_assumptions": [],
            "acceptance_gaps": [],
        },
    )
    assert result.acceptance_gaps == (
        f"gate-applicability:{taste.RED_REQUIRED_EXECUTABLE_PROBLEM}",
    )
    gate = taste.decomposition_gate(result)
    assert not gate.allowed
    assert gate.reopened_forks == ()


@pytest.mark.parametrize(
    ("replacement", "problem"),
    [
        (
            "| contract-matrix | v1 | empty<br>non-empty |",
            "contract-matrix-interface-version-required",
        ),
        (
            "| contract-matrix | v1 | empty<br>empty |",
            "contract-matrix-rows-not-unique",
        ),
    ],
)
def test_contract_matrix_requires_versioned_unique_declared_rows(
    taste: _MoldTasteTestModule,
    replacement: str,
    problem: str,
) -> None:
    if "interface-version" in problem:
        replacement = "| contract-matrix | | empty<br>non-empty |"
    spec = red_spec().replace(
        "| contract-matrix | v1 | empty<br>non-empty |",
        replacement,
    )

    with pytest.raises(taste.ApplicabilityError, match=problem):
        _ = taste.parse_gate_applicability(spec)


def test_appearance_only_stays_not_applicable_with_explicit_surface(
    taste: _MoldTasteTestModule,
) -> None:
    spec = """---
source: mold-handshake
gate_applicability:
  disposition: not-applicable
  work_class: appearance-only
  ui_surface: not-applicable
  reason: visual-only change
---
# Appearance
"""
    applicability = taste.parse_gate_applicability(spec)
    assert isinstance(applicability, taste.NotApplicable)
    assert applicability.ui_surface == "not-applicable"


def test_not_applicable_allows_acceptance_ids_without_test_contracts(
    taste: _MoldTasteTestModule,
) -> None:
    spec = """---
gate_applicability:
  disposition: not-applicable
  work_class: docs-only
  reason: documentation-only change
---
# Docs

## Acceptance Criteria
- AC-1: The guide describes the new command.
"""
    assert isinstance(taste.parse_gate_applicability(spec), taste.NotApplicable)


def test_not_applicable_rejects_even_an_empty_test_contract_section(
    taste: _MoldTasteTestModule,
) -> None:
    spec = """---
gate_applicability:
  disposition: not-applicable
  work_class: docs-only
  reason: documentation-only change
---
# Docs

## Acceptance Criteria
- AC-1: The guide describes the new command.

## Test Contracts
"""
    with pytest.raises(
        taste.ApplicabilityError, match="not-applicable-cannot-carry-test-contracts"
    ):
        _ = taste.parse_gate_applicability(spec)


def test_red_required_rejects_contracts_without_stable_acceptance_ids(
    taste: _MoldTasteTestModule,
) -> None:
    spec = red_spec().replace("- AC-1:", "- first:").replace("- AC-2:", "- second:")
    with pytest.raises(taste.ApplicabilityError, match="acceptance-ids-required"):
        _ = taste.parse_gate_applicability(spec)


def test_strict_ui_mode_blocks_missing_surface(taste: _MoldTasteTestModule) -> None:
    spec = red_spec().replace("  ui_surface: non-browser\n", "")
    with pytest.raises(taste.ApplicabilityError, match="ui-surface-required"):
        _ = taste.parse_gate_applicability(spec, require_ui_surface=True)


def test_browser_ui_requires_named_browser_interface_and_outer_seam(
    taste: _MoldTasteTestModule,
) -> None:
    spec = red_spec().replace("ui_surface: non-browser", "ui_surface: browser")
    spec = spec.replace("existing service boundary", "internal helper")
    with pytest.raises(taste.ApplicabilityError, match="browser-e2e-seam"):
        _ = taste.parse_gate_applicability(spec)


def test_valid_browser_ui_surface_passes_with_browser_interface_and_seam(
    taste: _MoldTasteTestModule,
) -> None:
    spec = red_spec().replace("ui_surface: non-browser", "ui_surface: browser")
    spec = spec.replace("public call", "existing browser interface")
    spec = spec.replace("existing service boundary", "existing browser E2E outer seam")
    applicability = taste.parse_gate_applicability(spec)
    assert isinstance(applicability, taste.RedRequired)
    assert applicability.ui_surface == "browser"


def test_explicit_non_browser_behavior_remains_valid_and_prose_does_not_reclassify(
    taste: _MoldTasteTestModule,
) -> None:
    spec = red_spec() + "\nFunctional UI is ordinary behavior with a browser seam.\n"
    applicability = taste.parse_gate_applicability(spec)
    assert isinstance(applicability, taste.RedRequired)
    assert applicability.ui_surface == "non-browser"


def test_legacy_spec_without_ui_surface_remains_compatible(taste: _MoldTasteTestModule) -> None:
    spec = red_spec().replace("source: mold-handshake\n", "")
    spec = spec.replace("  ui_surface: non-browser\n", "")
    applicability = taste.parse_gate_applicability(spec)
    assert isinstance(applicability, taste.RedRequired)
    assert applicability.ui_surface is None


def test_red_required_handoff_preserves_pointer_and_metadata(taste: _MoldTasteTestModule) -> None:
    applicability = taste.parse_gate_applicability(red_spec())
    metadata = {"spec_sha256": "abc", "taste_sha256": "def"}
    handoff = taste.auto_handoff("artifact://specs/a.md", applicability, metadata)
    assert handoff["command"] == ["/cook", "--auto", "artifact://specs/a.md"]
    assert handoff["spec_ref"] == "artifact://specs/a.md"
    handoff_metadata = handoff["metadata"]
    assert isinstance(handoff_metadata, dict)
    handoff_metadata = cast(dict[str, object], handoff_metadata)
    assert handoff_metadata["spec_sha256"] == "abc"
    assert handoff_metadata["taste_sha256"] == "def"
    gate_applicability = handoff_metadata["gate_applicability"]
    assert isinstance(gate_applicability, dict)
    gate_applicability = cast(dict[str, object], gate_applicability)
    assert gate_applicability["disposition"] == "red-required"
    assert gate_applicability["ui_surface"] == "non-browser"
    assert metadata == {"spec_sha256": "abc", "taste_sha256": "def"}
