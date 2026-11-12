"""Regression guard: the Mold altitude and diagram evals stay consistent.

Each altitude topic has a draft case and a pick case in one family, so a
near-copy never crosses a train, validation, or holdout split. The set needs
at least four task families, because the skillz splitter refuses fewer.

A draft fixture records the user's fork decisions and leaves one fork open.
The draft case must hold that fork as `[TBD]`, `[?]`, or `[BLOCKED]` instead
of deciding it.

A prompt gives the task, the files, and the output form. It never states a
rule that an assertion grades, so a Mold without that rule fails the case.
Each assertion is one skillz EARS criterion, and one ID has one text.

The pick answer key must be a permutation of the three labels. All three
drafts share the same surface sections, so no single section, fence, or
length rank gives away the key. The `right` draft opens with one diagram that
`diagrams.md` allows. The fence rule that grades a draft spec accepts only
`mermaid` diagrams and the `text` Placement block.

Each diagram view case names one `diagrams.md` view in its expected output.
Each fork-card case lists the forks of its state fixture, and the expected
output gives each fork a graph or a symbol table.
"""

from __future__ import annotations

import itertools
import json
import re
from collections.abc import Callable
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
VERDICTS = ("too-low", "right", "too-high")
ALLOWED_FENCES = {"mermaid", "text"}
DIAGRAM_KINDS = {"flowchart", "sequenceDiagram", "stateDiagram-v2", "erDiagram", "classDiagram"}
FAMILIES = {"alt-runtime", "alt-rack", "alt-language", "alt-product", "diag-structure", "diag-behavior", "diag-data"}
# The skillz splitter needs two train families, a validation family, and a holdout family.
MINIMUM_FAMILIES = 4
# Phrases that state a graded Mold rule. A prompt that holds one gives the rule away.
RULE_LEAKS = (
    "execution_holds",
    "handshake.md",
    "voice.md",
    "references/diagrams.md",
    "do not decide",
    "simulate a user reply",
    "Placement block",
    "pseudocode",
    "helper signature",
    "rejected option",
    "Title: <view>",
)
ASSERTION = re.compile(r"^\[([A-Z][A-Z0-9-]+) \| (critical|pass-fail|quality) \| (Ubiquitous|Event|Unwanted|Optional)\] (.+)$")
EARS_TRIGGER = {"Ubiquitous": None, "Event": "WHEN", "Unwanted": "IF", "Optional": "WHERE"}
# The criterion shape that skillz accepts (`_ears` in skillz_experiments/_cases.py): one optional
# leading WHEN, WHILE, IF, or WHERE clause, then one THE <subject> SHALL <response>.
EARS = re.compile(r"(?:(?P<trigger>WHEN|WHILE|IF|WHERE)\s+\S.*?\s+)?THE\s+\S.*?\s+SHALL\s+\S.*", re.S)
EARS_WORDS = re.compile(r"\b(?:WHEN|WHILE|IF|WHERE|THE|SHALL)\b")
QUOTED = re.compile(r"`[^`]*`|\"[^\"]*\"")
# The most pick cases that one surface cue or length rank may predict in full.
MAX_CUE_HITS = 4
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


def _named(prefix: str) -> list[dict[str, object]]:
    return [case for case in _cases() if cast(str, case["name"]).startswith(prefix)]


def _pick_cases() -> list[dict[str, object]]:
    return [case for case in _named("al-") if cast(str, case["name"]).endswith("-pick")]


def _draft_cases() -> list[dict[str, object]]:
    return [case for case in _named("al-") if not cast(str, case["name"]).endswith("-pick")]


def _fixture(case: dict[str, object]) -> str:
    return (MOLD / cast(list[str], case["files"])[0]).read_text(encoding="utf-8")


def _answer_key(case: dict[str, object]) -> dict[str, str]:
    return dict(KEY.findall(cast(str, case["expected_output"])))


