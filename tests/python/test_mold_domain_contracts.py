"""Contract tests for Mold's domain-boundary and durable-knowledge guidance.

Ported from PR #330 (codex/pr93-residuals) and reworked for the current tree:
downstream-consumption assertions are scoped to press/age/cure's actual files.
Cook's SKILL.md has no glossary read today — that gap is a flagged follow-up,
not asserted here.
"""

from __future__ import annotations

import re
from pathlib import Path

from test_transport_audit import _unaccounted_sites

REPO_ROOT = Path(__file__).resolve().parents[2]
MOLD_REFS = REPO_ROOT / "skills" / "mold" / "references"
MOLD_SKILL = REPO_ROOT / "skills" / "mold" / "SKILL.md"
HANDSHAKE = MOLD_REFS / "handshake.md"
MODES = MOLD_REFS / "modes.md"
ADR = MOLD_REFS / "adr.md"
CURDLE = MOLD_REFS / "curdle.md"
EVALS = MOLD_REFS / "evals.md"
GATE_GRAPH_SRC = REPO_ROOT / "src" / "easy_cheese" / "skills" / "mold" / "gate_graph.py"
SKILLS = REPO_ROOT / "skills"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _section(path: Path, heading: str, witness: str) -> str:
    body = _text(path)
    marker = f"## {heading}"
    assert marker in body, f"{witness}: no section {marker!r} in {path.name}"
    start = body.index(marker)
    end = body.find("\n## ", start + len(marker))
    return body[start:] if end == -1 else body[start:end]


def _subsection(path: Path, heading: str, witness: str) -> str:
    body = _text(path)
    marker = f"### {heading}"
    assert marker in body, f"{witness}: no subsection {marker!r} in {path.name}"
    start = body.index(marker)
    next_subsection = body.find("\n### ", start + len(marker))
    next_section = body.find("\n## ", start + len(marker))
    ends = [position for position in (next_subsection, next_section) if position != -1]
    return body[start : min(ends)] if ends else body[start:]


def _assert_phrases(path: Path, witness: str, *phrases: str) -> None:
    body = _text(path).casefold()
    missing = [phrase for phrase in phrases if phrase.casefold() not in body]
    assert not missing, f"{witness}: {path.relative_to(REPO_ROOT)} missing {missing}"


# --- AC-1: strict all-three ADR eligibility filter -------------------------

ADR_WITNESS = "adr.md missing all-three eligibility filter"


def test_adr_requires_all_three_eligibility_criteria() -> None:
    eligibility = _section(ADR, "What earns an ADR", ADR_WITNESS).casefold()
    for phrase in (
        "all three",
        "hard to reverse",
        "surprising without context",
        "real trade-off",
    ):
        assert phrase in eligibility, f"{ADR_WITNESS}: {phrase!r}"


def test_adr_ledger_entries_are_candidates_not_automatic() -> None:
    ledger = _section(ADR, "Decision ledger", ADR_WITNESS).casefold()
    for phrase in (
        "[agent-decided]",
        "candidate",
        "not an automatic adr",
        "all three",
    ):
        assert phrase in ledger, f"{ADR_WITNESS}: {phrase!r}"


def test_adr_filter_carried_by_skill_and_spec_template() -> None:
    _assert_phrases(MOLD_SKILL, ADR_WITNESS, "all three adr eligibility criteria")
    _assert_phrases(CURDLE, ADR_WITNESS, "qualifying decisions get full adrs per `adr.md`")


# --- AC-2: Grill boundary-scenario rule ------------------------------------

GRILL_WITNESS = "modes.md missing Grill boundary-scenario rule"


def test_grill_requires_concrete_boundary_scenarios() -> None:
    body = _text(MODES)
    mode_names = re.findall(
        r"^### (Explore|Ground|Shape|Sketch|Grill|Diagnose) —", body, re.MULTILINE
    )
    assert mode_names == ["Explore", "Ground", "Shape", "Sketch", "Grill", "Diagnose"]

    grill = _subsection(MODES, "Grill — adversarial clarification", GRILL_WITNESS)
    folded = grill.casefold()
    for phrase in (
        "boundary-scenario rule",
        "domain boundaries or relationships are in scope",
        "invent at least one concrete scenario",
    ):
        assert phrase in folded, f"{GRILL_WITNESS}: {phrase!r}"


# --- AC-3: ambiguous second-context routing + worked example ---------------

CONTEXT_WITNESS = "curdle.md missing second-context routing"


def test_ambiguous_second_context_routes_through_question_transport() -> None:
    domain_model = _section(
        CURDLE, "Domain model (cumulative by-product)", CONTEXT_WITNESS
    )
    assert "existing or proposed second context" in domain_model.casefold(), CONTEXT_WITNESS
    assert "ask-user-question.md" in domain_model, CONTEXT_WITNESS
    assert "write only the selected context" in domain_model.casefold(), CONTEXT_WITNESS


