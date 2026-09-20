"""PR plan types: how a finished run becomes pull requests.

The plan is consumed by shell emitters that interpolate `branch` and `base`
RAW into git commands, so those two fields are charset-gated at the type
boundary rather than at each call site -- an unvalidated ref reaching the
emitter is a shell-injection seam, not a cosmetic problem. Retired the
contract src/fanout/validate_pr_plan.py used to enforce independently --
that validator now delegates here via `easy_cheese_schemas.compat.load`.
"""

from __future__ import annotations

import re
import sys
from enum import Enum
from typing import Protocol, cast

from attrs import define, field, validators

from easy_cheese_schemas.contracts import ContractVersion, contract, marked_contracts_in


class _NamedAttribute(Protocol):
    name: str


# A leading `-` makes the ref option-shaped: `git checkout -b '-x' main` still
# reaches git as a flag, since shell quoting does not stop option parsing.
# The lookaheads reject the other `git check-ref-format` violations that a
# shell emitter would otherwise hit late: a leading or trailing `/`, `//`,
# `..`, and a trailing `.`. `_git_ref` checks each path component for a
# leading `.` and a `.lock` suffix, because git applies both per component.
BRANCH_RE = re.compile(
    r"^(?!-)(?!/)(?!.*\.\.)(?!.*//)(?!.*/$)(?!.*\.$)[A-Za-z0-9._/-]+$"
)
# 7 is git's default short-SHA floor (`core.abbrev`); shorter values risk
# colliding with a branch or tag of the same name, since git resolves refs
# before SHA prefixes. Full SHA-1 is 40 hex chars.
COMMIT_SHA_RE = re.compile(r"^[0-9a-fA-F]{7,40}$")

__all__ = ["PrGroup", "PrPlan", "PrShape"]


class PrShape(str, Enum):
    """Topology of the PR set a run publishes."""

    SINGLE = "single"
    ORTHOGONAL_FLAT = "orthogonal_flat"
    STACKED_LINEAR = "stacked_linear"
    DIAMOND_STACK = "diamond_stack"


def _non_empty_string(_instance: object, attribute: _NamedAttribute, value: object) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{attribute.name} must be a non-empty string")


def _string_list(_instance: object, attribute: _NamedAttribute, value: object) -> None:
    if not isinstance(value, list):
        raise ValueError(f"{attribute.name} must be a list")
    items = cast("list[object]", value)
    for index, item in enumerate(items, start=1):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{attribute.name}[{index}] must be a non-empty string")


def _non_empty_list(_instance: object, attribute: _NamedAttribute, value: object) -> None:
    if not value:
        raise ValueError(f"{attribute.name} must be a non-empty list")


def _is_git_ref(value: object) -> bool:
    """Return True when ``value`` is a branch name git accepts.

    A path component that starts with `.` or ends with `.lock` is a
    `check-ref-format` violation the regex does not cover, since git applies
    both rules to every component, not only to the whole ref.
    """
    return (
        isinstance(value, str)
        and BRANCH_RE.match(value) is not None
        and not any(
            part.startswith(".") or part.endswith(".lock") for part in value.split("/")
        )
    )


def _git_ref(_instance: object, attribute: _NamedAttribute, value: object) -> None:
    if not _is_git_ref(value):
        raise ValueError(f"{attribute.name} contains characters unsafe for a git ref")


def _commit_shas(_instance: object, attribute: _NamedAttribute, value: object) -> None:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{attribute.name} must be a non-empty list")
    commits = cast("list[object]", value)
    for index, commit in enumerate(commits, start=1):
        if not isinstance(commit, str) or COMMIT_SHA_RE.match(commit) is None:
            raise ValueError(
                f"{attribute.name}[{index}] must be a hex SHA (7-40 hex chars); " + f"got {commit!r}"
            )


def _distinct_branches(
    _instance: object, attribute: _NamedAttribute, groups: list[PrGroup]
) -> None:
    """Two groups claiming one branch would race the same ref."""
    seen: set[str] = set()
    for group in groups:
        if group.branch in seen:
            raise ValueError(
                f"{attribute.name} must be branch-distinct: {group.branch!r} is "
                + "claimed by two groups -- the two pull requests would race the "
                + "same ref"
            )
        seen.add(group.branch)


