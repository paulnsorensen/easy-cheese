"""Contract tests for issue #300 — /cheese must let the live user message
override the --continue handoff state machine.

Three rules the fix pins into skills/cheese/SKILL.md:

1. **Override direction.** Both `## Flow` and `## --continue` must instruct the
   agent to read the full user message and execute its prose *instead of* the
   handoff protocol where they conflict — the handoff restores state, the live
   message overrides it.
2. **Gated-branch carve-out.** In the `gated:` branch, a message that already
   contains directives or answers the gate must be executed with the gate
   surfaced as one plain line, *before* (and instead of) raising the structured
   research/decide/build question.
3. **Declined-gate rule.** A declined question gate is an answer; the router
   must not re-raise it.

Each assertion pins ordering, not bare co-occurrence: the PR #297 review called
out vacuous substring-co-occurrence checks, so every guard here encodes the
*direction* of the rule (handoff restores → live message overrides; carve-out
precedes the structured ask; declined → do-not-re-raise) via `_assert_in_order`.
A reword that keeps the words but flips the direction still fails.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CHEESE = REPO_ROOT / "skills" / "cheese" / "SKILL.md"


def _text() -> str:
    return CHEESE.read_text(encoding="utf-8")


def _section(text: str, heading: str) -> str:
    marker = f"## {heading}"
    start = text.index(marker)
    end = text.find("\n## ", start + len(marker))
    return text[start:] if end == -1 else text[start:end]


def _assert_in_order(body: str, *phrases: str) -> None:
    folded = body.casefold()
    last = -1
    for phrase in phrases:
        idx = folded.find(phrase.casefold())
        assert idx != -1, f"missing phrase: {phrase!r}"
        assert idx > last, f"phrase out of order: {phrase!r}"
        last = idx


def test_cheese_skill_exists() -> None:
    assert CHEESE.exists(), f"cheese SKILL moved or renamed: {CHEESE}"


def test_flow_reads_full_message_and_live_overrides_handoff() -> None:
    # Rule 1 in ## Flow: prose is a directive list executed *instead of* the
    # handoff protocol; the handoff restores state, the live message overrides.
    # Ordering pins the override DIRECTION, not mere word co-occurrence.
    section = _section(_text(), "Flow")
    _assert_in_order(
        section,
        "read the full user message",
        "directive list",
        "instead of",
        "handoff protocol",
        "the handoff file restores state",
        "the user's live message overrides it",
    )


def test_continue_reads_full_message_and_live_overrides_handoff() -> None:
    # Rule 1 in ## --continue: the same override direction must be stated on the
    # branch that actually parses the handoff slug, not only in the generic flow.
    section = _section(_text(), "--continue")
    _assert_in_order(
        section,
        "read the full user message",
        "directive list",
        "instead of",
        "handoff protocol",
        "the handoff file restores state",
        "the user's live message overrides it",
    )


def test_gated_branch_executes_directives_before_raising_the_question() -> None:
    # Rule 2: in the gated: branch, directives/answers in the message are
    # executed with the gate surfaced as one plain line, and this carve-out is
    # stated BEFORE the structured research/decide/build ask — so the carve-out
    # takes precedence over the mandatory question rather than following it.
    section = _section(_text(), "--continue")
    _assert_in_order(
        section,
        "starts with `gated:`",
        "if the accompanying message contains directives or already answers the gate",
        "execute them and surface the gate as one line of plain text",
        "do not raise the structured question",
        "ask the user which direction",
    )


def test_declined_gate_is_not_re_raised() -> None:
    # Rule 3: a declined question gate is an answer; ordering pins that the
    # consequence is "do not re-raise", not some weaker disposition.
    section = _section(_text(), "Rules")
    _assert_in_order(
        section,
        "a declined question gate is an answer",
        "do not re-raise it",
        "wait for freeform input",
    )
