"""Contract tests for the question-transport-policy `gated:` classifier.

The `gated:` branch of `/cheese --continue` (skills/cheese/SKILL.md) must, for
each open gate item, classify it mechanical vs design per the policy
chokepoint in `skills/cheese/references/ask-user-question.md` (`## When to
structure`) rather than copying that policy inline:

1. **Pointer, not copy.** The gated branch points at the transport reference
   instead of restating its freshness/mechanical/design definitions.
2. **Mechanical fast-path.** A mechanical item may go straight to the
   structured research/decide/build question.
3. **Design item -> prose first.** A design item whose weighing was not
   already shown this session must not go straight to a structured question;
   the weighing is re-established in prose (both ends, code-grounded
   evidence, pushback invited) before any structured question.
4. **Converge, then at most one confirm.** After prose convergence, at most
   one structured confirm follows -- never more.
5. **Never bundle.** Multiple design forks never collapse into one prompt.
6. **Regression pin.** The #303 live-message carve-out (directives/answers in
   the message execute before the structured question is ever raised) still
   holds after this composition.

Each assertion pins ordering via `_assert_in_order`, not bare
substring co-occurrence -- a reword that keeps the words but flips the
direction (e.g. design items going straight to structured) still fails.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CHEESE = REPO_ROOT / "skills" / "cheese" / "SKILL.md"
TRANSPORT = REPO_ROOT / "skills" / "cheese" / "references" / "ask-user-question.md"


def _text() -> str:
    return CHEESE.read_text(encoding="utf-8")


def _section(text: str, heading: str) -> str:
    marker = f"## {heading}"
    start = text.index(marker)
    end = text.find("\n## ", start + len(marker))
    return text[start:] if end == -1 else text[start:end]


def _gated_bullet(text: str) -> str:
    # Bounds the span to the single `gated:` sub-bullet of `--continue`
    # (not the whole section) so a classifier moved to a sibling bullet
    # still fails, even though the whole-section ordering test would not
    # notice the move.
    start_marker = "**When `status:` starts with `gated:`**"
    end_marker = "**When `next:` is a list**"
    section = _section(text, "--continue")
    start = section.index(start_marker)
    end = section.index(end_marker, start)
    return section[start:end]


def _assert_in_order(body: str, *phrases: str) -> None:
    folded = body.casefold()
    last = -1
    for phrase in phrases:
        idx = folded.find(phrase.casefold())
        assert idx != -1, f"missing phrase: {phrase!r}"
        assert idx > last, f"phrase out of order: {phrase!r}"
        last = idx


def test_cheese_skill_and_transport_reference_exist() -> None:
    assert CHEESE.exists(), f"cheese SKILL moved or renamed: {CHEESE}"
    assert TRANSPORT.exists(), f"transport policy reference moved or renamed: {TRANSPORT}"


def test_gated_branch_points_at_transport_reference_not_a_copy() -> None:
    # Rule 1: the gated branch links to the § When to structure chokepoint
    # rather than restating its definitions inline.
    section = _section(_text(), "--continue")
    assert "references/ask-user-question.md" in section
    assert "When to structure" in section


def test_gated_branch_classifies_before_choosing_a_transport() -> None:
    # Rules 2-5: classification precedes the mechanical/design fork, mechanical
    # goes straight to structured, design re-establishes prose weighing first,
    # converges, then allows at most one structured confirm, and never bundles.
    section = _section(_text(), "--continue")
    _assert_in_order(
        section,
        "ask the user which direction",
        "classify each open gate item as mechanical or design",
        "a mechanical item may go straight to that structured question",
        "a design item",
        "must not",
        "re-establish the weighing in prose first",
        "converge conversationally",
        "ask at most one structured confirm",
        "never bundle multiple design forks into one prompt",
    )


def test_design_item_definition_requires_session_context() -> None:
    # Rule 3: the design classification is pinned to "weighing not already
    # shown this session", not merely "a design decision exists".
    section = _section(_text(), "--continue")
    _assert_in_order(
        section,
        "a design item",
        "whose weighing was not already shown this session",
        "must not",
    )


def test_live_message_carve_out_still_precedes_the_classifier() -> None:
    # Rule 6 (regression pin for #303): directives/answers in the live message
    # still execute, and the gate still surfaces as one plain line, BEFORE the
    # classifier or the structured question is ever reached.
    section = _section(_text(), "--continue")
    _assert_in_order(
        section,
        "starts with `gated:`",
        "if the accompanying message contains directives or already answers the gate",
        "execute them and surface the gate as one line of plain text",
        "do not raise the structured question",
        "classify each open gate item as mechanical or design",
    )


def test_classifier_lives_inside_the_gated_bullet_not_a_sibling_bullet() -> None:
    # Bound the classifier phrases to the `gated:` sub-bullet itself. A
    # classifier relocated to a sibling `--continue` bullet after "ask the
    # user which direction" would still satisfy the whole-section ordering
    # test above; bounding the span to the single bullet catches the move.
    bullet = _gated_bullet(_text())
    _assert_in_order(
        bullet,
        "ask the user which direction",
        "classify each open gate item as mechanical or design",
        "a mechanical item may go straight to that structured question",
        "a design item",
        "must not",
        "re-establish the weighing in prose first",
        "converge conversationally",
        "ask at most one structured confirm",
        "never bundle multiple design forks into one prompt",
    )


def test_prose_weighing_keeps_both_ends_code_grounded_evidence_and_pushback() -> None:
    # Rule 3 detail: dropping "both ends", "code-grounded evidence", or
    # "pushback invited" from the parenthetical would silently weaken what
    # "prose weighing" requires while leaving the coarser phrase-order test
    # above green.
    bullet = _gated_bullet(_text())
    _assert_in_order(
        bullet,
        "re-establish the weighing in prose first",
        "both ends",
        "code-grounded evidence",
        "pushback invited",
        "converge conversationally",
    )


def test_transport_reference_when_to_structure_still_defines_the_terms() -> None:
    # The pointer (rule 1) is only meaningful while the target section still
    # carries the mechanical/design/one-confirm definitions the gated
    # bullet defers to -- ground the pointer against the target's own
    # content, not just its existence.
    transport_text = TRANSPORT.read_text(encoding="utf-8")
    section = _section(transport_text, "When to structure")
    _assert_in_order(
        section,
        "mechanical fast-path",
        "design definition",
        "one confirm, never bundled",
    )