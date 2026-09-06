"""The Press attempt telemetry record (issue #548).

The record must answer three questions the aggregate metrics cannot: which
operation kept failing, why each agent was delegated to, and whether the
production-source boundary held. It must never change Press routing.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import cast

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


# The CLI request carries only the agent's observations; `outcome` and
# `repair_cycles` come from the attempt's route artifact (#611).
CLI_REQUEST: dict[str, object] = {
    key: value
    for key, value in GREEN_REQUEST.items()
    if key not in {"outcome", "repair_cycles"}
}


def _cli_request(**overrides: object) -> dict[str, object]:
    return {**CLI_REQUEST, **overrides}


def _write_route(
    root: Path, slug: str, attempt: int, outcome: str, repair_cycles: int
) -> Path:
    press_dir = root / ".cheese" / "press"
    press_dir.mkdir(parents=True, exist_ok=True)
    path = press_dir / f"{slug}.attempt-{attempt}.route.json"
    _ = path.write_text(
        json.dumps({"outcome": outcome, "repair_cycles": repair_cycles}),
        encoding="utf-8",
    )
    return path


def _write_request(tmp_path: Path, payload: dict[str, object]) -> Path:
    request = tmp_path / "telemetry-request.json"
    _ = request.write_text(json.dumps(payload), encoding="utf-8")
    return request


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
    with pytest.raises(
        ValueError, match=r"each delegations entry keys mismatch: missing \['purpose'\]"
    ):
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


def test_cli_reads_outcome_and_repair_cycles_from_the_route_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    _ = _write_route(tmp_path, "outer-tdd-gates", 2, "in_contract_red", 1)
    observed = _cli_request(
        attempt=2,
        tool_errors=[
            {"phase": "attack", "operation": "pytest"},
            {"phase": "attack", "operation": "pytest"},
        ],
        delegations=[{"role": "reviewer", "purpose": "replay the attack digest"}],
        changed_files=["tests/fanout/python/test_press_route.py"],
    )

    assert press_telemetry_cli.main([str(_write_request(tmp_path, observed))]) == 0
    record = cast(dict[str, object], json.loads(capsys.readouterr().out))
    assert record == press_telemetry.telemetry_record(
        **observed, outcome="in_contract_red", repair_cycles=1
    )
    assert (record["outcome"], record["repair_cycles"]) == ("in_contract_red", 1)


def test_cli_resolves_the_route_artifact_from_the_git_toplevel(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _ = subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    nested = tmp_path / "src" / "pkg"
    nested.mkdir(parents=True)
    monkeypatch.chdir(nested)
    _ = _write_route(tmp_path, "outer-tdd-gates", 1, "green", 0)

    assert press_telemetry_cli.main([str(_write_request(tmp_path, _cli_request()))]) == 0
    record = cast(dict[str, object], json.loads(capsys.readouterr().out))
    assert record["outcome"] == "green"


def test_cli_rejects_a_request_that_restates_the_route_fields(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The retyped `outcome: green` from #611 is now an unknown key, not evidence."""
    monkeypatch.chdir(tmp_path)
    _ = _write_route(tmp_path, "outer-tdd-gates", 1, "in_contract_red", 0)
    retyped = _cli_request(outcome="green", repair_cycles=0)

    assert press_telemetry_cli.main([str(_write_request(tmp_path, retyped))]) == 1
    assert (
        "request keys mismatch: unknown ['outcome', 'repair_cycles']"
        in capsys.readouterr().err
    )


def test_cli_requires_every_request_key(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    incomplete = dict(CLI_REQUEST)
    del incomplete["delegations"]

    assert press_telemetry_cli.main([str(_write_request(tmp_path, incomplete))]) == 1
    assert "request keys mismatch: missing ['delegations']" in capsys.readouterr().err


def test_cli_refuses_to_record_an_attempt_that_was_never_routed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)

    assert press_telemetry_cli.main([str(_write_request(tmp_path, _cli_request()))]) == 1
    err = capsys.readouterr().err
    assert "route artifact not found" in err
    assert str(tmp_path / ".cheese" / "press" / "outer-tdd-gates.attempt-1.route.json") in err
    assert "run press-route" in err


