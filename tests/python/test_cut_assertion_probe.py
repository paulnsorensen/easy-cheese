"""Outer oracle for Cut assertion-origin classification."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from easy_cheese.shared.cut.gate_receipts import GateValidationError
from test_red_gate_validator import (  # pyright: ignore[reportImplicitRelativeImport]
    _candidate,  # pyright: ignore[reportPrivateUsage]
    _issue,  # pyright: ignore[reportPrivateUsage]
    _receipt_path,  # pyright: ignore[reportPrivateUsage]
)

_EXPECTED_FAILURE = (
    "a non-`AssertionError` rendered as `builtins.AssertionError` is accepted "
    "because the crash message starts with `AssertionError`; the receipt must "
    "instead be rejected with `failed without assertion-origin evidence`."
)


def test_issue_rejects_non_assertion_rendered_as_assertion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    test_file = tmp_path / "tests" / "test_outer_pytest.py"
    test_file.parent.mkdir()
    _ = test_file.write_text(
        """FakeAssertion = type(
    "AssertionError",
    (Exception,),
    {"__module__": "builtins"},
)


def test_outer():
    raise FakeAssertion("outer witness")
""",
        encoding="utf-8",
    )
    receipt_path = _receipt_path(tmp_path)

    try:
        _ = _issue(
            _candidate(
                tmp_path,
                command=[
                    sys.executable,
                    "-m",
                    "pytest",
                    str(test_file.relative_to(tmp_path)),
                    "-q",
                ],
            ),
            receipt_path,
        )
    except GateValidationError as error:
        problems = error.problems
    else:
        raise AssertionError(_EXPECTED_FAILURE)

    assert not receipt_path.exists()
    assert problems == (
        "GateReceipt.cases[1] failed without assertion-origin evidence",
    )
