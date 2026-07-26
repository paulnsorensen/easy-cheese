import pytest

from skill_distill.canonical import validate_family
from skill_distill.contracts import CanonicalCenter, DistillationFamily, RelationKind


def atom(action, *, condition="always"):
    return {"action": action, "object": "run", "condition": condition, "source_span": {"path": "x", "start": 1, "end": 1}}


def family(relation=RelationKind.SHARED_SHELL):
    center = CanonicalCenter("f", (atom("verify"),), {"a": (atom("halt", condition="on failure"),), "b": ()})
    return DistillationFamily("f", relation, ("a", "b"), center)


def test_family_validates_every_member_against_one_center_and_residual():
    originals = {"a": (atom("verify"), atom("halt", condition="on failure")), "b": (atom("verify"),)}
    result = validate_family(family(), originals)
    assert result.eligible
    assert [member.member_id for member in result.members] == ["a", "b"]
    assert all(member.preserved for member in result.members)


def test_family_never_infers_missing_member_transitively():
    with pytest.raises(ValueError, match="member b"):
        validate_family(family(), {"a": (atom("verify"), atom("halt", condition="on failure"))})


def test_only_rewrite_relations_are_eligible_and_shared_shell_residuals_are_explicit():
    originals = {"a": (atom("verify"), atom("halt", condition="on failure")), "b": (atom("verify"),)}
    with pytest.raises(ValueError, match="relation"):
        validate_family(family(RelationKind.CONFLICT), originals)
    broken = DistillationFamily("f", RelationKind.SHARED_SHELL, ("a", "b"), CanonicalCenter("f", (atom("verify"),), {"a": ()}))
    with pytest.raises(ValueError, match="explicit residual"):
        validate_family(broken, originals)
