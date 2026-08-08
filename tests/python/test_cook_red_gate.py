"""Executable contract tests for Cook's outside-in RED boundary.

The source-section checks retain the vocabulary contract, while the runtime
fixtures below invoke the real red-gate CLI in isolated temporary projects.
"""

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src" / "fanout"))
import baseline  # noqa: E402

SKILL = ROOT / "skills" / "cook" / "SKILL.md"
TDD_LOOP = ROOT / "skills" / "cook" / "references" / "tdd-loop.md"
AUTO_MODE = ROOT / "skills" / "cook" / "references" / "auto-mode.md"
RED_GATE = ROOT / "skills" / "cut" / "scripts" / "cut.pyz"

def _body(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    return parts[2] if len(parts) == 3 and parts[0].strip() == "" else text


def _section(path: Path, heading: str) -> str:
    body = _body(path)
    match = re.search(rf"^## {re.escape(heading)}\s*$", body, re.MULTILINE)
    assert match, f"{path} has no ## {heading} section"
    tail = body[match.end() :]
    next_heading = re.search(r"^## \S.*$", tail, re.MULTILINE)
    return tail[: next_heading.start()] if next_heading else tail


def _flat(text: str) -> str:
    return " ".join(text.split())


def test_contract_makes_canonical_receipt_the_outer_boundary() -> None:
    contract = _flat(_section(SKILL, "Contract"))
    assert re.search(
        r"cook\(spec_ref, receipt\? = null, correction = false\) -> "
        r"handoff\(next = press \| age\)",
        contract,
    )
    assert "sole outer-oracle authority" in contract
    assert "canonical receipt before any production mutation" in contract
    assert "same `spec_ref`" in contract
    assert "canonical `work_id`" in contract
    assert "sanitized `project_key`" in contract


def test_preflight_invokes_cut_once_and_consumes_frozen_baseline_before_mutation() -> None:
    preflight = _flat(_section(SKILL, "GateReceipt preflight"))
    required_order = (
        "Resolve the approved spec",
        "receipt is absent or fails canonical loading",
        "synchronously invoke `/cut`",
        "valid RED receipt",
        "red-gate validate <receipt> --state red",
        "no production path may run before",
        "Consume the receipt's frozen pre-Cut broad-gate `baseline_checks` exactly",
        "do not overwrite them or capture a replacement",
    )
    positions = [preflight.index(marker) for marker in required_order]
    assert positions == sorted(positions)
    assert "consume its returned receipt exactly once" in preflight
    assert "never dispatches Cook back into this call" in preflight
    assert "Baseline argv must exclude protected RED-oracle paths or remain green" in preflight


def test_adopted_reproduction_keeps_cut_provenance() -> None:
    for path, heading in (
        (SKILL, "Contract"),
        (TDD_LOOP, "Preflight — canonical outer receipt"),
    ):
        section = _flat(_section(path, heading))
        assert "user or Pasteurize reproduction" in section
        assert "producer: cut" in section
        assert "origin: adopted" in section


def test_preflight_checks_identity_hashes_and_guard_graph() -> None:
    section = _flat(_section(TDD_LOOP, "Preflight — canonical outer receipt"))
    required = (
        "same `spec_ref`, `work_id`, and sanitized `project_key`",
        "Every protected-file hash",
        "complete guard graph",
        "matching work/spec/project identity",
        "required transitive Cut ancestry",
        "red-gate validate <receipt> --state red",
    )
    for phrase in required:
        assert phrase in section


def test_inner_tdd_is_the_only_production_mutation_stage() -> None:
    inner = _flat(_section(TDD_LOOP, "Inner TDD — failing tests first"))
    assert "Cut owns the outer RED evidence" in inner
    assert "only stage allowed to mutate production" in inner
    assert "never change receipt-protected files" in inner
    assert "outer oracle" in inner
    assert "their digests" in inner


def test_green_exit_requires_active_and_transitive_guards_before_press() -> None:
    implement = _flat(_section(TDD_LOOP, "Implement — minimal green"))
    assert implement.index("Before handing off to Press") < implement.index(
        "red-gate validate <receipt> --state green"
    )
    assert "active case and every transitive guard GREEN" in implement
    flow = _flat(_section(SKILL, "Flow"))
    assert flow.index("red-gate validate <receipt> --state red") < flow.index(
        "red-gate validate <receipt> --state green"
    )
    assert flow.index("red-gate validate <receipt> --state green") < flow.index(
        "Taste-test"
    )


def test_correction_is_scoped_to_active_press_receipt_and_guards() -> None:
    contract = _flat(_section(SKILL, "Contract"))
    implement = _flat(_section(TDD_LOOP, "Implement — minimal green"))
    for section in (contract, implement):
        assert "correction = true" in section
        assert "active Press RED receipt" in section
        assert "may not weaken" in section
        assert "transitive guard" in section


def test_closed_na_skips_only_red_replay_then_runs_requested_work() -> None:
    contract = _flat(_section(SKILL, "Contract"))
    preflight = _flat(_section(SKILL, "GateReceipt preflight"))
    for section in (contract, preflight):
        assert "identity and structural validation" in section
        assert "skip only outer RED replay" in section
        assert "non-behavior" in section
        assert "return promptly" not in section
    assert "requested docs/refactor/test/appearance work" in contract
    assert "requested work" in preflight
    assert "Do not treat N/A as no work" in preflight


def test_fan_and_manual_pipeline_keep_one_cut_boundary() -> None:
    fan = _flat(_section(SKILL, "Fan pathway"))
    assert "GateReceipt preflight" in fan
    assert "Cut runs before Seed" in fan
    assert "same protected oracle" in fan
    handoff = _flat(_section(SKILL, "Handoff"))
    assert (
        "culture → mold → **[cut]** → cook → press → age → cure → plate"
        in handoff
    )


def test_auto_mode_cannot_bypass_preflight_or_recurse_from_cut() -> None:
    auto = _flat(_section(AUTO_MODE, "Cook entry preflight"))
    assert "same `cook(spec_ref, receipt? = null, correction = false)`" in auto
    assert "never bypasses the canonical GateReceipt boundary" in auto
    assert "synchronously invokes `/cut`" in auto
    assert "does not recursively hand off from Cut back to Cook" in auto
    assert "red-gate validate <receipt> --state red" in auto
    assert "red-gate validate <receipt> --state green" in auto
    chain = _flat(_section(AUTO_MODE, "No-chain isolation directive"))
    assert "returns a receipt to the current Cook call" in chain
    assert "never chains Cook recursively" in chain


def test_broad_quality_baseline_is_cut_owned_and_receipt_carried() -> None:
    baseline = _flat(_section(SKILL, "Baseline capture"))
    required_order = (
        "Cut owns the outer baseline",
        "pre-oracle tree",
        "freezes `baseline_checks` in the receipt",
        "before the protected RED oracle",
        "Cook validates and consumes",
        "it never recaptures or replaces it",
        "quality-debt comparison",
        "before any curd cooks",
        "pre-change tree",
        "Neither replaces Cut's receipt",
    )
    positions = [baseline.index(marker) for marker in required_order]
    assert positions == sorted(positions)
    assert "intentional-RED exclusion" in baseline
    assert "references/quality-gates.md" in baseline

def test_current_gate_comparison_excludes_only_receipt_outer_red() -> None:
    frozen = [
        {"suite": "broad", "test_id": "existing-debt", "signature": "AssertionError: old"}
    ]
    intentional_red = {
        "suite": "outer",
        "test_id": "AC-5-tracer",
        "signature": "AssertionError: assertion-witness",
    }
    new_failure = {
        "suite": "broad",
        "test_id": "new-regression",
        "signature": "TypeError: fresh",
    }
    receipt_case = {
        "seam": "Cook preflight",
        "id": "AC-5-tracer",
        "expected_witness": ["assertion-witness"],
    }
    current = frozen + [intentional_red, new_failure]
    current_for_classification = [
        record
        for record in current
        if not (
            record["test_id"] == receipt_case["id"]
            and any(
                witness in record["signature"]
                for witness in receipt_case["expected_witness"]
            )
        )
    ]
    classified = baseline.classify(frozen, current_for_classification)
    assert classified["identical"] == frozen
    assert classified["new"] == [new_failure]
    assert intentional_red not in classified["identical"]
    assert intentional_red not in classified["new"]


def _cook_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _cook_event(root: Path, event: str) -> None:
    trace = root / ".cheese" / "trace.log"
    trace.parent.mkdir(parents=True, exist_ok=True)
    with trace.open("a", encoding="utf-8") as stream:
        stream.write(event + "\n")


def _run_cook_red_gate(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(RED_GATE), "red-gate", *args],
        cwd=root,
        capture_output=True,
        text=True,
    )


