"""Contract for briesearch uncertainty and local-check reporting."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
REFERENCES = REPO_ROOT / "skills" / "briesearch" / "references"


def _read(name: str) -> str:
    return (REFERENCES / name).read_text(encoding="utf-8")


def _short_form() -> str:
    blocks: list[str] = re.findall(r"```markdown\n(.*?)```", _read("synthesis.md"), re.DOTALL)
    short = [b for b in blocks if "## Research:" in b]
    assert len(short) == 1, "synthesis.md must document one short-form template"
    return short[0]


def test_short_form_has_uncertainty_section_with_four_columns() -> None:
    template = _short_form()
    assert "### Uncertainty and local checks" in template
    header = (
        "| Decision affected | Evidence | Remaining uncertainty in our environment"
        " | Smallest local check |"
    )
    assert header in template
    assert "`none`" in template


def test_uncertainty_section_sits_between_open_questions_and_confidence() -> None:
    template = _short_form()
    order = [
        template.index(h)
        for h in ("### Open questions", "### Uncertainty and local checks", "### Confidence")
    ]
    assert order == sorted(order)


def test_synthesis_says_docs_are_not_proof_of_deployed_integration() -> None:
    text = _read("synthesis.md")
    assert "does not show that our deployed integration works" in text
    assert "Cap a claim about our integration at `speculating` until a local check runs" in text
    assert "Claim about our deployed integration with no local check run" in text


def test_query_planning_stops_when_uncertainty_requires_execution() -> None:
    text = _read("query-planning.md")
    assert (
        "Stop when the remaining uncertainty requires execution rather than more sources."
        in text
    )
    done_lines = [ln for ln in text.splitlines() if ln.startswith("- Done when:")]
    assert len(done_lines) == 2
    assert all("requires execution rather than more sources" in ln for ln in done_lines)


_LOCAL_CHECK_HEADER = (
    "| Decision affected | Evidence | Remaining uncertainty in our environment"
    " | Smallest local check |\n|---|---|---|---|\n"
)


def _local_check_violations(section: str) -> list[tuple[str, str]]:
    from easy_cheese.skills.briesearch import ground_check

    report = (
        "## Research: q\n\n### Uncertainty and local checks\n"
        + section
        + "\n### Confidence\n`speculating` — one source.\n"
    )
    violations, _ = ground_check.check_report(report)
    return [(v.level, v.kind) for v in violations if v.kind == "LOCAL_CHECK"]


@pytest.mark.parametrize(
    "section",
    [
        "none\n",
        "`none`\n",
        _LOCAL_CHECK_HEADER
        + "| Pick the retry knob | docs say 3 retries | our proxy may cap it"
        + " | `pytest tests/test_retry.py -k proxy` |\n",
    ],
)
def test_ground_check_accepts_none_or_a_complete_local_check_table(section: str) -> None:
    assert _local_check_violations(section) == []


@pytest.mark.parametrize(
    "section",
    [
        _LOCAL_CHECK_HEADER + "| Pick the retry knob | docs say 3 | proxy may cap it |  |\n",
        "| Decision | Evidence |\n|---|---|\n| a | b |\n",
        "we should probably check this later\n",
    ],
    ids=["empty-local-check", "wrong-columns", "prose-only"],
)
def test_ground_check_rejects_an_uncertainty_without_a_local_check(section: str) -> None:
    assert _local_check_violations(section) == [("error", "LOCAL_CHECK")]


def test_ground_check_ignores_a_report_without_the_section() -> None:
    from easy_cheese.skills.briesearch import ground_check

    violations, _ = ground_check.check_report("## Research: q\n\n### Finding\nA.\n")
    assert all(v.kind != "LOCAL_CHECK" for v in violations)


def test_long_form_and_skill_output_carry_the_local_checks() -> None:
    synthesis = _read("synthesis.md")
    skill = (REFERENCES.parent / "SKILL.md").read_text(encoding="utf-8")
    assert "the `### Uncertainty and local checks` section, and the verification log" in synthesis
    assert "the local checks for any remaining uncertainty" in skill
