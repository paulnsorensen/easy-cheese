"""Behavioral tests for strict receipt issue and replay validation."""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CUT_ROOT = REPO_ROOT / "src" / "cut"


def _load_red_gate() -> ModuleType:
    sys.path.insert(0, str(CUT_ROOT))
    spec = importlib.util.spec_from_file_location(
        "red_gate_validator_under_test", CUT_ROOT / "red_gate.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


red_gate = _load_red_gate()


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _spec(path: Path, interface: str) -> None:
    path.write_text(
        f"""---
status: approved
gate_applicability:
  disposition: red-required
  work_class: behavior
---
# Outer behavior

## Acceptance Criteria
- AC-1: the outer behavior rejects invalid state.

## Test Contracts
| Acceptance | Interface referent | Outermost stable seam | Expected failure | Mode |
| --- | --- | --- | --- | --- |
| AC-1 | `{interface}` | `{interface}` | outer witness | tracer |
""",
        encoding="utf-8",
    )


def _receipt_path(
    root: Path,
    name: str = "receipt.json",
    *,
    producer: str = "cut",
) -> Path:
    return root / ".cheese" / producer / name


def _begin(
    payload: dict[str, object],
    label: str,
) -> tuple[object, Path, Path]:
    root = Path.cwd().resolve()
    producer = str(payload.get("producer"))
    namespace = root / ".cheese" / producer
    namespace.mkdir(parents=True, exist_ok=True)
    sequence = 1
    while True:
        stem = f"{label}.{sequence}"
        plan_path = namespace / f"{stem}.plan.json"
        token_path = namespace / f"{stem}.phase.json"
        if not token_path.exists() and not token_path.is_symlink():
            break
        sequence += 1
    checks = [
        {"id": check["id"], "argv": check["argv"], "cwd": check["cwd"]}
        for check in payload.get("baseline_checks", [])
    ]
    plan_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "producer": producer,
                "work_id": payload["work_id"],
                "project_key": payload["project_key"],
                "production_paths": payload.get(
                    "production_paths",
                    ["production-state.txt"],
                ),
                "baseline_checks": checks,
            }
        ),
        encoding="utf-8",
    )
    token = red_gate.begin_phase(plan_path, token_path)
    candidate_directory = namespace / "candidates"
    candidate_directory.mkdir(exist_ok=True)
    return token, token_path, candidate_directory / f"{stem}.json"


def _issue(
    candidate: Path | str | dict[str, object],
    output: Path | str,
) -> object:
    output_path = Path(output)
    payload = (
        dict(candidate)
        if isinstance(candidate, dict)
        else json.loads(Path(candidate).read_text(encoding="utf-8"))
    )
    token, token_path, issue_candidate = _begin(payload, output_path.name)
    payload.update(token.to_dict())
    issue_candidate.write_text(json.dumps(payload), encoding="utf-8")
    return red_gate.issue_gate(issue_candidate, output_path, token_path)


def _candidate(
    tmp_path: Path, *, command: list[str] | None = None
) -> dict[str, object]:
    oracle = tmp_path / "tests" / "oracle.py"
    oracle.parent.mkdir(exist_ok=True)
    oracle.write_text("oracle\n", encoding="utf-8")
    (tmp_path / "production-state.txt").write_text("red\n", encoding="utf-8")
    approved_spec = tmp_path / "approved.md"
    _spec(approved_spec, "outer behavior")
    red_command = command or [
        sys.executable,
        "-c",
        "from pathlib import Path; state=Path('production-state.txt').read_text(); assert state.strip() != 'red', 'outer witness'",
    ]
    return {
        "schema_version": 1,
        "work_id": "work-validator",
        "project_key": "validator-project",
        "producer": "cut",
        "disposition": "red",
        "spec_ref": str(approved_spec),
        "spec_sha256": _digest(approved_spec),
        "phase_token_ref": None,
        "phase_token_sha256": None,
        "guard_receipt_refs": [],
        "contracts": [
            {
                "acceptance_id": "AC-1",
                "interface": "outer behavior",
                "seam": "outer behavior",
                "expected_failure": "outer witness",
                "mode": "tracer",
                "contract_source": "approved",
            }
        ],
        "baseline_checks": [
            {
                "id": "baseline",
                "argv": [sys.executable, "-c", "pass"],
                "cwd": ".",
                "observed_exit_code": 0,
            }
        ],
        "cases": [
            {
                "id": "AC-1-tracer",
                "acceptance_ids": ["AC-1"],
                "curd": "validator",
                "seam": "outer behavior",
                "argv": red_command,
                "cwd": ".",
                "kind": "behavior",
                "origin": "generated",
                "expected_witness": ["outer witness"],
                "observed_exit_code": 1,
                "observed_witness": "outer witness",
            }
        ],
        "protected_files": [{"path": "tests/oracle.py", "sha256": _digest(oracle)}],
        "not_applicable_reason": None,
    }


def _matrix_candidate(
    tmp_path: Path,
    *,
    declared_rows: tuple[str, ...] = ("empty", "non-empty"),
    observed_rows: tuple[str, ...] | None = None,
    interface_version: str | None = "v1",
    command: list[str] | None = None,
) -> dict[str, object]:
    payload = _candidate(tmp_path, command=command)
    spec_path = Path(str(payload["spec_ref"]))
    version_cell = interface_version or ""
    rows_cell = "<br>".join(declared_rows)
    spec_path.write_text(
        f"""---
status: approved
gate_applicability:
  disposition: red-required
  work_class: behavior
---
# Outer behavior

## Acceptance Criteria
- AC-1: the outer behavior rejects invalid state.

## Test Contracts
| Acceptance | Interface referent | Outermost stable seam | Expected failure | Mode | Interface version | Matrix rows |
| --- | --- | --- | --- | --- | --- | --- |
| AC-1 | `outer behavior` | `outer behavior` | outer witness | contract-matrix | {version_cell} | {rows_cell} |
""",
        encoding="utf-8",
    )
    payload["spec_sha256"] = _digest(spec_path)
    contract = payload["contracts"][0]
    contract.update(
        {
            "mode": "contract-matrix",
            "interface_version": interface_version,
            "matrix_rows": list(declared_rows),
        }
    )
    base_case = payload["cases"][0]
    payload["cases"] = [
        {
            **base_case,
            "id": f"AC-1-matrix-{index}",
            "kind": "contract",
            "matrix_row": row,
        }
        for index, row in enumerate(observed_rows or declared_rows, start=1)
    ]
    return payload


