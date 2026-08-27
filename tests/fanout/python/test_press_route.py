from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

SRC_ROOT = Path(__file__).resolve().parents[3] / "src"
for source in (SRC_ROOT, SRC_ROOT / "fanout"):
    value = str(source)
    if value not in sys.path:
        sys.path.insert(0, value)

from easy_cheese.shared.cut import red_gate  # noqa: E402
from easy_cheese.shared.fanout import press_route  # noqa: E402
from easy_cheese.shared.fanout import press_route_cli  # noqa: E402


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _spec(root: Path) -> Path:
    path = root / "spec.md"
    path.write_text(
        """---
status: approved
gate_applicability:
  disposition: red-required
  work_class: behavior
---
# Press boundary

## Acceptance Criteria
- AC-1: the outer behavior advances monotonically.

## Test Contracts
| Acceptance | Interface referent | Outermost stable seam | Expected failure | Mode |
| --- | --- | --- | --- | --- |
| AC-1 | `outer behavior` | `outer behavior` | outer witness | tracer |
""",
        encoding="utf-8",
    )
    return path


def _begin(
    root: Path,
    producer: str,
    label: str,
    production_paths: list[str] | None = None,
) -> tuple[Path, str]:
    namespace = root / ".cheese" / producer
    namespace.mkdir(parents=True, exist_ok=True)
    plan = namespace / f"{label}.plan.json"
    token = namespace / f"{label}.phase.json"
    plan.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "producer": producer,
                "work_id": "press-route-work",
                "project_key": "press-route-project",
                "production_paths": production_paths or ["production-state.txt"],
                "baseline_checks": [
                    {
                        "id": "baseline",
                        "argv": [sys.executable, "-c", "pass"],
                        "cwd": ".",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    result = red_gate.begin_phase(plan, token)
    return token, result.phase_token_sha256


def _issue(
    root: Path,
    producer: str,
    label: str,
    threshold: int,
    guards: list[str],
    production_paths: list[str] | None = None,
) -> tuple[Path, Path, str]:
    token, token_digest = _begin(root, producer, label, production_paths)
    oracle = root / "tests" / f"{label}.py"
    oracle.parent.mkdir(exist_ok=True)
    oracle.write_text(
        "from pathlib import Path\n"
        "level = int(Path('production-state.txt').read_text())\n"
        f"assert level >= {threshold}, 'outer witness'\n",
        encoding="utf-8",
    )
    spec = root / "spec.md"
    namespace = root / ".cheese" / producer
    candidate_dir = namespace / "candidates"
    candidate_dir.mkdir(exist_ok=True)
    candidate = candidate_dir / f"{label}.json"
    receipt = namespace / f"{label}.receipt.json"
    payload = {
        "schema_version": 1,
        "work_id": "press-route-work",
        "project_key": "press-route-project",
        "producer": producer,
        "disposition": "red",
        "spec_ref": "spec.md",
        "spec_sha256": _digest(spec),
        "phase_token_ref": str(token.relative_to(root)),
        "phase_token_sha256": token_digest,
        "guard_receipt_refs": guards,
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
                "id": f"{label}-case",
                "acceptance_ids": ["AC-1"],
                "curd": "press-route",
                "seam": "outer behavior",
                "argv": [sys.executable, str(oracle.relative_to(root))],
                "cwd": ".",
                "kind": "behavior",
                "origin": "generated",
                "expected_witness": ["outer witness"],
                "observed_exit_code": 1,
                "observed_witness": "outer witness",
            }
        ],
        "protected_files": [
            {"path": str(oracle.relative_to(root)), "sha256": _digest(oracle)}
        ],
        "not_applicable_reason": None,
    }
    candidate.write_text(json.dumps(payload), encoding="utf-8")
    red_gate.issue_gate(candidate, receipt, token)
    return receipt, token, token_digest


def _project(root: Path) -> Path:
    _spec(root)
    (root / "production-state.txt").write_text("0", encoding="utf-8")
    receipt, _, _ = _issue(root, "cut", "cut", 1, [])
    (root / "production-state.txt").write_text("1", encoding="utf-8")
    assert red_gate.validate_gate(receipt, "green").ok
    return receipt


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


def test_green_route_consumes_a_fresh_phase_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    cut = _project(tmp_path)
    token, digest = _begin(tmp_path, "press", "press-green")

    assert (
        press_route.route_from_receipt("green", cut, token, digest)
        == press_route.Dispatch()
    )
    with pytest.raises(press_route.ReceiptChainError, match="already been routed"):
        press_route.route_from_receipt("green", cut, token, digest)


def test_green_route_rejects_a_reformatted_token_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    cut = _project(tmp_path)
    token, digest = _begin(tmp_path, "press", "press-canonical")
    assert (
        press_route.route_from_receipt("green", cut, token, digest)
        == press_route.Dispatch()
    )
    copied = token.with_name("press-copied.phase.json")
    copied.write_text(json.dumps(json.loads(token.read_text())), encoding="utf-8")

    with pytest.raises(press_route.ReceiptChainError, match="canonical encoding"):
        press_route.route_from_receipt("green", cut, copied, _digest(copied))