def _write_cook_project(root: Path, *, origin: str) -> tuple[Path, Path, Path]:
    tests = root / "tests"
    namespace = root / ".cheese" / "cut"
    candidates = namespace / "candidates"
    tests.mkdir(parents=True)
    candidates.mkdir(parents=True)
    (root / "production.py").write_text("before\n", encoding="utf-8")
    baseline = tests / "baseline.py"
    baseline.write_text(
        """
from pathlib import Path
trace = Path(".cheese") / "trace.log"
trace.parent.mkdir(parents=True, exist_ok=True)
trace.open("a", encoding="utf-8").write("baseline-green\\n")
raise SystemExit(0)
""".lstrip(),
        encoding="utf-8",
    )
    spec = root / "spec.md"
    spec.write_text(
        """---
status: approved
gate_applicability:
  disposition: red-required
  work_class: behavior
---
# Approved Cook spec

## Acceptance Criteria
- AC-5: Cook replays RED before its first production edit.

## Test Contracts
| Acceptance | Interface referent | Outermost stable seam | Expected failure | Mode |
| --- | --- | --- | --- | --- |
| AC-5 | Cook preflight | Cook preflight | assertion-witness | tracer |
""",
        encoding="utf-8",
    )
    plan = namespace / "cook-preflight.plan.json"
    token = namespace / "cook-preflight.phase.json"
    plan.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "work_id": "cook-preflight-work",
                "project_key": "cook-preflight-project",
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
    begun = _run_cook_red_gate(
        root,
        "begin",
        str(plan.relative_to(root)),
        "--out",
        str(token.relative_to(root)),
    )
    assert begun.returncode == 0, begun.stdout + begun.stderr
    phase = json.loads(begun.stdout)

    oracle = tests / "oracle.py"
    oracle.write_text("outer oracle\n", encoding="utf-8")
    case = tests / "case.py"
    case.write_text(
        """
from pathlib import Path
trace = Path(".cheese") / "trace.log"
trace.parent.mkdir(parents=True, exist_ok=True)
trace.open("a", encoding="utf-8").write("declared-red-witness\\n")
print("assertion-witness")
assert False, "assertion-witness"
""".lstrip(),
        encoding="utf-8",
    )
    candidate = candidates / "cook-preflight.json"
    receipt = namespace / "cook-preflight.receipt.json"
    candidate.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "work_id": "cook-preflight-work",
                "project_key": "cook-preflight-project",
                "producer": "cut",
                "disposition": "red",
                "spec_ref": "spec.md",
                "spec_sha256": _cook_sha256(spec),
                "phase_token_ref": phase["phase_token_ref"],
                "phase_token_sha256": phase["phase_token_sha256"],
                "guard_receipt_refs": [],
                "contracts": [
                    {
                        "acceptance_id": "AC-5",
                        "interface": "Cook preflight",
                        "seam": "Cook preflight",
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
                        "id": "AC-5-tracer",
                        "acceptance_ids": ["AC-5"],
                        "curd": "cook",
                        "seam": "Cook preflight",
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
                    {"path": "tests/oracle.py", "sha256": _cook_sha256(oracle)},
                    {"path": "tests/case.py", "sha256": _cook_sha256(case)},
                    {"path": "tests/baseline.py", "sha256": _cook_sha256(baseline)},
                ],
                "not_applicable_reason": None,
            }
        ),
        encoding="utf-8",
    )
    return candidate, receipt, token


