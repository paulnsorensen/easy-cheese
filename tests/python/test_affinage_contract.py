"""Contract regressions for the /affinage skill prose and its report grammar.

Each test guards one finding from the r014 megamerge affinage review round.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from easy_cheese.shared.findings import Finding, parse_findings_report

REPO_ROOT = Path(__file__).resolve().parents[2]
AFFINAGE = REPO_ROOT / "skills" / "affinage"
SKILL = AFFINAGE / "SKILL.md"
REFERENCES = AFFINAGE / "references"

VALID_LOCATION_TIERS = {"class", "module", "cross-module", "contract"}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _template_report() -> str:
    text = _read(REFERENCES / "report-template.md")
    return text.split("```markdown", 1)[1].split("```", 1)[0]


# --- blocker: a resolved merge conflict must reach publication ---------------


def test_melt_leaves_the_resolution_for_plate() -> None:
    conflict = _read(REFERENCES / "merge-conflict.md")
    assert "Let `/plate` own the resolution commit and the PR update." in conflict
    assert "`/melt` leaves the resolution uncommitted." in conflict
    assert "Let `/melt` or `/cure` own the resolution commit." not in conflict


def test_remote_status_recheck_follows_publication() -> None:
    conflict = _read(REFERENCES / "merge-conflict.md")
    publish = conflict.index("Run terminal `/plate` after every approved reply posts.")
    recheck = conflict.index("Then run `affinage.pyz pr-status` again")
    assert publish < recheck, "the remote status recheck must follow terminal /plate"


def test_publication_is_not_gated_on_a_cure_fix_alone() -> None:
    skill = _read(SKILL)
    assert "Also publish when `/melt` resolved a merge conflict." in skill
    assert (
        "Skip publication and write-back when the working tree has no change." in skill
    )
    assert "Skip publication and write-back when `/cure` applies no fix." not in skill


# --- blocker: the reply gate must cover cure replies ------------------------


def test_reply_gate_covers_applied_and_deferred_replies() -> None:
    templates = _read(REFERENCES / "handoff-templates.md")
    assert "Show the gate after `/cure` returns." in templates
    assert (
        "A drafted reply is an applied reply, a deferred reply, a push-back draft,"
        in templates
    )
    assert "or an investigation note." in templates
    assert (
        "Post every applied reply, every deferred reply, and every push-back draft."
        in templates
    )
    assert "Let the user select any drafted reply to post." in templates


def test_skill_drafts_replies_before_one_gate() -> None:
    skill = _read(SKILL)
    draft_cure = skill.index("10. **Draft cure replies.**")
    post = skill.index(
        "11. **Post replies.** Show one reply gate for every drafted reply."
    )
    publish = skill.index("12. **Publish.**")
    assert draft_cure < post < publish


# --- high: harness portability ----------------------------------------------


def test_skill_forbids_the_skill_dir_variable_in_invocation_paths() -> None:
    skill = _read(SKILL)
    assert (
        "Do not use the `${CLAUDE_SKILL_DIR}` environment variable in an invocation path."
        in skill
    )
    assert "only as an optional host fallback" not in skill
    assert (
        'The rule "slash commands are host renderings, not the control model" applies here.'
        in skill
    )


# --- high: canonical handback grammar ---------------------------------------


def test_halt_line_carries_the_status_key() -> None:
    skill = _read(SKILL)
    assert "Use `status: halt: <reason>` when `gh` or `pr-status` fails." in skill
    assert "Use `halt: <reason>` when" not in skill


# --- high: the report template must use valid location tiers ----------------


@pytest.mark.parametrize("finding", parse_findings_report(_template_report()))
def test_template_findings_use_a_valid_location_tier(finding: Finding) -> None:
    assert finding.location_tier in VALID_LOCATION_TIERS, (
        f"invalid location tier: {finding.location_tier!r}"
    )


# --- high: cure must be able to parse the affinage report -------------------


def test_cure_parser_reads_every_template_severity_finding() -> None:
    findings = parse_findings_report(_template_report())
    assert len(findings) == 5, "the shared parser must read every severity bullet"
    dimensions = {f.dimension for f in findings}
    assert {"security", "correctness", "efficiency", "deslop"} <= dimensions
    assert all(f.location for f in findings)
    assert all(f.recommendation for f in findings)


def test_provenance_moves_to_a_source_sub_field() -> None:
    template = _read(REFERENCES / "report-template.md")
    assert "  - source: from-comment:<id> · author: alice" in template
    assert "  - source: from-check:test-suite" in template
    assert "- **[from-comment:<id>] [security:blocker]**" not in template
    flow = _read(REFERENCES / "flow-details.md")
    assert "Add a `source: from-comment:<id>` line so `/cure` can reply." in flow


# --- high: the --hard seam reaches hard-cheese only through plate -----------


def test_affinage_forwards_hard_to_terminal_plate() -> None:
    skill = _read(SKILL)
    assert "- `--hard` — Pass the metacognitive gate flag to terminal `/plate`." in skill
    assert "Send terminal `/plate [--open-pr] [--hard] [--safe]`." in skill
    auto = _read(REFERENCES / "auto-mode.md")
    assert (
        "- Send terminal `/plate --open-pr [--hard]` only when the working tree has a change."
        in auto
    )


def test_only_plate_invokes_hard_cheese_after_verification() -> None:
    skill = _read(SKILL)
    plate_line = "`/plate` runs `/hard-cheese` after it verifies the final artifact."
    assert plate_line in skill
    assert "`/cure` does not call `/plate` in this chain." in skill
    assert "/hard-cheese" not in skill.replace(plate_line, ""), (
        "only the Plate boundary may name /hard-cheese"
    )


# --- medium: pr reference and auto stake ------------------------------------


def test_pr_reference_normalizes_before_the_integer_command() -> None:
    skill = _read(SKILL)
    assert (
        "`<pr-ref>` accepts a PR number, a `PR#<n>` reference, or a full GitHub PR URL."
        in skill
    )
    assert "Extract the integer before you call `pr-status`." in skill


def test_bare_auto_has_a_defined_stake_floor() -> None:
    skill = _read(SKILL)
    assert "Bare `--auto` uses the `medium+` default floor." in skill


# --- low: section ownership --------------------------------------------------


def test_affinage_owns_its_two_extra_sections() -> None:
    skill = _read(SKILL)
    assert "Use the severity sections from `/age`." in skill
    assert (
        "Add the `## Needs-investigation` and `## Reviewer-rejected` sections from `/affinage`."
        in skill
    )


# --- medium: STE100 single-term rule ----------------------------------------


def test_fresh_review_is_the_only_term_for_the_extra_age_pass() -> None:
    for path in [SKILL, *sorted(REFERENCES.glob("*.md"))]:
        text = _read(path)
        assert "Fresh-window" not in text, f"{path} uses a second fresh-review term"
        assert "fresh `/age` pass" not in text, f"{path} uses a third fresh-review term"
