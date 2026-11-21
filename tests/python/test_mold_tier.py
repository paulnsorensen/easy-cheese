"""Behavior of `mold.pyz tier`, which picks the Mold tier from Bounds-pass facts."""

from __future__ import annotations

import json
from typing import cast

import pytest

from easy_cheese.skills.mold import commands


def _tier(capsys: pytest.CaptureFixture[str], *args: str) -> dict[str, object]:
    assert commands.main(["tier", *args]) == 0
    return cast(dict[str, object], json.loads(capsys.readouterr().out))


def test_public_api_rename_is_not_quick(capsys: pytest.CaptureFixture[str]) -> None:
    # The baseline mold-leverage-2 run named the contract trigger and still took Quick.
    out = _tier(capsys, "--verdict", "low", "--trigger", "contract")
    assert out["tier"] == "light"
    assert out["line"] == "tier: light (fired leverage trigger: contract)"


def test_clear_private_change_is_quick(capsys: pytest.CaptureFixture[str]) -> None:
    assert _tier(capsys, "--verdict", "skipped")["tier"] == "quick"


@pytest.mark.parametrize(
    "args,reason",
    [
        (("--verdict", "high"), "shape-check verdict high"),
        (("--verdict", "unknown"), "shape-check verdict unknown"),
        (("--verdict", "low", "--forks", "3"), "3 consequential forks"),
        (("--verdict", "low", "--curds", "2"), "2 expected curds"),
        (("--verdict", "low", "--public-seam"), "new cross-module public seam"),
        (("--verdict", "low", "--diagnose"), "Diagnose input"),
    ],
)
def test_full_rows(
    capsys: pytest.CaptureFixture[str], args: tuple[str, ...], reason: str
) -> None:
    out = _tier(capsys, *args, "--trigger", "auth")
    assert out["tier"] == "full"
    assert out["reasons"] == [reason]


@pytest.mark.parametrize(
    "args", [("--verdict", "medium"), ("--verdict", "low", "--forks", "2")]
)
def test_light_rows_without_a_trigger(
    capsys: pytest.CaptureFixture[str], args: tuple[str, ...]
) -> None:
    assert _tier(capsys, *args)["tier"] == "light"


def test_each_fired_trigger_is_a_reason_once(capsys: pytest.CaptureFixture[str]) -> None:
    out = _tier(
        capsys, "--verdict", "low", "--trigger", "auth", "--trigger", "contract",
        "--trigger", "auth",
    )
    assert out["reasons"] == ["fired leverage trigger: auth", "fired leverage trigger: contract"]


@pytest.mark.parametrize(
    "args",
    [
        ("--verdict", "low", "--trigger", "public-api"),
        ("--verdict", "tiny"),
        ("--verdict", "low", "--forks", "-1"),
        (),
    ],
)
def test_bad_input_exits_nonzero(
    capsys: pytest.CaptureFixture[str], args: tuple[str, ...]
) -> None:
    assert commands.main(["tier", *args]) != 0
    assert capsys.readouterr().out == ""
