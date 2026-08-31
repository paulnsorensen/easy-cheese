"""Contract guard for #543 — bounded active orchestration + the grounded fast path.

Measurement on #543 (16 top-level invocations, plus the 20-run session
cross-check) found the two levers that would have cut mold's active time were
written as hedged *steps*: wiki grounding degraded to "skip; proceed with code
evidence only", and explorer delegation read as an accelerator. Rules written as
suggestions get skipped — 2 `ground` calls and 1 explorer spawn across 20 runs,
against 28 hand-run Bash calls per run. So both became preconditions with a
coherence gate behind them, and each phase got a bound with a named exhaustion
move instead of waiting on token pressure.

These tests pin the parts of that contract that live in more than one file and
would otherwise drift apart: the two gates must exist in the machine-readable
gate model and reach the handshake, the fork-round cap must be the same number
in `SKILL.md` and the budget table, every budget row must still name both a
bound and an exhaustion move, and the fast path must keep its coverage triad and
its gate carve-out. Handshake-checklist ↔ `COHERENCE_GATES` parity is asserted
in `test_gate_graph.py`; this file asserts what the two new gates *say*.
"""

from __future__ import annotations

import re
from pathlib import Path
from types import ModuleType
from typing import Protocol, cast

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MOLD_SKILL = REPO_ROOT / "skills" / "mold" / "SKILL.md"
CONTEXT_BUDGET = REPO_ROOT / "skills" / "mold" / "references" / "context-budget.md"
GROUNDING = REPO_ROOT / "skills" / "mold" / "references" / "grounding.md"

GROUNDING_GATE = "grounding-recorded"
EXPLORATION_GATE = "exploration-delegated"

_WORD_NUMBERS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
}


class _Node(Protocol):
    id: str
    label: str
    kind: str


class _Edge(Protocol):
    src: str
    dst: str
    label: str


class _GateModel(Protocol):
    nodes: tuple[_Node, ...]
    edges: tuple[_Edge, ...]

    def by_kind(self, kind: str) -> tuple[_Node, ...]: ...
    def ids(self) -> set[str]: ...


class _GateGraphModule(Protocol):
    GATE_MODEL: _GateModel
    HANDSHAKE: _Node


@pytest.fixture
def gate_graph(gate_graph: ModuleType) -> _GateGraphModule:
    return cast(_GateGraphModule, cast(object, gate_graph))


def _table_rows(markdown: str, first_header: str) -> list[list[str]]:
    """Cells of the pipe table whose header row starts with ``first_header``.

    Returns body rows only (header and the `---` separator are dropped), each as
    a list of stripped cell strings.
    """
    rows: list[list[str]] = []
    collecting = False
    for line in markdown.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            if collecting:
                break
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if not collecting:
            if cells and cells[0] == first_header:
                collecting = True
            continue
        if set("".join(cells)) <= {"-", ":"}:
            continue
        rows.append(cells)
    return rows


def _first_number(text: str) -> int | None:
    digits = re.search(r"\b(\d+)\b", text)
    if digits:
        return int(digits.group(1))
    words = re.search(r"\b(" + "|".join(_WORD_NUMBERS) + r")\b", text, re.I)
    return _WORD_NUMBERS[words.group(1).lower()] if words else None


def _gate(model: _GateModel, gate_id: str) -> _Node:
    matches = [n for n in model.by_kind("gate") if n.id == gate_id]
    assert matches, (
        f"coherence gate {gate_id!r} is missing from the gate model — "
        f"#543 made grounding and explorer delegation gates, not hedged steps; "
        f"present gates: {sorted(n.id for n in model.by_kind('gate'))}"
    )
    return matches[0]


def test_orchestration_gates_reach_the_handshake(gate_graph: _GateGraphModule) -> None:
    model = gate_graph.GATE_MODEL
    handshake_id = gate_graph.HANDSHAKE.id
    for gate_id in (GROUNDING_GATE, EXPLORATION_GATE):
        node = _gate(model, gate_id)
        assert any(e.src == node.id and e.dst == handshake_id for e in model.edges), (
            f"gate {gate_id!r} does not feed {handshake_id!r} — an unwired gate "
            "blocks nothing, which is the failure mode #543 was filed about"
        )


def test_grounding_gate_binds_the_first_structured_question(
    gate_graph: _GateGraphModule,
) -> None:
    label = _gate(gate_graph.GATE_MODEL, GROUNDING_GATE).label.lower()
    assert "first structured question" in label, (
        "the grounding gate must name the moment it blocks (the first structured "
        f"question); a bare 'grounding done' gate has no trigger: {label!r}"
    )
    assert "absent" in label, (
        "the grounding gate must accept an explicit hallouminate-absent record, "
        f"or the degrade path becomes a hard block on an optional plugin: {label!r}"
    )