def test_green_route_inherits_the_current_receipt_production_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "other-state.txt").write_text("stable", encoding="utf-8")
    cut = _project(tmp_path)
    token, digest = _begin(
        tmp_path,
        "press",
        "press-wrong-production-root",
        ["other-state.txt"],
    )
    (tmp_path / "production-state.txt").write_text("2", encoding="utf-8")

    with pytest.raises(press_route.ReceiptChainError, match="production_paths"):
        press_route.route_from_receipt("green", cut, token, digest)


def test_red_route_inherits_the_prior_receipt_production_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "other-state.txt").write_text("stable", encoding="utf-8")
    cut = _project(tmp_path)
    receipt, token, digest = _issue(
        tmp_path,
        "press",
        "press-red-wrong-production-root",
        2,
        [str(cut.relative_to(tmp_path))],
        ["other-state.txt"],
    )

    with pytest.raises(press_route.ReceiptChainError, match="production_paths"):
        press_route.route_from_receipt(
            "in_contract_red",
            receipt,
            token,
            digest,
        )


def test_green_route_rejects_a_symlinked_decision_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    cut = _project(tmp_path)
    token, digest = _begin(tmp_path, "press", "press-decision-symlink")
    outside = tmp_path.parent / f"{tmp_path.name}-outside-decisions"
    outside.mkdir()
    (tmp_path / ".cheese" / "press-decisions").symlink_to(
        outside, target_is_directory=True
    )

    with pytest.raises(press_route.ReceiptChainError, match="unsafe"):
        press_route.route_from_receipt("green", cut, token, digest)
    assert list(outside.iterdir()) == []


def test_press_receipt_rejects_a_symlinked_history_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    cut = _project(tmp_path)
    outside = tmp_path.parent / f"{tmp_path.name}-outside-history"
    outside.mkdir()
    (tmp_path / ".cheese" / "press-history").symlink_to(
        outside, target_is_directory=True
    )

    with pytest.raises(red_gate.GateValidationError, match="unsafe"):
        _issue(
            tmp_path,
            "press",
            "unsafe-history",
            2,
            [str(cut.relative_to(tmp_path))],
        )
    assert list(outside.iterdir()) == []


def test_red_routes_derive_the_bound_from_authoritative_history(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    cut = _project(tmp_path)
    guards = [str(cut.relative_to(tmp_path))]
    receipts: list[Path] = []
    tokens: list[tuple[Path, str]] = []
    expected = [
        press_route.Continue(),
        press_route.Continue(),
        press_route.Stop("third-red", gated_evidence=True),
    ]

    for attempt, action in enumerate(expected, start=1):
        receipt, token, digest = _issue(
            tmp_path,
            "press",
            f"press-{attempt}",
            attempt + 1,
            guards,
        )
        receipts.append(receipt)
        tokens.append((token, digest))
        assert (
            press_route.route_from_receipt(
                "in_contract_red",
                receipt,
                token,
                digest,
            )
            == action
        )
        guards.append(str(receipt.relative_to(tmp_path)))
        if attempt < 3:
            (tmp_path / "production-state.txt").write_text(
                str(attempt + 1), encoding="utf-8"
            )

    with pytest.raises(press_route.ReceiptChainError, match="already been routed"):
        press_route.route_from_receipt(
            "in_contract_red",
            receipts[-1],
            *tokens[-1],
        )
    stale_token, stale_digest = _begin(tmp_path, "press", "stale-route")
    with pytest.raises(
        press_route.ReceiptChainError,
        match="(?:not the latest immutable Press receipt|oracle dependency changed)",
    ):
        press_route.route_from_receipt(
            "green",
            receipts[1],
            stale_token,
            stale_digest,
        )


def test_route_derives_production_change_from_phase_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    cut = _project(tmp_path)
    token, digest = _begin(tmp_path, "press", "production-change")
    (tmp_path / "production-state.txt").write_text("2", encoding="utf-8")

    assert press_route.route_from_receipt(
        "green", cut, token, digest
    ) == press_route.Stop(
        "production-changed",
        gated_evidence=False,
    )


def test_route_rejects_malformed_authoritative_history(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    cut = _project(tmp_path)
    receipt, token, digest = _issue(
        tmp_path,
        "press",
        "history",
        2,
        [str(cut.relative_to(tmp_path))],
    )
    history = next((tmp_path / ".cheese" / "press-history").glob("*.json"))
    history.write_text("{}", encoding="utf-8")

    with pytest.raises(press_route.ReceiptChainError, match="Press history"):
        press_route.route_from_receipt("in_contract_red", receipt, token, digest)


def test_cli_requires_phase_token_evidence(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    request = tmp_path / "request.json"
    request.write_text(
        '{"outcome":"green","current_receipt":"x"}',
        encoding="utf-8",
    )
    assert press_route_cli.main(["press-route", str(request)]) == 1
    assert "phase_token_ref" in capsys.readouterr().err
