"""Schema values retained at the direct Mold-to-Cook boundary."""

from __future__ import annotations

import pytest

from easy_cheese_schemas import mold_cook
from easy_cheese_schemas.contracts import (
    PlannerUncertainty,
    UncertaintyScope,
    contract,
)
from easy_cheese_schemas.mold_cook import (
    MOLD_COOK_CONTRACTS,
    CookExecutionHold,
    CookHoldKind,
    CookRequirementKind,
    CookSetupAuthorization,
    CookUnmetRequirement,
    MoldCookCoverage,
    registered_contracts,
)


def test_coverage_preserves_exact_selected_ids_and_remainder() -> None:
    remainder = PlannerUncertainty(
        description="One independent curd remains",
        scope=UncertaintyScope.OMITTED_WORK,
    )
    coverage = MoldCookCoverage(
        curd_ids=["root", "leaf"],
        unresolved_work=[remainder],
    )

    assert coverage.curd_ids == ("root", "leaf")
    assert coverage.unresolved_work == (remainder,)


@pytest.mark.parametrize("curd_ids", [(), ("root", "root")])
def test_coverage_rejects_empty_or_duplicate_selection(
    curd_ids: tuple[str, ...],
) -> None:
    with pytest.raises(ValueError):
        _ = MoldCookCoverage(curd_ids=curd_ids)


@pytest.mark.parametrize("path", ["/tmp/setup.py", "../setup.py"])
def test_setup_authorization_rejects_escaping_paths(path: str) -> None:
    with pytest.raises(ValueError):
        _ = CookSetupAuthorization(
            prerequisite_curd_id="root",
            allowed_paths=(path,),
            allowed_commands=("python -m pytest tests/setup.py",),
        )


@pytest.mark.parametrize(
    ("paths", "commands"),
    [((), ("python -m pytest tests/setup.py",)), (("tests/setup.py",), ())],
)
def test_setup_authorization_requires_paths_and_commands(
    paths: tuple[str, ...], commands: tuple[str, ...]
) -> None:
    with pytest.raises(ValueError):
        _ = CookSetupAuthorization(
            prerequisite_curd_id="root",
            allowed_paths=paths,
            allowed_commands=commands,
        )


def test_setup_authorization_keeps_bounded_command_and_path() -> None:
    value = CookSetupAuthorization(
        prerequisite_curd_id="root",
        allowed_paths=["tests/setup.py"],
        allowed_commands=["python -m pytest tests/setup.py"],
    )
    assert value.prerequisite_curd_id == "root"
    assert value.allowed_paths == ("tests/setup.py",)
    assert value.allowed_commands == ("python -m pytest tests/setup.py",)


def test_hold_and_requirement_keep_distinct_reasons() -> None:
    hold = CookExecutionHold(
        hold_id="user-hold",
        kind=CookHoldKind.USER_INTENT,
        reason="User paused execution",
    )
    requirement = CookUnmetRequirement(
        requirement_id="runner",
        kind=CookRequirementKind.RUNNER,
        description="Runner setup is needed",
    )
    assert hold.kind is CookHoldKind.USER_INTENT
    assert requirement.kind is CookRequirementKind.RUNNER


def test_mold_cook_contracts_is_the_derived_alias() -> None:
    assert MOLD_COOK_CONTRACTS == registered_contracts() == ()


def test_registered_contracts_follow_the_contract_markers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    probe = contract("mold-cook-probe")(type("_ProbeContract", (), {}))
    probe.__module__ = mold_cook.__name__
    monkeypatch.setattr(mold_cook, "_ProbeContract", probe, raising=False)

    assert ("mold-cook-probe", probe) in registered_contracts()
