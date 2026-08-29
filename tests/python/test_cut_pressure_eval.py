"""Pressure-evaluate the durable Cut workflow against its pre-skill failure."""

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import cast

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL = REPO_ROOT / "skills" / "cut" / "SKILL.md"
PRESSURE = REPO_ROOT / "skills" / "cut" / "references" / "pressure-eval.md"
RED_GATE = REPO_ROOT / "skills" / "cut" / "scripts" / "cut.pyz"


def _body(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    return parts[2] if len(parts) == 3 and parts[0].strip() == "" else text


def _section(text: str, heading: str) -> str:
    match = re.search(rf"^## {re.escape(heading)}\s*$", text, re.MULTILINE)
    assert match, f"missing ## {heading}"
    tail = text[match.end() :]
    next_heading = re.search(r"^## \S.*$", tail, re.MULTILINE)
    return tail[: next_heading.start()] if next_heading else tail


def _events(section: str) -> tuple[str, ...]:
    match = re.search(r"^events:\n(?P<body>(?:- .+\n)+)", section, re.MULTILINE)
    assert match, f"missing event trace in section:\n{section}"
    return tuple(line[2:] for line in match.group("body").splitlines())


def _corrected_trace_passes(section: str) -> bool:
    events = _events(section)
    required = (
        "read-spec",
        "red-gate-contracts",
        "select-or-infer-contracts",
        "select-existing-runner",
        "write-test-only-tracer",
        "baseline-green",
        "declared-red-witness",
        "protected-test-digests",
        "red-gate-issue",
        "return-receipt-to-cook",
        "no-recursive-cook-dispatch",
    )
    if events != required:
        return False
    return (
        "production_edit_before_issue: false" in section
        and "production_edit_during_issue: false" in section
        and "initial_guard_receipt_refs: []" in section
        and "producer: cut" in section
        and re.search(r"status: ok\s+next: cook\s+artifact: \.cheese/cut/<slug>\.json", section)
        is not None
    )


def _oracle_sensitivity_passes(section: str) -> bool:
    required_rows = (
        "oracle-sensitivity: required",
        "mutation: remove expected witness -> reject",
        "absence: remove baseline check -> reject",
        "mutation: change production file -> reject",
        "absence: remove protected test digest -> reject",
        "absence: replace red-gate issue with raw receipt write -> reject",
        "absence: use an unavailable runner without a harness decision -> reject",
    )
    return all(row in section for row in required_rows)


def test_pressure_fixture_has_the_two_required_verdict_sections() -> None:
    text = PRESSURE.read_text(encoding="utf-8")
    assert text.startswith("# Cut pressure evaluation\n")
    baseline = _section(text, "Failing pre-skill baseline")
    corrected = _section(text, "Corrected durable workflow")
    assert "baseline_verdict: fail" in baseline
    assert "corrected_verdict: pass" in corrected
    assert "no Cut skill loaded" in baseline


def test_pre_skill_baseline_fails_before_durable_outer_red() -> None:
    baseline = _section(PRESSURE.read_text(encoding="utf-8"), "Failing pre-skill baseline")
    events = _events(baseline)
    assert events[0] == "read-spec"
    assert events.index("production-edit:first") < events.index("write-test")
    assert "red-gate-issue" not in events
    assert "baseline_artifact: absent" in baseline
    assert "baseline_handoff: absent" in baseline


def test_corrected_workflow_preserves_order_and_receipt_boundary() -> None:
    corrected = _section(PRESSURE.read_text(encoding="utf-8"), "Corrected durable workflow")
    assert _corrected_trace_passes(corrected)
    events = _events(corrected)
    assert events.index("baseline-green") < events.index("declared-red-witness")
    assert events.index("declared-red-witness") < events.index("red-gate-issue")
    assert not any(event.startswith("production-edit") for event in events)


def test_corrected_workflow_keeps_synchronous_cook_non_recursive() -> None:
    corrected = _section(PRESSURE.read_text(encoding="utf-8"), "Corrected durable workflow")
    events = _events(corrected)
    assert events[-2:] == ("return-receipt-to-cook", "no-recursive-cook-dispatch")
    assert "dispatch-cook-with-receipt" in corrected
    assert "issue the receipt first" in corrected


def test_oracle_sensitivity_is_required_and_each_absence_is_rejected() -> None:
    section = _section(PRESSURE.read_text(encoding="utf-8"), "Oracle-sensitivity mutations")
    assert _oracle_sensitivity_passes(section)
    rows = (
        "oracle-sensitivity: required",
        "mutation: remove expected witness -> reject",
        "absence: remove baseline check -> reject",
        "mutation: change production file -> reject",
        "absence: remove protected test digest -> reject",
        "absence: replace red-gate issue with raw receipt write -> reject",
        "absence: use an unavailable runner without a harness decision -> reject",
    )
    for row in rows:
        mutated = section.replace(row, "", 1)
        assert mutated != section, f"fixture did not contain mutation row: {row}"
        assert not _oracle_sensitivity_passes(mutated), (
            f"oracle evaluator became insensitive when this row disappeared: {row}"
        )


def test_ac_12_executes_pre_cut_baseline_and_corrected_trace(tmp_path: Path) -> None:
    baseline_root = tmp_path / "pre-cut"
    baseline_root.mkdir()
    (baseline_root / ".cheese").mkdir()
    (baseline_root / "tests").mkdir()
    baseline_driver = baseline_root / "baseline.py"
    _ = baseline_driver.write_text(
        """
from pathlib import Path

root = Path.cwd()
trace = root / ".cheese" / "trace.log"
def event(name):
    trace.open("a", encoding="utf-8").write(name + "\\n")
event("read-spec")
(root / "production.py").write_text("implemented-before-red\\n", encoding="utf-8")
event("production-edit:first")
(root / "tests" / "test_behavior.py").write_text("assert True\\n", encoding="utf-8")
event("write-test")
event("run-tests-after-production-edit")
event("report-green")
raise SystemExit(1)
""".lstrip(),
        encoding="utf-8",
    )
    baseline = subprocess.run(
        [sys.executable, str(baseline_driver)],
        cwd=baseline_root,
        capture_output=True,
        text=True,
    )
    assert baseline.returncode == 1
    baseline_events = (baseline_root / ".cheese" / "trace.log").read_text(
        encoding="utf-8"
    ).splitlines()
    assert baseline_events.index("production-edit:first") < baseline_events.index(
        "write-test"
    )
    assert not (baseline_root / ".cheese" / "cut.json").exists()

    corrected_root = tmp_path / "with-cut"
    corrected_root.mkdir()
    _record_event(corrected_root, "read-spec")
    _record_event(corrected_root, "cut-skill-active")
    _, candidate, receipt, token = _write_cut_project(corrected_root)
    _record_event(corrected_root, "red-gate-issue:start")
    issued = _red_gate_cli(
        corrected_root,
        "issue",
        str(candidate.relative_to(corrected_root)),
        "--token",
        str(token.relative_to(corrected_root)),
        "--out",
        str(receipt.relative_to(corrected_root)),
    )
    assert issued.returncode == 0, issued.stdout + issued.stderr
    _record_event(corrected_root, "red-gate-issue:ok")
    assert receipt.exists()
    _record_event(corrected_root, "production-edit:first")
    _ = (corrected_root / "production.py").write_text(
        "implemented-after-red\n", encoding="utf-8"
    )
    corrected_events = (corrected_root / ".cheese" / "trace.log").read_text(
        encoding="utf-8"
    ).splitlines()
    baseline_positions = [
        index
        for index, event in enumerate(corrected_events)
        if event == "baseline-green"
    ]
    assert len(baseline_positions) == 2
    required = (
        "read-spec",
        "cut-skill-active",
        "red-gate-begin:start",
        "red-gate-begin:ok",
        "oracle:write",
        "red-gate-issue:start",
        "declared-red-witness",
        "red-gate-issue:ok",
        "production-edit:first",
    )
    positions = [corrected_events.index(event) for event in required]
    assert positions == sorted(positions)
    assert corrected_events.index("red-gate-begin:start") < baseline_positions[0]
    assert baseline_positions[0] < corrected_events.index("red-gate-begin:ok")
    assert corrected_events.index("red-gate-issue:start") < baseline_positions[1]
    assert baseline_positions[1] < corrected_events.index("declared-red-witness")

def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _record_event(root: Path, event: str) -> None:
    trace = root / ".cheese" / "trace.log"
    trace.parent.mkdir(parents=True, exist_ok=True)
    with trace.open("a", encoding="utf-8") as stream:
        _ = stream.write(event + "\n")


def _red_gate_cli(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(RED_GATE), "red-gate", *args],
        cwd=root,
        capture_output=True,
        text=True,
    )


