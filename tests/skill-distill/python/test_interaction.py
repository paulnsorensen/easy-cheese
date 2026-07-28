from skill_distill.interaction import gate_interactions


def test_cross_family_gate_passes_without_bisect_when_combination_passes():
    calls = []
    result = gate_interactions(("a", "b"), lambda families: calls.append(families) or True)
    assert result.passed
    assert result.failing_families == ()
    assert calls == [("a", "b")]


def test_cross_family_failure_is_bisected_to_minimal_interaction():
    def gate(families):
        return not {"b", "d"}.issubset(families)

    result = gate_interactions(("a", "b", "c", "d"), gate)
    assert not result.passed
    assert result.failing_families == ("b", "d")
