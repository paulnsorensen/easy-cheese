"""Runtime event traces for the outer Press gate intervals (AC-7/AC-8)."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import cast


ROOT = Path(__file__).resolve().parents[2]
RED_GATE = ROOT / "skills" / "cut" / "scripts" / "cut.pyz"
PRESS_ROUTE = ROOT / "skills" / "press" / "scripts" / "press.pyz"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _event(root: Path, name: str) -> None:
    trace = root / ".cheese" / "trace.log"
    trace.parent.mkdir(parents=True, exist_ok=True)
    with trace.open("a", encoding="utf-8") as stream:
        _ = stream.write(name + "\n")


def _red_gate(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(RED_GATE), "red-gate", *args],
        cwd=root,
        capture_output=True,
        text=True,
    )


def _press_route(root: Path, request: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(PRESS_ROUTE), "press-route"],
        cwd=root,
        input=request.read_text(encoding="utf-8"),
        capture_output=True,
        text=True,
    )


def _production_fingerprint(root: Path) -> tuple[tuple[str, str, str], ...]:
    """Fingerprint production entries while excluding test/receipt transport."""
    ignored_top = {".cheese", "tests", "spec.md"}
    entries: list[tuple[str, str, str]] = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if relative.parts[0] in ignored_top or "__pycache__" in relative.parts:
            continue
        key = relative.as_posix()
        if path.is_symlink():
            entries.append((key, "symlink", os.readlink(path)))
        elif path.is_file():
            entries.append((key, "file", _sha256(path)))
        elif path.is_dir():
            entries.append((key, "directory", ""))
        else:
            entries.append((key, "unsupported", ""))
    return tuple(entries)


def _write_project(root: Path) -> dict[str, Path]:
    (root / "tests").mkdir(parents=True)
    (root / ".cheese").mkdir()
    (root / ".cheese" / "cut" / "candidates").mkdir(parents=True)
    (root / ".cheese" / "press" / "candidates").mkdir(parents=True)
    _ = (root / "production.py").write_text("before\n", encoding="utf-8")
    _ = (root / ".production-config").write_text("stable\n", encoding="utf-8")
    (root / "production-link").symlink_to("production.py")
    oracle = root / "tests" / "oracle.py"
    baseline = root / "tests" / "baseline.py"
    _ = baseline.write_text(
        """
from pathlib import Path
trace = Path(".cheese") / "trace.log"
trace.parent.mkdir(parents=True, exist_ok=True)
trace.open("a", encoding="utf-8").write("baseline-green\\n")
raise SystemExit(0)
""".lstrip(),
        encoding="utf-8",
    )
    cut_case = root / "tests" / "cut_case.py"
    _ = cut_case.write_text(
        """
from pathlib import Path
state = Path("production.py").read_text(encoding="utf-8").strip()
trace = Path(".cheese") / "trace.log"
trace.parent.mkdir(parents=True, exist_ok=True)
trace.open("a", encoding="utf-8").write("cut-case\\n")
print("assertion-origin")
assert state != "before", "assertion-origin"
""".lstrip(),
        encoding="utf-8",
    )
    attack = root / "tests" / "attack.py"
    _ = attack.write_text(
        """
from pathlib import Path
state = Path(".production-config").read_text(encoding="utf-8").strip()
trace = Path(".cheese") / "trace.log"
trace.parent.mkdir(parents=True, exist_ok=True)
trace.open("a", encoding="utf-8").write("attack-case\\n")
print("assertion-origin")
assert state == "repaired", "assertion-origin"
""".lstrip(),
        encoding="utf-8",
    )
    spec = root / "spec.md"
    _ = spec.write_text(
        """---
gate_applicability:
  disposition: red-required
  work_class: behavior
---
# Approved outer gate spec

## Acceptance Criteria
- AC-7: Press replays original GREEN before its attack.
- AC-8: Press keeps production unchanged during each owned interval.