def _split_drafts(text: str) -> dict[str, str]:
    parts = re.split(r"^## Draft ([XYZ])\n", text, flags=re.M)
    labels = parts[1::2]
    assert labels == list(LABELS), labels
    drafts = dict(zip(labels, parts[2::2], strict=True))
    return {label: body.split("\nSource:", 1)[0] for label, body in drafts.items()}


def _drafts(case: dict[str, object]) -> dict[str, str]:
    return _split_drafts(_fixture(case))


def _ids(case: dict[str, object]) -> set[str]:
    return {a.split(" ", 1)[0].lstrip("[") for a in cast(list[str], case["assertions"])}


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
    assert {case["family"] for case in cases} == FAMILIES
    assert len(_named("al-")) + len(_named("dg-")) == len(cases)
    for case in cases:
        for rel in cast(list[str], case["files"]):
            assert (MOLD / rel).is_file(), rel
            assert rel in cast(str, case["prompt"])


def test_families_keep_near_copies_together_and_can_split() -> None:
    altitude = {cast(str, c["family"]) for c in _named("al-")}
    diagram = {cast(str, c["family"]) for c in _named("dg-")}
    assert altitude.isdisjoint(diagram)
    assert len(altitude | diagram) >= MINIMUM_FAMILIES
    by_name = {cast(str, c["name"]): c for c in _cases()}
    for pick in _pick_cases():
        draft = by_name[cast(str, pick["name"]).removesuffix("-pick")]
        assert pick["family"] == draft["family"], pick["name"]


def test_every_topic_has_a_draft_case_and_a_pick_case() -> None:
    names = {cast(str, case["name"]) for case in _named("al-")}
    topics = {name for name in names if not name.endswith("-pick")}
    assert len(topics) == 8
    assert names == topics | {f"{topic}-pick" for topic in topics}


def _fixture_tier(case: dict[str, object]) -> str:
    tier = re.search(r"^Tier: (quick|light|full)\.$", _fixture(case), re.M)
    assert tier, case["name"]
    return tier.group(1)


def test_draft_prompt_tier_matches_the_problem_fixture() -> None:
    for case in _draft_cases():
        assert f"`tier: {_fixture_tier(case)}`" in cast(str, case["prompt"])
        assert "answer/spec.md" in cast(str, case["prompt"])
        assert {"R-ALT-DIAGRAM", "R-ALT-HOLD-OPEN"} <= _ids(case)


def _leaks(prompt: str) -> list[str]:
    return [phrase for phrase in RULE_LEAKS if phrase in prompt]


def test_prompts_do_not_hand_over_the_graded_rules() -> None:
    for case in _cases():
        assert not _leaks(cast(str, case["prompt"])), case["name"]


def test_leak_probe_rejects_the_original_hold_prompt() -> None:
    leaky = "Keep each open fork, marked as `references/handshake.md` allows, with an `execution_holds` entry."
    assert _leaks(leaky) == ["execution_holds", "handshake.md"]


def _ears(text: str) -> str | None:
    """Return the leading EARS keyword of one skillz criterion, `THE` when it has none, or None."""
    plain = QUOTED.sub('""', text).strip()
    match = EARS.fullmatch(plain)
    if not match:
        return None
    expected = ([match["trigger"]] if match["trigger"] else []) + ["THE", "SHALL"]
    return (match["trigger"] or "THE") if EARS_WORDS.findall(plain) == expected else None


def test_assertions_are_single_ears_criteria_with_one_text_per_id() -> None:
    texts: dict[str, str] = {}
    for case in _cases():
        for assertion in cast(list[str], case["assertions"]):
            match = ASSERTION.match(assertion)
            assert match, (case["name"], assertion)
            rid, _, form, text = match.groups()
            assert _ears(text) == (EARS_TRIGGER[form] or "THE"), (rid, form, text)
            assert texts.setdefault(rid, text) == text, f"{rid} has two texts"