def test_issue_writes_only_after_replaying_red_and_validate_replays_green(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    candidate = tmp_path / "candidate.json"
    receipt_path = _receipt_path(tmp_path)
    candidate.write_text(json.dumps(_candidate(tmp_path)), encoding="utf-8")

    receipt = _issue(candidate, receipt_path)

    assert receipt_path.exists()
    assert receipt.cases[0].observed_exit_code == 1
    assert receipt.cases[0].observed_witness == "outer witness"
    assert red_gate.validate_gate(receipt_path, "red").ok

    (tmp_path / "production-state.txt").write_text("green\n", encoding="utf-8")
    assert red_gate.validate_gate(receipt_path, "green").ok


def test_versioned_contract_matrix_requires_each_declared_row_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    receipt_path = _receipt_path(tmp_path, "matrix.receipt.json")

    receipt = _issue(_matrix_candidate(tmp_path), receipt_path)

    assert [case.matrix_row for case in receipt.cases] == ["empty", "non-empty"]
    assert red_gate.validate_gate(receipt_path, "red").ok


@pytest.mark.parametrize(
    ("payload_changes", "problem"),
    [
        ({"interface_version": None}, "interface version"),
        ({"declared_rows": ("empty", "empty")}, "rows-not-unique"),
        (
            {
                "declared_rows": ("empty", "non-empty"),
                "observed_rows": ("empty",),
            },
            "missing rows",
        ),
        (
            {
                "declared_rows": ("empty", "non-empty"),
                "observed_rows": ("empty", "non-empty", "other"),
            },
            "unexpected rows",
        ),
    ],
)
def test_contract_matrix_rejects_unversioned_or_incomplete_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    payload_changes: dict[str, object],
    problem: str,
) -> None:
    monkeypatch.chdir(tmp_path)

    with pytest.raises(red_gate.GateValidationError) as raised:
        _issue(_matrix_candidate(tmp_path, **payload_changes), _receipt_path(tmp_path))

    assert any(problem in detail for detail in raised.value.problems)


def test_validate_rejects_an_unprotected_test_fixture_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    payload = _candidate(
        tmp_path,
        command=[
            sys.executable,
            "-c",
            (
                "from pathlib import Path; "
                "state=Path('production-state.txt').read_text().strip(); "
                "Path('tests/attack-fixture.txt').read_text(); "
                "assert state != 'red', 'outer witness'"
            ),
        ],
    )
    fixture = tmp_path / "tests" / "attack-fixture.txt"
    fixture.write_text("red\n", encoding="utf-8")
    receipt_path = _receipt_path(tmp_path, "fixture.receipt.json")
    _issue(payload, receipt_path)
    (tmp_path / "production-state.txt").write_text("green\n", encoding="utf-8")
    fixture.write_text("green\n", encoding="utf-8")

    result = red_gate.validate_gate(receipt_path, "green")

    assert not result.ok
    assert any(
        "oracle dependency changed since phase entry: tests/attack-fixture.txt"
        in problem
        for problem in result.problems
    )


def test_issue_rejects_receipt_contracts_from_a_different_spec(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    first_spec = tmp_path / "first.md"
    second_spec = tmp_path / "second.md"
    _spec(first_spec, "outer behavior")
    _spec(second_spec, "different behavior")
    payload = _candidate(tmp_path)
    payload["spec_ref"] = second_spec.name
    payload["spec_sha256"] = _digest(second_spec)
    candidate = tmp_path / "candidate.json"
    receipt_path = _receipt_path(tmp_path)
    candidate.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(red_gate.GateValidationError) as raised:
        _issue(candidate, receipt_path)

    assert not receipt_path.exists()
    assert any("exact spec contracts" in problem for problem in raised.value.problems)


def test_issue_accepts_absolute_approved_spec_outside_project_root_and_enforces_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    approved_spec = tmp_path.parent / f"{tmp_path.name}-approved.md"
    _spec(approved_spec, "outer behavior")
    payload = _candidate(tmp_path)
    payload["spec_ref"] = str(approved_spec)
    payload["spec_sha256"] = _digest(approved_spec)
    contract = red_gate.parse_gate_applicability(approved_spec).contracts[0]
    payload["contracts"] = [contract.to_dict()]
    payload["cases"][0]["seam"] = contract.seam
    candidate = tmp_path / "candidate.json"
    receipt_path = _receipt_path(tmp_path)
    candidate.write_text(json.dumps(payload), encoding="utf-8")

    receipt = _issue(candidate, receipt_path)

    assert receipt.spec_ref == str(approved_spec)
    assert red_gate.validate_gate(receipt_path, "red").ok

    stale_payload = {**payload, "spec_sha256": "0" * 64}
    stale_candidate = tmp_path / "stale-candidate.json"
    stale_candidate.write_text(json.dumps(stale_payload), encoding="utf-8")
    with pytest.raises(red_gate.GateValidationError) as stale:
        _issue(stale_candidate, _receipt_path(tmp_path, "stale-receipt.json"))
    assert any("spec_sha256 is stale" in problem for problem in stale.value.problems)

    mismatched_payload = {
        **payload,
        "contracts": [
            {
                "acceptance_id": "AC-1",
                "interface": "different behavior",
                "seam": "outer behavior",
                "expected_failure": "outer witness",
                "mode": "tracer",
                "contract_source": "approved",
            }
        ],
    }
    mismatched_candidate = tmp_path / "mismatched-candidate.json"
    mismatched_candidate.write_text(json.dumps(mismatched_payload), encoding="utf-8")
    with pytest.raises(red_gate.GateValidationError) as mismatched:
        _issue(mismatched_candidate, _receipt_path(tmp_path, "mismatched-receipt.json"))
    assert any(
        "exact spec contracts" in problem for problem in mismatched.value.problems
    )


def test_issue_rejects_output_path_that_overwrites_protected_oracle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    candidate = tmp_path / "candidate.json"
    candidate.write_text(json.dumps(_candidate(tmp_path)), encoding="utf-8")
    protected = tmp_path / "tests" / "oracle.py"
    original = protected.read_text(encoding="utf-8")

    with pytest.raises(red_gate.GateValidationError) as raised:
        _issue(candidate, protected)

    assert protected.read_text(encoding="utf-8") == original
    assert any("receipt output" in problem for problem in raised.value.problems)


def test_issue_rejects_receipt_output_outside_project_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    candidate = tmp_path / "candidate.json"
    candidate.write_text(json.dumps(_candidate(tmp_path)), encoding="utf-8")
    outside_dir = tmp_path.parent / f"{tmp_path.name}-outside"
    outside_dir.mkdir()
    output = outside_dir / "receipt.json"

    with pytest.raises(red_gate.GateValidationError) as raised:
        _issue(candidate, output)

    assert any(
        "receipt output" in problem and "project root" in problem
        for problem in raised.value.problems
    )
    assert not output.exists()


def test_issue_rejects_symlinked_receipt_output_before_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    candidate = tmp_path / "candidate.json"
    candidate.write_text(json.dumps(_candidate(tmp_path)), encoding="utf-8")
    target = tmp_path / "target.json"
    alias = tmp_path / "alias.json"
    alias.symlink_to(target)

    with pytest.raises(red_gate.GateValidationError) as raised:
        _issue(candidate, alias)

    assert not target.exists()
    assert any("symlink" in problem for problem in raised.value.problems)


def test_issue_rejects_receipt_input_outside_project_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    outside_dir = tmp_path.parent / f"{tmp_path.name}-input-outside"
    outside_dir.mkdir()
    candidate = outside_dir / "candidate.json"
    payload = _candidate(tmp_path)
    output = _receipt_path(tmp_path)
    plan = _receipt_path(tmp_path, "outside-input.plan.json")
    token_path = _receipt_path(tmp_path, "outside-input.phase.json")
    plan.parent.mkdir(parents=True, exist_ok=True)
    plan.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "producer": "cut",
                "work_id": payload["work_id"],
                "project_key": payload["project_key"],
                "production_paths": ["production-state.txt"],
                "baseline_checks": [
                    {"id": check["id"], "argv": check["argv"], "cwd": check["cwd"]}
                    for check in payload["baseline_checks"]
                ],
            }
        ),
        encoding="utf-8",
    )
    token = red_gate.begin_phase(plan, token_path)
    payload.update(token.to_dict())
    candidate.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(red_gate.GateValidationError) as raised:
        red_gate.issue_gate(candidate, output, token_path)

    assert not output.exists()
    assert any(
        "receipt input" in problem and "project root" in problem
        for problem in raised.value.problems
    )


