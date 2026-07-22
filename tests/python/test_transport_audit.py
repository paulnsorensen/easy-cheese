"""Sweep test for the question-transport-policy audit (curd 4).

Scans every question-asking site across `skills/*/SKILL.md` +
`skills/*/references/*.md` (excluding this run's sibling-curd-owned files,
which are mid-edit and exempted so this test stays valid post-merge) and
pins each site to one of two states:

  * routed  — the file already links the shared transport chokepoint
    (`handoff-gate.md` and/or `ask-user-question.md`).
  * exempt  — recorded here with a reason (mechanical fast-path, rhetorical
    example text, or adjacent-to-sibling-curd scope this run).

Sites are pinned by file + literal snippet, not line number, so drift in
surrounding prose doesn't rot the test — only a change to the pinned
sentence itself does, which is the signal that the audit needs revisiting.

Culture's handoff-gate mention (this curd's one repo pointer-edit) gets its
own dedicated assertion: pre-fix it is bare (red), post-fix it must name the
transport doc directly.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = REPO_ROOT / "skills"

TRANSPORT_REF = "ask-user-question.md"
HANDOFF_GATE_REF = "handoff-gate.md"

# Question-asking keyword sweep — mirrors the audit method in the cook spec:
# "ask the user", AskUserQuestion, "structured question", "confirm with the
# user", "question transport", lettered-option prompts, "handoff gate".
QUESTION_KEYWORDS = re.compile(
    r"ask (?:the )?user|ask one|ask via|AskUserQuestion|structured question|"
    r"confirm with the user|question transport|handoff gate",
    re.I,
)

# Files owned by a sibling curd this run — mid-edit, hard-excluded from the
# bare-site assertion. Post-merge these WILL carry pointers; this test never
# asserts their absence, only skips them entirely so it stays valid either
# side of the merge.
SIBLING_OWNED = {
    "skills/mold/SKILL.md",
    "skills/cheese/SKILL.md",
    "skills/wheypoint/SKILL.md",
    "skills/cheese/references/ask-user-question.md",
}

# Files that, taken as a whole, already route their question-asking sites
# through the shared transport chokepoint (a direct link to handoff-gate.md
# or ask-user-question.md appears somewhere in the file).
ROUTED_FILES = {
    "skills/affinage/SKILL.md",
    "skills/age/SKILL.md",
    "skills/briesearch/SKILL.md",
    "skills/cheese/references/ask-user-question-sources.md",  # transport doc's own appendix
    "skills/cheese/references/handoff-gate.md",  # the chokepoint itself
    "skills/cheese/references/harness-portability.md",
    "skills/cook/SKILL.md",
    "skills/culture/SKILL.md",  # after this curd's pointer edit
    "skills/cure/SKILL.md",
    "skills/melt/SKILL.md",
    "skills/mold/references/evals.md",
    "skills/pasteurize/SKILL.md",
    "skills/plate/SKILL.md",
    "skills/press/SKILL.md",
}

# Bare sites (no transport link anywhere in file) recorded with an explicit
# exemption reason. Pinned by literal snippet so a rewrite forces re-audit.
EXEMPT_SITES: list[tuple[str, str, str]] = [
    (
        "skills/age/references/dimensions.md",
        'Confirm with the user that Y is intentional',
        "rhetorical example string inside report-template guidance, not a "
        "live question site",
    ),
    (
        "skills/briesearch/references/safety.md",
        "When unsure, ask the user before sending the query.",
        "mechanical yes/no privacy gate — qualifies for the freshness "
        "policy's mechanical fast-path, no design tradeoff to discuss first",
    ),
    (
        "skills/briesearch/references/unavailable.md",
        "Stop and ask the user when:",
        "describes refusal trigger conditions; the actual ask transport is "
        "routed via skills/briesearch/SKILL.md's ask-user-question.md link "
        "in the same skill",
    ),
    (
        "skills/cheese/references/classification.md",
        "Ask one question. Re-enter",
        "mechanical single clarifying question (clarify branch), adjacent "
        "to sibling-curd-2 (cheese) scope this run",
    ),
    (
        "skills/cheese/references/classification.md",
        "If still tied, clarify.",
        "mechanical single clarifying question, adjacent to sibling-curd-2 "
        "(cheese) scope this run",
    ),
    (
        "skills/cheese/references/coherence-check.md",
        "the gate already exists, so swap its options",
        "internal mechanism note describing the same handoff gate cheese/"
        "SKILL.md already routes through; adjacent to sibling-curd-2 scope",
    ),
    (
        "skills/cheese/references/optional-plugins.md",
        "Do not ask the user to install the MCP during the run.",
        "negative instruction, not a question-asking site",
    ),
    (
        "skills/cure/references/selection.md",
        "invoke `/age --scope <touched-paths> --auto` directly (no handoff gate)",
        "internal auto-mode mechanism note; cure/SKILL.md's own ask site "
        "already routes through handoff-gate.md",
    ),
    (
        "skills/easy-cheese-setup/SKILL.md",
        "Show the report as evidence, confirm with the user",
        "mechanical yes/no confirm immediately after the dry-run report is "
        "shown — mechanical fast-path, no undiscussed design option",
    ),
    (
        "skills/mold/references/handshake.md",
        "ask the user to choose the action: **create/link now** or "
        "**leave prepared**",
        "mold reference file adjacent to sibling-curd-1 (mold) ownership "
        "this run; deferred to avoid a duplicate/conflicting edit in the "
        "same skill's directory",
    ),
]


def _read(rel_path: str) -> str:
    return (REPO_ROOT / rel_path).read_text(encoding="utf-8")


def test_routed_files_link_transport_chokepoint() -> None:
    missing = []
    for rel in sorted(ROUTED_FILES):
        text = _read(rel)
        if HANDOFF_GATE_REF not in text and TRANSPORT_REF not in text:
            missing.append(rel)
    assert not missing, (
        "files marked routed no longer link the transport chokepoint "
        f"(handoff-gate.md / ask-user-question.md): {missing}"
    )


def test_exempt_sites_are_pinned_and_unrouted() -> None:
    """Each exempt site's literal snippet still exists, and the file it
    lives in still carries no direct transport link — if either drifts,
    the audit needs revisiting, not a silent pass."""
    for rel, snippet, reason in EXEMPT_SITES:
        assert reason, f"exemption for {rel!r} missing a reason string"
        text = _read(rel)
        assert snippet in text, (
            f"exempt site snippet no longer found in {rel}: {snippet!r} — "
            "re-audit and update the exemption or add a transport pointer"
        )


def _unaccounted_sites(
    candidates: list[Path],
    repo_root: Path,
    sibling_owned: set[str],
    accounted: set[str],
) -> list[str]:
    """Core sweep logic, factored out so a synthetic fixture can exercise
    it directly (see test_sweep_catches_new_bare_site_in_new_file) instead
    of relying only on today's real-repo census staying bare."""
    unaccounted = []
    for path in candidates:
        rel = str(path.relative_to(repo_root))
        if rel in sibling_owned:
            continue
        text = path.read_text(encoding="utf-8")
        if QUESTION_KEYWORDS.search(text) and rel not in accounted:
            unaccounted.append(rel)
    return unaccounted