def test_ears_probe_rejects_a_compound_or_lowercase_assertion() -> None:
    assert _ears("THE spec SHALL keep the fork open.") == "THE"
    assert _ears("WHEN a fork is open THE spec SHALL hold it.") == "WHEN"
    assert _ears("The spec shall keep the fork open.") is None
    assert _ears("WHEN a fork is open THE spec SHALL hold it. WHEN a choice is made THE spec SHALL record it.") is None


def test_draft_cases_hold_the_open_fork_instead_of_deciding_it() -> None:
    for case in _draft_cases():
        prompt = cast(str, case["prompt"])
        fixture = _fixture(case)
        assert "AGENT-DECIDED: no human" not in prompt, case["name"]
        assert "Nobody answers a question in this run." in prompt, case["name"]
        assert {"R-ALT-HOLD-USER", "R-ALT-HOLD-OPEN"} <= _ids(case), case["name"]
        assert "## Recorded user decisions" in fixture, case["name"]
        forks = re.findall(r"^- (D-\d+ \(user\)|Open \(no user decision yet\)):", fixture, re.M)
        assert forks.count("Open (no user decision yet)") == 1, case["name"]
        assert "open with an `execution_holds` entry" in cast(str, case["expected_output"])
        # tiers.md: Light allows at most two consequential forks; three or more mean Full.
        assert len(forks) <= 2 or _fixture_tier(case) == "full", case["name"]


# Each view case maps to (expected output phrase, `diagrams.md` checklist term, fixture fact that selects it).
VIEW_CASES = {
    "dg-view-container": ("Container view", "**Container** view", "adds a report service"),
    "dg-view-component": ("Component view", "**Component** view", "The change stays inside it."),
    "dg-view-context": ("System Context view", "**System Context** view", "No external system is added."),
    "dg-view-landscape": ("System Landscape view", "**System Landscape** view", "three software systems"),
    "dg-view-deployment": ("Deployment view", "**Deployment** view", "adds a second region"),
    "dg-view-sequence": ("`sequenceDiagram`", "**sequence** diagram", "moves the fraud call before the card provider call"),
    "dg-view-async-sequence": (
        "asynchronous `sequenceDiagram`", "**asynchronous sequence** diagram", "No application, data store, or queue is added.",
    ),
    "dg-view-agent-handoff": (
        "agent handoff `sequenceDiagram`", "**agent handoff sequence** diagram", "hand code research to a code-explorer sub-agent",
    ),
    "dg-view-database": ("database diagram", "**database** diagram", "adds two tables"),
    "dg-view-state": ("`stateDiagram-v2`", "**state** diagram", "no table, column, or service changes"),
    "dg-view-flow": ("flow diagram", "**flow** diagram", "Each ticket crosses three existing modules"),
    "dg-view-overlap-async": ("asynchronous `sequenceDiagram`", "**asynchronous sequence** diagram", "already exist"),
    "dg-view-overlap-container": ("Container view", "**Container** view", "The search service and its index are new."),
    "dg-view-pressure": ("database diagram", "**database** diagram", "The real risk is the schema"),
}


def test_diagram_view_cases_name_one_checklist_view() -> None:
    cases = {cast(str, c["name"]): c for c in _named("dg-view-")}
    assert set(cases) == set(VIEW_CASES)
    checklist = DIAGRAMS_DOC.read_text(encoding="utf-8")
    for name, (phrase, term, fact) in VIEW_CASES.items():
        case = cases[name]
        prompt = cast(str, case["prompt"])
        assert phrase in cast(str, case["expected_output"]), name
        # The fixture fact that makes the checklist select this view, and no other.
        assert fact in _fixture(case), name
        assert re.search(rf"Draw an? {re.escape(term)}\b", checklist), term
        assert f"`tier: {_fixture_tier(case)}`" in prompt
        assert "answer/diagrams.md" in prompt
        assert {"R-DIAG-VIEW", "R-DIAG-C4-FLOWCHART", "R-DIAG-MERMAID"} <= _ids(case)
        assert ("R-DIAG-SMALLEST" in _ids(case)) == (name == "dg-view-pressure")


