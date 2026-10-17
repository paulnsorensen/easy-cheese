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
        .replace("age | cook | done", "age")
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
    assert "next: age | cook | done" in _output_preamble()
    assert "next: press" not in skill


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


def test_finding_hands_off_to_cook_and_green_to_age() -> None:
    """A finding is a Cook correction; only GREEN reaches Age."""
    skill = _read(SKILL)
    gap = _read(REFERENCES / "gap-analysis.md")

    assert "| finding (an attack test exposes a defect) | `ok-with-concerns: <defect>` | `cook` |" in skill
    assert "A `next: cook` handoff is a Cook correction (`correction = true`)." in skill
    assert "- GREEN hands off to `/age`." in gap
    assert "- A finding hands off to Cook as a correction (`next: cook`)." in gap
    assert "- Invalid evidence and production changes stop." in gap


def test_press_outcome_vocabulary_has_no_red_gate() -> None:
    """The RED gate is removed; Press selects one of four outcomes."""
    skill = _read(SKILL)
    gap = _read(REFERENCES / "gap-analysis.md")
    outcomes = "`green`, `finding`, `invalid_evidence`, or `production_changed`"

    assert outcomes in skill
    assert outcomes in gap
    for removed in ("in_contract_red", "third-red", "press-corrective-cook", "RED gate"):
        assert removed not in skill
        assert removed not in gap


def test_gap_analysis_preserves_the_attack() -> None:
    """Replays reuse one attack; weakening it to reach GREEN is forbidden."""
    gap = _read(REFERENCES / "gap-analysis.md")

    assert "Run the same adversarial attack. Do not change its test or fixture digest." in gap
    assert "Never weaken the attack to obtain GREEN." in gap


def test_press_has_no_retired_route_or_telemetry_references() -> None:
    """`press-route`, `press-telemetry`, and the telemetry reference are gone."""
    assert not (REFERENCES / "telemetry.md").exists()
    commands = _read(REFERENCES / "commands.md")
    skill = _read(SKILL)

    for removed in ("press-route", "press-telemetry"):
        assert removed not in commands
        assert removed not in skill