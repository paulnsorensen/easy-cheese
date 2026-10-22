"""Regression guard: the Mold altitude and diagram evals stay consistent.

Each altitude topic has a draft case and a pick case. The pick answer key must
be a permutation of the three labels, and the fixture must hold three drafts.
The `right` draft opens with one diagram that `diagrams.md` allows and rejects
options. The `too-high` draft rejects nothing. The fence rule that grades a
draft spec accepts only `mermaid` diagrams and the `text` Placement block.

Each diagram view case names one `diagrams.md` view in its expected output.
Each fork-card case lists the forks of its state fixture, and the expected
output gives each fork a graph or a symbol table.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import cast

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MOLD = REPO_ROOT / "skills" / "mold"
EVALS_JSON = MOLD / "evals" / "evals.json"
EVALS_FILES = MOLD / "evals" / "files"
EVALS_DOC = MOLD / "references" / "evals.md"
DIAGRAMS_DOC = REPO_ROOT / "skills" / "cheese" / "references" / "diagrams.md"

LABELS = ("X", "Y", "Z")
VERDICTS = {"too-low", "right", "too-high"}
ALLOWED_FENCES = {"mermaid", "text"}
DIAGRAM_KINDS = {"flowchart", "sequenceDiagram", "stateDiagram-v2", "erDiagram", "classDiagram"}
FENCE = re.compile(r"^\s*(```+|~~~+)\s*([\w+-]*)")
KEY = re.compile(r"\b([XYZ]): (too-low|right|too-high)\b")
# Terms from the source design-doc skill and its company tooling.
SCRUBBED = re.compile(
    r"\b(rung|outlines?|preset|notion|linear|multiplier|corp doc|corp-\d+|technical initiative|generate-design-doc)\b",
    re.IGNORECASE,
)


def _cases() -> list[dict[str, object]]:
    data = cast(dict[str, object], json.loads(EVALS_JSON.read_text(encoding="utf-8")))
    assert data["skill_name"] == "mold"
    return cast(list[dict[str, object]], data["evals"])


def _family(family: str) -> list[dict[str, object]]:
    return [case for case in _cases() if case["family"] == family]


def _pick_cases() -> list[dict[str, object]]:
    return [case for case in _family("altitude") if cast(str, case["name"]).endswith("-pick")]


def _answer_key(case: dict[str, object]) -> dict[str, str]:
    return dict(KEY.findall(cast(str, case["expected_output"])))


def _drafts(case: dict[str, object]) -> dict[str, str]:
    text = (MOLD / cast(list[str], case["files"])[0]).read_text(encoding="utf-8")
    parts = re.split(r"^## Draft ([XYZ])\n", text, flags=re.M)
    return dict(zip(parts[1::2], parts[2::2], strict=True))


def fence_violations(text: str) -> list[str]:
    """Return the info string of each opening fence that a draft spec may not hold."""
    violations: list[str] = []
    opened = False
    for line in text.splitlines():
        match = FENCE.match(line)
        if not match:
            continue
        if not opened and match.group(2) not in ALLOWED_FENCES:
            violations.append(match.group(2) or "untagged")
        opened = not opened
    return violations


def test_cases_have_unique_ids_and_existing_files() -> None:
    cases = _cases()
    assert [case["id"] for case in cases] == list(range(len(cases)))
    assert len({case["name"] for case in cases}) == len(cases)
    assert {case["family"] for case in cases} == {"altitude", "diagram"}
    for case in cases:
        for rel in cast(list[str], case["files"]):
            assert (MOLD / rel).is_file(), rel
            assert rel in cast(str, case["prompt"])


def test_every_topic_has_a_draft_case_and_a_pick_case() -> None:
    names = {cast(str, case["name"]) for case in _family("altitude")}
    topics = {name for name in names if not name.endswith("-pick")}
    assert len(topics) == 8
    assert names == topics | {f"{topic}-pick" for topic in topics}


def _fixture_tier(case: dict[str, object]) -> str:
    text = (MOLD / cast(list[str], case["files"])[0]).read_text(encoding="utf-8")
    tier = re.search(r"^Tier: (quick|light|full)\.$", text, re.M)
    assert tier, case["name"]
    return tier.group(1)


def test_draft_prompt_tier_matches_the_problem_fixture() -> None:
    for case in _family("altitude"):
        if cast(str, case["name"]).endswith("-pick"):
            continue
        assert f"`tier: {_fixture_tier(case)}`" in cast(str, case["prompt"])
        assert "answer/spec.md" in cast(str, case["prompt"])
        assert any("R-ALT-DIAGRAM" in a for a in cast(list[str], case["assertions"]))


# Each view case maps to (the phrase in its expected output, the `diagrams.md` term for that view).
VIEW_CASES = {
    "dg-view-container": ("Container view", "**Container** view"),
    "dg-view-component": ("Component view", "**Component** view"),
    "dg-view-context": ("System Context view", "**System Context** view"),
    "dg-view-landscape": ("System Landscape view", "**System Landscape** view"),
    "dg-view-deployment": ("Deployment view", "**Deployment** view"),
    "dg-view-sequence": ("`sequenceDiagram`", "**sequence** diagram"),
    "dg-view-async-sequence": ("asynchronous `sequenceDiagram`", "**asynchronous sequence** diagram"),
    "dg-view-agent-handoff": ("agent handoff `sequenceDiagram`", "**agent handoff sequence** diagram"),
    "dg-view-database": ("database diagram", "**database** diagram"),
    "dg-view-state": ("`stateDiagram-v2`", "**state** diagram"),
    "dg-view-flow": ("flow diagram", "**flow** diagram"),
    "dg-view-overlap-async": ("asynchronous `sequenceDiagram`", "**asynchronous sequence** diagram"),
    "dg-view-overlap-container": ("Container view", "**Container** view"),
    "dg-view-pressure": ("database diagram", "**database** diagram"),
}


def test_diagram_view_cases_name_one_checklist_view() -> None:
    cases = {cast(str, c["name"]): c for c in _family("diagram") if cast(str, c["name"]).startswith("dg-view-")}
    assert set(cases) == set(VIEW_CASES)
    checklist = DIAGRAMS_DOC.read_text(encoding="utf-8")
    for name, (phrase, term) in VIEW_CASES.items():
        case = cases[name]
        prompt = cast(str, case["prompt"])
        assertions = " ".join(cast(list[str], case["assertions"]))
        assert phrase in cast(str, case["expected_output"]), name
        assert re.search(rf"Draw an? {re.escape(term)}\b", checklist), term
        assert f"`tier: {_fixture_tier(case)}`" in prompt
        assert "answer/diagrams.md" in prompt
        assert "R-DIAG-VIEW" in assertions and "R-DIAG-NOTATION" in assertions
        assert ("R-DIAG-SMALLEST" in assertions) == (name == "dg-view-pressure")


def test_fork_card_cases_cover_every_fork_of_the_state() -> None:
    cases = [c for c in _family("diagram") if cast(str, c["name"]).startswith("dg-fork-")]
    assert len(cases) == 3
    for case in cases:
        state = (MOLD / cast(list[str], case["files"])[0]).read_text(encoding="utf-8")
        forks = cast(list[str], re.findall(r"^- (F-\d+): ", state, re.M))
        assert forks == [f"F-{n}" for n in range(1, len(forks) + 1)], case["name"]
        prompt = cast(str, case["prompt"])
        expected = cast(str, case["expected_output"])
        assert f"F-1 to {forks[-1]} in order" in prompt
        assert "does not render Mermaid" in prompt
        assert all(fork in expected for fork in forks), case["name"]
        assert f"{forks[-1]} uses a symbol table and no graph" in expected
        assert "no mermaid fence" in expected
        ids = {a.split(" ", 1)[0].lstrip("[") for a in cast(list[str], case["assertions"])}
        assert {"R-FORK-GRAPH", "R-FORK-TABLE", "R-FORK-NO-MERMAID", "R-FORK-FIELDS"} <= ids


def _case_id(case: object) -> str:
    return cast(str, cast(dict[str, object], case)["name"])


def _draft_with(case: dict[str, object], verdict: str) -> str:
    key = _answer_key(case)
    return _drafts(case)[next(label for label, given in key.items() if given == verdict)]


@pytest.mark.parametrize("case", _pick_cases(), ids=_case_id)
def test_pick_key_is_a_permutation_of_the_three_verdicts(case: dict[str, object]) -> None:
    key = _answer_key(case)
    assert sorted(key) == list(LABELS)
    assert set(key.values()) == VERDICTS
    assert sorted(_drafts(case)) == list(LABELS)


@pytest.mark.parametrize("case", _pick_cases(), ids=_case_id)
def test_right_draft_opens_with_one_allowed_diagram(case: dict[str, object]) -> None:
    right = _draft_with(case, "right")
    assert fence_violations(right) == []
    blocks = cast(list[str], re.findall(r"^```mermaid\n(.*?)^```", right, re.M | re.S))
    assert len(blocks) == 1
    assert blocks[0].split(maxsplit=1)[0] in DIAGRAM_KINDS
    assert "C4Context" not in blocks[0]
    assert right.index("```mermaid") < right.index("\n- ")
    assert re.search(r"^Title: `[^`]+`\.$", right, re.M)
    assert "Rejected:" in right
    too_high = _draft_with(case, "too-high")
    assert "Rejected:" not in too_high
    assert "```" not in too_high


def test_fence_rule_rejects_the_too_low_bodies() -> None:
    rejected: set[str] = set()
    for case in _pick_cases():
        rejected.update(fence_violations(_draft_with(case, "too-low")))
    assert {"yaml", "ebnf", "python", "sql", "lua"} <= rejected
    assert fence_violations("```text\nslice: billing\n```\n") == []


def test_fixtures_hold_no_source_skill_or_company_terms() -> None:
    paths = [EVALS_JSON, *sorted(EVALS_FILES.rglob("*.md"))]
    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert not SCRUBBED.search(text), f"{path.relative_to(REPO_ROOT)}: {SCRUBBED.search(text)}"


def test_evals_reference_points_at_the_altitude_and_diagram_cases() -> None:
    doc = EVALS_DOC.read_text(encoding="utf-8")
    assert "## Altitude evals" in doc
    assert "## Diagram evals" in doc
    assert "(../evals/evals.json)" in doc
    assert "(../../cheese/references/diagrams.md)" in doc
    assert "tests/python/test_mold_altitude_evals.py" in doc
    ids = (
        "R-ALT-ACTOR", "R-ALT-SEAMS", "R-ALT-CRUX", "R-ALT-DECIDE", "R-ALT-SCOPE", "R-ALT-DIAGRAM",
        "R-DIAG-VIEW", "R-DIAG-SMALLEST", "R-DIAG-NOTATION",
        "R-FORK-GRAPH", "R-FORK-C4", "R-FORK-TABLE", "R-FORK-NO-MERMAID", "R-FORK-FIELDS",
    )
    for rid in ids:
        assert f"`{rid}`" in doc, rid
    for case in _cases():
        for assertion in cast(list[str], case["assertions"]):
            rid = assertion.split(" ", 1)[0].lstrip("[")
            assert f"`{rid}`" in doc, rid