## Test Contracts
| Acceptance | Interface referent | Outermost stable seam | Expected failure | Mode |
| --- | --- | --- | --- | --- |
| AC-7 | outer gate interval | outer gate interval | assertion-origin | tracer |
| AC-8 | outer gate interval | outer gate interval | assertion-origin | tracer |
""",
        encoding="utf-8",
    )
    return {
        "oracle": oracle,
        "baseline": baseline,
        "cut_case": cut_case,
        "attack": attack,
        "spec": spec,
        "cut_candidate": root / ".cheese" / "cut" / "candidates" / "cut.json",
        "cut_receipt": root / ".cheese" / "cut" / "cut.json",
        "press_candidate": root / ".cheese" / "press" / "candidates" / "press.json",
        "press_resume_candidate": (
            root / ".cheese" / "press" / "candidates" / "press-resume.json"
        ),
        "press_receipt": root / ".cheese" / "press" / "press.json",
        "route_request": root / ".cheese" / "route.json",
    }


def _candidate(
    root: Path,
    paths: dict[str, Path],
    *,
    producer: str,
    guard_receipts: list[str],
) -> dict[str, object]:
    case = paths["cut_case"] if producer == "cut" else paths["attack"]
    witness = "assertion-origin"
    protected_files = [
        {
            "path": str(case.relative_to(root)),
            "sha256": _sha256(case),
        },
        {
            "path": "tests/baseline.py",
            "sha256": _sha256(paths["baseline"]),
        },
    ]
    if paths["oracle"].exists():
        protected_files.insert(
            0,
            {
                "path": str(paths["oracle"].relative_to(root)),
                "sha256": _sha256(paths["oracle"]),
            },
        )
    return {
        "schema_version": 1,
        "work_id": "press-interval-work",
        "project_key": "press-interval-project",
        "producer": producer,
        "disposition": "red",
        "spec_ref": "spec.md",
        "spec_sha256": _sha256(paths["spec"]),
        "phase_token_ref": None,
        "phase_token_sha256": None,
        "guard_receipt_refs": guard_receipts,
        "contracts": [
            {
                "acceptance_id": "AC-7",
                "interface": "outer gate interval",
                "seam": "outer gate interval",
                "expected_failure": "assertion-origin",
                "mode": "tracer",
                "contract_source": "approved",
            },
            {
                "acceptance_id": "AC-8",
                "interface": "outer gate interval",
                "seam": "outer gate interval",
                "expected_failure": "assertion-origin",
                "mode": "tracer",
                "contract_source": "approved",
            },
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
                "id": "AC-7-tracer",
                "acceptance_ids": ["AC-7"],
                "curd": "press-interval",
                "seam": "outer gate interval",
                "argv": [sys.executable, str(case.relative_to(root))],
                "cwd": ".",
                "kind": "behavior",
                "origin": "generated",
                "expected_witness": [witness],
                "observed_exit_code": 1,
                "observed_witness": witness,
            },
            {
                "id": "AC-8-tracer",
                "acceptance_ids": ["AC-8"],
                "curd": "press-interval",
                "seam": "outer gate interval",
                "argv": [sys.executable, str(case.relative_to(root))],
                "cwd": ".",
                "kind": "behavior",
                "origin": "generated",
                "expected_witness": [witness],
                "observed_exit_code": 1,
                "observed_witness": witness,
            },
        ],
        "protected_files": protected_files,
        "not_applicable_reason": None,
    }


def _begin(
    root: Path,
    candidate: Path,
    *,
    label: str,
) -> tuple[Path, dict[str, object]]:
    payload = cast(dict[str, object], json.loads(candidate.read_text(encoding="utf-8")))
    producer = str(payload["producer"])
    namespace = root / ".cheese" / producer
    namespace.mkdir(parents=True, exist_ok=True)
    plan_path = namespace / f"{label}.plan.json"
    token_path = namespace / f"{label}.phase.json"
    _ = plan_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "producer": producer,
                "work_id": payload["work_id"],
                "project_key": payload["project_key"],
                "production_paths": [
                    ".production-config",
                    "production.py",
                ],
                "baseline_checks": [
                    {
                        "id": check["id"],
                        "argv": check["argv"],
                        "cwd": check["cwd"],
                    }
                    for check in cast(list[dict[str, object]], payload["baseline_checks"])
                ],
            }
        ),
        encoding="utf-8",
    )
    result = _red_gate(
        root,
        "begin",
        str(plan_path.relative_to(root)),
        "--out",
        str(token_path.relative_to(root)),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload.update(cast(dict[str, object], json.loads(result.stdout)))
    _ = candidate.write_text(json.dumps(payload), encoding="utf-8")
    return token_path, payload


def _issue(
    root: Path,
    candidate: Path,
    receipt: Path,
    *,
    label: str,
    oracle: Path | None = None,
) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
    token_path, payload = _begin(root, candidate, label=label)
    if oracle is not None:
        if not oracle.exists():
            _ = oracle.write_text("outer oracle\n", encoding="utf-8")
        oracle_ref = str(oracle.relative_to(root))
        protected_files = [
            entry
            for entry in cast(list[dict[str, object]], payload["protected_files"])
            if entry["path"] != oracle_ref
        ]
        protected_files.insert(
            0,
            {"path": oracle_ref, "sha256": _sha256(oracle)},
        )
        payload["protected_files"] = protected_files
        _ = candidate.write_text(json.dumps(payload), encoding="utf-8")
    result = _red_gate(
        root,
        "issue",
        str(candidate.relative_to(root)),
        "--token",
        str(token_path.relative_to(root)),
        "--out",
        str(receipt.relative_to(root)),
    )
    payload = cast(dict[str, object], json.loads(result.stdout)) if result.stdout else {}
    return result, payload


def test_ac_7_8_press_replays_green_then_preserves_each_interval_and_attack(
    tmp_path: Path,
) -> None:
    paths = _write_project(tmp_path)
    cut_candidate = _candidate(tmp_path, paths, producer="cut", guard_receipts=[])
    _ = paths["cut_candidate"].write_text(json.dumps(cut_candidate), encoding="utf-8")
    cut_result, _ = _issue(
        tmp_path,
        paths["cut_candidate"],
        paths["cut_receipt"],
        label="cut",
        oracle=paths["oracle"],
    )
    assert cut_result.returncode == 0, cut_result.stdout + cut_result.stderr
    _ = (tmp_path / "production.py").write_text("after-cut\n", encoding="utf-8")
    _ = (tmp_path / ".cheese" / "trace.log").write_text("", encoding="utf-8")

    press_candidate = _candidate(
        tmp_path,
        paths,
        producer="press",
        guard_receipts=[str(paths["cut_receipt"].relative_to(tmp_path))],
    )
    _ = paths["press_candidate"].write_text(json.dumps(press_candidate), encoding="utf-8")
    attack_digest = _sha256(paths["attack"])

    _event(tmp_path, "press:entry")
    first_before = _production_fingerprint(tmp_path)
    first_paths = {entry[0] for entry in first_before}
    assert {".production-config", "production-link"} <= first_paths
    _event(tmp_path, "press:original-green:start")
    original_green = _red_gate(
        tmp_path,
        "validate",
        str(paths["cut_receipt"].relative_to(tmp_path)),
        "--state",
        "green",
    )
    assert original_green.returncode == 0, original_green.stdout + original_green.stderr
    _event(tmp_path, "press:original-green:ok")
    assert _production_fingerprint(tmp_path) == first_before

    _event(tmp_path, "press:attack:start")
    press_result, press_payload = _issue(
        tmp_path,
        paths["press_candidate"],
        paths["press_receipt"],
        label="press",
    )
    assert press_result.returncode == 0, press_result.stdout + press_result.stderr
    _event(tmp_path, "press:receipt:issued")
    assert press_payload["producer"] == "press"
    assert press_payload["guard_receipt_refs"] == [
        str(paths["cut_receipt"].relative_to(tmp_path))
    ]
    assert _sha256(paths["attack"]) == attack_digest
    assert _production_fingerprint(tmp_path) == first_before

    _ = paths["route_request"].write_text(
        json.dumps(
            {
                "outcome": "in_contract_red",
                "current_receipt": str(paths["press_receipt"].relative_to(tmp_path)),
                "phase_token_ref": press_payload["phase_token_ref"],
                "phase_token_sha256": press_payload["phase_token_sha256"],
            }
        ),
        encoding="utf-8",
    )
    route_continue = _press_route(tmp_path, paths["route_request"])
    assert route_continue.returncode == 0, route_continue.stdout + route_continue.stderr
    assert json.loads(route_continue.stdout) == {
        "action": "continue",
        "reason": "press-corrective-cook",
    }
    _event(tmp_path, "press:route:continue")
    first_after = _production_fingerprint(tmp_path)
    assert first_after == first_before

    # The corrective Cook may edit production between Press-owned intervals.
    _event(tmp_path, "cook:repair")
    _ = (tmp_path / "production.py").write_text("after-repair\n", encoding="utf-8")
    _ = (tmp_path / ".production-config").write_text("repaired\n", encoding="utf-8")

    second_before = _production_fingerprint(tmp_path)
    _event(tmp_path, "press:resume")
    resumed_original_green = _red_gate(
        tmp_path,
        "validate",
        str(paths["cut_receipt"].relative_to(tmp_path)),
        "--state",
        "green",
    )
    assert resumed_original_green.returncode == 0, (
        resumed_original_green.stdout + resumed_original_green.stderr
    )
    _event(tmp_path, "press:original-green:resume:ok")
    resume_candidate = _candidate(
        tmp_path,
        paths,
        producer="press",
        guard_receipts=[
            str(paths["cut_receipt"].relative_to(tmp_path)),
            str(paths["press_receipt"].relative_to(tmp_path)),
        ],
    )
    _ = paths["press_resume_candidate"].write_text(
        json.dumps(resume_candidate), encoding="utf-8"
    )
    _, resume_payload = _begin(
        tmp_path, paths["press_resume_candidate"], label="press-resume"
    )
    assert resume_payload["phase_token_ref"] != press_payload["phase_token_ref"]
    persisted_resume = cast(
        dict[str, object],
        json.loads(paths["press_resume_candidate"].read_text(encoding="utf-8")),
    )
    assert persisted_resume["phase_token_ref"] == resume_payload["phase_token_ref"]

    resumed_attack = _red_gate(
        tmp_path,
        "validate",
        str(paths["press_receipt"].relative_to(tmp_path)),
        "--state",
        "green",
    )
    assert resumed_attack.returncode == 0, resumed_attack.stdout + resumed_attack.stderr
    resumed_payload = cast(dict[str, object], json.loads(resumed_attack.stdout))
    assert resumed_payload["ok"] is True
    _event(tmp_path, "press:attack:replay")
    assert _sha256(paths["attack"]) == attack_digest
    press_cases = cast(list[dict[str, object]], press_payload["cases"])
    press_candidate_cases = cast(list[dict[str, object]], press_candidate["cases"])
    assert press_cases[0]["argv"] == press_candidate_cases[0]["argv"]

    _ = paths["route_request"].write_text(
        json.dumps(
            {
                "outcome": "green",
                "current_receipt": str(paths["press_receipt"].relative_to(tmp_path)),
                "phase_token_ref": resume_payload["phase_token_ref"],
                "phase_token_sha256": resume_payload["phase_token_sha256"],
            }
        ),
        encoding="utf-8",
    )
    route_age = _press_route(tmp_path, paths["route_request"])
    assert route_age.returncode == 0, route_age.stdout + route_age.stderr
    assert json.loads(route_age.stdout) == {"action": "dispatch", "command": "/age"}
    _event(tmp_path, "press:route:age")
    second_after = _production_fingerprint(tmp_path)
    assert second_after == second_before

    events = (
        (tmp_path / ".cheese" / "trace.log").read_text(encoding="utf-8").splitlines()
    )
    assert events.index("press:original-green:ok") < events.index("press:attack:start")
    assert events.index("press:route:continue") < events.index("cook:repair")
    assert events.index("cook:repair") < events.index("press:resume")
    assert events.index("press:resume") < events.index("press:attack:replay")
    assert events.index("press:attack:replay") < events.index("press:route:age")