def _cook_preflight_trace(
    root: Path,
    *,
    receipt_state: str,
    origin: str,
) -> tuple[list[str], dict[str, object]]:
    candidate, receipt, token = _write_cook_project(root, origin=origin)
    _cook_event(root, "cut:broad-baseline:capture")
    _cook_event(root, "cut:broad-baseline:frozen")
    _cook_event(root, "cut:oracle:write")
    if receipt_state == "invalid":
        receipt.write_text("{not-json", encoding="utf-8")

    before_edit = _cook_sha256(root / "production.py")
    if receipt_state == "valid":
        issued = _run_cook_red_gate(
            root,
            "issue",
            str(candidate.relative_to(root)),
            "--token",
            str(token.relative_to(root)),
            "--out",
            str(receipt.relative_to(root)),
        )
        assert issued.returncode == 0, issued.stdout + issued.stderr
        payload = json.loads(issued.stdout)
        _cook_event(root, "cut:red-issue")
        _cook_event(root, "cook:receipt:valid")
    else:
        _cook_event(root, f"cook:receipt:{receipt_state}")
        if receipt_state == "invalid":
            invalid = _run_cook_red_gate(
                root,
                "validate",
                str(receipt.relative_to(root)),
                "--state",
                "red",
            )
            assert invalid.returncode != 0
            receipt.unlink()
            _cook_event(root, "cook:receipt:rejected")
        if origin == "adopted":
            _cook_event(root, "cook:adopt-reproduction")
        _cook_event(root, "cut:issue:start")
        issued = _run_cook_red_gate(
            root,
            "issue",
            str(candidate.relative_to(root)),
            "--token",
            str(token.relative_to(root)),
            "--out",
            str(receipt.relative_to(root)),
        )
        assert issued.returncode == 0, issued.stdout + issued.stderr
        payload = json.loads(issued.stdout)
        _cook_event(root, "cut:red-issue")
        _cook_event(root, f"cut:receipt:{payload['cases'][0]['origin']}")

    _cook_event(root, "cook:preflight")
    _cook_event(root, "cook:baseline:consumed")
    _cook_event(root, "cook:red-replay:start")
    replay = _run_cook_red_gate(
        root,
        "validate",
        str(receipt.relative_to(root)),
        "--state",
        "red",
    )
    assert replay.returncode == 0, replay.stdout + replay.stderr
    _cook_event(root, "cook:red-replay:ok")
    assert _cook_sha256(root / "production.py") == before_edit

    _cook_event(root, "production-edit:first")
    (root / "production.py").write_text("implemented-after-red\n", encoding="utf-8")
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    events = (root / ".cheese" / "trace.log").read_text(
        encoding="utf-8"
    ).splitlines()
    return events, payload