def test_cli_rejects_a_route_artifact_that_contradicts_the_attempt_number(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    _ = _write_route(tmp_path, "outer-tdd-gates", 2, "green", 0)

    request = _write_request(tmp_path, _cli_request(attempt=2))
    assert press_telemetry_cli.main([str(request)]) == 1
    assert "attempt 2 contradicts repair_cycles 0" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("route_text", "message"),
    [
        ("[]", "expected a mapping"),
        ('{"outcome": "green"}', "keys mismatch: missing ['repair_cycles']"),
        (
            '{"outcome": "green", "repair_cycles": 0, "action": "dispatch"}',
            "keys mismatch: unknown ['action']",
        ),
        ('{"outcome": "purple", "repair_cycles": 0}', "invalid outcome 'purple'"),
    ],
)
def test_cli_rejects_a_route_artifact_that_press_route_would_reject(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    route_text: str,
    message: str,
) -> None:
    monkeypatch.chdir(tmp_path)
    route = _write_route(tmp_path, "outer-tdd-gates", 1, "green", 0)
    _ = route.write_text(route_text, encoding="utf-8")

    assert press_telemetry_cli.main([str(_write_request(tmp_path, _cli_request()))]) == 1
    assert message in capsys.readouterr().err


@pytest.mark.parametrize("slug", ["../../etc/passwd", "Outer TDD", ""])
def test_cli_validates_the_slug_before_building_the_route_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    slug: str,
) -> None:
    monkeypatch.chdir(tmp_path)

    request = _write_request(tmp_path, _cli_request(slug=slug))
    assert press_telemetry_cli.main([str(request)]) == 1
    err = capsys.readouterr().err
    assert "slug" in err
    assert "route artifact" not in err


def test_cli_bounds_the_attempt_before_building_the_route_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)

    request = _write_request(tmp_path, _cli_request(attempt=4))
    assert press_telemetry_cli.main([str(request)]) == 1
    err = capsys.readouterr().err
    assert "attempt must be between 1 and 3" in err
    assert "route artifact" not in err


@pytest.mark.parametrize("path", [".", "./", "./."])
def test_changed_file_naming_nothing_is_rejected(path: str) -> None:
    with pytest.raises(ValueError, match="must name a file or directory"):
        _ = press_telemetry.telemetry_record(**_request(changed_files=[path]))


def test_classify_path_handles_a_path_with_no_parts() -> None:
    assert (
        press_telemetry.classify_path(".")
        == press_telemetry.FileClass.PRODUCTION_SOURCE
    )


def test_metadata_dir_rule_scans_every_ancestor_part() -> None:
    assert (
        press_telemetry.classify_path("backend/docs/architecture")
        == press_telemetry.FileClass.METADATA
    )


def test_changed_file_with_a_backslash_is_rejected() -> None:
    with pytest.raises(ValueError, match="repository-relative path"):
        _ = press_telemetry.telemetry_record(
            **_request(changed_files=["src\\app.py"])
        )


def test_changed_file_with_a_drive_letter_is_rejected() -> None:
    with pytest.raises(ValueError, match="repository-relative path"):
        _ = press_telemetry.telemetry_record(
            **_request(changed_files=["C:/app.py"])
        )


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("tests/", press_telemetry.FileClass.TESTS),
        ("docs/", press_telemetry.FileClass.METADATA),
    ],
)
def test_trailing_slash_directory_classifies_by_its_own_name(
    path: str, expected: press_telemetry.FileClass
) -> None:
    assert press_telemetry.classify_path(path) == expected


def test_trailing_slash_directories_survive_path_normalization() -> None:
    record = press_telemetry.telemetry_record(
        **_request(outcome="green", changed_files=["tests/", "./docs/"])
    )

    assert record["production_source_files"] == []
    assert record["changed_file_classes"] == ["metadata", "tests"]
    assert record["boundary_consistent"] is True


def test_operations_normalize_whitespace_and_case_before_aggregating() -> None:
    record = press_telemetry.telemetry_record(
        **_request(
            tool_errors=[
                {"phase": "attack", "operation": " pytest"},
                {"phase": "attack", "operation": "PyTest"},
            ]
        )
    )
    assert record["operations"] == [
        {"phase": "attack", "operation": "pytest", "errors": 2, "recurring": True}
    ]


def test_whitespace_only_operation_is_rejected() -> None:
    with pytest.raises(ValueError, match=r"tool_errors\[\]\.operation"):
        _ = press_telemetry.telemetry_record(
            **_request(tool_errors=[{"phase": "attack", "operation": "   "}])
        )


def test_max_attempts_is_re_exported_from_press_route() -> None:
    from easy_cheese.shared.fanout import press_route

    assert press_telemetry.MAX_ATTEMPTS is press_route.MAX_ATTEMPTS