def test_fork_card_cases_cover_every_fork_of_the_state() -> None:
    cases = _named("dg-fork-")
    assert len(cases) == 3
    for case in cases:
        state = _fixture(case)
        forks = cast(list[str], re.findall(r"^- (F-\d+): ", state, re.M))
        assert forks == [f"F-{n}" for n in range(1, len(forks) + 1)], case["name"]
        # tiers.md: three or more open forks put the session in the Full tier.
        assert len(forks) < 3 or _fixture_tier(case) == "full", case["name"]
        prompt = cast(str, case["prompt"])
        expected = cast(str, case["expected_output"])
        assert f"F-1 to {forks[-1]} in order" in prompt
        assert "does not render Mermaid" in prompt
        assert all(fork in expected for fork in forks), case["name"]
        assert f"{forks[-1]} uses a symbol table and no graph" in expected
        assert "no mermaid fence" in expected
        assert {"R-FORK-GRAPH", "R-FORK-TABLE", "R-FORK-NO-MERMAID", "R-FORK-FIELDS"} <= _ids(case)


def _case_id(case: object) -> str:
    return cast(str, cast(dict[str, object], case)["name"])


def _draft_with(case: dict[str, object], verdict: str) -> str:
    key = _answer_key(case)
    return _drafts(case)[next(label for label, given in key.items() if given == verdict)]


# The pinned answer keys. A swapped label must fail here, not only in a live grade.
PICK_KEYS = {
    "al-kep-credential-plugin-pick": {"X": "too-high", "Y": "right", "Z": "too-low"},
    "al-rfc-dyn-trait-pick": {"X": "too-low", "Y": "too-high", "Z": "right"},
    "al-pep-dataclasses-pick": {"X": "right", "Y": "too-low", "Z": "too-high"},
    "al-oxide-control-plane-db-pick": {"X": "too-high", "Y": "too-low", "Z": "right"},
    "al-oxide-bootstrap-network-pick": {"X": "too-low", "Y": "right", "Z": "too-high"},
    "al-ticket-hold-pick": {"X": "right", "Y": "too-high", "Z": "too-low"},
    "al-rate-limiter-outage-pick": {"X": "too-high", "Y": "too-low", "Z": "right"},
    "al-crux-depth-pick": {"X": "too-low", "Y": "right", "Z": "too-high"},
}


@pytest.mark.parametrize("case", _pick_cases(), ids=_case_id)
def test_pick_key_is_a_permutation_of_the_three_verdicts(case: dict[str, object]) -> None:
    key = _answer_key(case)
    assert key == PICK_KEYS[cast(str, case["name"])]
    assert sorted(key) == list(LABELS)
    assert set(key.values()) == set(VERDICTS)
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
    assert "```text\nslice: " in right


SHARED_SECTIONS = ("- Problem: ", "- Decision", "- Crux", "- Rejected: ", "- Out of scope: ", "- Verification: ")


@pytest.mark.parametrize("case", _pick_cases(), ids=_case_id)
def test_every_pick_draft_shows_the_same_surface_sections(case: dict[str, object]) -> None:
    for label, draft in _drafts(case).items():
        assert "```mermaid\n" in draft, label
        assert re.search(r"^Title: `[^`]+`\.$", draft, re.M), label
        assert "Alternatives:" not in draft, label
        for section in SHARED_SECTIONS:
            assert section in draft, (label, section)


def _surface_features(text: str) -> set[str]:
    langs = cast(list[str], re.findall(r"^```(\w*)", text, re.M))
    words = cast(list[str], re.findall(r"^- ([A-Z][\w -]*?):", text, re.M))
    fields = cast(list[str], re.findall(r"^([a-z][a-z ]*):", text, re.M))
    found = {f"fence:{lang or 'untagged'}" for lang in langs}
    found |= {f"bullet:{word}" for word in words}
    found |= {f"field:{field}" for field in fields}
    if any(lang not in ALLOWED_FENCES for lang in langs):
        found.add("has:body fence")
    for token in ("TBD", "<br>[", "subgraph", "Legend:", "|---|", "because", "func ", "def ", "`", "user decides"):
        if token in text:
            found.add(f"has:{token}")
    return found


