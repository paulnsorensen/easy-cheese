"""Strong documentation contracts for the tests-only Press gate."""

from __future__ import annotations

import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src" / "fanout"))

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL = REPO_ROOT / "skills" / "press" / "SKILL.md"
GAPS = REPO_ROOT / "skills" / "press" / "references" / "gap-analysis.md"


def _body(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    return parts[2] if len(parts) == 3 and parts[0].strip() == "" else text


def _flat(path: Path) -> str:
    return " ".join(_body(path).split())


def test_press_is_tests_only_and_exposes_the_locked_callable() -> None:
    text = _flat(SKILL)
    assert "press(spec_ref, original_receipt)" in text
    assert 'Continue("press-corrective-cook")' in text
    assert 'Dispatch("/age")' in text
    assert "Stop(gated_evidence)" in text
    assert "never edits production code" in text
    assert "never owns first coverage" in text


def test_entry_replays_green_and_protects_oracle_before_attack() -> None:
    text = _flat(SKILL)
    replay = text.index("red-gate validate <receipt> --state green")
    digest = text.index("Verify every protected oracle digest", replay)
    attack = text.index("## Adversarial loop")
    assert replay < digest < attack
    assert "That token freezes all non-production oracle dependencies" in text
    assert "post-Cook resume" in text


def test_press_evidence_is_canonical_and_fully_chained() -> None:
    text = _flat(SKILL)
    assert "red-gate issue" in text
    assert "producer: press" in text
    assert "guards the original Cut receipt" in text
    assert "every prior Press receipt" in text
    assert "failing test and its digest remain unchanged" in text
    assert "raw or hand-written `GateReceipt`" in text
    assert "invalid, stale, unchained" in text.lower()


def test_press_repair_is_fresh_identical_and_exactly_two_cycles() -> None:
    text = _flat(SKILL)
    assert "fresh bounded Cook" in text
    assert "identical attack" in text
    assert "same attack/test digest" in text
    assert "P1 has `completed_cycles=0`" in text
    assert (
        "Caller-supplied `repair_cycles`, `completed_cycles`, or "
        "`production_changed` fields are forbidden"
    ) in text
    assert "A phase token is consumed by exactly one route decision" in text
    assert "P3 has `completed_cycles=2`" in text
    assert 'Stop("third-red", gated_evidence=True)' in text
    assert "no global `dispatch: /cook` action" in text


def test_press_p1_p2_p3_paths_are_attempt_qualified_and_forward_receipts() -> None:
    text = _flat(SKILL)
    table_start = text.index("| Press attempt |")
    table_end = text.index("For each row", table_start)
    table = text[table_start:table_end]
    previous = -1
    for attempt in range(1, 4):
        paths = (
            f".cheese/press/<slug>.attempt-{attempt}.plan.json",
            f".cheese/press/<slug>.attempt-{attempt}.phase.json",
            f".cheese/press/candidates/<slug>.attempt-{attempt}.json",
            f".cheese/press/<slug>.attempt-{attempt}.json",
            f".cheese/press/<slug>.attempt-{attempt}.route.json",
        )
        for path in paths:
            position = table.index(path)
            assert position > previous
            previous = position
    assert "For RED, set `current_receipt` to the new receipt from that row" in text
    assert "P1 uses the original Cut receipt, P2 uses P1, and P3 uses P2" in text
    assert "Never point a GREEN route at the unissued receipt path" in text
    assert "do not create P4 names or overwrite any earlier path" in text


def test_only_green_reaches_age_and_baseline_readiness_survives() -> None:
    text = _flat(SKILL)
    assert 'Dispatch("/age")' in text
    assert 'only a GREEN `Dispatch("/age")` reaches the global Age route' in text
    assert "baseline-aware readiness behavior" in text
    assert "same test and signature" in text
    assert "new or changed failures remain blocking" in text.lower()


def test_third_red_output_is_terminal_not_auto_runnable() -> None:
    text = _flat(SKILL)
    assert (
        '| `Stop("third-red", gated_evidence=True)` | `ok` | `done` | `stop` |' in text
    )
    assert "`next: done` is terminal and never auto-dispatches" in text


def test_gap_analysis_records_press_ownership_and_derives_the_repair_bound() -> None:
    text = _flat(GAPS)
    assert "Press is not a second first-coverage phase" in text
    assert "Cut/Cook own first coverage" in text
    assert "Do not manufacture one hardening test per changed behavior" in text
    assert "producer: press" in text
    assert "every prior Press receipt" in text
    assert "request cannot provide a repair counter" in text
    assert "current_receipt" in text
    assert "symlinked" in text
    assert "cross-work/spec/project" in text
    assert "`completed_cycles=0` or `1`" in text
    assert "`completed_cycles=2`" in text
    assert "before issuing another receipt" in text
    assert "global Cook dispatch" in text