def _write_cut_project(
    root: Path,
    *,
    failure: str = "none",
    origin: str = "generated",
) -> tuple[Path, Path, Path, Path]:
    tests = root / "tests"
    namespace = root / ".cheese" / "cut"
    candidates = namespace / "candidates"
    tests.mkdir(parents=True)
    candidates.mkdir(parents=True)
    _ = (root / "production.py").write_text("before\n", encoding="utf-8")
    baseline = tests / "baseline.py"
    _ = baseline.write_text(
        """
from pathlib import Path
trace = Path(".cheese") / "trace.log"
trace.parent.mkdir(parents=True, exist_ok=True)
trace.open("a", encoding="utf-8").write("baseline-green\\n")
raise SystemExit(1 if (Path(".cheese") / "fail-baseline").exists() else 0)
""".lstrip(),
        encoding="utf-8",
    )
    spec = root / "spec.md"
    _ = spec.write_text(
        """---
status: approved
gate_applicability:
  disposition: red-required
  work_class: behavior
---
# Approved spec

## Acceptance Criteria
- AC-3: outer RED must expose assertion-witness.

## Test Contracts
| Acceptance | Interface referent | Outermost stable seam | Expected failure | Mode |
| --- | --- | --- | --- | --- |
| AC-3 | temporary project behavior | temporary project behavior | assertion-witness | tracer |
""",
        encoding="utf-8",
    )
    plan = namespace / "pressure.plan.json"
    token = namespace / "pressure.phase.json"
    _ = plan.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "work_id": "pressure-work",
                "project_key": "pressure-project",
                "producer": "cut",
                "production_paths": ["production.py"],
                "baseline_checks": [
                    {
                        "id": "baseline",
                        "argv": [sys.executable, "tests/baseline.py"],
                        "cwd": ".",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    _record_event(root, "red-gate-begin:start")
    begun = _red_gate_cli(
        root,
        "begin",
        str(plan.relative_to(root)),
        "--out",
        str(token.relative_to(root)),
    )
    assert begun.returncode == 0, begun.stdout + begun.stderr
    phase = cast(dict[str, object], json.loads(begun.stdout))
    _record_event(root, "red-gate-begin:ok")
    if failure == "baseline":
        (root / ".cheese" / "fail-baseline").touch()

    oracle = tests / "oracle.py"
    _ = oracle.write_text("outer oracle\n", encoding="utf-8")
    _record_event(root, "oracle:write")
    case = tests / "case.py"
    case_body = """
from pathlib import Path
trace = Path(".cheese") / "trace.log"
trace.parent.mkdir(parents=True, exist_ok=True)
trace.open("a", encoding="utf-8").write("declared-red-witness\\n")
"""
    if failure == "harness":
        case_body += "raise RuntimeError('broken harness')\n"
    elif failure == "production":
        case_body += "Path('production.py').write_text('changed\\n', encoding='utf-8')\n"
    _ = case.write_text(
        case_body + "print('assertion-witness')\nassert False, 'assertion-witness'\n",
        encoding="utf-8",
    )
    candidate = candidates / "pressure.json"
    receipt = namespace / "pressure.receipt.json"
    _ = candidate.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "work_id": "pressure-work",
                "project_key": "pressure-project",
                "producer": "cut",
                "disposition": "red",
                "spec_ref": "spec.md",
                "spec_sha256": _sha256(spec),
                "phase_token_ref": phase["phase_token_ref"],
                "phase_token_sha256": phase["phase_token_sha256"],
                "guard_receipt_refs": [],
                "contracts": [
                    {
                        "acceptance_id": "AC-3",
                        "interface": "temporary project behavior",
                        "seam": "temporary project behavior",
                        "expected_failure": "assertion-witness",
                        "mode": "tracer",
                        "contract_source": "approved",
                    }
                ],
                "baseline_checks": [
                    {
                        "id": "baseline",
                        "argv": [sys.executable, "tests/baseline.py"],
                        "cwd": ".",
                        "observed_exit_code": 0,
                    }
                ],
                "cases": [
                    {
                        "id": "AC-3-tracer",
                        "acceptance_ids": ["AC-3"],
                        "curd": "pressure",
                        "seam": "temporary project behavior",
                        "argv": [sys.executable, "tests/case.py"],
                        "cwd": ".",
                        "kind": "behavior",
                        "origin": origin,
                        "expected_witness": ["assertion-witness"],
                        "observed_exit_code": 1,
                        "observed_witness": "assertion-witness",
                    }
                ],
                "protected_files": [
                    {"path": "tests/oracle.py", "sha256": _sha256(oracle)},
                    {"path": "tests/case.py", "sha256": _sha256(case)},
                    {"path": "tests/baseline.py", "sha256": _sha256(baseline)},
                ],
                "not_applicable_reason": None,
            }
        ),
        encoding="utf-8",
    )
    return root, candidate, receipt, token


@pytest.mark.parametrize(
    ("failure", "expected_problem"),
    [
        ("production", "production-tree"),
        ("harness", "harness"),
        ("baseline", "baseline_checks[1] is not GREEN"),
    ],
)
def test_ac_3_issue_rejects_runtime_red_evidence_failures(
    tmp_path: Path,
    failure: str,
    expected_problem: str,
) -> None:
    root, candidate, receipt, token = _write_cut_project(tmp_path, failure=failure)
    result = _red_gate_cli(
        root,
        "issue",
        str(candidate.relative_to(root)),
        "--token",
        str(token.relative_to(root)),
        "--out",
        str(receipt.relative_to(root)),
    )
    assert result.returncode != 0
    assert not receipt.exists()
    assert expected_problem in result.stdout + result.stderr

def test_pressure_reference_is_reachable_from_skill_without_second_hop() -> None:
    skill = _body(SKILL)
    assert "references/pressure-eval.md" in skill
    reference = PRESSURE.read_text(encoding="utf-8")
    assert not re.search(r"\]\((?:references/|\.\./)[^)]+\)", reference)
