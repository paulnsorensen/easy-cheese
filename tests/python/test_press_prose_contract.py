"""Regression cover for the Press prose contracts that the r014 review found broken.

Each test locks one blocker, high, medium, or low finding from
`review-press.md` or an `edge-press-*.md` note, so a later edit cannot
silently restore the defect.
"""
from __future__ import annotations

import re
from pathlib import Path

from easy_cheese.shared.handoff import parse_handoff_slug

REPO_ROOT = Path(__file__).resolve().parents[2]
PRESS = REPO_ROOT / "skills" / "press"
SKILL = PRESS / "SKILL.md"
REFERENCES = PRESS / "references"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _output_preamble() -> str:
    """Return the fenced preamble that `## Output` tells Press to write."""
    skill = _read(SKILL)
    output = skill.split("## Output", 1)[1].split("\n## ", 1)[0]
    blocks: list[str] = re.findall(r"```markdown\n(.*?)```", output, re.DOTALL)
    assert len(blocks) == 1, "`## Output` must document exactly one preamble"
    return blocks[0]


def test_documented_preamble_parses_with_the_canonical_parser() -> None:
    """The blocker: `action:`/`telemetry:` parsed as the orientation."""
    template = _output_preamble()
    concrete = (
        template.replace("<canonical status field>", "ok")
        .replace("age | done", "age")
        .replace("<slug>", "outer-tdd-gates")
        .replace("<preserved Cook value>", "none")
        .replace("none | <baseline artifact path>", "none")
        .replace("<one-line orientation>", "Press hardening is green.")
    )

    slug = parse_handoff_slug(concrete)

    assert slug.status == "ok"
    assert slug.next_skill == "age"
    assert slug.artifact == ".cheese/cook/outer-tdd-gates.md"
    assert slug.durable_flags == "none"
    assert slug.baseline == "none"
    assert slug.orientation == "Press hardening is green."


def test_preamble_declares_no_press_only_keys() -> None:
    """`action:` and `telemetry:` belong in the report body, not the preamble."""
    template = _output_preamble()

    assert "action:" not in template
    assert "telemetry:" not in template


def test_press_never_routes_to_itself() -> None:
    """The shared writer rejects the undeclared `press -> press` transition."""
    skill = _read(SKILL)
    output = skill.split("\n## Output\n", 1)[1].split("\n## ", 1)[0]

    assert "| `press` |" not in output
    assert "next: age | done" in _output_preamble()
    assert "Do not write `next: press`." in skill


def test_artifact_names_the_consumed_cook_report() -> None:
    """Press and Cheese disagreed on the meaning of `artifact:`."""
    skill = _read(SKILL)

    assert "artifact: .cheese/cook/<slug>.md" in skill
    assert "`artifact:` names the consumed Cook report." in skill


def test_press_declares_its_input_flags() -> None:
    """Cook sends `--auto`, `--hard`, and `--open-pr`; Press must accept them."""
    skill = _read(SKILL)

    assert "/press <slug> [--auto] [--hard] [--open-pr]" in skill
    assert "`--open-pr` is publication permission. Only the user supplies it." in skill
    assert "Press never adds it." in skill


def test_auto_mode_forwards_only_supplied_flags() -> None:
    """Auto mode must not invent publication permission."""
    skill = _read(SKILL)
    auto = skill.split("\n## Auto mode\n", 1)[1].split("\n## ", 1)[0]

    assert "Dispatch `/age <slug> --auto`" in auto
    assert "Add `--hard` when the user supplied it." in auto
    assert "Add `--open-pr` when the user supplied it." in auto


def test_no_chain_directive_names_cook_not_ultracook() -> None:
    """Cook's fan pathway owns the retired Ultracook directive."""
    skill = _read(SKILL)

    assert "Cook's fan pathway owns this directive." in skill
    assert "Test for the directive itself. Do not test for the source name." in skill
    # Press must not gate the directive on the retired source name.
    assert "If `/ultracook` sets" not in skill


def test_report_body_carries_the_age_review_follow_ups() -> None:
    """Age requires a summary of unresolved Press items."""
    skill = _read(SKILL)

    assert "## Review follow-ups" in skill
    assert "Age reads this section." in skill
    assert "`ok-with-concerns: <concern>`" in skill


def test_baseline_is_one_artifact_reference() -> None:
    """The handoff preamble accepts one physical line for each key."""
    skill = _read(SKILL)

    assert "The Cook `baseline:` line names one artifact." in skill
    assert "<Cook baseline block>" not in skill


def test_third_red_does_not_dispatch_age() -> None:
    """`gap-analysis.md` and `SKILL.md` gave two dispositions."""
    gap = _read(REFERENCES / "gap-analysis.md")

    assert "ready for terminal reporting" in gap
    assert "Press does not dispatch Age after that result." in gap


def test_gap_analysis_defines_its_attempt_terms() -> None:
    """`P1`, `P2`, and `P3` were undefined in this area."""
    gap = _read(REFERENCES / "gap-analysis.md")

    assert "attempt 1, 1 for attempt 2, and 2 for attempt 3" in gap
    assert not re.search(r"\bP[123]\b", gap)


def test_metadata_paths_are_not_boundary_safe() -> None:
    """The audit accepted non-test metadata changes."""
    telemetry = _read(REFERENCES / "telemetry.md")

    assert "The `metadata` class does not make a path boundary-safe." in telemetry
    assert "Classify the attempt as `production_changed`" in telemetry


def test_command_summary_names_every_public_action() -> None:
    """`press-route` also returns the `/age` dispatch."""
    commands = _read(REFERENCES / "commands.md")

    assert "continue, dispatch /age, or stop" in commands
