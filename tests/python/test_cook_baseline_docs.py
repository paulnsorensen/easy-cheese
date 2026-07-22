"""Content-asserting tests for cook/SKILL.md's baseline-aware quality-gate prose.

Guards against a future edit silently dropping the baseline policy: each
assertion targets one of the four WHEN clauses in the cook handoff (lazy
capture; identical->record+continue; new/changed->2-round bounded fix with
same-signature-twice halt; design-shaped->halt with classification).
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills" / "cook" / "SKILL.md"
QUALITY_GATES = ROOT / "skills" / "cook" / "references" / "quality-gates.md"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def section_after(skill: str, header: str) -> str:
    """Body between a line-start `header` and the next line-start `## `."""
    marker = "\n" + header + "\n"
    start = skill.index(marker) + len(marker)
    rest = skill[start:]
    return rest.split("\n## ", 1)[0]


def gates_section(skill: str) -> str:
    return section_after(skill, "## Quality gates")


def test_quality_gates_section_links_shared_baseline_reference() -> None:
    skill = read(SKILL)
    assert QUALITY_GATES.is_file()
    section = gates_section(skill)
    assert "references/quality-gates.md" in section


def test_bare_cook_lazily_captures_baseline_with_no_frame() -> None:
    section = gates_section(read(SKILL))
    assert "no baseline yet" in section or "no frame" in section
    assert "lazily" in section
    assert "pre-change tree" in section


def test_identical_failures_are_recorded_and_never_halt() -> None:
    section = gates_section(read(SKILL))
    identical_line = next(
        line for line in section.splitlines() if line.strip().startswith("- **Identical")
    )
    assert "baseline" in identical_line
    assert "never halt" in identical_line


def test_new_or_changed_failures_get_bounded_two_round_fix() -> None:
    section = gates_section(read(SKILL))
    new_line = next(
        line for line in section.splitlines() if line.strip().startswith("- **New or changed")
    )
    assert "2 rounds" in new_line
    assert "twice" in new_line and "halt" in new_line


def test_halt_conditions_include_design_shaped_and_carry_classification() -> None:
    section = gates_section(read(SKILL))
    halt_line = next(
        line for line in section.splitlines() if line.strip().startswith("- **Halt**")
    )
    assert "design-shaped" in halt_line
    assert "classification" in halt_line


def test_auto_mode_early_stop_exempts_identical_and_defers_to_baseline_policy() -> None:
    skill = read(SKILL)
    section = skill.split("### When auto mode stops early", 1)[1].split("\n### ", 1)[0]
    assert "references/quality-gates.md" in section
    assert "new" in section.lower() and "changed" in section.lower()
    assert "Identical-to-baseline failures" in section
    assert "never stop auto" in section


def test_handoff_slug_schema_carries_optional_baseline_field() -> None:
    skill = read(SKILL)
    schema = section_after(skill, "## Handoff slug")
    assert "baseline: omitted" in schema
    assert "quality-gates.md" in schema
