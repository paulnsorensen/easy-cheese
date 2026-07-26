from skill_distill.mutations import deterministic_mutations


def test_mutations_are_deterministic_and_each_changes_one_obligation():
    atoms = ({"action": "write", "object": "artifact", "condition": "after gate", "polarity": "required", "order": 1},)
    first = deterministic_mutations(atoms)
    second = deterministic_mutations(atoms)
    assert first == second
    assert [case.kind for case in first] == ["drop", "polarity", "condition", "order"]
    assert all(case.obligations != atoms for case in first)