def test_exploration_gate_accepts_a_recorded_parent_context_fallback(
    gate_graph: _GateGraphModule,
) -> None:
    label = _gate(gate_graph.GATE_MODEL, EXPLORATION_GATE).label.lower()
    assert "digest" in label, (
        f"the exploration gate must require the explorer's digest: {label!r}"
    )
    assert "record" in label, (
        "hand-run parent-context exploration must remain reachable as a *recorded* "
        f"degrade — otherwise the gate is unsatisfiable without sub-agents: {label!r}"
    )


def test_wiki_grounding_fallback_leaves_a_record() -> None:
    rows = _table_rows(MOLD_SKILL.read_text(encoding="utf-8"), "Need")
    grounding_rows = [r for r in rows if "Wiki grounding" in r[0]]
    assert len(grounding_rows) == 1, (
        f"expected exactly one wiki-grounding row in SKILL.md's tool table, got "
        f"{len(grounding_rows)}"
    )
    fallback = grounding_rows[0][-1].lower()
    assert "ledger" in fallback, (
        "the wiki-grounding fallback must write the absence to the ledger. The "
        "measured regression in #543 was a silent 'skip; proceed with code "
        f"evidence only', which reads as optional: {fallback!r}"
    )


def test_fork_round_cap_agrees_between_skill_and_budget_table() -> None:
    skill_rule = [
        line
        for line in MOLD_SKILL.read_text(encoding="utf-8").splitlines()
        if "fork round" in line.lower() and line.lstrip().startswith("-")
    ]
    assert len(skill_rule) == 1, (
        f"expected exactly one fork-round rule in SKILL.md § Rules, got {skill_rule}"
    )
    budget_rows = _table_rows(CONTEXT_BUDGET.read_text(encoding="utf-8"), "Budget")
    fork_rows = [r for r in budget_rows if r[0].lower().startswith("fork round")]
    assert len(fork_rows) == 1, f"expected one 'Fork rounds' budget row, got {fork_rows}"

    skill_cap = _first_number(skill_rule[0])
    budget_cap = _first_number(fork_rows[0][1])
    assert skill_cap is not None and skill_cap == budget_cap, (
        f"fork-round cap drifted: SKILL.md says {skill_cap}, "
        f"context-budget.md says {budget_cap} — they are one rule in two files"
    )


def test_every_budget_names_a_bound_and_an_exhaustion_move() -> None:
    rows = _table_rows(CONTEXT_BUDGET.read_text(encoding="utf-8"), "Budget")
    assert len(rows) >= 4, f"orchestration budget table lost rows: {rows}"
    for row in rows:
        assert len(row) == 3, f"budget row is not (budget, bound, on exhaustion): {row}"
        budget, bound, on_exhaustion = row
        assert bound, f"budget {budget!r} has no bound — an unbounded budget is prose"
        assert on_exhaustion, (
            f"budget {budget!r} names no exhaustion move; #543's whole point is that "
            "hitting the bound must force a checkpoint or a recorded degrade"
        )

    covered = " ".join(r[0].lower() for r in rows)
    for axis in ("fork round", "tool call", "spawn", "failure"):
        assert axis in covered, (
            f"no budget covers {axis!r} — the cost axes #543 measured were tool "
            f"calls, sub-agent spawns, repeated failures, and fork rounds: {covered!r}"
        )


def test_fast_path_coverage_requires_all_three_criteria() -> None:
    text = GROUNDING.read_text(encoding="utf-8")
    _, _, fast_path = text.partition("## Prior-evidence fast path")
    assert fast_path, "grounding.md lost the prior-evidence fast path (#543)"
    fast_path = fast_path.split("\n## ")[0].lower()
    for criterion in ("cited", "fresh", "decisive"):
        assert f"**{criterion}.**" in fast_path, (
            f"the fast path's coverage test must keep its {criterion!r} criterion — "
            "dropping one lets uncited or stale prior evidence skip a pass"
        )


def test_fast_path_never_skips_a_gate() -> None:
    text = GROUNDING.read_text(encoding="utf-8").lower()
    _, _, fast_path = text.partition("## prior-evidence fast path")
    fast_path = fast_path.split("\n## ")[0]
    assert "two-key handshake" in fast_path and "taste test" in fast_path, (
        "the fast path must state that it skips work, never a gate: the two-key "
        "handshake and the fresh-context fork taste test stay out of its reach "
        "(#543 non-goals)"
    )