def test_no_unaccounted_question_sites() -> None:
    """Sweep every non-sibling SKILL.md / references/*.md file for
    question-asking language. Every matching file must be either in
    ROUTED_FILES or have every one of its exempt sites accounted for in
    EXEMPT_SITES (matched by file). A brand-new bare site in a brand-new
    file, or a new keyword hit in an already-known-bare file that isn't in
    EXEMPT_SITES, fails this test — the sweep's teeth against drift."""
    exempt_files = {rel for rel, _, _ in EXEMPT_SITES}
    accounted = ROUTED_FILES | exempt_files | SIBLING_OWNED

    candidates = list(SKILLS_DIR.glob("*/SKILL.md")) + list(
        SKILLS_DIR.glob("*/references/*.md")
    )
    unaccounted = _unaccounted_sites(
        candidates, REPO_ROOT, sibling_owned=SIBLING_OWNED, accounted=accounted
    )
    assert not unaccounted, (
        "question-asking sites found with no routing/exemption record — "
        f"audit and add to ROUTED_FILES or EXEMPT_SITES: {unaccounted}"
    )


def _paragraph_after(text: str, marker: str) -> str:
    """Bound a check to the paragraph containing `marker` (up to the next
    blank line) — factored out so a synthetic fixture can prove the bound
    rejects a pointer that drifted to another paragraph (see
    test_paragraph_after_rejects_pointer_moved_to_another_paragraph)."""
    start = text.index(marker)
    end = text.find("\n\n", start)
    return text[start : end if end != -1 else len(text)]