def test_issue_rejects_harness_failure_and_leaves_no_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    candidate = tmp_path / "candidate.json"
    receipt_path = _receipt_path(tmp_path)
    payload = _candidate(tmp_path)
    payload["cases"][0]["argv"] = [
        sys.executable,
        "-c",
        "raise SyntaxError('broken harness')",
    ]
    candidate.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(red_gate.GateValidationError) as raised:
        _issue(candidate, receipt_path)

    assert not receipt_path.exists()
    assert any("harness" in problem for problem in raised.value.problems)


def test_issue_rejects_text_only_failure_without_assertion_origin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    candidate = tmp_path / "candidate.json"
    receipt_path = _receipt_path(tmp_path)
    payload = _candidate(
        tmp_path,
        command=[sys.executable, "-c", "print('outer witness'); raise SystemExit(1)"],
    )
    candidate.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(red_gate.GateValidationError) as raised:
        _issue(candidate, receipt_path)

    assert not receipt_path.exists()
    assert any("assertion-origin" in problem for problem in raised.value.problems)


def test_issue_rejects_fabricated_assertion_traceback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    command = [
        sys.executable,
        "-c",
        (
            "print('Traceback (most recent call last):\\n"
            '  File "fake.py", line 1, in <module>\\n'
            "AssertionError: outer witness'); raise SystemExit(1)"
        ),
    ]

    with pytest.raises(red_gate.GateValidationError) as raised:
        _issue(_candidate(tmp_path, command=command), _receipt_path(tmp_path))

    assert any(
        "assertion-origin" in problem or "harness" in problem
        for problem in raised.value.problems
    )