def _line_after(text: str, prefix: str) -> str:
    match = re.search(rf"^{re.escape(prefix)}(.*)$", text, re.M)
    return match.group(1) if match else ""


RANK_METRICS: tuple[Callable[[str], int], ...] = (
    len,
    lambda text: text.count("\n- "),
    lambda text: text.count(". "),
    lambda text: _line_after(text, "**Answer:** ").count(". "),
    lambda text: len(_line_after(text, "- Rejected: ").split()),
    lambda text: text.count("\n"),
)


def _cue_hits(drafts_and_keys: list[tuple[dict[str, str], dict[str, str]]]) -> int:
    """Return the most cases that one surface feature or one rank predicts in full."""
    features = [{label: _surface_features(text) for label, text in drafts.items()} for drafts, _ in drafts_and_keys]
    every = {feature for per_case in features for found in per_case.values() for feature in found}
    best = 0
    for feature, verdict, present in itertools.product(every, VERDICTS, (True, False)):
        hits = 0
        for per_case, (_, key) in zip(features, drafts_and_keys, strict=True):
            owners = [label for label, f in per_case.items() if (feature in f) == present]
            hits += len(owners) == 1 and key[owners[0]] == verdict
        best = max(best, hits)
    for metric, order in itertools.product(RANK_METRICS, itertools.permutations(VERDICTS)):
        hits = 0
        for drafts, key in drafts_and_keys:
            ranked = sorted(drafts, key=lambda label: metric(drafts[label]))
            hits += all(key[label] == order[rank] for rank, label in enumerate(ranked))
        best = max(best, hits)
    return best


def test_no_single_surface_cue_or_length_rank_predicts_the_pick_keys() -> None:
    drafts_and_keys = [(_drafts(case), _answer_key(case)) for case in _pick_cases()]
    assert _cue_hits(drafts_and_keys) <= MAX_CUE_HITS


def test_cue_probe_rejects_a_fixture_set_with_a_token_cue() -> None:
    """The probe must catch the original leak: only the right draft held `Rejected:`."""
    keys = [_answer_key(case) for case in _pick_cases()]
    leaky = [
        ({label: ("- Rejected: a reason\n" if verdict == "right" else "- Other: text\n") for label, verdict in key.items()}, key)
        for key in keys
    ]
    assert _cue_hits(leaky) == len(keys)


# A private helper with a call signature in the Placement block is a below-altitude detail.
PRIVATE_SIGNATURE = re.compile(r"^private: .*\w\([^)]*\)", re.M)


def test_each_too_low_draft_holds_a_body_or_a_helper_signature() -> None:
    rejected: set[str] = set()
    for case in _pick_cases():
        too_low = _draft_with(case, "too-low")
        violations = fence_violations(too_low)
        assert violations or PRIVATE_SIGNATURE.search(too_low), case["name"]
        assert not PRIVATE_SIGNATURE.search(_draft_with(case, "right")), case["name"]
        rejected.update(violations)
    assert {"yaml", "ebnf", "python", "sql"} <= rejected
    assert fence_violations("```text\nslice: billing\n```\n") == []
    assert not PRIVATE_SIGNATURE.search("private: zone windows; sent records\n")


def test_draft_split_rejects_a_repeated_label() -> None:
    with pytest.raises(AssertionError):
        _ = _split_drafts("## Draft X\na\n## Draft X\nb\n## Draft Y\nc\n## Draft Z\nd\n")


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
    for family in FAMILIES:
        assert f"`{family}`" in doc, family
    assert "`must`" in doc
    for case in _cases():
        for rid in _ids(case):
            assert f"`{rid}`" in doc, rid