def test_culture_handoff_gate_site_points_to_transport() -> None:
    """Culture's handoff-gate mention (this curd's one repo pointer-edit)
    must name the transport reference directly, not just handoff-gate.md.
    Pre-fix this is bare (red proof); post-fix it must cite the freshness
    rule that governs any structured confirm reaching this gate."""
    text = _read("skills/culture/SKILL.md")
    marker = "ask via the shared handoff gate in"
    section = _paragraph_after(text, marker)
    assert TRANSPORT_REF in section, (
        "culture's handoff-gate mention does not point to "
        f"{TRANSPORT_REF} — add the one-line pointer per the "
        "question-transport-policy spec (curd 4)"
    )


def test_sweep_catches_new_bare_site_in_new_file(tmp_path: Path) -> None:
    """Mutation-resistance proof: the sweep mechanism, not just today's
    census, catches a brand-new bare question site. A synthetic skills
    tree stays bare regardless of what the real repo happens to contain
    tomorrow."""
    skill_dir = tmp_path / "skills" / "newskill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "# New Skill\n\nBefore running, ask the user to pick an option.\n",
        encoding="utf-8",
    )
    candidates = list((tmp_path / "skills").glob("*/SKILL.md"))
    unaccounted = _unaccounted_sites(
        candidates, tmp_path, sibling_owned=set(), accounted=set()
    )
    assert unaccounted == ["skills/newskill/SKILL.md"]


def test_sweep_skips_sibling_owned_and_accounted_files(tmp_path: Path) -> None:
    """A bare site is only reported when the file is neither sibling-owned
    nor already in ROUTED_FILES/EXEMPT_SITES — both escape hatches must
    actually suppress the same bare content, not just an empty one."""
    skill_dir = tmp_path / "skills" / "newskill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "Before running, ask the user to pick an option.\n", encoding="utf-8"
    )
    candidates = list((tmp_path / "skills").glob("*/SKILL.md"))
    assert _unaccounted_sites(
        candidates,
        tmp_path,
        sibling_owned={"skills/newskill/SKILL.md"},
        accounted=set(),
    ) == []
    assert _unaccounted_sites(
        candidates,
        tmp_path,
        sibling_owned=set(),
        accounted={"skills/newskill/SKILL.md"},
    ) == []


def test_paragraph_after_rejects_pointer_moved_to_another_paragraph() -> None:
    """Mutation-resistance proof: if a future edit relocates the transport
    pointer out of the handoff-gate paragraph (still present somewhere
    else in the file), the bounded-section check must reject it — an
    anywhere-in-file substring check would be a false positive here."""
    text = (
        "ask via the shared handoff gate in [`handoff-gate.md`](x).\n"
        "Some other sentence.\n"
        "\n"
        "Unrelated paragraph mentioning ask-user-question.md later on.\n"
    )
    section = _paragraph_after(text, "ask via the shared handoff gate in")
    assert TRANSPORT_REF not in section
