"""Fan-out mechanics contract: one-message dispatch, every-width verifier, recall rule.

`/age` under-specified three mechanics that let a fan-out run degrade silently:
workers dispatched serially instead of in one message, the cheap verifier
skipped below n=2 with no substitute grading, and lens workers self-filtering
findings the verifier was supposed to catch. These tests bind the published
prose to each fix.
"""

from __future__ import annotations

from pathlib import Path

from easy_cheese.shared.findings import parse_findings_report

ROOT = Path(__file__).resolve().parents[2]
AGE_DIR = ROOT / "skills" / "age"
SKILL = (AGE_DIR / "SKILL.md").read_text(encoding="utf-8")
FAN_OUT = (AGE_DIR / "references" / "fan-out.md").read_text(encoding="utf-8")
PACKET = (AGE_DIR / "references" / "packet.md").read_text(encoding="utf-8")
REPORT_EXAMPLE = (AGE_DIR / "references" / "report-example.md").read_text(
    encoding="utf-8"
)
HANDOFF_DETAIL = (AGE_DIR / "references" / "handoff-detail.md").read_text(
    encoding="utf-8"
)


def _seam(text: str, n: int) -> str:
    marker = f"**Seam {n}"
    next_marker = f"**Seam {n + 1}"
    start = text.index(marker)
    end = text.index(next_marker, start) if next_marker in text else len(text)
    return text[start:end]


def test_seam_3_requires_one_message_dispatch() -> None:
    seam_3 = _seam(FAN_OUT, 3)
    assert (
        "Dispatch all `len(lenses)` Agent calls in one message, never sequentially."
        in seam_3
    )
    assert "never sequentially" in seam_3
    assert "one worker per lens" in seam_3
    assert "run_in_background" in seam_3


def test_report_records_dispatched_worker_count() -> None:
    agent_resolution = REPORT_EXAMPLE.split("\n## Agent resolution\n", 1)[1].split(
        "\n## Confidence", 1
    )[0]
    assert "dispatched:" in agent_resolution
    assert "one message:" in agent_resolution

    findings = parse_findings_report(REPORT_EXAMPLE)
    bands = [f.severity for f in findings]
    assert bands.count("blocker") >= 1
    assert bands.count("high") >= 1
    assert bands.count("medium") >= 1
    assert bands.count("low") >= 1


def test_verifier_runs_at_every_width() -> None:
    seam_6 = _seam(FAN_OUT, 6)
    assert "does not run at n=1" not in seam_6
    assert "does not run at" not in seam_6
    assert "every width" in seam_6
    assert "batches of up to ten" in seam_6


def test_verifier_skipped_as_sub_agent() -> None:
    assert "verifier: skipped (sub-agent)" in HANDOFF_DETAIL
    assert "verifier: skipped (sub-agent)" in REPORT_EXAMPLE

    n1_paragraph = SKILL.split("For `n=1`", 1)[1].split("\n\n", 1)[0]
    assert "Seam 6" in n1_paragraph
    assert "sub-agent" in n1_paragraph
    assert "sub-agent" in _seam(FAN_OUT, 6)


def test_packet_carries_the_finder_recall_rule() -> None:
    assert "nameable failure scenario" in PACKET
