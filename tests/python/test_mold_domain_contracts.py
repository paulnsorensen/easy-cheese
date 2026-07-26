"""Contract tests for Mold's domain-boundary and durable-knowledge guidance."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MOLD_REFS = REPO_ROOT / "skills" / "mold" / "references"
MOLD_SKILL = REPO_ROOT / "skills" / "mold" / "SKILL.md"
HANDSHAKE = MOLD_REFS / "handshake.md"
MODES = MOLD_REFS / "modes.md"
ADR = MOLD_REFS / "adr.md"
CURDLE = MOLD_REFS / "curdle.md"
EVALS = MOLD_REFS / "evals.md"
DOWNSTREAM = {
    name: REPO_ROOT / "skills" / name / "SKILL.md"
    for name in ("cook", "press", "age", "cure")
}


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _section(path: Path, heading: str) -> str:
    body = _text(path)
    marker = f"## {heading}"
    start = body.index(marker)
    end = body.find("\n## ", start + len(marker))
    return body[start:] if end == -1 else body[start:end]


def _subsection(path: Path, heading: str) -> str:
    body = _text(path)
    marker = f"### {heading}"
    start = body.index(marker)
    next_subsection = body.find("\n### ", start + len(marker))
    next_section = body.find("\n## ", start + len(marker))
    ends = [position for position in (next_subsection, next_section) if position != -1]
    return body[start : min(ends)] if ends else body[start:]


def _assert_phrases(path: Path, *phrases: str) -> None:
    body = _text(path).casefold()
    missing = [phrase for phrase in phrases if phrase.casefold() not in body]
    assert not missing, f"{path.relative_to(REPO_ROOT)} missing: {missing}"


def test_six_modes_remain_and_grill_requires_concrete_boundary_scenarios() -> None:
    body = _text(MODES)
    mode_names = re.findall(r"^### (Explore|Ground|Shape|Sketch|Grill|Diagnose) —", body, re.MULTILINE)
    assert mode_names == ["Explore", "Ground", "Shape", "Sketch", "Grill", "Diagnose"]
    assert "### Glossary" not in body

    grill = body[body.index("### Grill —") : body.index("### Diagnose —")]
    for phrase in (
        "domain boundaries or relationships are in scope",
        "invent at least one concrete scenario",
        "required",
    ):
        assert phrase.casefold() in grill.casefold()


def test_adr_requires_all_three_eligibility_criteria() -> None:
    eligibility = _section(ADR, "What earns an ADR")
    for phrase in (
        "all three",
        "hard to reverse",
        "surprising without context",
        "real trade-off",
    ):
        assert phrase.casefold() in eligibility.casefold()


def test_agent_decisions_are_adr_candidates_not_automatic_records() -> None:
    ledger = _section(ADR, "Decision ledger")
    for phrase in (
        "[AGENT-DECIDED]",
        "candidate",
        "not an automatic ADR",
        "all three",
        "spec's one-line decision-log",
    ):
        assert phrase.casefold() in ledger.casefold()


def test_core_mold_and_spec_template_do_not_bypass_adr_filter() -> None:
    _assert_phrases(
        MOLD_SKILL,
        "decisions that meet all three ADR eligibility criteria",
        "only qualifying candidates also become ADRs",
    )
    _assert_phrases(CURDLE, "qualifying decisions get full ADRs per `adr.md`")


def test_manual_overloaded_term_eval_requires_full_durable_flush() -> None:
    case = _subsection(EVALS, "Overloaded term → Ground → durable writes").casefold()
    for phrase in (
        "canonical-term question",
        ".cheese/glossary/<slug>.md",
        "cumulative domain model",
        "reads both back",
        "completion record",
    ):
        assert phrase.casefold() in case


def test_manual_adr_eval_covers_positive_and_each_negative_outcome() -> None:
    case = _subsection(EVALS, "ADR eligibility matrix")
    qualifying = next(line for line in case.splitlines() if "qualifies: all three" in line.casefold())
    assert "write one ADR" in qualifying

    for criterion in (
        "missing hard to reverse",
        "missing surprising without context",
        "missing real trade-off",
    ):
        outcome = next(line for line in case.splitlines() if criterion in line.casefold())
        assert "spec decision-log" in outcome
        assert "write no ADR" in outcome


def test_manual_ambiguous_context_eval_asks_and_writes_only_selection() -> None:
    case = _subsection(EVALS, "Ambiguous second-context routing").casefold()
    assert "asks the user" in case
    assert "writes only the selected context" in case


def test_durable_write_protocol_includes_resolved_glossary() -> None:
    _assert_phrases(HANDSHAKE, "glossary target included when terms were resolved")
    atomic_write = _section(CURDLE, "Atomic write").casefold()
    for phrase in (
        "per-slug glossary when ground resolved terms",
        "read back",
        "completion record",
    ):
        assert phrase in atomic_write


def test_ambiguous_routing_covers_existing_or_proposed_second_context() -> None:
    domain_model = _section(CURDLE, "Domain model (cumulative by-product)")
    assert "existing or proposed second context" in domain_model.casefold()
    assert "../../cheese/references/ask-user-question.md" in domain_model


def test_worked_example_runs_from_term_resolution_to_completion_record() -> None:
    example = _section(CURDLE, "Worked example — term to durable record")
    folded = example.casefold()
    positions = [
        folded.index(phrase.casefold())
        for phrase in (
            "**Ground resolves.**",
            "**Handshake commitment.**",
            "**Curdle writes.**",
            "**Read-back.**",
            "**Completion record.**",
        )
    ]
    assert positions == sorted(positions)
    for phrase in (
        "ask the user which bounded context owns the term",
        "write only the selected context",
    ):
        assert phrase.casefold() in folded


def test_downstream_skills_consume_or_boundedly_correct_domain_terms() -> None:
    for name in ("cook", "press", "age"):
        _assert_phrases(DOWNSTREAM[name], ".cheese/glossary/<slug>.md", "read")
    _assert_phrases(
        DOWNSTREAM["cure"],
        "diff-touched terms only",
        "flag, don't reverse",
        "never overrules",
    )
