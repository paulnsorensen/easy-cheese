"""Content tests for the /hard-cheese skill.

These are smoke tests that check the SKILL.md files contain the load-bearing
content the spec promises: attribution to Sankaranarayanan 2026, SOLO rubric,
fail-open divergence note, --hard propagation across the pipeline skills.

Behavioural tests (does the gate actually block? does the judge sub-agent
return correct scores?) are integration tests against a Claude harness and
live outside this suite.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS = REPO_ROOT / "skills"
HARD = SKILLS / "hard-cheese"


# ---------------------------------------------------------------------------
# Skill structure


def test_skill_md_exists() -> None:
    assert (HARD / "SKILL.md").is_file(), "skills/hard-cheese/SKILL.md missing"


def test_references_exist() -> None:
    assert (HARD / "references" / "judge-prompt.md").is_file()
    assert (HARD / "references" / "composition.md").is_file()


# ---------------------------------------------------------------------------
# Attribution: paper, arxiv URL, vibecheck repo URL, fail-open divergence


@pytest.fixture(scope="module")
def skill_body() -> str:
    return (HARD / "SKILL.md").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def judge_prompt() -> str:
    return (HARD / "references" / "judge-prompt.md").read_text(encoding="utf-8")


def test_paper_citation_in_skill(skill_body: str) -> None:
    assert "Sankaranarayanan" in skill_body
    assert "Epistemic Debt" in skill_body
    assert "Metacognitive Scripts" in skill_body


def test_arxiv_url_in_skill(skill_body: str) -> None:
    assert "arxiv.org/abs/2602.20206" in skill_body


def test_vibecheck_repo_url_in_skill(skill_body: str) -> None:
    assert "github.com/sreecharansankaranarayanan/vibecheck" in skill_body


def test_fail_open_divergence_called_out(skill_body: str) -> None:
    lowered = skill_body.lower()
    assert "fail open" in lowered or "fail-open" in lowered
    assert "diverg" in lowered, "must name the divergence from the paper"


def test_solo_rubric_in_judge_prompt(judge_prompt: str) -> None:
    assert "SOLO" in judge_prompt
    assert "Relational" in judge_prompt
    assert "Prestructural" in judge_prompt
    assert "Multistructural" in judge_prompt
    assert "Extended Abstract" in judge_prompt


def test_solo_pass_threshold_is_three(judge_prompt: str) -> None:
    text = judge_prompt.lower()
    assert "3" in text and "relational" in text


def test_solo_threshold_aligns_with_rubric_level(judge_prompt: str) -> None:
    """Structural strengthening of `test_solo_pass_threshold_is_three`.

    The threshold rule (`score >= 3`) must reference the rubric's level-3
    label (Multistructural). Mentioning only `Relational` (level 4 in the
    rubric) creates the same contradiction that age pass #1 caught: a
    judge LLM reading "score ≥ 3 (Relational)" against a rubric where
    level 3 = Multistructural receives mutually exclusive signals.

    Mirror constraint: no `pass threshold` annotation is permitted on the
    Relational (level 4) bullet, because threshold ≥ 3 makes Multistructural
    the minimum pass, not Relational.
    """
    # The threshold-rule LINE must reference the rubric's level-3 label
    # (Multistructural) — not just have "Multistructural" appear somewhere in
    # the file, which would be a tautology since the rubric body always
    # defines level 3 = Multistructural. The regression vector is the
    # threshold rule reverting to "(Relational)" while the rubric stays put.
    threshold_lines = [
        line for line in judge_prompt.splitlines()
        if "Pass threshold" in line or "pass threshold" in line
    ]
    assert threshold_lines, "judge-prompt must contain a 'Pass threshold' rule line"
    assert any("Multistructural" in line for line in threshold_lines), (
        "the 'Pass threshold' rule line must reference 'Multistructural' "
        "(rubric's level-3 label). Naming only 'Relational' (level 4) on "
        "the threshold line reopens the contradiction caught by age pass #1. "
        f"Found threshold lines: {threshold_lines}"
    )
    # The Relational bullet must not carry the threshold annotation.
    rel_idx = judge_prompt.find("**Relational**")
    assert rel_idx >= 0, "rubric must define a Relational level"
    next_bullet = judge_prompt.find("\n> 5.", rel_idx)
    rel_bullet = judge_prompt[rel_idx:next_bullet if next_bullet > 0 else len(judge_prompt)]
    assert "pass threshold" not in rel_bullet.lower(), (
        "Relational bullet must not carry a 'pass threshold' annotation; "
        "threshold >= 3 makes Multistructural the minimum pass, not Relational"
    )


def test_socratic_retry_in_skill(skill_body: str) -> None:
    assert "Socratic" in skill_body
    assert "socratic-cap" in skill_body.lower() or "--socratic-cap" in skill_body


def test_no_judge_log_only_mode_in_skill(skill_body: str) -> None:
    assert "--no-judge" in skill_body


# ---------------------------------------------------------------------------
# --hard propagation across the pipeline skills


PROPAGATION_SKILLS = ["cheese", "mold", "cook", "press", "age", "cure"]


@pytest.mark.parametrize("skill", PROPAGATION_SKILLS)
def test_hard_flag_mentioned_in_pipeline_skill(skill: str) -> None:
    body = (SKILLS / skill / "SKILL.md").read_text(encoding="utf-8")
    assert "--hard" in body, f"`--hard` missing from skills/{skill}/SKILL.md"


def test_cure_invokes_hard_cheese() -> None:
    body = (SKILLS / "cure" / "SKILL.md").read_text(encoding="utf-8")
    assert "/hard-cheese" in body, "cure must reference /hard-cheese — it is the gate-firing skill"


def test_cure_documents_auto_puncture() -> None:
    body = (SKILLS / "cure" / "SKILL.md").read_text(encoding="utf-8").lower()
    assert "puncture" in body or "--hard" in body
    assert "auto" in body and "hard" in body, "cure must document --auto/--hard composition"


# ---------------------------------------------------------------------------
# Composition reference covers the three invocation modes


def test_composition_matrix_covers_modes() -> None:
    text = (HARD / "references" / "composition.md").read_text(encoding="utf-8")
    assert "standalone" in text.lower()
    assert "--auto" in text and "--hard" in text
    assert "puncture" in text.lower(), "composition reference must name the single puncture point"


# ---------------------------------------------------------------------------
# Generic language: spec calls for tool-agnostic phrasing


def test_skill_uses_generic_pr_language(skill_body: str) -> None:
    text = skill_body.lower()
    assert "pull request" in text or "share for review" in text or "shared for review" in text


def test_hard_cheese_skill_does_not_reference_gh() -> None:
    """The new skill must stay tool-agnostic: no /gh references in SKILL.md
    or composition.md. The spec's open question #5 explicitly locks generic
    language — `/gh` is not shipped with easy-cheese.

    Allowed: SKILL.md may mention `/gh` once inside the "Preferred tools" row
    that explicitly notes it as `n/a` / out of scope, since that row exists
    to *exclude* gh, not to require it. We pin that to a single occurrence;
    anything more is a regression.
    """
    skill = (HARD / "SKILL.md").read_text(encoding="utf-8")
    comp = (HARD / "references" / "composition.md").read_text(encoding="utf-8")
    # composition.md must be entirely free of /gh references
    assert "/gh" not in comp, "composition.md must stay tool-agnostic"
    # SKILL.md is allowed one mention in the explicit out-of-scope row
    assert skill.count("/gh") <= 1, (
        "skills/hard-cheese/SKILL.md should mention /gh at most once "
        "(in the out-of-scope row of Preferred tools)"
    )


# ---------------------------------------------------------------------------
# Spec-promised behaviours that must stay documented


def test_slug_fallback_documented(skill_body: str) -> None:
    """Spec: when no slug is supplied, fall back to HEAD short SHA."""
    text = skill_body.lower()
    assert "short sha" in text or "short-sha" in text
    assert "head" in text and "fallback" in text


def test_freshness_check_documented(skill_body: str) -> None:
    """Spec: re-invocation against same HEAD skips with `previously passed`."""
    text = skill_body.lower()
    assert "freshness" in text
    assert "previously passed" in text
    assert "diff_head" in text


def test_judge_runs_in_fresh_context(skill_body: str, judge_prompt: str) -> None:
    """Load-bearing invariant: the judge sub-agent MUST run in fresh context.
    Same-context judging is the failure mode the gate exists to avoid.
    """
    assert "fresh context" in skill_body.lower() or "fresh-context" in skill_body.lower()
    assert "fresh context" in judge_prompt.lower() or "fresh-context" in judge_prompt.lower()
    # Negative bias clause must be present somewhere in the skill or prompt
    combined = (skill_body + judge_prompt).lower()
    assert "bias" in combined, "must document the same-context bias rationale"


def test_non_tty_guard_documented(skill_body: str) -> None:
    """Spec: --auto --hard must abort cleanly in non-TTY environments
    rather than vacuously pass the gate with no human in the loop.
    """
    text = skill_body.lower()
    composition = (HARD / "references" / "composition.md").read_text(encoding="utf-8").lower()
    combined = text + composition
    assert "tty" in combined
    assert "interactive" in combined


def test_cap_exhaustion_blocks_chain(skill_body: str) -> None:
    """Spec: --socratic-cap exhaustion sets status=FAILED and exits non-zero
    so downstream chains do not proceed.
    """
    text = skill_body
    assert "FAILED" in text, "cap exhaustion status must be named"
    text_lower = text.lower()
    assert "non-zero" in text_lower or "exit 1" in text_lower or "exit `1`" in text_lower


def test_artifact_frontmatter_required_fields(skill_body: str) -> None:
    """Spec: artifact frontmatter must travel with attribution, rubric,
    divergence note, diff anchors, status, and attempt count so the audit
    trail is self-contained.
    """
    required = ["attribution", "rubric", "divergence", "diff_base", "diff_head", "status", "attempts"]
    for field in required:
        assert f"{field}:" in skill_body, f"artifact frontmatter must document `{field}:`"


def test_single_puncture_point_invariant() -> None:
    """The whole composition story rests on `--hard` puncturing `--auto`
    in exactly one place. composition.md and cure must both name the
    single puncture point so a future edit can't sneak in extra pauses.
    """
    comp = (HARD / "references" / "composition.md").read_text(encoding="utf-8").lower()
    cure = (SKILLS / "cure" / "SKILL.md").read_text(encoding="utf-8").lower()
    assert "single" in comp and "puncture" in comp
    assert "once" in cure or "single" in cure, "cure must name the single puncture point"


def test_attribution_uniform_across_artifacts() -> None:
    """The citation, the arxiv URL, the vibecheck repo URL, and the
    fail-open divergence note must all appear in the judge prompt as
    well — the rubric carries provenance just like the skill body.
    """
    judge = (HARD / "references" / "judge-prompt.md").read_text(encoding="utf-8")
    assert "Sankaranarayanan" in judge
    assert "arxiv.org/abs/2602.20206" in judge
    assert "github.com/sreecharansankaranarayanan/vibecheck" in judge


def test_cure_auto_puncture_clause_lives_in_auto_section() -> None:
    """Placement matters: the auto-puncture clause must live inside cure's
    `### Auto mode` section, not as a free-floating paragraph elsewhere.
    A future reader looking at auto mode must see it without searching.
    """
    cure = (SKILLS / "cure" / "SKILL.md").read_text(encoding="utf-8")
    auto_idx = cure.find("### Auto mode")
    assert auto_idx >= 0, "cure must have an `### Auto mode` section"
    rules_idx = cure.find("## Rules", auto_idx)
    auto_section = cure[auto_idx:rules_idx if rules_idx >= 0 else len(cure)]
    assert "--hard" in auto_section, "--hard puncture clause must live inside `### Auto mode`"
    assert "puncture" in auto_section.lower()


def test_judge_prompt_demands_diff_grounded_grading(judge_prompt: str) -> None:
    """The judge must steelman strict reading and demand diff-grounded
    cause-and-effect — these are the calibration rules. Without them a
    lenient judge silently lets template answers pass.
    """
    text = judge_prompt.lower()
    assert "strict" in text or "steelman" in text
    assert "cause-and-effect" in text or "cause and effect" in text
    assert "diff" in text


def test_judge_output_shape_is_documented(judge_prompt: str) -> None:
    """The parent skill parses the judge's JSON. The fields and constraints
    must be unambiguous — any ambiguity becomes a parser bug or a
    fail-open path that should not have fired.
    """
    text = judge_prompt
    for field in ["score", "level", "pass", "feedback", "socratic_qs"]:
        assert f'"{field}"' in text, f"judge output JSON must document `{field}` field"


def test_socratic_cap_default_is_three(skill_body: str) -> None:
    """Spec: default cap is 3. Capping at 1 would be hostile; capping at
    10 would create infinite-loop risk. The value is a contract.
    """
    text = skill_body
    assert "--socratic-cap N=3" in text or "Default `3`" in text or "Default 3" in text
