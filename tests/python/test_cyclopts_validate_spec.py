"""Cyclopts contract tests for the Mold specification validator."""

from __future__ import annotations

# Pytest fixture protocols are not present in the type-checking dependency set.
# pyright: reportUnknownParameterType=false, reportMissingParameterType=false
# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false

from pathlib import Path

from easy_cheese.skills.mold import validate_spec


FIXTURES = Path(__file__).parent / "fixtures" / "spec_format"


def test_validate_spec_help_is_successful_without_validation(capsys) -> None:
    assert validate_spec.main(["--help"]) == 0
    captured = capsys.readouterr()
    assert "SPEC-PATH" in captured.out
    assert captured.err == ""


def test_validate_spec_binds_path_and_strict_option() -> None:
    path = FIXTURES / "valid_spec.md"
    assert validate_spec.main(["--strict", str(path)]) == 0
