"""PrPlan: src/fanout/validate_pr_plan.py vs easy_cheese_schemas.PrPlan.

The two sides agree on every case in this table -- including the shape rules
(`single` means one group, `orthogonal_flat` means every group is based off
main) and the duplicate-branch rule, which the types now carry. `branch` and
`base` reach a shell emitter uninterpolated, so the charset cases are the ones
that matter most if either side ever loosens.
"""

from __future__ import annotations

import pytest
from easy_cheese_schemas import PrPlan, load
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
    agreed_valid(
        "stacked_linear with a real dependency",
        plan(
            shape="stacked_linear",
            groups=[
                pr_group("ultracook/feature/pr-1"),
                {
                    "branch": "ultracook/feature/pr-2",
                    "title": "feat: pr-2",
                    "base": "ultracook/feature/pr-1",
                    "commits": ["abc1234"],
                    "depends_on": ["ultracook/feature/pr-1"],
                },
            ],
        ),
    ),
    agreed_invalid(
        "depends_on names a branch outside the plan",
        plan(
            shape="stacked_linear",
            groups=[
                {
                    "branch": "ultracook/feature/pr-1",
                    "title": "feat: pr-1",
                    "base": "main",
                    "commits": ["abc1234"],
                    "depends_on": ["ghost"],
                }
            ],
        ),
    ),
    agreed_invalid(
        "group depends on itself",
        plan(
            shape="stacked_linear",
            groups=[
                {
                    "branch": "ultracook/feature/pr-1",
                    "title": "feat: pr-1",
                    "base": "main",
                    "commits": ["abc1234"],
                    "depends_on": ["ultracook/feature/pr-1"],
                }
            ],
        ),
    ),
    agreed_invalid(
        "two groups form a dependency cycle",
        plan(
            shape="stacked_linear",
            groups=[
                {
                    "branch": "ultracook/feature/pr-1",
                    "title": "feat: pr-1",
                    "base": "main",
                    "commits": ["abc1234"],
                    "depends_on": ["ultracook/feature/pr-2"],
                },
                {
                    "branch": "ultracook/feature/pr-2",
                    "title": "feat: pr-2",
                    "base": "main",
                    "commits": ["abc1234"],
                    "depends_on": ["ultracook/feature/pr-1"],
                },
            ],
        ),
    ),
    agreed_invalid(
        "base names neither target_branch nor a plan branch",
        plan(
            shape="stacked_linear",
            groups=[
                {
                    "branch": "ultracook/feature/pr-1",
                    "title": "feat: pr-1",
                    "base": "ghost",
                    "commits": ["abc1234"],
                    "depends_on": [],
                }
            ],
        ),
    ),
    agreed_invalid(
        "three groups form a dependency cycle",
        plan(
            shape="stacked_linear",
            groups=[
                {"branch": "a", "title": "feat: a", "base": "main", "commits": ["abc1234"], "depends_on": ["b"]},
                {"branch": "b", "title": "feat: b", "base": "main", "commits": ["abc1234"], "depends_on": ["c"]},
                {"branch": "c", "title": "feat: c", "base": "main", "commits": ["abc1234"], "depends_on": ["a"]},
            ],
        ),
    ),
    agreed_invalid("branch starting with a dash", group(branch="-delete-everything")),
    agreed_invalid("base starting with a dash", group(base="-f")),
    agreed_valid(
        "orthogonal_flat groups branch off a non-main target_branch",
        plan(
            shape="orthogonal_flat",
            target_branch="develop",
            groups=[
                {"branch": "a", "title": "feat: a", "base": "develop", "commits": ["abc1234"], "depends_on": []},
                {"branch": "b", "title": "feat: b", "base": "develop", "commits": ["abc1234"], "depends_on": []},
            ],
        ),
    ),
    agreed_invalid(
        "orthogonal_flat group off main when target_branch is develop",
        plan(
            shape="orthogonal_flat",
            target_branch="develop",
            groups=[
                {"branch": "a", "title": "feat: a", "base": "develop", "commits": ["abc1234"], "depends_on": []},
                {"branch": "b", "title": "feat: b", "base": "main", "commits": ["abc1234"], "depends_on": []},
            ],
        ),
    ),
    agreed_valid(
        "non-main target_branch names a valid base",
        plan(
            shape="stacked_linear",
            target_branch="develop",
            groups=[
                {"branch": "a", "title": "feat: a", "base": "develop", "commits": ["abc1234"], "depends_on": []},
            ],
        ),
    ),
]


def test_charset_invalid_base_surfaces_the_git_ref_error() -> None:
    """The topology validator skips a charset-invalid base so PrGroup's own
    git-ref rejection -- the shell-injection guard -- is what surfaces."""
    problems = list(load(group(base="main\nrm -rf /"), PrPlan, strict=True).problems)
    assert any("base contains characters unsafe for a git ref" in problem for problem in problems)
    assert not any("must name target_branch" in problem for problem in problems)


def test_divergence_table_is_honest() -> None:
    assert_table_is_honest(CASES)


@pytest.mark.parametrize("case", agreeing(CASES), ids=ids(agreeing(CASES)))
def test_validator_and_type_agree(case: Case, pr_plan_validator: Validator) -> None:
    assert_conforms(case, pr_plan_validator, PrPlan)


def test_target_branch_defaults_to_main() -> None:
    """AC-3: a plan that omits target_branch defaults it to main."""
    loaded = load(pr_plan(), PrPlan, strict=True)
    assert loaded.value is not None
    assert loaded.value.target_branch == "main"


def test_no_known_divergence_remains() -> None:
    """Asserted rather than left to the empty-parameter skip below, so a
    divergence that opens later has to be added to the table deliberately."""
    assert divergent(CASES) == []


@pytest.mark.parametrize("case", divergent(CASES), ids=ids(divergent(CASES)))
def test_known_divergence_still_holds(case: Case, pr_plan_validator: Validator) -> None:
    assert_conforms(case, pr_plan_validator, PrPlan)