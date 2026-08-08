"""Contract tests for Cut's first-class continuation routing."""

from __future__ import annotations

from pathlib import Path

from easy_cheese_schemas import NextMove

REPO_ROOT = Path(__file__).resolve().parents[2]
CHEESE = REPO_ROOT / "skills" / "cheese" / "SKILL.md"
RESUME = REPO_ROOT / "skills" / "cheese" / "references" / "continue-resume.md"
WHEYPOINT = REPO_ROOT / "skills" / "wheypoint" / "SKILL.md"


def _corpus() -> str:
    return "\n".join(
        path.read_text(encoding="utf-8") for path in (CHEESE, RESUME, WHEYPOINT)
    )


def test_cut_is_canonical_and_the_pipeline_routes_mold_cut_cook() -> None:
    assert NextMove.CUT.value == "cut"
    body = _corpus()
    pipeline = "culture -> mold -> cut -> cook -> press -> age -> cure -> plate"
    assert pipeline in body
    assert "red-required" in body
    assert "next: cut" in body
    assert "next: cook" in body
    assert "/cut" in body
    assert "/cook" in body


def test_continue_preserves_receipt_pointer_mode_and_explicit_flags() -> None:
    body = _corpus()
    assert "artifact:" in body
    assert "GateReceipt" in body
    assert "mode:" in body
    for flag in ("--auto", "--hard", "--open-pr", "--safe"):
        assert flag in body
    assert "forwards that `artifact:` unchanged" in body
    assert "never inferred" in body


def test_press_corrective_routing_stays_continue_owned() -> None:
    body = _corpus()
    assert "continue: press-corrective-cook" in body
    assert "not a global Press-to-Cook dispatch" in body
    assert "global Press-to-Cook dispatch" not in body.replace(
        "not a global Press-to-Cook dispatch", ""
    )
