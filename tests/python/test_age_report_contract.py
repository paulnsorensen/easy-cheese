"""Keep published finding templates compatible with the real Cure parser."""

from __future__ import annotations

import re
from pathlib import Path

from easy_cheese.shared.findings import parse_findings_report

ROOT = Path(__file__).resolve().parents[2]
REPORT_EXAMPLE = (
    ROOT / "skills" / "age" / "references" / "report-example.md"
).read_text(encoding="utf-8")


def _published_finding_template() -> str:
    """The fenced block `report-example.md` tells the reviewer to copy verbatim."""
    block = re.search(r"```markdown\n(.*?)```", REPORT_EXAMPLE, re.DOTALL)
    assert block is not None, "The report example has no fenced finding template."
    return block.group(1)


def test_the_published_finding_template_parses_into_one_finding() -> None:
    filled = (
        _published_finding_template()
        .replace("<dim>", "correctness")
        .replace("<sev>", "high")
        .replace("path:line", "src/app.py:42")
        .replace("<claim>", "the retry loop never resets the backoff")
        .replace("location: <tier>", "location: module")
        .replace("fix-cost-now: <tier>", "fix-cost-now: contained")
        .replace("fix-cost-later: <tier>", "fix-cost-later: spreading")
        .replace("confidence: <tier>", "confidence: certain")
        .replace("<action>", "reset `delay` at the top of the loop")
    )
    findings = parse_findings_report("## High\n" + filled)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.dimension == "correctness"
    assert finding.severity == "high"
    assert finding.location == "src/app.py:42"
    assert finding.fix_cost_now == "contained"
    assert finding.fix_cost_later == "spreading"
    assert finding.confidence == "certain"
    assert finding.recommendation == "reset `delay` at the top of the loop."


def test_the_worked_report_preserves_finding_identity() -> None:
    findings = parse_findings_report(REPORT_EXAMPLE)

    assert [
        (finding.dimension, finding.severity, finding.location) for finding in findings
    ] == [
        ("encapsulation", "blocker", "src/users/index.ts:42"),
        ("security", "high", "src/api/admin/users.ts:55"),
        ("complexity", "medium", "src/utils/format.ts:200-240"),
        ("conventions", "medium", "src/config.py:12"),
        ("deslop", "low", "src/utils/format.ts:18"),
        ("altitude", "low", "src/utils/format.ts:24"),
    ]
