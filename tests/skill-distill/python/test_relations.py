import pytest

from skill_distill.relations import (
    RelationKind,
    eligible_for_rewrite,
    parse_relation,
)


def test_only_the_seven_approved_relations_validate():
    assert {parse_relation(relation).value for relation in RelationKind} == {
        "equivalent", "left-subsumes-right", "right-subsumes-left", "shared-shell",
        "conflict", "unrelated", "insufficient-evidence",
    }
    with pytest.raises(ValueError, match="unsupported semantic relation"):
        parse_relation("near-duplicate")


@pytest.mark.parametrize(
    "relation", [
        RelationKind.LEFT_SUBSUMES_RIGHT,
        RelationKind.RIGHT_SUBSUMES_LEFT,
        RelationKind.CONFLICT,
        RelationKind.UNRELATED,
        RelationKind.INSUFFICIENT_EVIDENCE,
    ],
)
def test_noneligible_relations_cannot_form_rewrite_families(relation):
    eligibility = eligible_for_rewrite("pair-1", relation, complete=True)

    assert not eligibility.eligible
    with pytest.raises(ValueError, match="cannot form a rewrite family"):
        eligibility.require_eligible()


def test_eligible_relation_still_requires_a_complete_reconciliation():
    assert not eligible_for_rewrite("pair-1", RelationKind.EQUIVALENT, complete=False).eligible
