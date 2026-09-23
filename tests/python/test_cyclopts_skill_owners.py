"""Smoke tests for migrated skill-owner Cyclopts entry points."""

from __future__ import annotations
# pyright: reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownMemberType=false, reportUnknownVariableType=false

import pytest

from easy_cheese.skills.cook import contract_handlers as cook
from easy_cheese.skills.hard_cheese import rank_hunks
from easy_cheese.skills.melt import batch_resolve, detect_squash_residue
from easy_cheese.skills.mold import contract_handlers as mold
from easy_cheese.skills.mold import review


@pytest.mark.parametrize(
    ("main", "args", "marker"),
    [
        (mold.main, ["--help"], "SPEC"),
        (mold.normalize_planner_main, ["--help"], "WRITER"),
        (cook.prepare_main, ["--help"], "SOURCE"),
        (cook.resubmit_main, ["--help"], "PREVIOUS"),
        (review.serve_main, ["--help"], "STATE-DIR"),
        (rank_hunks.main, ["--help"], "BASE"),
        (batch_resolve.main, ["--help"], "APPLY"),
        (detect_squash_residue.main, ["--help"], "BASE"),
    ],
)
def test_cyclopts_owner_help_is_available(main, args, marker, capsys) -> None:
    assert main(args) == 0
    captured = capsys.readouterr()
    assert marker in captured.out
    assert captured.err == ""


def test_cook_resubmit_exposes_repeatable_clear_hold_option(capsys) -> None:
    # Cyclopts must expose list options as repeatable flags, not one opaque value.
    assert cook.resubmit_main(["--help"]) == 0
    assert "clear-hold" in capsys.readouterr().out
