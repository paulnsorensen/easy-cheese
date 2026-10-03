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
from _pytest.capture import CaptureFixture

if TYPE_CHECKING:
    from easy_cheese.shared.taste_test import (  # noqa: V104 -- names used only in quoted Protocol annotations
        ApplicabilityError as _ApplicabilityError,
        ForkTasteVerdict as _ForkTasteVerdict,
        TasteGateResult as _TasteGateResult,
        TasteTestError as _TasteTestError,
    )

REPO_ROOT = Path(__file__).resolve().parents[2]
TASTE_SOURCE = REPO_ROOT / "src" / "easy_cheese" / "shared" / "taste_test.py"


class _MoldTasteTestModule(Protocol):
    REFLECTIONS: tuple[str, ...]
    TEST_CONTRACT_REFLECTION: str
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
    def decomposition_gate(
        self, verdict: "_ForkTasteVerdict", *, correction_round: int = ...
    ) -> "_TasteGateResult": ...
    def typed_mold_document(self, spec: object) -> object: ...
    def required_reflections(self, spec: object) -> tuple[str, ...]: ...
    def lexical_precheck(
        self, draft: object, decision_ledger: object
    ) -> tuple[str, ...]: ...
    def goal_coverage(
        self, draft: object, decision_ledger: object
    ) -> dict[str, str]: ...
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


def verdict(taste: _MoldTasteTestModule, draft: object = DRAFT) -> dict[str, object]:
    return {
        "draft_sha256": taste.draft_sha256(draft),
        "verdict": "pass",
        "forks": [
            {
                "id": "F-1",
                "decision": "outer tracer",
                "reflected_in": list(taste.required_reflections(draft)),
            },
            {
                "id": "F-2",
                "decision": "browser seam",
                "reflected_in": list(taste.required_reflections(draft)),
            },
        ],
        "contradictions": [],
        "orphaned_decisions": [],
        "unsupported_assumptions": [],
        "acceptance_gaps": [],
    }


def contract_spec() -> str:
    return """---
source: mold-handshake
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


GROUNDING_TWO_WIKI_PROBES = """
## Grounding
| Probe | Outcome | Evidence |
| --- | --- | --- |
| wiki | hit | wiki page |
| wiki | miss | second wiki probe |
"""


@pytest.mark.parametrize(
    "source", ["mold-handshake", "agent-mini-spec", "mold-curd-mini-spec"]
)
def test_marked_source_without_gate_applicability_passes_the_taste_gate(
    taste: _MoldTasteTestModule, source: str
) -> None:
    draft = f"---\nsource: {source}\n---\n" + DRAFT
    result = taste.taste_test(draft, LEDGER, verdict(taste, draft))
    assert result.passed, result.acceptance_gaps
    assert result.acceptance_gaps == ()


@pytest.mark.parametrize("source", ["mold-handshake", "agent-mini-spec"])
def test_taste_gate_reports_document_gaps_for_marked_sources(
    taste: _MoldTasteTestModule, source: str
) -> None:
    draft = f"---\nsource: {source}\n---\n" + DRAFT + GROUNDING_TWO_WIKI_PROBES
    result = taste.taste_test(draft, LEDGER, verdict(taste, draft))
    assert not result.passed
    assert any(
        gap.startswith("spec-document:")
        and "Grounding table must record the wiki probe exactly once" in gap
        for gap in result.acceptance_gaps
    )
    assert not any("gate-applicability" in gap for gap in result.acceptance_gaps)


def test_taste_gate_keeps_document_compatibility_for_legacy_spec(
    taste: _MoldTasteTestModule,
) -> None:
    draft = "---\nslug: legacy-spec\n---\n" + DRAFT
    result = taste.taste_test(draft, LEDGER, verdict(taste, draft))
    assert result.passed
    assert not any(gap.startswith("spec-document:") for gap in result.acceptance_gaps)


def test_taste_gate_ignores_document_problems_in_legacy_spec(
    taste: _MoldTasteTestModule,
) -> None:
    draft = "---\nslug: legacy-spec\n---\n" + DRAFT + GROUNDING_TWO_WIKI_PROBES
    result = taste.taste_test(draft, LEDGER, verdict(taste, draft))
    assert result.passed, result.acceptance_gaps


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


DRAFT_WITHOUT_CONTRACTS = """---
source: mold-handshake
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


