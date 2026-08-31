"""The Press attempt telemetry record (issue #548).

The record must answer three questions the aggregate metrics cannot: which
operation kept failing, why each agent was delegated to, and whether the
production-source boundary held. It must never change Press routing.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SRC_ROOT = Path(__file__).resolve().parents[3] / "src"
for source in (SRC_ROOT, SRC_ROOT / "fanout"):
    value = str(source)
    if value not in sys.path:
        sys.path.insert(0, value)

from easy_cheese.shared.fanout import press_telemetry  # noqa: E402
from easy_cheese.shared.fanout import press_telemetry_cli  # noqa: E402

GREEN_REQUEST: dict[str, object] = {
    "slug": "outer-tdd-gates",
    "attempt": 1,
    "outcome": "green",
    "repair_cycles": 0,
    "tool_errors": [],
    "delegations": [],
    "changed_files": [],
}


def _request(**overrides: object) -> dict[str, object]:
    return {**GREEN_REQUEST, **overrides}


def test_clean_attempt_records_every_derived_field() -> None:
    assert press_telemetry.telemetry_record(**GREEN_REQUEST) == {
        "slug": "outer-tdd-gates",
        "attempt": 1,
        "outcome": "green",
        "repair_cycles": 0,
        "changed_file_count": 0,
        "changed_file_classes": [],
        "production_source_files": [],
        "boundary_consistent": True,
        "tool_error_count": 0,
        "operations": [],
        "delegations": [],
    }


def test_repeated_operation_is_recurring_and_single_failure_is_transient() -> None:
    record = press_telemetry.telemetry_record(
        **_request(
            tool_errors=[
                {"phase": "attack", "operation": "pytest"},
                {"phase": "attack", "operation": "pytest"},
                {"phase": "report", "operation": "write-artifact"},
            ]
        )
    )
    assert record["tool_error_count"] == 3
    assert record["operations"] == [
        {"phase": "attack", "operation": "pytest", "errors": 2, "recurring": True},
        {
            "phase": "report",
            "operation": "write-artifact",
            "errors": 1,
            "recurring": False,
        },
    ]


def test_same_operation_in_different_phases_stays_separate() -> None:
    record = press_telemetry.telemetry_record(
        **_request(
            tool_errors=[
                {"phase": "read", "operation": "git"},
                {"phase": "attack", "operation": "git"},
            ]
        )
    )
    assert record["operations"] == [
        {"phase": "attack", "operation": "git", "errors": 1, "recurring": False},
        {"phase": "read", "operation": "git", "errors": 1, "recurring": False},
    ]


def test_unknown_phase_is_rejected_so_counts_stay_aggregatable() -> None:
    with pytest.raises(ValueError, match="invalid phase 'attacking'"):
        _ = press_telemetry.telemetry_record(
            **_request(tool_errors=[{"phase": "attacking", "operation": "pytest"}])
        )


def test_delegation_without_a_purpose_is_rejected() -> None:
    with pytest.raises(ValueError, match=r"delegations\[\]\.purpose"):
        _ = press_telemetry.telemetry_record(
            **_request(delegations=[{"role": "coder", "purpose": "  "}])
        )


def test_delegation_missing_the_purpose_key_is_rejected() -> None:
    with pytest.raises(ValueError, match="exactly purpose, role"):
        _ = press_telemetry.telemetry_record(
            **_request(delegations=[{"role": "reviewer"}])
        )


def test_delegations_keep_request_order() -> None:
    record = press_telemetry.telemetry_record(
        **_request(
            delegations=[
                {"role": "reviewer", "purpose": "assertion sensitivity sweep"},
                {"role": "coder", "purpose": "corrective cook for attempt 1 RED"},
            ]
        )
    )
    assert record["delegations"] == [
        {"role": "reviewer", "purpose": "assertion sensitivity sweep"},
        {"role": "coder", "purpose": "corrective cook for attempt 1 RED"},
    ]


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("tests/fanout/python/test_press_route.py", press_telemetry.FileClass.TESTS),
        ("src/pkg/tests/helper.py", press_telemetry.FileClass.TESTS),
        ("pkg/widget_test.go", press_telemetry.FileClass.TESTS),
        ("web/widget.spec.ts", press_telemetry.FileClass.TESTS),
        ("tests/bash/test_install.bats", press_telemetry.FileClass.TESTS),
        ("docs/press.md", press_telemetry.FileClass.METADATA),
        ("pyproject.toml", press_telemetry.FileClass.METADATA),
        ("LICENSE", press_telemetry.FileClass.METADATA),
        ("src/easy_cheese/shared/fanout/press_route.py", press_telemetry.FileClass.PRODUCTION_SOURCE),
        ("justfile", press_telemetry.FileClass.PRODUCTION_SOURCE),
    ],
)
def test_path_taxonomy(path: str, expected: press_telemetry.FileClass) -> None:
    assert press_telemetry.classify_path(path) == expected


def test_production_source_under_a_green_attempt_is_flagged_inconsistent() -> None:
    record = press_telemetry.telemetry_record(
        **_request(
            changed_files=[
                "tests/fanout/python/test_press_route.py",
                "src/easy_cheese/shared/fanout/press_route.py",
                "README.md",
            ]
        )
    )
    assert record["changed_file_count"] == 3
    assert record["changed_file_classes"] == ["metadata", "production_source", "tests"]
    assert record["production_source_files"] == [
        "src/easy_cheese/shared/fanout/press_route.py"
    ]
    assert record["boundary_consistent"] is False


def test_production_source_under_a_production_changed_attempt_is_consistent() -> None:
    record = press_telemetry.telemetry_record(
        **_request(
            outcome="production_changed",
            changed_files=["src/easy_cheese/shared/fanout/press_route.py"],
        )
    )
    assert record["boundary_consistent"] is True


def test_tests_only_attempt_reports_no_production_source() -> None:
    record = press_telemetry.telemetry_record(
        **_request(changed_files=["tests/fanout/python/test_press_route.py"])
    )
    assert record["changed_file_classes"] == ["tests"]
    assert record["production_source_files"] == []
    assert record["boundary_consistent"] is True


def test_attempt_must_match_the_completed_repair_cycles() -> None:
    with pytest.raises(ValueError, match="attempt 1 contradicts repair_cycles 2"):
        _ = press_telemetry.telemetry_record(**_request(attempt=1, repair_cycles=2))


def test_third_red_attempt_is_accepted() -> None:
    record = press_telemetry.telemetry_record(
        **_request(attempt=3, outcome="in_contract_red", repair_cycles=2)
    )
    assert record["attempt"] == 3
    assert record["outcome"] == "in_contract_red"


def test_fourth_attempt_is_rejected() -> None:
    with pytest.raises(ValueError, match="attempt must be between 1 and 3"):
        _ = press_telemetry.telemetry_record(**_request(attempt=4, repair_cycles=3))


def test_boolean_attempt_is_rejected() -> None:
    with pytest.raises(ValueError, match="attempt must be an integer"):
        _ = press_telemetry.telemetry_record(**_request(attempt=True))


def test_invalid_outcome_is_rejected_with_the_router_vocabulary() -> None:
    with pytest.raises(ValueError, match="invalid outcome 'purple'"):
        _ = press_telemetry.telemetry_record(**_request(outcome="purple"))


def test_invalid_slug_is_rejected() -> None:
    with pytest.raises(ValueError, match="kebab-case"):
        _ = press_telemetry.telemetry_record(**_request(slug="Outer TDD"))


def test_absolute_changed_file_is_rejected() -> None:
    with pytest.raises(ValueError, match="repository-relative path"):
        _ = press_telemetry.telemetry_record(**_request(changed_files=["/etc/passwd"]))


def test_traversing_changed_file_is_rejected() -> None:
    with pytest.raises(ValueError, match="repository-relative path"):
        _ = press_telemetry.telemetry_record(
            **_request(changed_files=["../other-repo/src/app.py"])
        )


def test_non_list_tool_errors_is_rejected() -> None:
    with pytest.raises(ValueError, match="tool_errors must be a list"):
        _ = press_telemetry.telemetry_record(**_request(tool_errors={"phase": "attack"}))


def test_cli_emits_the_record_for_a_request_file(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    request = tmp_path / "telemetry.json"
    payload = _request(
        attempt=2,
        outcome="in_contract_red",
        repair_cycles=1,
        tool_errors=[
            {"phase": "attack", "operation": "pytest"},
            {"phase": "attack", "operation": "pytest"},
        ],
        delegations=[{"role": "reviewer", "purpose": "replay the attack digest"}],
        changed_files=["tests/fanout/python/test_press_route.py"],
    )
    _ = request.write_text(json.dumps(payload), encoding="utf-8")

    assert press_telemetry_cli.main([str(request)]) == 0
    assert json.loads(capsys.readouterr().out) == press_telemetry.telemetry_record(
        **payload
    )


def test_cli_requires_every_request_key(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    request = tmp_path / "telemetry.json"
    incomplete = dict(GREEN_REQUEST)
    del incomplete["delegations"]
    _ = request.write_text(json.dumps(incomplete), encoding="utf-8")

    assert press_telemetry_cli.main([str(request)]) == 1
    assert "delegations" in capsys.readouterr().err


def test_cli_rejects_extra_request_keys(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    request = tmp_path / "telemetry.json"
    _ = request.write_text(
        json.dumps(_request(duration_seconds=246)), encoding="utf-8"
    )

    assert press_telemetry_cli.main([str(request)]) == 1
    assert "request must contain exactly" in capsys.readouterr().err
