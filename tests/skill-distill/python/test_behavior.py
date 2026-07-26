import pytest

from skill_distill.behavior import evaluate_behavior
from skill_distill.contracts import BehaviorScorecard


def rows(matrix, subject, scenario, critical_pass=True, noncritical_passes=9):
    result = []
    for repetition in range(1, 4):
        for phrasing in ("a", "b", "c"):
            result.append(BehaviorScorecard(matrix, subject, scenario, phrasing, repetition, "critical", True, True, critical_pass, critical_pass))
    for index in range(9):
        passed = index < noncritical_passes
        result.append(BehaviorScorecard(matrix, subject, scenario, f"n{index % 3}", index // 3 + 1, "noncritical", False, True, passed, passed))
    return result


def test_critical_obligations_allow_zero_distortion():
    originals = rows("o1", "original-1", "route") + rows("o2", "original-2", "route")
    result = evaluate_behavior(originals, rows("v", "variant", "route", critical_pass=False))
    assert not result.passed
    assert result.scenarios[0].critical_distortions == 9


def test_noncritical_degradation_is_bounded_by_self_variance_capped_at_five_points():
    originals = rows("o1", "original-1", "route", noncritical_passes=9) + rows("o2", "original-2", "route", noncritical_passes=8)
    result = evaluate_behavior(originals, rows("v", "variant", "route", noncritical_passes=8))
    assert not result.passed
    assert result.scenarios[0].allowed_degradation == 0.05


def test_fixture_without_noncritical_assertions_runs_only_critical_gate():
    originals = [row for row in rows("o1", "original-1", "route") + rows("o2", "original-2", "route") if row.critical]
    variant = [row for row in rows("v", "variant", "route") if row.critical]
    result = evaluate_behavior(originals, variant)
    assert result.passed
    assert result.scenarios[0].noncritical_rate is None


def test_variant_cannot_omit_an_original_obligation():
    originals = rows("o1", "original-1", "route") + rows("o2", "original-2", "route")
    variant = [row for row in rows("v", "variant", "route") if row.obligation_id != "critical"]
    with pytest.raises(ValueError, match="obligation signatures differ"):
        evaluate_behavior(originals, variant)


def test_variant_cannot_reclassify_an_original_obligation_as_noncritical():
    originals = rows("o1", "original-1", "route") + rows("o2", "original-2", "route")
    variant = [
        BehaviorScorecard(
            row.matrix_id,
            row.subject,
            row.scenario,
            row.phrasing,
            row.repetition,
            row.obligation_id,
            False if row.obligation_id == "critical" else row.critical,
            row.expected,
            row.observed,
            row.passed,
        )
        for row in rows("v", "variant", "route")
    ]
    with pytest.raises(ValueError, match="obligation signatures differ"):
        evaluate_behavior(originals, variant)