def _without_document_gaps(gaps: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(gap for gap in gaps if not gap.startswith("spec-document:"))


def test_reflections_are_the_three_reachable_sections(
    taste: _MoldTasteTestModule,
) -> None:
    assert taste.REFLECTIONS == ("approach", "interface", "acceptance")
    assert taste.TEST_CONTRACT_REFLECTION == "test-contract"


def test_draft_without_test_contracts_owes_only_the_three_reflections(
    taste: _MoldTasteTestModule,
) -> None:
    assert taste.required_reflections(DRAFT_WITHOUT_CONTRACTS) == taste.REFLECTIONS


def test_draft_with_test_contracts_also_owes_the_test_contract_reflection(
    taste: _MoldTasteTestModule,
) -> None:
    assert taste.required_reflections(DRAFT) == (
        *taste.REFLECTIONS,
        taste.TEST_CONTRACT_REFLECTION,
    )
    assert taste.required_reflections(contract_spec()) == (
        *taste.REFLECTIONS,
        taste.TEST_CONTRACT_REFLECTION,
    )


def test_draft_without_test_contracts_passes_without_a_test_contract_reflection(
    taste: _MoldTasteTestModule,
) -> None:
    result = taste.taste_test(
        DRAFT_WITHOUT_CONTRACTS,
        LEDGER,
        _verdict_with(taste, DRAFT_WITHOUT_CONTRACTS, taste.REFLECTIONS),
    )
    assert not any(gap.endswith(":test-contract") for gap in result.acceptance_gaps)
    assert _without_document_gaps(result.acceptance_gaps) == ()


def test_draft_without_test_contracts_still_owes_the_other_reflections(
    taste: _MoldTasteTestModule,
) -> None:
    result = taste.taste_test(
        DRAFT_WITHOUT_CONTRACTS,
        LEDGER,
        _verdict_with(taste, DRAFT_WITHOUT_CONTRACTS, ("approach",)),
    )
    assert not result.passed
    assert {
        "missing-reflection:F-1:interface",
        "missing-reflection:F-1:acceptance",
        "missing-reflection:F-2:interface",
        "missing-reflection:F-2:acceptance",
    } <= set(result.acceptance_gaps)
    assert not any(gap.endswith(":test-contract") for gap in result.acceptance_gaps)


def test_draft_with_test_contracts_requires_the_test_contract_reflection(
    taste: _MoldTasteTestModule,
) -> None:
    draft = contract_spec().replace(
        "## Acceptance\n",
        "## Approach\nF-1 outer tracer\n\n## Interface sketches\nF-1 outer tracer\n\n## Acceptance\n",
    )
    ledger = [LEDGER[0]]
    payload = _verdict_with(taste, draft, taste.REFLECTIONS)
    payload["forks"] = [cast(list[dict[str, object]], payload["forks"])[0]]
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
    with pytest.raises(taste.TasteTestError):
        _ = taste.taste_test(DRAFT, LEDGER, None)  # pyright: ignore[reportArgumentType]


def test_cli_requires_verdict_file(
    taste: _MoldTasteTestModule, tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    draft = tmp_path / "draft.md"
    ledger = tmp_path / "ledger.json"
    _ = draft.write_text(DRAFT, encoding="utf-8")
    _ = ledger.write_text(json.dumps(LEDGER), encoding="utf-8")
    exit_code = taste.main(["--draft", str(draft), "--ledger", str(ledger)])
    assert exit_code == 2
    envelope = cast(dict[str, object], json.loads(capsys.readouterr().err))
    assert envelope["exit_code"] == 2


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


GOAL = "Users can resume an interrupted session"
GOAL_DRAFT = DRAFT.replace(
    "# Draft\n",
    f"# Draft\n\n## Problem statement\n{GOAL}, without re-authenticating.\n",
    1,
)
GOAL_LEDGER: dict[str, object] = {"goal": GOAL, "forks": LEDGER}


def test_pinned_goal_in_problem_statement_passes(taste: _MoldTasteTestModule) -> None:
    result = taste.taste_test(GOAL_DRAFT, GOAL_LEDGER, verdict(taste, GOAL_DRAFT))
    assert result.passed, result.acceptance_gaps


def test_goal_missing_from_problem_statement_is_goal_drift(
    taste: _MoldTasteTestModule,
) -> None:
    drifted = GOAL_DRAFT.replace(GOAL, "Sessions have a retry policy")
    result = taste.taste_test(drifted, GOAL_LEDGER, verdict(taste, drifted))
    assert not result.passed
    assert result.acceptance_gaps == ("goal-drift",)
    assert not taste.decomposition_gate(result).allowed


def test_goal_without_problem_section_is_a_missing_section(
    taste: _MoldTasteTestModule,
) -> None:
    result = taste.taste_test(DRAFT, GOAL_LEDGER, verdict(taste))
    assert not result.passed
    assert result.acceptance_gaps == ("missing-section:goal:problem",)


def test_goal_less_ledger_skips_the_goal_gate(taste: _MoldTasteTestModule) -> None:
    result = taste.taste_test(DRAFT, {"forks": LEDGER}, verdict(taste))
    assert result.passed, result.acceptance_gaps


def test_blank_goal_is_a_ledger_error(taste: _MoldTasteTestModule) -> None:
    with pytest.raises(taste.TasteTestError, match="ledger-goal-empty"):
        _ = taste.taste_test(DRAFT, {"goal": "  ", "forks": LEDGER}, verdict(taste))


def test_id_keyed_ledger_with_goal_passes(taste: _MoldTasteTestModule) -> None:
    id_keyed_ledger: dict[str, object] = {
        "goal": GOAL,
        "F-1": {"decision": "outer tracer", "status": "settled", "consequential": True},
        "F-2": {"decision": "browser seam", "status": "settled", "consequential": True},
    }
    result = taste.taste_test(GOAL_DRAFT, id_keyed_ledger, verdict(taste, GOAL_DRAFT))
    assert result.passed, result.acceptance_gaps


def test_trailing_goal_heading_does_not_override_problem_statement(
    taste: _MoldTasteTestModule,
) -> None:
    draft = GOAL_DRAFT + "\n## Goal\nsomething else\n"
    result = taste.taste_test(draft, GOAL_LEDGER, verdict(taste, draft))
    assert result.passed, result.acceptance_gaps


def test_reflected_in_problem_alias_is_rejected(taste: _MoldTasteTestModule) -> None:
    bad = verdict(taste)
    forks = cast(list[dict[str, object]], bad["forks"])
    forks[0]["reflected_in"] = ["problem"]
    with pytest.raises(
        taste.TasteTestError, match="fork-invalid-reflection:F-1:problem"
    ):
        _ = taste.taste_test(DRAFT, LEDGER, bad)


def test_goal_match_is_case_and_whitespace_insensitive(
    taste: _MoldTasteTestModule,
) -> None:
    spaced_goal = "Users  can Resume  an interrupted   session"
    draft = GOAL_DRAFT.replace(GOAL, "USERS CAN  resume an INTERRUPTED session")
    ledger: dict[str, object] = {"goal": spaced_goal, "forks": LEDGER}
    result = taste.taste_test(draft, ledger, verdict(taste, draft))
    assert result.passed, result.acceptance_gaps


GOAL_MAPPING_DRAFT: dict[str, object] = {
    "Goal:": f"{GOAL}, without re-authenticating.",
    "Approach": "F-1 outer tracer; F-2 browser seam",
    "Interface sketches": "F-1 outer tracer; F-2 browser seam",
    "Acceptance": "F-1 outer tracer; F-2 browser seam",
    "Test Contracts": "F-1 outer tracer; F-2 browser seam",
}


def test_punctuated_goal_key_in_mapping_draft_is_recognized(
    taste: _MoldTasteTestModule,
) -> None:
    result = taste.taste_test(
        GOAL_MAPPING_DRAFT, GOAL_LEDGER, verdict(taste, GOAL_MAPPING_DRAFT)
    )
    assert result.passed
    assert result.acceptance_gaps == ()


UNDERSCORE_MAPPING_DRAFT: dict[str, object] = {
    **{key: value for key, value in GOAL_MAPPING_DRAFT.items() if key != "Test Contracts"},
    "test_contracts": "F-1 outer tracer; F-2 browser seam",
}


def test_underscore_reflection_key_in_mapping_draft_is_recognized(
    taste: _MoldTasteTestModule,
) -> None:
    result = taste.taste_test(
        UNDERSCORE_MAPPING_DRAFT, GOAL_LEDGER, verdict(taste, UNDERSCORE_MAPPING_DRAFT)
    )
    assert result.acceptance_gaps == ()


def test_goal_alignment_heading_is_not_recognized(
    taste: _MoldTasteTestModule,
) -> None:
    draft = DRAFT.replace(
        "# Draft\n",
        f"# Draft\n\n## Goal alignment\n{GOAL}, without re-authenticating.\n",
        1,
    )
    result = taste.taste_test(draft, GOAL_LEDGER, verdict(taste, draft))
    assert not result.passed
    assert result.acceptance_gaps == ("missing-section:goal:problem",)


def test_third_failed_verdict_halts_after_two_corrections(taste: _MoldTasteTestModule) -> None:
    blocked = verdict(taste)
    blocked["verdict"] = "fail"
    blocked["acceptance_gaps"] = ["named fork needs correction"]
    result = taste.taste_test(DRAFT, LEDGER, blocked)
    assert not taste.decomposition_gate(result, correction_round=0).halted
    assert not taste.decomposition_gate(result, correction_round=1).halted
    final = taste.decomposition_gate(result, correction_round=2)
    assert final.halted and not final.allowed


def _document_problems(taste: _MoldTasteTestModule, spec: str) -> tuple[str, ...]:
    with pytest.raises(taste.ApplicabilityError) as error:
        _ = taste.typed_mold_document(spec)
    return error.value.problems


def test_typed_document_exposes_no_gate_applicability_surface(
    taste: _MoldTasteTestModule,
) -> None:
    for name in (
        "parse_gate_applicability",
        "RedRequired",
        "NotApplicable",
        "TestContract",
        "NOT_APPLICABLE_REFLECTIONS",
        "RED_REQUIRED_EXECUTABLE_PROBLEM",
    ):
        assert not hasattr(taste, name), name


def test_document_consumes_canonical_grounding_rules(
    taste: _MoldTasteTestModule,
) -> None:
    spec = (
        contract_spec()
        + """

## Grounding
| Probe | Outcome | Evidence |
| --- | --- | --- |
| wiki | hit | wiki page |
| wiki | miss | second wiki probe |
"""
    )
    assert any(
        "Grounding table must record the wiki probe exactly once" in problem
        for problem in _document_problems(taste, spec)
    )


def test_present_test_contracts_must_cover_every_acceptance_id(
    taste: _MoldTasteTestModule,
) -> None:
    spec = contract_spec().replace(
        "| AC-2 | public call | existing service boundary | assert empty input is rejected | contract-matrix | v1 | empty<br>non-empty |\n",
        "",
    )
    assert any(
        "Test Contracts table must cover every Acceptance ID exactly once" in problem
        and "missing=['AC-2']" in problem
        for problem in _document_problems(taste, spec)
    )


@pytest.mark.parametrize(
    ("replacement", "problem"),
    [
        (
            "| contract-matrix | | empty<br>non-empty |",
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
    spec = contract_spec().replace(
        "| contract-matrix | v1 | empty<br>non-empty |",
        replacement,
    )
    assert any(problem in item for item in _document_problems(taste, spec))


def test_guard_only_contracts_are_valid_without_a_cut_handoff_rule(
    taste: _MoldTasteTestModule,
) -> None:
    spec = contract_spec().replace(
        "| assert result is returned | tracer | | |",
        "| existing behavior remains byte-identical | guard | | |",
    ).replace(
        "| assert empty input is rejected | contract-matrix | v1 | empty<br>non-empty |",
        "| existing behavior remains byte-identical | guard | | |",
    )
    assert not any(
        "executable" in problem for problem in _document_problems_or_empty(taste, spec)
    )


def _document_problems_or_empty(
    taste: _MoldTasteTestModule, spec: str
) -> tuple[str, ...]:
    try:
        _ = taste.typed_mold_document(spec)
    except taste.ApplicabilityError as error:
        return error.problems
    return ()


def test_contracts_without_stable_acceptance_ids_are_rejected(
    taste: _MoldTasteTestModule,
) -> None:
    spec = contract_spec().replace("- AC-1:", "- first:").replace("- AC-2:", "- second:")
    assert any(
        "acceptance-ids-required" in problem
        for problem in _document_problems(taste, spec)
    )


def test_spec_without_test_contracts_section_has_no_contract_problem(
    taste: _MoldTasteTestModule,
) -> None:
    spec = contract_spec().split("## Test Contracts")[0]
    assert not any(
        "Test Contracts" in problem or "contract-matrix" in problem
        for problem in _document_problems_or_empty(taste, spec)
    )



def test_lexical_precheck_passes_on_reflected_draft(
    taste: _MoldTasteTestModule,
) -> None:
    gaps = taste.lexical_precheck(DRAFT, LEDGER)
    assert gaps == ()


def test_lexical_precheck_names_unreflected_fork_per_section(
    taste: _MoldTasteTestModule,
) -> None:
    draft = DRAFT.replace(
        "## Acceptance\nF-1 outer tracer; F-2 browser seam",
        "## Acceptance\nF-1 outer tracer",
    )
    assert taste.lexical_precheck(draft, LEDGER) == (
        "unreflected-decision:F-2:acceptance",
    )


def test_lexical_precheck_reports_missing_section(
    taste: _MoldTasteTestModule,
) -> None:
    draft = DRAFT.replace("## Interface sketches\n", "")
    assert taste.lexical_precheck(draft, LEDGER) == (
        "missing-section:F-1:interface",
        "missing-section:F-2:interface",
    )


def test_lexical_precheck_matches_fork_id_tag_without_decision_words(
    taste: _MoldTasteTestModule,
) -> None:
    draft = """# Draft

## Approach
F-2 browser seam

## Interface sketches
F-2 browser seam

## Acceptance
AC-1: WHEN x THE SYSTEM SHALL y (F-2)

## Test Contracts
F-2 browser seam
"""
    ledger = [{"id": "F-2", "decision": "browser seam", "status": "settled", "consequential": True}]
    gaps = taste.lexical_precheck(draft, ledger)
    assert gaps == ()


def test_cli_precheck_exits_zero_when_clean_and_one_with_gaps(
    taste: _MoldTasteTestModule, tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    draft = tmp_path / "draft.md"
    ledger = tmp_path / "ledger.json"
    _ = draft.write_text(DRAFT, encoding="utf-8")
    _ = ledger.write_text(json.dumps(LEDGER), encoding="utf-8")
    exit_code = taste.main(["--draft", str(draft), "--ledger", str(ledger), "--precheck"])
    assert exit_code == 0
    captured = capsys.readouterr()
    output = cast(dict[str, object], json.loads(captured.out))
    assert output == {"gaps": []}

    draft_with_gaps = DRAFT.replace(
        "## Interface sketches\n", ""
    )
    _ = draft.write_text(draft_with_gaps, encoding="utf-8")
    exit_code = taste.main(["--draft", str(draft), "--ledger", str(ledger), "--precheck"])
    assert exit_code == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    envelope = cast(dict[str, object], json.loads(captured.err))
    assert envelope["exit_code"] == 1
    message = cast(str, envelope["error"])
    assert "missing-section:F-1:interface" in message
    assert "missing-section:F-2:interface" in message


def test_cli_precheck_and_verdict_are_mutually_exclusive(
    taste: _MoldTasteTestModule, tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    draft = tmp_path / "draft.md"
    ledger = tmp_path / "ledger.json"
    verdict_file = tmp_path / "verdict.json"
    _ = draft.write_text(DRAFT, encoding="utf-8")
    _ = ledger.write_text(json.dumps(LEDGER), encoding="utf-8")
    _ = verdict_file.write_text(json.dumps(verdict(taste)), encoding="utf-8")
    exit_code = taste.main([
        "--draft", str(draft),
        "--ledger", str(ledger),
        "--verdict", str(verdict_file),
        "--precheck"
    ])
    assert exit_code == 2
    envelope = cast(dict[str, object], json.loads(capsys.readouterr().err))
    assert envelope["exit_code"] == 2


COVERAGE_CLAUSES: list[dict[str, str]] = [
    {"id": "G-1", "text": "resume an interrupted session"},
    {"id": "G-2", "text": "without re-authenticating"},
    {"id": "G-3", "text": "across devices"},
    {"id": "G-4", "text": "with an audit log entry"},
]
COVERAGE_LEDGER: dict[str, object] = {
    "goal": GOAL,
    "goal_clauses": COVERAGE_CLAUSES,
    "forks": LEDGER,
}
COVERAGE_DRAFT = GOAL_DRAFT.replace(
    "## Acceptance\nF-1 outer tracer; F-2 browser seam",
    """## Non-goals
- cross-device resume (G-3) [AGENT-INTRODUCED]

## Acceptance
- AC-1: WHEN x THE SYSTEM SHALL y (F-1, G-1)
- AC-2: WHEN x THE SYSTEM SHALL z (F-2, G-2, G-4)""",
    1,
)


def test_goal_coverage_passes_when_every_clause_has_a_disposition(
    taste: _MoldTasteTestModule,
) -> None:
    assert taste.lexical_precheck(COVERAGE_DRAFT, COVERAGE_LEDGER) == ()
    result = taste.taste_test(
        COVERAGE_DRAFT, COVERAGE_LEDGER, verdict(taste, COVERAGE_DRAFT)
    )
    assert result.passed, result.acceptance_gaps


def test_goal_coverage_names_each_uncovered_clause(
    taste: _MoldTasteTestModule,
) -> None:
    draft = COVERAGE_DRAFT.replace(", G-4)", ")")
    assert taste.lexical_precheck(draft, COVERAGE_LEDGER) == ("goal-coverage:G-4",)
    result = taste.taste_test(draft, COVERAGE_LEDGER, verdict(taste, draft))
    assert not result.passed
    assert result.acceptance_gaps == ("goal-coverage:G-4",)
    assert not taste.decomposition_gate(result).allowed


def test_goal_coverage_cap_fails_when_fewer_than_half_ship(
    taste: _MoldTasteTestModule,
) -> None:
    # G-2 and G-4 move to follow-ups: dispositions are explicit, but only 1/4 ships.
    draft = COVERAGE_DRAFT.replace(", G-2, G-4)", ")").replace(
        "## Acceptance\n",
        "## Deferred follow-ups\n- **FU-1** — later (G-2, G-4)\n\n## Acceptance\n",
        1,
    )
    assert taste.lexical_precheck(draft, COVERAGE_LEDGER) == ("goal-coverage-cap:1/4",)


def test_goal_coverage_accepts_exactly_half_shipped_and_reports_dispositions(
    taste: _MoldTasteTestModule,
) -> None:
    draft = COVERAGE_DRAFT.replace(", G-4)", ")").replace(
        "## Acceptance\n",
        "## Open questions\n- [TBD] audit log shape (G-4)\n\n## Acceptance\n",
        1,
    )
    assert taste.lexical_precheck(draft, COVERAGE_LEDGER) == ()
    assert taste.goal_coverage(draft, COVERAGE_LEDGER) == {
        "G-1": "covered",
        "G-2": "covered",
        "G-3": "non-goal",
        "G-4": "tbd",
    }


def test_goal_coverage_tag_does_not_match_a_longer_id(
    taste: _MoldTasteTestModule,
) -> None:
    ledger = {"goal_clauses": [{"id": "G-1", "text": "a"}], "forks": LEDGER}
    draft = DRAFT.replace("## Acceptance\n", "## Acceptance\n- AC-1: x (G-12)\n", 1)
    assert taste.lexical_precheck(draft, ledger) == (
        "goal-coverage:G-1",
        "goal-coverage-cap:0/1",
    )


def test_goal_coverage_skips_when_ledger_has_no_clauses(
    taste: _MoldTasteTestModule,
) -> None:
    assert taste.lexical_precheck(GOAL_DRAFT, GOAL_LEDGER) == ()
    assert taste.goal_coverage(GOAL_DRAFT, GOAL_LEDGER) == {}


def test_cli_coverage_prints_disposition_envelope_and_exits_zero(
    taste: _MoldTasteTestModule, tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    draft = tmp_path / "draft.md"
    ledger = tmp_path / "ledger.json"
    _ = draft.write_text(COVERAGE_DRAFT, encoding="utf-8")
    _ = ledger.write_text(json.dumps(COVERAGE_LEDGER), encoding="utf-8")
    exit_code = taste.main(["--draft", str(draft), "--ledger", str(ledger), "--coverage"])
    assert exit_code == 0
    output = cast(dict[str, object], json.loads(capsys.readouterr().out))
    assert output == {
        "clauses": {
            "G-1": "covered",
            "G-2": "covered",
            "G-3": "non-goal",
            "G-4": "covered",
        },
        "covered": 3,
        "total": 4,
    }


def test_cli_coverage_ignores_a_goal_tag_in_acceptance_prose(
    taste: _MoldTasteTestModule, tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    # G-4 appears only in prose, not on a structured `AC-n:` line: not covered.
    draft_text = COVERAGE_DRAFT.replace(", G-4)", ")").replace(
        "## Acceptance\n",
        "## Acceptance\nThis section defers G-4 to a later spec.\n",
        1,
    )
    draft = tmp_path / "draft.md"
    ledger = tmp_path / "ledger.json"
    _ = draft.write_text(draft_text, encoding="utf-8")
    _ = ledger.write_text(json.dumps(COVERAGE_LEDGER), encoding="utf-8")
    exit_code = taste.main(["--draft", str(draft), "--ledger", str(ledger), "--coverage"])
    assert exit_code == 0
    output = cast(dict[str, object], json.loads(capsys.readouterr().out))
    assert cast(dict[str, str], output["clauses"])["G-4"] == "uncovered"


@pytest.mark.parametrize(
    ("clauses", "problem"),
    [
        ("G-1", "ledger-goal-clauses-invalid"),
        ([{"id": "F-1", "text": "wrong prefix"}], "ledger-goal-clauses-invalid"),
        ([{"id": "G-1", "text": " "}], "ledger-goal-clauses-invalid"),
        (
            [{"id": "G-1", "text": "a"}, {"id": "G-1", "text": "b"}],
            "ledger-duplicate-goal-clause",
        ),
    ],
)
def test_malformed_goal_clauses_are_ledger_errors(
    taste: _MoldTasteTestModule, clauses: object, problem: str
) -> None:
    with pytest.raises(taste.TasteTestError, match=problem):
        _ = taste.lexical_precheck(DRAFT, {"goal_clauses": clauses, "forks": LEDGER})


def test_id_keyed_ledger_ignores_goal_clauses_key(taste: _MoldTasteTestModule) -> None:
    ledger: dict[str, object] = {
        "goal_clauses": [{"id": "G-1", "text": "a"}],
        "F-1": {"decision": "outer tracer", "status": "settled", "consequential": True},
    }
    draft = DRAFT.replace("## Acceptance\n", "## Acceptance\n- AC-1: x (G-1)\n", 1)
    assert taste.lexical_precheck(draft, ledger) == ()
