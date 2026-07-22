"""Doc-lint guard for the question-transport-policy spec's freshness classifier.

Pins the new `## When to structure` section in
`skills/cheese/references/ask-user-question.md` (the single policy chokepoint
four downstream curds point at): the freshness rule (a structured question may
only confirm trade-offs already discussed with the user this session; an
undiscussed design option always gets prose weighing first), the
mechanical-fast-path definition + examples, the design definition (options
whose weighing needs session context to be intelligible; an undiscussed
design fork is by definition non-fresh), and the one-structured-confirm-max /
never-bundle-design-forks rule.

Each assertion pins the *semantic relationship* within a bounded span, not a
vacuous co-occurrence of isolated substrings anywhere in the file — the same
discipline `test_culture_convergence.py` and `test_cheese_live_message.py`
use.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TRANSPORT_DOC = REPO_ROOT / "skills" / "cheese" / "references" / "ask-user-question.md"


def _section(text: str, heading: str) -> str:
    marker = f"## {heading}"
    start = text.index(marker)
    end = text.find("\n## ", start + len(marker))
    raw = text[start:] if end == -1 else text[start:end]
    # The section is soft-wrapped markdown prose; flatten line breaks to
    # spaces so a bounded-span regex can cross a wrapped line without
    # crossing a sentence (period) boundary.
    return re.sub(r"\s+", " ", raw)


# --- Freshness rule -----------------------------------------------------
# A structured question may only confirm a trade-off already discussed with
# the user this session.
FRESHNESS_CONFIRMS_SESSION = re.compile(
    r"structured question\b[^.\n]{0,80}\bconfirm\b[^.\n]{0,80}\bsession\b",
    re.I,
)
# Structured questions never introduce an undiscussed design option.
FRESHNESS_NEVER_INTRODUCES = re.compile(
    r"never\b[^.\n]{0,40}\bintroduce\b[^.\n]{0,40}\bundiscussed\b[^.\n]{0,20}\bdesign option\b",
    re.I,
)


# --- Mechanical fast-path -------------------------------------------------
# Definition: intelligible without prior-session context.
MECHANICAL_DEFINITION = re.compile(
    r"mechanical item\b[^.\n]{0,40}\bintelligible without\b[^.\n]{0,40}\bsession context\b",
    re.I,
)
# Examples: branch name, yes/no dispatch.
MECHANICAL_EXAMPLES = re.compile(
    r"branch name\b[^.\n]{0,40}\byes/no dispatch\b",
    re.I,
)
# A mechanical item may be asked as a direct structured question.
MECHANICAL_DIRECT_ASK = re.compile(
    r"mechanical item\b[^.\n]{0,60}\bdirect structured question\b",
    re.I,
)


# --- Design definition -----------------------------------------------------
# A design item's options need session context to be intelligible.
DESIGN_DEFINITION = re.compile(
    r"design item\b[^.\n]{0,60}\bsession context\b[^.\n]{0,40}\bintelligible\b",
    re.I,
)
# An undiscussed design fork is by definition non-fresh.
DESIGN_FORK_NONFRESH = re.compile(
    r"undiscussed design fork\b[^.\n]{0,40}\bby definition\b[^.\n]{0,20}\bnon-fresh\b",
    re.I,
)


# --- One-confirm-max / never-bundle ----------------------------------------
# After prose convergence, at most one structured confirm.
ONE_CONFIRM_MAX = re.compile(
    r"prose convergence\b[^.\n]{0,40}\bat most one\b[^.\n]{0,20}\bstructured confirm\b",
    re.I,
)
# Never bundle multiple design forks into one prompt.
NEVER_BUNDLE_FORKS = re.compile(
    r"never bundle\b[^.\n]{0,40}\bmultiple design forks\b",
    re.I,
)


def test_transport_doc_exists() -> None:
    assert TRANSPORT_DOC.exists(), f"transport doc moved or renamed: {TRANSPORT_DOC}"


def test_when_to_structure_section_present() -> None:
    text = TRANSPORT_DOC.read_text(encoding="utf-8")
    assert "## When to structure" in text, (
        "§ When to structure is missing — the question-transport-policy spec's "
        "freshness classifier has no home in the transport chokepoint doc."
    )


def test_freshness_rule() -> None:
    section = _section(TRANSPORT_DOC.read_text(encoding="utf-8"), "When to structure")
    missing = []
    if not FRESHNESS_CONFIRMS_SESSION.search(section):
        missing.append("a structured question may only confirm trade-offs discussed this session")
    if not FRESHNESS_NEVER_INTRODUCES.search(section):
        missing.append("structured questions never introduce an undiscussed design option")
    assert not missing, (
        "freshness rule absent or too weak in § When to structure:\n  - "
        + "\n  - ".join(missing)
    )


def test_mechanical_fast_path() -> None:
    section = _section(TRANSPORT_DOC.read_text(encoding="utf-8"), "When to structure")
    missing = []
    if not MECHANICAL_DEFINITION.search(section):
        missing.append("mechanical item definition: intelligible without session context")
    if not MECHANICAL_EXAMPLES.search(section):
        missing.append("mechanical examples: branch name, yes/no dispatch")
    if not MECHANICAL_DIRECT_ASK.search(section):
        missing.append("a mechanical item may be asked as a direct structured question")
    assert not missing, (
        "mechanical fast-path clause absent or incomplete in § When to structure:\n  - "
        + "\n  - ".join(missing)
    )


def test_design_definition() -> None:
    section = _section(TRANSPORT_DOC.read_text(encoding="utf-8"), "When to structure")
    missing = []
    if not DESIGN_DEFINITION.search(section):
        missing.append("design item definition: options need session context to be intelligible")
    if not DESIGN_FORK_NONFRESH.search(section):
        missing.append("an undiscussed design fork is by definition non-fresh")
    assert not missing, (
        "design definition clause absent or incomplete in § When to structure:\n  - "
        + "\n  - ".join(missing)
    )


def test_one_confirm_max_never_bundled() -> None:
    section = _section(TRANSPORT_DOC.read_text(encoding="utf-8"), "When to structure")
    missing = []
    if not ONE_CONFIRM_MAX.search(section):
        missing.append("at most one structured confirm after prose convergence")
    if not NEVER_BUNDLE_FORKS.search(section):
        missing.append("never bundle multiple design forks into one prompt")
    assert not missing, (
        "one-confirm-max / never-bundle clause absent or incomplete in § When to structure:\n  - "
        + "\n  - ".join(missing)
    )
