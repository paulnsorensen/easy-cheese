"""Documentation-lint tests for ultracook's frame-owned baseline capture.

The `## Baseline capture` section in `skills/ultracook/SKILL.md` and the
`{baseline}` field in `skills/ultracook/references/curd-prompt.md` encode a
prose contract with no code path: nothing else fails if the wording rots. If
the capture-before-any-curd-cooks ordering, the tested-classifier reference,
or the substitution field silently disappear, a future editor could
reintroduce per-curd baseline capture (defeating the single-capture-per-run
guarantee) with no test catching it.

String-shaped, like test_ultracook_skills.py: these assert the clauses stay
written down, not that they parse into a grammar.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = REPO_ROOT / "skills"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _skill(name: str) -> str:
    return _read(SKILLS_DIR / name / "SKILL.md")


SECTION_HEADER = "## Baseline capture"


class TestBaselineCaptureSection:
    def test_section_exists(self) -> None:
        body = _skill("ultracook")
        assert SECTION_HEADER in body, (
            "ultracook SKILL.md must document the frame-owned baseline-capture "
            "contract, or the single-capture-per-run guarantee has no written spec"
        )

    def test_section_links_quality_gates_doc(self) -> None:
        body = _skill("ultracook")
        idx = body.find(SECTION_HEADER)
        assert idx != -1
        # Scope the link check to the section body (up to the next `## `
        # heading) so an unrelated link elsewhere in the file can't satisfy
        # this — the baseline section must itself point at the shared policy
        # doc rather than restating (and drifting from) the taxonomy inline.
        next_heading = body.find("\n## ", idx + len(SECTION_HEADER))
        section = body[idx:next_heading if next_heading != -1 else len(body)]
        assert "cook/references/quality-gates.md" in section, (
            "Baseline capture section must link quality-gates.md — the single "
            "source of truth for the classification taxonomy — instead of "
            "restating it inline where it can drift"
        )

    def test_capture_happens_before_any_curd_cooks(self) -> None:
        body = _skill("ultracook")
        idx = body.find(SECTION_HEADER)
        assert idx != -1
        next_heading = body.find("\n## ", idx + len(SECTION_HEADER))
        section = body[idx:next_heading if next_heading != -1 else len(body)]
        # This is the core ordering guarantee: capture happens once, before
        # fan-out, not once per curd. If this phrase is edited away, a
        # per-curd capture could creep back in unnoticed.
        assert "before any curd cooks" in section.lower(), (
            "Baseline capture must state it runs before any curd cooks — the "
            "ordering guarantee that makes capture frame-owned, not per-cook"
        )

    def test_classification_defers_to_tested_helper(self) -> None:
        body = _skill("ultracook")
        idx = body.find(SECTION_HEADER)
        assert idx != -1
        next_heading = body.find("\n## ", idx + len(SECTION_HEADER))
        section = body[idx:next_heading if next_heading != -1 else len(body)]
        # Classification must route through the tested helper, never get
        # eyeballed by the agent — this is what quality-gates.md mandates,
        # and the guarantee is worthless if the section stops naming it.
        assert "src/fanout/baseline.py::classify()" in section

    def test_manifest_baseline_block_referenced_for_parallel_mode(self) -> None:
        body = _skill("ultracook")
        idx = body.find(SECTION_HEADER)
        assert idx != -1
        next_heading = body.find("\n## ", idx + len(SECTION_HEADER))
        section = body[idx:next_heading if next_heading != -1 else len(body)]
        assert "baseline:" in section and "manifest.yaml" in section, (
            "Parallel mode must record the classified baseline in the run "
            "manifest's `baseline:` block so curd dispatches can read it back"
        )


class TestCurdPromptBaselineField:
    def test_substitution_list_carries_baseline_field(self) -> None:
        body = _read(SKILLS_DIR / "ultracook" / "references" / "curd-prompt.md")
        # Anchor to the literal substitution-list line rather than a bare
        # `{baseline}` substring match, so the field can't be satisfied by an
        # unrelated mention elsewhere in the template.
        assert "{spec_summary}`, `{baseline}`, `{prior_handoff}`" in body, (
            "curd-prompt.md's substitution list must declare `{baseline}` — "
            "without it the template body's `{baseline}` placeholder is undefined"
        )

    def test_template_body_substitutes_baseline(self) -> None:
        body = _read(SKILLS_DIR / "ultracook" / "references" / "curd-prompt.md")
        assert "Baseline: {baseline}" in body, (
            "curd-prompt.md's template body must substitute {baseline} so each "
            "curd's cook dispatch receives the manifest's baseline block"
        )

    def test_baseline_field_states_a_curd_never_captures_its_own(self) -> None:
        body = _read(SKILLS_DIR / "ultracook" / "references" / "curd-prompt.md")
        idx = body.find("Baseline: {baseline}")
        assert idx != -1
        line_end = body.find("\n", idx)
        line = body[idx:line_end if line_end != -1 else len(body)]
        # Regression the field guards against: a curd re-capturing its own
        # baseline instead of reusing the run-level capture, which would
        # silently reintroduce per-curd redundant gate runs.
        assert "never capture" in line, (
            "{baseline} field must state a curd never captures its own "
            "baseline — the whole point of threading the value down"
        )
