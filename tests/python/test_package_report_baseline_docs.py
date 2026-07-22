"""Content-contract tests for package-report.md's collateral-repair and
baseline/honesty conventions (curd 3, spec baseline-quality-gate).

Each assertion targets a regression that would let a cook silently claim
green while baseline failures or unrecorded collateral repairs exist.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "skills" / "cook" / "references" / "package-report.md"


def read() -> str:
    return REPORT.read_text(encoding="utf-8")


def test_files_changed_records_collateral_repair_with_reason_and_policy_link() -> None:
    body = read()
    files_changed = body.split("### Files changed", 1)[1].split("### Tests", 1)[0]
    assert "collateral repair: <one-line reason>" in files_changed
    # The convention must tie back to the three-way policy that authorizes
    # collateral repairs outside the cooked contract, not stand alone.
    assert "quality-gates.md" in files_changed
    assert "three-way policy" in files_changed


def test_baseline_section_exists_between_risks_and_self_eval_and_links_policy() -> None:
    body = read()
    risks = body.index("### Risks")
    baseline = body.index("### Baseline")
    self_eval = body.index("### Self-eval")
    assert risks < baseline < self_eval

    baseline_section = body[baseline:self_eval]
    assert "identical to baseline" in baseline_section
    assert "outside the cooked contract" in baseline_section
    assert "not fixed" in baseline_section
    assert "quality-gates.md" in baseline_section


def test_self_eval_does_not_force_a_false_green_claim_on_recorded_baseline() -> None:
    body = read()
    self_eval = body.split("### Self-eval", 1)[1].split("### Next step", 1)[0]
    assert "Quality gates pass" in self_eval
    # A cook with recorded baseline failures must have an honest escape
    # hatch from the checklist instead of ticking a box that's a lie.
    assert "recorded baseline failure" in self_eval
    assert "Baseline section" in self_eval


def test_honesty_rules_require_stating_suite_not_green_when_baseline_recorded() -> None:
    body = read()
    honesty = body.split("## Honesty rules", 1)[1].split("## Stop conditions", 1)[0]
    assert "Baseline section lists any recorded failures" in honesty
    assert "not green" in honesty
    assert "lists those failures" in honesty


def test_stop_conditions_exempt_identical_baseline_failures() -> None:
    body = read()
    stop_conditions = body.split("## Stop conditions", 1)[1]
    assert "identical-to-baseline failures are recorded, not a stop condition" in stop_conditions
    assert "quality-gates.md" in stop_conditions