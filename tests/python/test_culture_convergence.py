"""Regression guard for issue #299 (culture user-facing convergence + fork medium).

Two gaps confirmed on origin/main @ 8e75a68 for `/culture` user-facing mode:

1. **Session-end ownership.** The Invariant, Flow step 5, and Handoff-slug
   `done` value all described session end as agent-executed with no owner, so a
   strong model could declare convergence on the user's behalf and end the
   thread unilaterally. The fix pins the USER as the one who declares the
   session over, and forbids the agent from declaring convergence for them.

2. **Fork medium.** The fork clauses constrained the *count* of consequential
   forks ("one at a time") but not the *medium*, so chained single-question
   structured popups satisfied the text while still railroading the dialogue.
   The fix requires forks to be raised conversationally in the dialogue and
   reserves structured question tools for the end-of-session handoff gate, and
   forbids bundling multiple forks into one prompt.

Each assertion pins the *semantic relationship* within a bounded span (who
declares, what is reserved for where), not a vacuous co-occurrence of isolated
substrings anywhere in the file — the exact defect called out on PR #297.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CULTURE_SKILL = REPO_ROOT / "skills" / "culture" / "SKILL.md"


def _body_below_frontmatter(path: Path) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                return "\n".join(lines[i + 1 :])
    return "\n".join(lines)


# --- Clause 1: session-end ownership -----------------------------------------
# The user is the subject who declares the session/thread over.
USER_DECLARES_END = re.compile(
    r"user\b[^.\n]{0,40}\bdeclares?\b[^.\n]{0,40}\b(?:session|thread)\b[^.\n]{0,20}\bover\b",
    re.I,
)
# The agent is explicitly barred from declaring convergence for the user.
AGENT_NEVER_CONVERGES = re.compile(
    r"agent\b[^.\n]{0,40}\bnever\b[^.\n]{0,40}\bdeclares?\b[^.\n]{0,40}\bconvergence\b",
    re.I,
)
# Flow step 5 must gate the wheypoint write on the user calling the thread over.
END_GATED_ON_USER = re.compile(
    r"user\b[^.\n]{0,40}\b(?:calls?|declares?)\b[^.\n]{0,40}\b(?:thread|session)\b[^.\n]{0,20}\bover\b[^.\n]{0,80}\bwheypoint\b",
    re.I,
)


# --- Clause 2: fork medium ---------------------------------------------------
# Forks are raised conversationally in the dialogue.
FORKS_CONVERSATIONAL = re.compile(
    r"\bforks?\b[^.\n]{0,40}\bconversational(?:ly)?\b[^.\n]{0,40}\bdialogue\b",
    re.I,
)
# Structured question tools are reserved for the handoff gate — not the dialogue.
STRUCTURED_RESERVED_FOR_HANDOFF = re.compile(
    r"reserve\b[^.\n]{0,40}\bstructured\b[^.\n]{0,80}\bhandoff\b",
    re.I,
)
# Multiple consequential forks must never be bundled into one prompt — this is
# what closes the chained single-question-popup gap that count-only wording left
# open.
NO_BUNDLED_FORKS = re.compile(
    r"never\b[^.\n]{0,30}\bbundle\b[^.\n]{0,40}\b(?:multiple|consequential)\b[^.\n]{0,20}\bforks?\b",
    re.I,
)


def test_culture_skill_exists() -> None:
    assert CULTURE_SKILL.exists(), f"culture SKILL.md moved or renamed: {CULTURE_SKILL}"


def test_user_owns_session_end() -> None:
    body = _body_below_frontmatter(CULTURE_SKILL)
    missing = []
    if not USER_DECLARES_END.search(body):
        missing.append("the user declares the session/thread over")
    if not AGENT_NEVER_CONVERGES.search(body):
        missing.append("the agent never declares convergence on the user's behalf")
    assert not missing, (
        "#299 session-end ownership clause absent — user-facing mode must name the "
        "USER as the one who ends the session, not the agent:\n  - "
        + "\n  - ".join(missing)
    )


def test_flow_step_five_gates_end_on_user() -> None:
    body = _body_below_frontmatter(CULTURE_SKILL)
    assert END_GATED_ON_USER.search(body), (
        "#299 wiring absent — the wheypoint write (session end) must be gated on the "
        "user calling the thread over, not executed unilaterally by the agent."
    )


def test_forks_raised_conversationally_not_bundled() -> None:
    body = _body_below_frontmatter(CULTURE_SKILL)
    missing = []
    if not FORKS_CONVERSATIONAL.search(body):
        missing.append("forks are raised conversationally in the dialogue")
    if not STRUCTURED_RESERVED_FOR_HANDOFF.search(body):
        missing.append("structured question tools are reserved for the handoff gate")
    if not NO_BUNDLED_FORKS.search(body):
        missing.append("multiple consequential forks are never bundled into one prompt")
    assert not missing, (
        "#299 fork-medium clause absent — count-only wording lets chained "
        "single-question popups railroad the dialogue; the medium must be pinned:\n  - "
        + "\n  - ".join(missing)
    )