def test_issue_accepts_unittest_assertion_origin(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    test_file = tmp_path / "tests" / "test_outer.py"
    test_file.parent.mkdir()
    test_file.write_text(
        """import unittest


class OuterTest(unittest.TestCase):
    def test_outer(self):
        self.fail("outer witness")


unittest.main()
""",
        encoding="utf-8",
    )

    receipt = _issue(
        _candidate(tmp_path, command=[sys.executable, str(test_file)]),
        _receipt_path(tmp_path),
    )

    assert receipt.cases[0].observed_exit_code == 1


def test_issue_accepts_python_module_unittest_assertion_origin(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    package = tmp_path / "tests"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    test_file = package / "test_outer_module.py"
    test_file.write_text(
        """import unittest


class OuterTest(unittest.TestCase):
    def test_outer(self):
        self.fail("outer witness")
""",
        encoding="utf-8",
    )

    receipt = _issue(
        _candidate(
            tmp_path,
            command=[
                sys.executable,
                "-m",
                "unittest",
                "tests.test_outer_module",
            ],
        ),
        _receipt_path(tmp_path),
    )

    assert receipt.cases[0].observed_exit_code == 1


def test_issue_accepts_python_module_pytest_assertion_origin(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    test_file = tmp_path / "tests" / "test_outer_pytest.py"
    test_file.parent.mkdir()
    test_file.write_text(
        """def test_outer():
    assert False, "outer witness"
""",
        encoding="utf-8",
    )

    receipt = _issue(
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
        _receipt_path(tmp_path),
    )

    assert receipt.cases[0].observed_exit_code == 1


def test_issue_accepts_plain_script_uncaught_assertion_origin(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    script = tmp_path / "candidate.py"
    script.write_text(
        "raise AssertionError('outer witness')\n",
        encoding="utf-8",
    )
    receipt_path = _receipt_path(tmp_path, "plain-script.receipt.json")

    receipt = _issue(
        _candidate(tmp_path, command=[sys.executable, str(script)]),
        receipt_path,
    )

    assert receipt_path.exists()
    assert receipt.cases[0].observed_exit_code == 1
    assert receipt.cases[0].observed_witness == "outer witness"


def test_issue_rejects_builtin_named_non_assertion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    script = tmp_path / "fake_assertion.py"
    script.write_text(
        "FakeAssertionError = type('AssertionError', (Exception,), {})\n"
        "FakeAssertionError.__module__ = 'builtins'\n"
        "print(f'TYPE {FakeAssertionError.__module__}.{FakeAssertionError.__name__}')\n"
        "raise FakeAssertionError('outer witness')\n",
        encoding="utf-8",
    )
    command = [sys.executable, str(script)]
    run = red_gate._run_case(command, tmp_path)
    assert (
        run.returncode,
        run.error,
        run.assertion_origin,
    ) == (1, None, False)
    assert "TYPE builtins.AssertionError" in run.output

    receipt_path = _receipt_path(tmp_path, "fake-assertion.receipt.json")
    with pytest.raises(red_gate.GateValidationError) as raised:
        _issue(_candidate(tmp_path, command=command), receipt_path)

    assert any(
        problem.endswith("failed in the harness, not its declared witness")
        for problem in raised.value.problems
    )
    assert not receipt_path.exists()


def test_rejects_misleading_python_executable_before_probe_fd(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    fake = tmp_path / "python3"
    fake.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    fake.chmod(0o755)
    command = [str(fake), "-c", "raise AssertionError('outer witness')"]

    def unexpected_pipe() -> tuple[int, int]:
        raise AssertionError("probe FD must not be created for an untrusted interpreter")

    with monkeypatch.context() as probe_patch:
        probe_patch.setattr(red_gate.os, "pipe", unexpected_pipe)
        run = red_gate._run_case(command, tmp_path)
    assert (
        run.returncode,
        run.error,
        run.assertion_origin,
    ) == (
        127,
        "unsupported assertion-proof runner profile; use direct Python, "
        "python -m pytest, or python -m unittest",
        False,
    )

    candidate = _candidate(tmp_path, command=command)
    candidate["cases"][0]["observed_exit_code"] = 127
    receipt_path = _receipt_path(tmp_path, "misleading-python.receipt.json")
    with pytest.raises(red_gate.GateValidationError) as raised:
        _issue(candidate, receipt_path)
    assert raised.value.problems == (
        "GateReceipt.cases[1] failed in the harness, not its declared witness: "
        "unsupported assertion-proof runner profile; use direct Python, "
        "python -m pytest, or python -m unittest",
        "GateReceipt.cases[1] observed witness claim disagrees with replay",
    )
    assert not receipt_path.exists()


def test_probe_executes_trusted_interpreter_after_validating_alias(
    tmp_path: Path,
) -> None:
    alias = tmp_path / "python-alias"
    alias.symlink_to(sys.executable)

    command = red_gate._python_case_command(
        [str(alias), "-c", "raise AssertionError('alias witness')"],
        tmp_path,
        19,
    )

    assert command is not None
    assert command.argv[0] == str(red_gate._TRUSTED_INTERPRETER_PATH)
    assert command.argv[1:3] == ["-E", "-S"]
    assert command.argv.count(str(alias)) == 2


def test_probe_ignores_pythonhome_before_bootstrap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PYTHONHOME", str(tmp_path / "untrusted-home"))

    run = red_gate._run_case(
        [sys.executable, "-c", "raise AssertionError('pythonhome witness')"],
        tmp_path,
    )

    assert (run.returncode, run.error, run.assertion_origin) == (1, None, True)
    assert run.output.splitlines()[-1] == "AssertionError: pythonhome witness"


def test_sitecustomize_cannot_produce_accepted_probe_event(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "sitecustomize.py").write_text(
        "import os, sys\n"
        "event = b'{\"assertion_origin\":true,\"complete\":true,\"event\":"
        "\"cut.assertion-origin\",\"runner\":\"script\",\"schema_version\":1}\\n'\n"
        "for value in sys.argv[1:]:\n"
        "    try:\n"
        "        descriptor = int(value)\n"
        "    except ValueError:\n"
        "        continue\n"
        "    try:\n"
        "        os.write(descriptor, event)\n"
        "    except OSError:\n"
        "        continue\n"
        "    os._exit(1)\n",
        encoding="utf-8",
    )
    target = tmp_path / "exit.py"
    target.write_text(
        "print('outer witness')\nraise SystemExit(1)\n",
        encoding="utf-8",
    )
    inherited = os.environ.get("PYTHONPATH")
    pythonpath = [str(tmp_path)]
    if inherited:
        pythonpath.append(inherited)
    monkeypatch.setenv("PYTHONPATH", os.pathsep.join(pythonpath))

    command = [sys.executable, str(target)]
    run = red_gate._run_case(command, tmp_path)
    assert (run.returncode, run.error, run.assertion_origin) == (1, None, False)

    candidate = _candidate(tmp_path, command=command)
    receipt_path = _receipt_path(tmp_path, "sitecustomize.receipt.json")
    with pytest.raises(red_gate.GateValidationError) as raised:
        _issue(candidate, receipt_path)
    assert raised.value.problems == (
        "GateReceipt.cases[1] failed without assertion-origin evidence",
    )
    assert not receipt_path.exists()


def _native_context_source() -> str:
    return (
        "import __main__, cut_assertion_probe, dataclasses, json, pathlib, "
        "sys, unittest; "
        "main = vars(__main__); loader = getattr(__main__, '__loader__', None); "
        "main_console = getattr(__main__, '_console_main', None); "
        "config_module = sys.modules.get('_pytest.config'); "
        "config_console = getattr(config_module, '_console_main', None); "
        "builtins_value = main.get('__builtins__'); "
        "print('OBS ' + repr(("
        "sys.flags.safe_path, sys.path[0], sys.argv, sys.orig_argv, "
        "sys.executable, sys.prefix, sys.exec_prefix, "
        "sys.base_prefix, sys.base_exec_prefix, "
        "__main__.__name__, "
        "getattr(getattr(__main__, '__spec__', None), 'name', None), "
        "'__file__' in main, main.get('__file__'), "
        "type(loader).__module__, type(loader).__qualname__, "
        "getattr(loader, 'name', getattr(loader, '__name__', None)), "
        "'__cached__' in main, main.get('__cached__'), "
        "getattr(__main__, '__package__', None), "
        "'__builtins__' in main, type(builtins_value).__name__, "
        "'_console_main' in main, "
        "getattr(main_console, '__module__', None), "
        "getattr(main_console, '__name__', None), "
        "(main_console is config_console) if main_console is not None else None, "
        "getattr(json, 'TARGET_LOCAL', False), "
        "getattr(cut_assertion_probe, 'TARGET_LOCAL', False), "
        "getattr(dataclasses, 'TARGET_LOCAL', False), "
        "getattr(pathlib, 'TARGET_LOCAL', False), "
        "getattr(unittest, 'TARGET_LOCAL', False)"
        "))); "
        "raise AssertionError('matrix witness')"
    )


def _matrix_command(profile: str, tmp_path: Path, source: str) -> list[str]:
    if profile == "code":
        return [sys.executable, "-c", source]
    if profile == "script":
        target = tmp_path / "matrix_script.py"
        target.write_text(source, encoding="utf-8")
        return [sys.executable, str(target)]
    if profile == "pytest":
        target = tmp_path / "tests" / "test_matrix.py"
        target.parent.mkdir()
        target.write_text(f"def test_matrix():\n    {source}\n", encoding="utf-8")
        return [sys.executable, "-m", "pytest", str(target), "-q"]
    target = tmp_path / "tests" / "test_matrix_unittest.py"
    target.parent.mkdir(exist_ok=True)
    target.write_text(
        "import unittest\n\n"
        "class MatrixTest(unittest.TestCase):\n"
        "    def test_matrix(self):\n"
        f"        {source}\n",
        encoding="utf-8",
    )
    return [
        sys.executable,
        "-m",
        "unittest",
        "discover",
        "-s",
        str(target.parent),
        "-p",
        "test_matrix_unittest.py",
    ]


def _observed_matrix_value(output: str, prefix: str = "OBS ") -> tuple[object, ...]:
    for line in output.splitlines():
        if line.startswith(prefix):
            value = ast.literal_eval(line[len(prefix) :])
            assert isinstance(value, tuple)
            return value
    raise AssertionError(f"missing {prefix!r} observation in {output!r}")


@pytest.mark.parametrize("safe_mode", [False, True], ids=["safe-off", "safe-on"])
@pytest.mark.parametrize("profile", ["code", "script", "pytest", "unittest"])
def test_probe_replays_native_context_in_both_safe_modes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    safe_mode: bool,
    profile: str,
) -> None:
    shadow = tmp_path / "shadow"
    shadow.mkdir()
    if profile in {"code", "script"}:
        for module_name in ("dataclasses", "pathlib"):
            (shadow / f"{module_name}.py").write_text(
                "TARGET_LOCAL = True\n",
                encoding="utf-8",
            )
    if profile != "pytest":
        (shadow / "json.py").write_text(
            "TARGET_LOCAL = True\n",
            encoding="utf-8",
        )
    if profile in {"code", "script"}:
        (shadow / "unittest.py").write_text(
            "TARGET_LOCAL = True\n",
            encoding="utf-8",
        )
    (shadow / "cut_assertion_probe.py").write_text(
        "TARGET_LOCAL = True\n",
        encoding="utf-8",
    )
    environment = os.environ.copy()
    inherited_pythonpath = os.environ.get("PYTHONPATH")
    pythonpath = [
        str(REPO_ROOT / "src"),
        str(shadow),
        str(REPO_ROOT / "shared" / "scripts"),
        str(REPO_ROOT / "vendor"),
    ]
    if inherited_pythonpath:
        pythonpath.append(inherited_pythonpath)
    environment["PYTHONPATH"] = os.pathsep.join(pythonpath)
    if safe_mode:
        environment["PYTHONSAFEPATH"] = "1"
    else:
        environment.pop("PYTHONSAFEPATH", None)
    command = _matrix_command(profile, tmp_path, _native_context_source())

    native = subprocess.run(
        command,
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env=environment,
    )
    assert native.returncode == 1, native.stdout + native.stderr
    native_observation = _observed_matrix_value(native.stdout + native.stderr)

    monkeypatch.setenv("PYTHONPATH", environment["PYTHONPATH"])
    if "PYTHONSAFEPATH" in environment:
        monkeypatch.setenv("PYTHONSAFEPATH", environment["PYTHONSAFEPATH"])
    else:
        monkeypatch.delenv("PYTHONSAFEPATH", raising=False)
    replay = red_gate._run_case(command, tmp_path)
    assert (
        replay.returncode,
        replay.error,
        replay.assertion_origin,
    ) == (1, None, True), replay.output
    replay_observation = _observed_matrix_value(replay.output)
    assert replay_observation == native_observation


def test_issue_rejects_an_unsupported_assertion_proof_runner_without_executing_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    with pytest.raises(red_gate.GateValidationError) as raised:
        _issue(
            _candidate(tmp_path, command=["/bin/false"]),
            _receipt_path(tmp_path),
        )

    assert any(
        "unsupported assertion-proof runner profile" in problem
        for problem in raised.value.problems
    )


def test_contract_red_rejects_text_only_incompatibility_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    candidate = tmp_path / "candidate.json"
    receipt_path = _receipt_path(tmp_path)
    payload = _matrix_candidate(
        tmp_path,
        declared_rows=("only",),
        command=[sys.executable, "-c", "print('outer witness'); raise SystemExit(1)"],
    )
    candidate.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(red_gate.GateValidationError) as raised:
        _issue(candidate, receipt_path)

    assert not receipt_path.exists()
    assert any("assertion-origin" in problem for problem in raised.value.problems)


def test_issue_rejects_production_tree_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    production = tmp_path / "production.py"
    production.write_text("before\n", encoding="utf-8")
    candidate = tmp_path / "candidate.json"
    receipt_path = _receipt_path(tmp_path)
    payload = _candidate(
        tmp_path,
        command=[
            sys.executable,
            "-c",
            "from pathlib import Path; Path('production.py').write_text('changed'); assert False, 'outer witness'",
        ],
    )
    candidate.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(red_gate.GateValidationError) as raised:
        _issue(candidate, receipt_path)

    assert not receipt_path.exists()
    assert any("production-tree" in problem for problem in raised.value.problems)


def test_issue_rejects_hidden_production_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    hidden = tmp_path / ".hidden-production"
    hidden.write_text("before\n", encoding="utf-8")
    candidate = tmp_path / "candidate.json"
    receipt_path = _receipt_path(tmp_path)
    payload = _candidate(
        tmp_path,
        command=[
            sys.executable,
            "-c",
            "from pathlib import Path; Path('.hidden-production').write_text('changed'); assert False, 'outer witness'",
        ],
    )
    candidate.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(red_gate.GateValidationError) as raised:
        _issue(candidate, receipt_path)

    assert not receipt_path.exists()
    assert any(".hidden-production" in problem for problem in raised.value.problems)


@pytest.mark.parametrize("relative_path", ["tests/helper.py", "vendor/dependency.py"])
def test_issue_rejects_replay_mutation_in_source_directories(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    relative_path: str,
) -> None:
    monkeypatch.chdir(tmp_path)
    source = tmp_path / relative_path
    source.parent.mkdir(exist_ok=True)
    source.write_text("before\n", encoding="utf-8")
    candidate = tmp_path / "candidate.json"
    receipt_path = _receipt_path(tmp_path)
    payload = _candidate(
        tmp_path,
        command=[
            sys.executable,
            "-c",
            (
                "from pathlib import Path; "
                f"Path({relative_path!r}).write_text('changed'); "
                "assert False, 'outer witness'"
            ),
        ],
    )
    candidate.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(red_gate.GateValidationError) as raised:
        _issue(candidate, receipt_path)

    assert not receipt_path.exists()
    assert any(relative_path in problem for problem in raised.value.problems)


def test_issue_rejects_symlink_identity_mutation_without_following_link(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "link-target.py"
    target.write_text("target\n", encoding="utf-8")
    link = tmp_path / "production-link.py"
    link.symlink_to(target.name)
    candidate = tmp_path / "candidate.json"
    receipt_path = _receipt_path(tmp_path)
    payload = _candidate(
        tmp_path,
        command=[
            sys.executable,
            "-c",
            (
                "from pathlib import Path; "
                "link=Path('production-link.py'); link.unlink(); "
                "link.symlink_to('other-target.py'); assert False, 'outer witness'"
            ),
        ],
    )
    candidate.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(red_gate.GateValidationError) as raised:
        _issue(candidate, receipt_path)

    assert not receipt_path.exists()
    assert any("production-link.py" in problem for problem in raised.value.problems)


def test_phase_entry_rejects_directory_symlinks_without_following_them(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    external = tmp_path.parent / f"{tmp_path.name}-external-tree"
    external.mkdir()
    (external / "state.txt").write_text("outside\n", encoding="utf-8")
    (tmp_path / "linked-tree").symlink_to(external, target_is_directory=True)
    payload = _candidate(tmp_path)

    with pytest.raises(red_gate.GateValidationError) as raised:
        _begin(payload, "directory-symlink")

    assert any(
        "directory symlink" in problem and "linked-tree" in problem
        for problem in raised.value.problems
    )


def test_issue_refuses_unsupported_production_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    special = tmp_path / "production.fifo"
    os.mkfifo(special)
    candidate = tmp_path / "candidate.json"
    receipt_path = _receipt_path(tmp_path)
    candidate.write_text(json.dumps(_candidate(tmp_path)), encoding="utf-8")

    with pytest.raises(red_gate.GateValidationError) as raised:
        _issue(candidate, receipt_path)

    assert not receipt_path.exists()
    assert any(
        "unsupported filesystem entry" in problem and "production.fifo" in problem
        for problem in raised.value.problems
    )


def test_issue_rejects_shell_shaped_argv_without_executing_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    candidate = tmp_path / "candidate.json"
    receipt_path = _receipt_path(tmp_path)
    payload = _candidate(tmp_path)
    payload["cases"][0]["argv"] = ["sh", "-c", "echo outer witness; exit 1"]
    candidate.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(red_gate.GateValidationError) as raised:
        _issue(candidate, receipt_path)

    assert not receipt_path.exists()
    assert any("shell" in problem for problem in raised.value.problems)


def test_issue_rejects_shell_interpreter_and_long_flag_in_separate_argv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    candidate = tmp_path / "candidate.json"
    receipt_path = _receipt_path(tmp_path)
    payload = _candidate(tmp_path)
    payload["cases"][0]["argv"] = ["env", "bash", "--command", "echo outer witness"]
    candidate.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(red_gate.GateValidationError) as raised:
        _issue(candidate, receipt_path)

    assert not receipt_path.exists()
    assert any("shell interpreter" in problem for problem in raised.value.problems)
    assert any("shell execution flag" in problem for problem in raised.value.problems)


@pytest.mark.parametrize(
    ("argv", "expected_problem"),
    [
        (["env", "-S", "bash -c", "echo outer witness"], "command wrapper"),
        (["ash", "-c", "echo outer witness"], "shell interpreter"),
    ],
)
def test_issue_rejects_indirect_shell_launchers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    argv: list[str],
    expected_problem: str,
) -> None:
    monkeypatch.chdir(tmp_path)
    candidate = tmp_path / "candidate.json"
    receipt_path = _receipt_path(tmp_path)
    payload = _candidate(tmp_path)
    payload["cases"][0]["argv"] = argv
    candidate.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(red_gate.GateValidationError) as raised:
        _issue(candidate, receipt_path)

    assert not receipt_path.exists()
    assert any(expected_problem in problem for problem in raised.value.problems)


def test_issue_rejects_project_runner_symlinked_to_shell(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    runner = tmp_path / "tests" / "runner"
    runner.parent.mkdir(exist_ok=True)
    runner.symlink_to("/bin/sh")
    candidate = tmp_path / "candidate.json"
    receipt_path = _receipt_path(tmp_path)
    payload = _candidate(tmp_path)
    payload["cases"][0]["argv"] = ["tests/runner", "-c", "echo outer witness"]
    candidate.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(red_gate.GateValidationError) as raised:
        _issue(candidate, receipt_path)

    assert not receipt_path.exists()
    assert any("shell interpreter" in problem for problem in raised.value.problems)


def test_validate_accumulates_guard_identity_and_graph_diagnostics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    first = _candidate(tmp_path)
    first["work_id"] = "first"
    first_path = tmp_path / "first.json"
    first_path.write_text(json.dumps(first), encoding="utf-8")
    child = _receipt_path(tmp_path, "first.receipt.json")
    _issue(first_path, child)
    press = _candidate(tmp_path)
    press["producer"] = "press"
    press["guard_receipt_refs"] = [
        child.relative_to(tmp_path).as_posix(),
        child.relative_to(tmp_path).as_posix(),
    ]
    press["work_id"] = "second"
    press_path = tmp_path / "press.json"
    press_path.write_text(json.dumps(press), encoding="utf-8")

    result = red_gate.validate_gate(press_path, "red")

    assert not result.ok
    assert any("duplicate" in problem for problem in result.problems)
    assert any("work_id" in problem for problem in result.problems)


def test_validate_rejects_active_stack_guard_cycle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    first = _candidate(tmp_path)
    first["producer"] = "press"
    first["guard_receipt_refs"] = ["second.json"]
    second = _candidate(tmp_path)
    second["producer"] = "press"
    second["guard_receipt_refs"] = ["first.json"]
    first_path = tmp_path / "first.json"
    second_path = tmp_path / "second.json"
    first_path.write_text(json.dumps(first), encoding="utf-8")
    second_path.write_text(json.dumps(second), encoding="utf-8")

    result = red_gate.validate_gate(first_path, "red")

    assert not result.ok
    assert any("cyclic" in problem for problem in result.problems)


def test_validate_accepts_a_second_repair_guard_diamond(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    def stateful_candidate(state_name: str) -> tuple[dict[str, object], Path]:
        payload = _candidate(tmp_path)
        state = tmp_path / state_name
        state.write_text("red\n", encoding="utf-8")
        payload["cases"][0]["argv"] = [
            sys.executable,
            "-c",
            (
                "from pathlib import Path; "
                f"state=Path({state_name!r}).read_text(); "
                "assert state.strip() != 'red', 'outer witness'"
            ),
        ]
        payload["production_paths"] = [
            "cut-state.txt",
            "first-repair-state.txt",
            "second-repair-state.txt",
            "third-repair-state.txt",
            "fourth-repair-state.txt",
        ]
        return payload, state

    cut, cut_state = stateful_candidate("cut-state.txt")
    cut_receipt_path = _receipt_path(tmp_path, "cut.receipt.json")
    _issue(cut, cut_receipt_path)
    cut_state.write_text("green\n", encoding="utf-8")

    first_repair, first_repair_state = stateful_candidate("first-repair-state.txt")
    first_repair["producer"] = "press"
    first_repair["guard_receipt_refs"] = [
        cut_receipt_path.relative_to(tmp_path).as_posix()
    ]
    first_repair_receipt_path = _receipt_path(
        tmp_path,
        "first-repair.receipt.json",
        producer="press",
    )
    _issue(first_repair, first_repair_receipt_path)
    first_repair_state.write_text("green\n", encoding="utf-8")

    second_repair, second_repair_state = stateful_candidate("second-repair-state.txt")
    second_repair["producer"] = "press"
    second_repair["guard_receipt_refs"] = [
        first_repair_receipt_path.relative_to(tmp_path).as_posix(),
        cut_receipt_path.relative_to(tmp_path).as_posix(),
    ]
    second_repair_receipt_path = _receipt_path(
        tmp_path,
        "second-repair.receipt.json",
        producer="press",
    )
    second_receipt = _issue(second_repair, second_repair_receipt_path)

    result = red_gate.validate_gate(second_repair_receipt_path, "red")

    assert result.ok, result.problems
    second_repair_state.write_text("green\n", encoding="utf-8")

    history_path, _ = red_gate._press_history_paths(tmp_path, second_receipt)
    history = json.loads(history_path.read_text(encoding="utf-8"))
    history["receipts"] = history["receipts"][:1]
    history_path.write_text(json.dumps(history), encoding="utf-8")
    third, third_state = stateful_candidate("third-repair-state.txt")
    third["producer"] = "press"
    third["guard_receipt_refs"] = [
        second_repair_receipt_path.relative_to(tmp_path).as_posix(),
        cut_receipt_path.relative_to(tmp_path).as_posix(),
    ]
    third_receipt_path = _receipt_path(
        tmp_path, "third-repair.receipt.json", producer="press"
    )

    _issue(third, third_receipt_path)

    recovered = json.loads(history_path.read_text(encoding="utf-8"))
    assert recovered["receipts"] == [
        first_repair_receipt_path.relative_to(tmp_path).as_posix(),
        second_repair_receipt_path.relative_to(tmp_path).as_posix(),
        third_receipt_path.relative_to(tmp_path).as_posix(),
    ]
    third_state.write_text("green\n", encoding="utf-8")
    for legacy_receipt_path in (
        first_repair_receipt_path,
        second_repair_receipt_path,
        third_receipt_path,
    ):
        legacy_receipt = json.loads(legacy_receipt_path.read_text(encoding="utf-8"))
        legacy_receipt["phase_token_ref"] = None
        legacy_receipt["phase_token_sha256"] = None
        legacy_receipt_path.write_text(
            json.dumps(legacy_receipt),
            encoding="utf-8",
        )
    history_path.unlink()
    fourth, _ = stateful_candidate("fourth-repair-state.txt")
    fourth["producer"] = "press"
    fourth["guard_receipt_refs"] = [
        third_receipt_path.relative_to(tmp_path).as_posix(),
        cut_receipt_path.relative_to(tmp_path).as_posix(),
    ]

    with pytest.raises(red_gate.GateValidationError) as raised:
        _issue(
            fourth,
            _receipt_path(tmp_path, "fourth-repair.receipt.json", producer="press"),
        )

    assert any(
        "Press history has reached the three RED observation limit" in problem
        for problem in raised.value.problems
    ), raised.value.problems


def test_issue_rejects_a_guard_with_a_tampered_phase_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    cut_receipt_path = _receipt_path(tmp_path, "guard-token.cut.json")
    cut_receipt = _issue(_candidate(tmp_path), cut_receipt_path)
    assert cut_receipt.phase_token_ref is not None
    (tmp_path / "production-state.txt").write_text("green\n", encoding="utf-8")

    press = _candidate(tmp_path)
    (tmp_path / "production-state.txt").write_text("green\n", encoding="utf-8")
    press_state = tmp_path / "press-state.txt"
    press_state.write_text("red\n", encoding="utf-8")
    press["producer"] = "press"
    press["guard_receipt_refs"] = [cut_receipt_path.relative_to(tmp_path).as_posix()]
    press["cases"][0]["argv"] = [
        sys.executable,
        "-c",
        (
            "from pathlib import Path; "
            "state=Path('press-state.txt').read_text(); "
            "assert state.strip() != 'red', 'outer witness'"
        ),
    ]
    token_path = tmp_path / cut_receipt.phase_token_ref
    token_path.write_text(
        token_path.read_text(encoding="utf-8") + " ",
        encoding="utf-8",
    )
    output = _receipt_path(tmp_path, "guard-token.press.json", producer="press")

    with pytest.raises(red_gate.GateValidationError) as raised:
        _issue(press, output)

    assert not output.exists()
    assert any(
        "phase_token_sha256 is stale" in problem for problem in raised.value.problems
    )


def test_phase_entry_token_allows_only_the_declared_new_oracle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    payload = _candidate(tmp_path)
    oracle = tmp_path / "tests" / "oracle.py"
    oracle.unlink()

    token, token_path, candidate = _begin(payload, "pre-cut")
    oracle.write_text("oracle\n", encoding="utf-8")
    payload.update(token.to_dict())
    candidate.write_text(json.dumps(payload), encoding="utf-8")
    receipt_path = _receipt_path(tmp_path, "pre-cut.receipt.json")

    receipt = red_gate.issue_gate(candidate, receipt_path, token_path)

    assert receipt_path.exists()
    assert receipt.phase_token_ref == token.phase_token_ref
    assert receipt.phase_token_sha256 == token.phase_token_sha256


def test_phase_entry_rejects_modifying_a_pre_existing_protected_oracle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    payload = _candidate(tmp_path)
    oracle = tmp_path / "tests" / "oracle.py"
    token, token_path, candidate = _begin(payload, "existing-oracle")
    oracle.write_text("weakened oracle\n", encoding="utf-8")
    payload["protected_files"][0]["sha256"] = _digest(oracle)
    payload.update(token.to_dict())
    candidate.write_text(json.dumps(payload), encoding="utf-8")
    receipt_path = _receipt_path(tmp_path, "existing-oracle.receipt.json")

    with pytest.raises(red_gate.GateValidationError) as raised:
        red_gate.issue_gate(candidate, receipt_path, token_path)

    assert not receipt_path.exists()
    assert any(
        "project file changed since phase entry: tests/oracle.py" in problem
        for problem in raised.value.problems
    )


def test_not_applicable_issuance_requires_and_persists_phase_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    payload = _candidate(tmp_path)
    approved_spec = Path(str(payload["spec_ref"]))
    approved_spec.write_text(
        """---
status: approved
gate_applicability:
  disposition: not-applicable
  work_class: appearance-only
  ui_surface: not-applicable
  reason: appearance-only change
---
# Appearance-only change
""",
        encoding="utf-8",
    )
    payload.update(
        disposition="not-applicable",
        spec_sha256=_digest(approved_spec),
        contracts=[],
        baseline_checks=[],
        cases=[],
        protected_files=[],
        not_applicable_reason="appearance-only change",
    )
    receipt_path = _receipt_path(tmp_path, "not-applicable.receipt.json")

    receipt = _issue(payload, receipt_path)

    assert receipt_path.exists()
    assert receipt.phase_token_ref is not None
    assert receipt.phase_token_sha256 is not None


def test_not_applicable_issuance_requires_the_exact_approved_reason(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    payload = _candidate(tmp_path)
    approved_spec = Path(str(payload["spec_ref"]))
    approved_spec.write_text(
        """---
status: approved
gate_applicability:
  disposition: not-applicable
  work_class: appearance-only
  ui_surface: not-applicable
  reason: approved appearance reason
---
# Appearance-only change
""",
        encoding="utf-8",
    )
    payload.update(
        disposition="not-applicable",
        spec_sha256=_digest(approved_spec),
        contracts=[],
        baseline_checks=[],
        cases=[],
        protected_files=[],
        not_applicable_reason="unrelated reason",
    )

    with pytest.raises(red_gate.GateValidationError) as raised:
        _issue(
            payload,
            _receipt_path(tmp_path, "wrong-reason.receipt.json"),
        )

    assert any(
        "not_applicable_reason does not match the exact spec reason" in problem
        for problem in raised.value.problems
    )


def test_phase_entry_token_rejects_production_changes_before_issue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    production = tmp_path / "production.py"
    production.write_text("before\n", encoding="utf-8")
    payload = _candidate(tmp_path)
    token, token_path, candidate = _begin(payload, "changed-production")
    production.write_text("after\n", encoding="utf-8")
    payload.update(token.to_dict())
    candidate.write_text(json.dumps(payload), encoding="utf-8")
    receipt_path = _receipt_path(tmp_path, "changed-production.receipt.json")

    with pytest.raises(red_gate.GateValidationError) as raised:
        red_gate.issue_gate(candidate, receipt_path, token_path)

    assert not receipt_path.exists()
    assert any(
        "project file changed since phase entry: production.py" in problem
        for problem in raised.value.problems
    )


def test_phase_begin_rejects_a_failing_baseline_without_writing_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    payload = _candidate(tmp_path)
    payload["baseline_checks"][0]["argv"] = [
        sys.executable,
        "-c",
        "raise SystemExit(3)",
    ]

    with pytest.raises(red_gate.GateValidationError) as raised:
        _begin(payload, "bad-baseline")

    assert any("is not green: exit 3" in problem for problem in raised.value.problems)
    assert not list((tmp_path / ".cheese" / "cut").glob("*.phase.json"))


def test_issue_rejects_an_external_spec_changed_during_replay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    payload = _candidate(tmp_path)
    external_spec = tmp_path.parent / f"{tmp_path.name}-approved.md"
    _spec(external_spec, "outer behavior")
    payload["spec_ref"] = str(external_spec)
    payload["spec_sha256"] = _digest(external_spec)
    payload["cases"][0]["argv"] = [
        sys.executable,
        "-c",
        (
            "from pathlib import Path; "
            f"spec=Path({str(external_spec)!r}); "
            "spec.write_text(spec.read_text() + '\\n', encoding='utf-8'); "
            "assert False, 'outer witness'"
        ),
    ]
    receipt_path = _receipt_path(tmp_path, "external-spec.receipt.json")

    with pytest.raises(red_gate.GateValidationError) as raised:
        _issue(payload, receipt_path)

    assert not receipt_path.exists()
    assert any(
        "spec_sha256 is stale" in problem or "changed during issue" in problem
        for problem in raised.value.problems
    )


def test_validate_rejects_an_external_spec_changed_during_replay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    payload = _candidate(tmp_path)
    external_spec = tmp_path.parent / f"{tmp_path.name}-validate-approved.md"
    _spec(external_spec, "outer behavior")
    payload["spec_ref"] = str(external_spec)
    payload["spec_sha256"] = _digest(external_spec)
    payload["cases"][0]["argv"] = [
        sys.executable,
        "-c",
        (
            "from pathlib import Path; "
            "state=Path('production-state.txt').read_text().strip(); "
            f"spec=Path({str(external_spec)!r}); "
            "spec.write_text(spec.read_text() + '\\n', encoding='utf-8') "
            "if state == 'green' else None; "
            "assert state != 'red', 'outer witness'"
        ),
    ]
    receipt_path = _receipt_path(tmp_path, "external-spec-validation.receipt.json")
    _issue(payload, receipt_path)
    (tmp_path / "production-state.txt").write_text("green\n", encoding="utf-8")

    result = red_gate.validate_gate(receipt_path, "green")

    assert not result.ok
    assert any(
        "spec_sha256 is stale" in problem
        or "receipt file changed during validation" in problem
        for problem in result.problems
    )


def test_issue_rejects_a_tampered_or_wrong_identity_phase_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    payload = _candidate(tmp_path)
    token, token_path, candidate = _begin(payload, "tampered")
    payload.update(token.to_dict())
    payload["work_id"] = "different-work"
    candidate.write_text(json.dumps(payload), encoding="utf-8")
    token_path.write_text(
        token_path.read_text(encoding="utf-8") + " ", encoding="utf-8"
    )

    with pytest.raises(red_gate.GateValidationError) as raised:
        red_gate.issue_gate(
            candidate,
            _receipt_path(tmp_path, "tampered.receipt.json"),
            token_path,
        )

    assert any(
        "phase_token_sha256 is stale" in problem for problem in raised.value.problems
    )
    assert any("work_id does not match" in problem for problem in raised.value.problems)


def test_inherited_phase_token_replays_but_cannot_be_reissued_or_tampered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    child = tmp_path / "child"
    source.mkdir()
    child.mkdir()
    monkeypatch.chdir(source)
    receipt_path = _receipt_path(source, "inherited.receipt.json")
    receipt = _issue(_candidate(source), receipt_path)
    assert receipt.phase_token_ref is not None
    receipt_relative = receipt_path.relative_to(source)
    token_relative = Path(receipt.phase_token_ref)
    for relative in (
        Path("approved.md"),
        Path("tests/oracle.py"),
        Path("production-state.txt"),
        receipt_relative,
        token_relative,
    ):
        target = child / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((source / relative).read_bytes())

    monkeypatch.chdir(child)
    result = red_gate.validate_gate(receipt_relative, "red")
    assert result.ok, result.problems

    with pytest.raises(red_gate.GateValidationError) as raised:
        red_gate.issue_gate(
            receipt.to_dict(),
            _receipt_path(child, "reissued.receipt.json"),
            token_relative,
        )
    assert any(
        "project_root does not match the current project root" in problem
        for problem in raised.value.problems
    )

    token_path = child / token_relative
    token_path.write_text(
        token_path.read_text(encoding="utf-8") + " ",
        encoding="utf-8",
    )
    tampered = red_gate.validate_gate(receipt_relative, "red")
    assert not tampered.ok
    assert any(
        "phase_token_sha256 is stale" in problem for problem in tampered.problems
    )

    token_path.unlink()
    missing = red_gate.validate_gate(receipt_relative, "red")
    assert not missing.ok
    assert any("phase token is missing" in problem for problem in missing.problems)


def test_issue_cli_has_no_tokenless_issuance_form(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    candidate = tmp_path / "candidate.json"
    candidate.write_text(json.dumps(_candidate(tmp_path)), encoding="utf-8")

    code = red_gate.main(["issue", str(candidate), "--out", "receipt.json"])

    assert code == 1
    assert "--token <token>" in capsys.readouterr().err


def test_run_case_reports_missing_probe_event_as_harness_error(
    tmp_path: Path,
) -> None:
    run = red_gate._run_case(
        [sys.executable, "-c", "import os; os._exit(1)"],
        tmp_path,
    )

    assert run.error == "assertion probe event missing or invalid"
    assert red_gate._looks_harness_failure(run)


def test_missing_probe_event_validation_problem_has_bounded_context(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    discarded_prefix = "discarded-prefix"
    marker = "probe-context"
    output = discarded_prefix + "x" * 300 + marker + "-outer witness-suffix"
    command = [
        sys.executable,
        "-c",
        f"import os, sys; sys.stdout.write({output!r}); "
        "sys.stdout.flush(); os._exit(23)",
    ]
    receipt_path = _receipt_path(tmp_path)

    candidate = _candidate(tmp_path, command=command)
    candidate["cases"][0]["observed_exit_code"] = 23
    with pytest.raises(red_gate.GateValidationError) as raised:
        _issue(candidate, receipt_path)

    expected_tail = "..." + output[-252:] + "'"
    expected_problem = (
        "GateReceipt.cases[1] failed in the harness: "
        "assertion probe event missing or invalid "
        f"(exit 23; output tail: {expected_tail})"
    )
    assert raised.value.problems == (expected_problem,)
    assert len(expected_tail) == 256
    assert marker in expected_problem
    assert discarded_prefix not in expected_problem

def test_source_probe_uses_canonical_worker_over_cwd_shadow(
    tmp_path: Path,
) -> None:
    (tmp_path / "cut_assertion_probe.py").write_text(
        "TARGET_LOCAL = True\n",
        encoding="utf-8",
    )
    run = red_gate._run_case(
        [
            sys.executable,
            "-c",
            (
                f"import sys, cut_assertion_probe; "
                f"assert sys.flags.safe_path is {sys.flags.safe_path!r}; "
                "assert cut_assertion_probe.TARGET_LOCAL is True; "
                "raise AssertionError('source bootstrap witness')"
            ),
        ],
        tmp_path,
    )

    assert run.error is None
    assert run.returncode == 1
    assert run.assertion_origin is True
    assert run.output.splitlines()[-1] == "AssertionError: source bootstrap witness"


def test_source_probe_quarantines_inherited_json_shadow(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PYTHONPATH", str(tmp_path))
    (tmp_path / "json.py").write_text(
        "TARGET_LOCAL = True\n",
        encoding="utf-8",
    )

    run = red_gate._run_case(
        [
            sys.executable,
            "-c",
            (
                "import json; "
                "assert json.TARGET_LOCAL is True; "
                "raise AssertionError('json shadow witness')"
            ),
        ],
        tmp_path,
    )

    assert run.error is None
    assert run.returncode == 1
    assert run.assertion_origin is True
    assert run.output.splitlines()[-1] == "AssertionError: json shadow witness"
