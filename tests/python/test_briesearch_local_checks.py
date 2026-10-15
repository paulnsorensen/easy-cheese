"""Prose contract for briesearch uncertainty and local-check reporting."""
from __future__ import annotations

import re
from pathlib import Path

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
    assert (
        "| Claim about our deployed integration with no local check run | cap at `speculating` |"
        in text
    )


def test_query_planning_stops_when_uncertainty_requires_execution() -> None:
    text = _read("query-planning.md")
    assert (
        "Stop when the remaining uncertainty requires execution rather than more sources."
        in text
    )
    done_lines = [ln for ln in text.splitlines() if ln.startswith("- Done when:")]
    assert len(done_lines) == 2
    assert all("requires execution rather than more sources" in ln for ln in done_lines)
