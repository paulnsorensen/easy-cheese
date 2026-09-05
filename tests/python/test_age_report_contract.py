"""The Age report contract must survive the trip into `/cure`.

`/age` publishes a finding syntax in prose and `/cure` parses it with
`easy_cheese.shared.findings`. Those two drifted: the prose dropped the list
marker and the location backticks, so the parser returned an empty selection and
`/cure` silently repaired nothing. These tests bind the published prose to the
real parser, and bind the writer command to the handoff fields that `/cheese`,
`/cook`, and `/cure` expect back.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from easy_cheese.shared.findings import parse_findings_report

ROOT = Path(__file__).resolve().parents[2]
SKILL = (ROOT / "skills" / "age" / "SKILL.md").read_text(encoding="utf-8")
REPORT_EXAMPLE = (
    ROOT / "skills" / "age" / "references" / "report-example.md"
).read_text(encoding="utf-8")
# The auto-mode rules live in the handoff reference; the corpus is what a
# reviewer actually reads.
CORPUS = SKILL + "\n".join(
    path.read_text(encoding="utf-8")
    for path in sorted((ROOT / "skills" / "age" / "references").glob("*.md"))
)


def _published_finding_template() -> str:
    """The fenced block `report-example.md` tells the reviewer to copy verbatim."""
    anchor = "A finding that drops the list marker or the location backticks is invisible to `/cure`."
    assert "references/report-example.md` § Body order" in SKILL, (
        "SKILL.md must route the reviewer to the published body order"
    )
    assert anchor in REPORT_EXAMPLE
    tail = REPORT_EXAMPLE.split(anchor, 1)[1]
    block = re.search(r"```markdown\n(.*?)```", tail, re.DOTALL)
    assert block is not None, "SKILL.md publishes no fenced finding template"
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


def test_the_worked_report_example_parses_every_severity_band() -> None:
    findings = parse_findings_report(REPORT_EXAMPLE)
    bands = [f.severity for f in findings]

    assert bands.count("blocker") >= 1
    assert bands.count("high") >= 1
    assert bands.count("medium") >= 1
    assert bands.count("low") >= 1
    assert all(f.location and f.recommendation for f in findings)


def _writer_command() -> str:
    line = next(
        raw
        for raw in SKILL.splitlines()
        if "write-handoff-artifact" in raw and "--phase age" in raw
    )
    return line


def test_the_writer_command_forwards_upstream_artifact_and_baseline() -> None:
    """Dropping these fields loses the press/cook chain that `/cure` resumes."""
    command = _writer_command()

    assert '--artifact ""' not in command
    assert '--artifact "<artifact>"' in command
    assert "--baseline " in command
    assert '--body-file ".cheese/age/<slug>-body.md"' in command


def test_the_report_body_is_a_separate_file_from_the_final_report() -> None:
    """Two writers on one target left a prewritten report after a failed gate."""
    assert "Write the body only. Do not write the handoff preamble into that file." in SKILL
    assert "Do not write `.cheese/age/<slug>.md` yourself. The gated writer creates it." in SKILL


def test_age_holds_no_cure_pass_counter() -> None:
    """`/cook`'s fixed chain length owns the cap; Age has no counter input."""
    assert "Increment the cure-pass count" not in CORPUS
    assert "Age counts no cure passes and holds no pass state." in CORPUS


@pytest.mark.parametrize("form", ["/age [<ref-or-range>]", "/age <slug>"])  # noqa: V107
def test_both_input_forms_accept_the_hard_flag(form: str) -> None:
    line = next(raw for raw in SKILL.splitlines() if raw.startswith(form))
    assert "[--hard]" in line


def test_the_scoped_form_accepts_a_slug_and_repeated_scopes() -> None:
    line = next(
        raw for raw in SKILL.splitlines() if raw.startswith("/age [<ref-or-range>]")
    )
    assert "[--scope <path>]..." in line
    assert "[--slug <slug>]" in line