def test_second_context_worked_example_runs_end_to_end() -> None:
    example = _section(
        CURDLE, "Worked example — term to durable record", CONTEXT_WITNESS
    )
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
        if phrase.casefold() in folded
    ]
    assert len(positions) == 5, f"{CONTEXT_WITNESS}: worked example steps incomplete"
    assert positions == sorted(positions), CONTEXT_WITNESS
    for phrase in (
        "ask the user which bounded context owns the term",
        "write only the selected context",
    ):
        assert phrase in folded, f"{CONTEXT_WITNESS}: {phrase!r}"


# --- AC-4: glossary folded into the Durable-writes gate --------------------

GLOSSARY_GATE_WITNESS = "durable-writes gate label missing glossary"
GLOSSARY_GATE_PHRASE = "glossary target included when terms were resolved"


def test_glossary_gate_label_in_handshake_and_gate_graph() -> None:
    _assert_phrases(HANDSHAKE, GLOSSARY_GATE_WITNESS, GLOSSARY_GATE_PHRASE)
    assert (
        GLOSSARY_GATE_PHRASE in _text(GATE_GRAPH_SRC).casefold()
    ), f"{GLOSSARY_GATE_WITNESS}: gate_graph.py"


def test_glossary_gate_durable_write_protocol_covers_glossary() -> None:
    atomic = _section(CURDLE, "Atomic write", GLOSSARY_GATE_WITNESS).casefold()
    for phrase in (
        "per-slug glossary when ground resolved terms",
        "read back",
        "completion record",
    ):
        assert phrase in atomic, f"{GLOSSARY_GATE_WITNESS}: {phrase!r}"


# --- AC-5: transport-audit direct-pointer escape hatch ---------------------

TRANSPORT_WITNESS = "transport-pointer site wrongly flagged"


def test_transport_pointer_site_is_accounted(tmp_path: Path) -> None:
    skill_dir = tmp_path / "skills" / "newskill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "# New Skill\n\nBefore running, ask the user to pick an option through "
        "[`ask-user-question.md`](../cheese/references/ask-user-question.md).\n",
        encoding="utf-8",
    )
    candidates = list((tmp_path / "skills").glob("*/SKILL.md"))
    flagged = _unaccounted_sites(
        candidates, tmp_path, sibling_owned=set(), accounted=set()
    )
    assert flagged == [], f"{TRANSPORT_WITNESS}: {flagged}"


# --- AC-6: manual transcript eval cases ------------------------------------

EVAL_WITNESS = "evals.md missing manual transcript case"


def test_manual_eval_overloaded_term_requires_full_durable_flush() -> None:
    case = _subsection(
        EVALS, "Overloaded term → Ground → durable writes", EVAL_WITNESS
    ).casefold()
    for phrase in (
        "canonical-term question",
        ".cheese/glossary/<slug>.md",
        "cumulative domain model",
        "reads both back",
        "completion record",
    ):
        assert phrase in case, f"{EVAL_WITNESS}: {phrase!r}"


def test_manual_eval_adr_matrix_covers_positive_and_each_negative() -> None:
    case = _subsection(EVALS, "ADR eligibility matrix", EVAL_WITNESS)
    qualifying = [
        line for line in case.splitlines() if "qualifies: all three" in line.casefold()
    ]
    assert qualifying and "write one ADR" in qualifying[0], EVAL_WITNESS
    for criterion in (
        "missing hard to reverse",
        "missing surprising without context",
        "missing real trade-off",
    ):
        outcomes = [
            line for line in case.splitlines() if criterion in line.casefold()
        ]
        assert outcomes, f"{EVAL_WITNESS}: {criterion!r}"
        assert "spec decision-log" in outcomes[0], f"{EVAL_WITNESS}: {criterion!r}"
        assert "write no ADR" in outcomes[0], f"{EVAL_WITNESS}: {criterion!r}"


def test_manual_eval_ambiguous_second_context_asks_and_writes_selection() -> None:
    case = _subsection(
        EVALS, "Ambiguous second-context routing", EVAL_WITNESS
    ).casefold()
    assert "asks the user" in case, EVAL_WITNESS
    assert "writes only the selected context" in case, EVAL_WITNESS


# --- AC-7: downstream consumption (durability pin; passes on current main) --


def test_downstream_skills_consume_domain_terms() -> None:
    # press and age read the per-slug glossary from their SKILL.md.
    for name in ("press", "age"):
        _assert_phrases(
            SKILLS / name / "SKILL.md",
            "downstream glossary consumption",
            ".cheese/glossary/<slug>.md",
        )
    # cure bounds domain-model correction in SKILL.md; the hard rules live in
    # its reference file, not SKILL.md verbatim.
    _assert_phrases(
        SKILLS / "cure" / "SKILL.md",
        "downstream cure bounding",
        "diff-touched terms only",
    )
    _assert_phrases(
        SKILLS / "cure" / "references" / "domain-model-correction.md",
        "downstream cure hard rules",
        "flag, don't reverse",
        "never overrules",
    )
    # KNOWN GAP (follow-up, not asserted): skills/cook/SKILL.md has no
    # glossary read today.