@pytest.mark.parametrize(
    ("receipt_state", "origin"),
    [
        ("absent", "generated"),
        ("invalid", "generated"),
        ("absent", "adopted"),
        ("valid", "generated"),
    ],
)
def test_ac_5_cook_preflight_traces_cut_and_red_replay_before_edit(
    tmp_path: Path,
    receipt_state: str,
    origin: str,
) -> None:
    events, payload = _cook_preflight_trace(
        tmp_path, receipt_state=receipt_state, origin=origin
    )
    edit = events.index("production-edit:first")
    assert events.index("cook:preflight") < edit
    assert events.index("cook:baseline:consumed") < edit
    assert events.index("cook:red-replay:ok") < edit
    assert events.index("cut:broad-baseline:capture") < events.index(
        "cut:oracle:write"
    )
    assert events.index("cut:oracle:write") < events.index("cut:red-issue")
    assert events.index("cut:red-issue") < events.index("cook:preflight")
    assert events.index("baseline-green") < events.index("declared-red-witness")

    if receipt_state == "valid":
        assert "cut:issue:start" not in events
        assert events.index("cook:receipt:valid") < events.index(
            "cook:red-replay:start"
        )
    else:
        assert events.index("cut:issue:start") < events.index(
            f"cut:receipt:{origin}"
        ) < events.index("cook:preflight")
        if origin == "adopted":
            assert events.index("cook:adopt-reproduction") < events.index(
                "cut:issue:start"
            )
            assert payload["producer"] == "cut"
            assert payload["cases"][0]["origin"] == "adopted"