def _matches_shape(
    instance: PrPlan, attribute: _NamedAttribute, groups: list[PrGroup]
) -> None:
    """The shape constrains the group set, so the rule lives on the field it
    reads. It is a field validator rather than an `__attrs_post_init__` check
    because `load` disables validators while structuring and re-runs them
    afterwards; a rule that raised from `__init__` would truncate the problem
    list to itself."""
    if instance.shape is PrShape.SINGLE and len(groups) != 1:
        raise ValueError(
            f"{attribute.name} must be exactly one group for the single shape, "
            + f"not {len(groups)}"
        )
    if instance.shape is PrShape.ORTHOGONAL_FLAT:
        for index, group in enumerate(groups, start=1):
            if group.base != instance.target_branch:
                raise ValueError(
                    f"{attribute.name}[{index}].base must be "
                    + f"{instance.target_branch} for orthogonal_flat"
                )


def _default_depends_on(value: list[str] | None) -> list[str]:
    return value if value is not None else []


@define(frozen=True)
class PrGroup:
    """One pull request: a branch, its base, and the commits it carries."""

    branch: str = field(validator=[_non_empty_string, _git_ref])
    title: str = field(validator=_non_empty_string)
    base: str = field(validator=[_non_empty_string, _git_ref])
    commits: list[str] = field(validator=_commit_shas)
    # Body may be empty -- `gh pr create --body ''` is valid -- so only the
    # type is constrained; the emitter calls `.replace()` on it.
    body: str | None = None
    # The old dict-validator treated an explicit `depends_on: null` the same as
    # an absent key -- both mean "no dependencies" -- so the field accepts
    # `None` and normalizes it before the list-shape validator ever sees it.
    depends_on: list[str] | None = field(
        default=None,
        converter=_default_depends_on,
        validator=_string_list,
    )


def _validate_topology(
    instance: PrPlan, attribute: _NamedAttribute, groups: list[PrGroup]
) -> None:
    """Every dependency and base names a plan branch or the target branch, no
    group depends on itself, and the dependency graph is acyclic."""
    branches = {group.branch for group in groups}
    valid_targets = branches | {instance.target_branch}
    for group in groups:
        # A charset-invalid base is a shell-injection seam that PrGroup's own
        # git-ref validator reports; skip only the membership check for it, so
        # the group's `depends_on` entries are still checked.
        base_is_safe = _is_git_ref(group.base)
        if base_is_safe and group.base not in valid_targets:
            raise ValueError(
                f"{attribute.name}: group {group.branch!r} base {group.base!r} "
                + "must name target_branch or a plan branch"
            )
        for dep in group.depends_on or []:
            if dep == group.branch:
                raise ValueError(
                    f"{attribute.name}: group {group.branch!r} depends_on "
                    + f"{dep!r} is a self-dependency"
                )
            if dep not in valid_targets:
                raise ValueError(
                    f"{attribute.name}: group {group.branch!r} depends_on "
                    + f"{dep!r} does not name target_branch or a plan branch"
                )
    _reject_cycles(attribute.name, groups)


def _reject_cycles(field_name: str, groups: list[PrGroup]) -> None:
    # A base edge is a topology dependency too: a group cannot land before its
    # own base, so a base-only cycle (a based on b, b based on a) is just as
    # non-executable as a depends_on cycle. The edge exists whenever the base
    # names a plan branch, so a group named like the target branch still joins
    # the walk.
    branches = {group.branch for group in groups}
    edges: dict[str, list[tuple[str, str]]] = {}
    for group in groups:
        entries = [
            (dep, "depends_on") for dep in (group.depends_on or []) if dep != group.branch
        ]
        if group.base in branches:
            entries.append((group.base, "is based on"))
        edges[group.branch] = entries
    state: dict[str, int] = {}

    def visit(node: str) -> None:
        state[node] = 1
        for dep, verb in edges[node]:
            if dep not in branches:
                continue
            if state.get(dep) == 1:
                raise ValueError(
                    f"{field_name}: group {node!r} {verb} {dep!r} forms a cycle"
                )
            if state.get(dep) != 2:
                visit(dep)
        state[node] = 2

    for branch in branches:
        if state.get(branch) is None:
            visit(branch)


@contract("pr-plan")
@define(frozen=True)
class PrPlan:
    """The full publish plan: one shape, at least one group."""

    contract_version: ContractVersion = field(
        validator=validators.instance_of(ContractVersion)
    )
    shape: PrShape
    target_branch: str = field(
        default="main", kw_only=True, validator=[_non_empty_string, _git_ref]
    )
    groups: list[PrGroup] = field(
        validator=[_non_empty_list, _distinct_branches, _matches_shape, _validate_topology],
        metadata={"min_items": 1},
    )


def registered_contracts() -> tuple[tuple[str, type], ...]:
    """Return marked contract classes in ``pr_plan.py`` in slug order."""
    return marked_contracts_in(sys.modules[__name__])