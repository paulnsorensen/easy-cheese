"""PrPlan: src/fanout/validate_pr_plan.py vs easy_cheese_schemas.PrPlan.

The two sides agree on every case in this table -- including the shape rules
(`single` means one group, `orthogonal_flat` means every group is based off
main) and the duplicate-branch rule, which the types now carry. `branch` and
`base` reach a shell emitter uninterpolated, so the charset cases are the ones
that matter most if either side ever loosens.
"""

from __future__ import annotations

import pytest
from easy_cheese_schemas import PrPlan
from schema_conformance import (
    Case,
    Validator,
    agreed_invalid,
    agreed_valid,
    agreeing,
    as_dict,
    as_list,
    assert_conforms,
    assert_table_is_honest,
    divergent,
    ids,
    pr_group,
    pr_plan,
)


def plan(**fields: object) -> dict[str, object]:
    payload = pr_plan()
    payload.update(fields)
    return payload


def group(**fields: object) -> dict[str, object]:
    payload = pr_plan()
    as_dict(as_list(payload["groups"])[0]).update(fields)
    return payload


def group_without(key: str) -> dict[str, object]:
    payload = pr_plan()
    del as_dict(as_list(payload["groups"])[0])[key]
    return payload


CASES: list[Case] = [
    agreed_valid("valid single plan", pr_plan()),
    agreed_valid("depends_on omitted", group_without("depends_on")),
    agreed_invalid("unknown shape", plan(shape="pyramid")),
    agreed_invalid("branch with unsafe charset", group(branch="feat;rm -rf /")),
    agreed_invalid("base with unsafe charset", group(base="main;echo")),
    agreed_invalid("commit sha below the short-SHA floor", group(commits=["abc"])),
    agreed_invalid("empty groups", plan(groups=[])),
    agreed_invalid("commits as a bare string", group(commits="abc1234")),
    agreed_invalid("body as an int", group(body=7)),
    agreed_invalid("depends_on as a bare string", group(depends_on="pr-1")),
    agreed_invalid(
        "single shape with two groups",
        plan(groups=[pr_group("ultracook/feature/pr-1"), pr_group("ultracook/feature/pr-2")]),
    ),
    agreed_invalid(
        "duplicate branch across groups",
        plan(
            shape="orthogonal_flat",
            groups=[pr_group("ultracook/feature/pr-1"), pr_group("ultracook/feature/pr-1")],
        ),
    ),
    agreed_invalid(
        "orthogonal_flat group based off another PR",
        plan(
            shape="orthogonal_flat",
            groups=[
                pr_group("ultracook/feature/pr-1"),
                pr_group("ultracook/feature/pr-2", base="ultracook/feature/pr-1"),
            ],
        ),
    ),
]


def test_divergence_table_is_honest() -> None:
    assert_table_is_honest(CASES)


@pytest.mark.parametrize("case", agreeing(CASES), ids=ids(agreeing(CASES)))
def test_validator_and_type_agree(case: Case, pr_plan_validator: Validator) -> None:
    assert_conforms(case, pr_plan_validator, PrPlan)


def test_no_known_divergence_remains() -> None:
    """Asserted rather than left to the empty-parameter skip below, so a
    divergence that opens later has to be added to the table deliberately."""
    assert divergent(CASES) == []


@pytest.mark.parametrize("case", divergent(CASES), ids=ids(divergent(CASES)))
def test_known_divergence_still_holds(case: Case, pr_plan_validator: Validator) -> None:
    assert_conforms(case, pr_plan_validator, PrPlan)