from __future__ import annotations

import sys
from pathlib import Path
from typing import cast

import pytest

SRC_ROOT = Path(__file__).resolve().parents[3] / "src"
for source in (SRC_ROOT, SRC_ROOT / "fanout"):
    value = str(source)
    if value not in sys.path:
        sys.path.insert(0, value)

from easy_cheese.shared.fanout import press_route  # noqa: E402
from easy_cheese.shared.fanout import press_route_cli  # noqa: E402


@pytest.mark.parametrize(
    ("outcome", "repair_cycles", "expected"),
    [
        (press_route.Outcome.GREEN, 0, press_route.Dispatch()),
        (press_route.Outcome.IN_CONTRACT_RED, 0, press_route.Continue()),
        (press_route.Outcome.IN_CONTRACT_RED, 1, press_route.Continue()),
        (
            press_route.Outcome.IN_CONTRACT_RED,
            2,
            press_route.Stop(reason="third-red", gated_evidence=True),
        ),
        (
            press_route.Outcome.INVALID_EVIDENCE,
            0,
            press_route.Stop(reason="invalid-evidence", gated_evidence=False),
        ),
        (
            press_route.Outcome.PRODUCTION_CHANGED,
            0,
            press_route.Stop(reason="production-changed", gated_evidence=False),
        ),
    ],
)
def test_press_route_truth_table(
    outcome: press_route.Outcome,
    repair_cycles: int,
    expected: press_route.Action,
) -> None:
    assert press_route.press_route(outcome, repair_cycles) == expected


def test_press_route_accepts_string_outcomes() -> None:
    assert press_route.press_route("green", 0) == press_route.Dispatch()


def test_press_route_rejects_unknown_outcome() -> None:
    with pytest.raises(ValueError, match="invalid outcome"):
        _ = press_route.press_route("purple", 0)


def test_press_route_rejects_non_string_outcome() -> None:
    with pytest.raises(ValueError, match="outcome must be a string"):
        _ = press_route.press_route(cast(str, cast(object, 7)), 0)


def test_press_route_rejects_repair_cycles_at_max_attempts() -> None:
    with pytest.raises(ValueError, match="must be less than 3"):
        _ = press_route.press_route("in_contract_red", press_route.MAX_ATTEMPTS)


def test_press_route_rejects_negative_repair_cycles() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        _ = press_route.press_route("green", -1)


def test_press_route_rejects_bool_repair_cycles() -> None:
    with pytest.raises(TypeError, match="non-negative"):
        _ = press_route.press_route("green", True)


def test_cli_routes_green_to_age_dispatch(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    request = tmp_path / "request.json"
    _ = request.write_text(
        '{"outcome":"green","repair_cycles":0}',
        encoding="utf-8",
    )
    assert press_route_cli.main([str(request)]) == 0
    out = capsys.readouterr().out
    assert '"action": "dispatch"' in out
    assert '"command": "/age"' in out


def test_cli_routes_third_red_to_stop(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    request = tmp_path / "request.json"
    _ = request.write_text(
        '{"outcome":"in_contract_red","repair_cycles":2}',
        encoding="utf-8",
    )
    assert press_route_cli.main([str(request)]) == 0
    out = capsys.readouterr().out
    assert '"action": "stop"' in out
    assert '"reason": "third-red"' in out


def test_cli_requires_exact_request_keys(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    request = tmp_path / "request.json"
    _ = request.write_text('{"outcome":"green"}', encoding="utf-8")
    assert press_route_cli.main([str(request)]) == 1
    assert "repair_cycles" in capsys.readouterr().err


def test_cli_rejects_extra_request_keys(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    request = tmp_path / "request.json"
    _ = request.write_text(
        '{"outcome":"green","repair_cycles":0,"current_receipt":"x"}',
        encoding="utf-8",
    )
    assert press_route_cli.main([str(request)]) == 1
    assert "repair_cycles" in capsys.readouterr().err


def test_cli_rejects_invalid_outcome(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    request = tmp_path / "request.json"
    _ = request.write_text(
        '{"outcome":"purple","repair_cycles":0}',
        encoding="utf-8",
    )
    assert press_route_cli.main([str(request)]) == 1
    assert "invalid outcome" in capsys.readouterr().err


def test_cli_rejects_bool_repair_cycles(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    request = tmp_path / "request.json"
    _ = request.write_text(
        '{"outcome":"green","repair_cycles":true}',
        encoding="utf-8",
    )
    assert press_route_cli.main([str(request)]) == 1
    assert "non-negative" in capsys.readouterr().err
