"""Regression guard for #287 (mold Rules bullet must route forks through the
question-transport reference, and gate structured-fork validity on
in-dialogue depth).

mold's tiered-lettered-options mechanism (ADR-003) predates the
question-transport policy spec, which centralizes the freshness rule (a
structured question may only confirm a trade-off already discussed this
session) at `skills/cheese/references/ask-user-question.md`. Downstream
skills must carry a one-line pointer to that section, never a copy. The fix
is two-part on mold's Rules bullet:

1. Route consequential forks through the transport doc path.
2. Add a conformance line: a structured fork is valid only when its depth was
   contributed in-dialogue first — mold's rendering of the freshness rule.

Each assertion pins the semantic relationship within the bounded span of the
Tiered lettered options bullet, not a bare substring co-occurrence anywhere in
the file.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MOLD_SKILL = REPO_ROOT / "skills" / "mold" / "SKILL.md"

TRANSPORT_DOC_PATH = "../cheese/references/ask-user-question.md"


def _body_below_frontmatter(path: Path) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                return "\n".join(lines[i + 1 :])
    return "\n".join(lines)


def _tiered_lettered_options_bullet(body: str) -> str:
    """Isolate the Tiered lettered options bullet from the Rules section."""
    rules_match = re.search(r"^## Rules\s*$", body, re.M)
    assert rules_match, "mold SKILL.md has no '## Rules' section"
    rest = body[rules_match.end() :]
    bullet_match = re.search(
        r"-\s*\*\*Tiered lettered options\.\*\*.*?(?=\n- \*\*|\n- Do not|\Z)",
        rest,
        re.S,
    )
    assert bullet_match, "mold Rules section has no 'Tiered lettered options' bullet"
    return bullet_match.group(0)


# Forks are routed through the question-transport reference, not resolved
# via an ad hoc local mechanism.
ROUTES_VIA_TRANSPORT = re.compile(
    r"\bvia\b[^.\n]{0,40}\bquestion transport\b[^.\n]{0,80}"
    + re.escape(TRANSPORT_DOC_PATH),
    re.I,
)

# A structured fork is valid only when its depth was contributed in-dialogue
# first — mold's rendering of the freshness rule.
CONFORMANCE_DEPTH_IN_DIALOGUE = re.compile(
    r"\bstructured fork\b[^.\n]{0,60}\bvalid\b[^.\n]{0,60}\bdepth\b[^.\n]{0,60}"
    r"\bcontributed\b[^.\n]{0,30}\bin-dialogue\b[^.\n]{0,20}\bfirst\b",
    re.I,
)


def test_mold_skill_exists() -> None:
    assert MOLD_SKILL.exists(), f"mold SKILL.md moved or renamed: {MOLD_SKILL}"


def test_rules_bullet_routes_forks_via_transport_doc() -> None:
    body = _body_below_frontmatter(MOLD_SKILL)
    bullet = _tiered_lettered_options_bullet(body)
    assert ROUTES_VIA_TRANSPORT.search(bullet), (
        "#287 — the Tiered lettered options Rules bullet must route "
        f"consequential forks via the question transport at `{TRANSPORT_DOC_PATH}`; "
        "found no such pointer in the bullet:\n" + bullet
    )


def test_rules_bullet_gates_structured_fork_on_in_dialogue_depth() -> None:
    body = _body_below_frontmatter(MOLD_SKILL)
    bullet = _tiered_lettered_options_bullet(body)
    assert CONFORMANCE_DEPTH_IN_DIALOGUE.search(bullet), (
        "#287 — the Tiered lettered options Rules bullet must add a conformance "
        "line: a structured fork is valid only when its depth was contributed "
        "in-dialogue first; found no such clause in the bullet:\n" + bullet
    )


def test_rules_bullet_keeps_abcd_mechanism() -> None:
    """ADR-003: mold keeps its A/B/C/D tiered-lettered-options mechanism —
    the transport pointer and conformance line must not have displaced it."""
    body = _body_below_frontmatter(MOLD_SKILL)
    bullet = _tiered_lettered_options_bullet(body)
    assert re.search(r"\bA/B/C/D\b", bullet), (
        "ADR-003 — the Tiered lettered options bullet must keep the A/B/C/D "
        "choice mechanism; found no such marker in the bullet:\n" + bullet
    )


def test_pointer_missing_cheese_prefix_is_rejected() -> None:
    """Mutation resistance: a pointer that drops the '../cheese/' prefix
    (e.g. a relative-path typo during a future edit) must not satisfy the
    transport-routing assertion."""
    body = _body_below_frontmatter(MOLD_SKILL)
    bullet = _tiered_lettered_options_bullet(body)
    mutated = bullet.replace(TRANSPORT_DOC_PATH, "references/ask-user-question.md")
    assert mutated != bullet, "fixture setup failed to mutate the pointer path"
    assert not ROUTES_VIA_TRANSPORT.search(mutated), (
        "pointer regex must reject a path missing the '../cheese/' prefix"
    )


def test_conformance_line_relocated_outside_bullet_is_not_credited() -> None:
    """Mutation resistance: the conformance clause must live inside the
    Tiered lettered options bullet itself. If a future edit moved it into a
    later bullet, isolating just the Tiered lettered options span must stop
    satisfying the assertion."""
    body = _body_below_frontmatter(MOLD_SKILL)
    bullet = _tiered_lettered_options_bullet(body)
    conformance_match = re.search(r"Conformance:.*", bullet, re.S)
    assert conformance_match, "expected a Conformance clause in the bullet fixture"
    truncated_bullet = bullet[: conformance_match.start()].rstrip()
    assert not CONFORMANCE_DEPTH_IN_DIALOGUE.search(truncated_bullet), (
        "conformance clause must live inside the Tiered lettered options bullet; "
        "a bullet span with the clause stripped off the end must not still "
        "satisfy the assertion"
    )


def test_pointer_present_elsewhere_in_file_does_not_satisfy_bullet_scope() -> None:
    """Boundary: the transport pointer must sit in the Tiered lettered options
    bullet specifically, not merely anywhere in mold/SKILL.md. Strip the
    pointer from the isolated bullet only (as if it had been moved to a
    different bullet) and confirm the isolated-span assertion still fails,
    even though the same path string could still exist elsewhere in the file.
    """
    body = _body_below_frontmatter(MOLD_SKILL)
    bullet = _tiered_lettered_options_bullet(body)
    bullet_without_pointer = ROUTES_VIA_TRANSPORT.sub("silently", bullet)
    assert bullet_without_pointer != bullet, "fixture setup failed to strip the pointer"
    assert not ROUTES_VIA_TRANSPORT.search(bullet_without_pointer), (
        "pointer removed from the bullet span must not satisfy the transport "
        "check even if the same path string exists elsewhere in the file"
    )
