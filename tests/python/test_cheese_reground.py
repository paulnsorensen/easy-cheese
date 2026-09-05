"""Contract tests for issue #147 — `/cheese --continue --reground`.

The flag exists to stop a resumed phase from building on a claim the tree has
since falsified, so the tests pin the properties that make it worth having
rather than the fact that the word appears:

1. **Bounded before it is spent.** The decay window is derived from the recorded
   commit and the dirty tree, and an empty window dispatches unchanged — a
   re-grounding pass that always runs is one users turn off.
2. **Adversarial, not confirmatory.** The claim pass is delegated to `/culture`
   in no-write mode with a falsification instruction, and a claim that merely
   still sounds plausible is `unverifiable`, never `holds`.
3. **`stale` gates, `unverifiable` does not.** A falsified premise is a user
   decision routed through research / decide / build; an unverified one is the
   pre-existing state of every resume and must not block.
4. **The router still never writes.** No note edit, no revision commit.

Every assertion pins ordering via `_assert_in_order`, so a reword that keeps the
vocabulary but reverses the rule (confirm instead of falsify, gate on
`unverifiable`, repair the handoff) still fails.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CHEESE = REPO_ROOT / "skills" / "cheese" / "SKILL.md"
RESUME = REPO_ROOT / "skills" / "cheese" / "references" / "continue-resume.md"


def _assert_in_order(body: str, *phrases: str) -> None:
    folded = body.casefold()
    last = -1
    for phrase in phrases:
        idx = folded.find(phrase.casefold())
        assert idx != -1, f"missing phrase: {phrase!r}"
        assert idx > last, f"phrase out of order: {phrase!r}"
        last = idx


def _reground_section() -> str:
    text = RESUME.read_text(encoding="utf-8")
    start = text.index("## --reground")
    end = text.find("\n## ", start + len("## --reground"))
    return text[start:] if end == -1 else text[start:end]


def test_skill_advertises_reground_as_a_continue_only_flag() -> None:
    text = CHEESE.read_text(encoding="utf-8")
    _assert_in_order(
        text,
        "- `--reground`",
        "with `--continue` only",
        "adversarially re-check",
    )


def test_reground_is_rejected_without_continue() -> None:
    _assert_in_order(
        _reground_section(),
        "meaningful only alongside `--continue`",
        "say so in one line and classify normally",
    )


def test_reground_never_rescues_a_resolution_that_already_stopped() -> None:
    _assert_in_order(
        _reground_section(),
        "after resolution has produced a dispatchable result",
        "before dispatch",
        "never rescues one and never softens one",
    )


def test_empty_decay_window_dispatches_unchanged() -> None:
    # Property 1: the window is computed, not assumed, and an empty one is a
    # cheap exit rather than a pass that always runs.
    _assert_in_order(
        _reground_section(),
        "bound the decay window deterministically",
        "git diff --name-only",
        "git status --porcelain",
        "an empty window means nothing moved",
        "dispatch unchanged",
        "no recorded commit has an unbounded window",
    )


def test_claims_are_attacked_by_culture_not_confirmed_by_the_router() -> None:
    # Property 2: the direction is falsification, the worker is /culture in
    # no-write mode, and plausibility is explicitly not evidence.
    _assert_in_order(
        _reground_section(),
        "attack them, do not confirm them",
        "/culture",
        "no-write mode",
        "look for the evidence that would make it *false*",
        "still sounds plausible is `unverifiable`, never `holds`",
        "the router does not do this reading itself",
    )


def test_stale_gates_and_unverifiable_does_not() -> None:
    # Property 3: pinned as an ordered contrast so swapping which verdict gates
    # cannot pass.
    _assert_in_order(
        _reground_section(),
        "any `stale` claim stops automatic dispatch",
        "research / decide / build",
        "dispatch nothing until the user picks",
        "an `unverifiable` verdict does not stop dispatch",
    )


def test_every_verdict_is_reported_not_just_the_failures() -> None:
    _assert_in_order(
        _reground_section(),
        "one line per claim",
        "reground: <holds|stale|unverifiable>",
        "a claim checked and cleared is as much of the record",
    )


def test_reground_never_writes_and_never_propagates() -> None:
    # Property 4 plus the flag's scope: a router that repaired the handoff it
    # just falsified would be authoring state, and a resume-time check that
    # rode along downstream would be a durable flag.
    _assert_in_order(
        _reground_section(),
        "never repair the handoff",
        "does not edit the note, commit a revision, or rewrite a claim",
        "never forwarded to the dispatched phase",
        "never becomes a durable flag",
    )
