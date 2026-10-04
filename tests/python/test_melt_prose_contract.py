"""Melt prose keeps the contracts that the review round applied."""

import re
from pathlib import Path
from typing import cast

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL = REPO_ROOT / "skills/melt/SKILL.md"
CASCADE = REPO_ROOT / "skills/melt/references/cascade-stages.md"


def test_format_support_comes_from_conflict_summary() -> None:
    """Step 4 reads the command result instead of a static format list."""
    cascade = CASCADE.read_text()

    assert "These formats include shell, SQL, YAML, and JSON." not in cascade
    assert "mergiraf_supported" in cascade
    assert "recommendation" in cascade
    assert "Do not use a static format list." in cascade


def test_cascade_uses_operation_for_mechanical_state() -> None:
    skill = SKILL.read_text()

    assert "melt.pyz detect-squash-residue --apply" in skill
    assert "melt.pyz operation --continue" in skill
    assert "git config --get" not in skill
    assert "git rebase --continue" not in skill
    assert skill.index("batch-resolve --debug") < skill.index("batch-resolve --apply")

def _handoff_gate() -> dict[str, object]:
    """Return the parsed handoff gate record from the Melt skill file."""
    pattern = r"```yaml\n(handoff_gate:.*?)```"
    blocks = cast("list[str]", re.findall(pattern, SKILL.read_text(), re.S))
    assert len(blocks) == 1, "Melt declares exactly one handoff gate record"
    document = cast("dict[str, dict[str, object]]", yaml.safe_load(blocks[0]))
    return document["handoff_gate"]


def _gate_options() -> list[dict[str, str]]:
    """Return the option records of the Melt handoff gate."""
    return cast("list[dict[str, str]]", _handoff_gate()["options"])


def test_handoff_gate_declares_every_required_field() -> None:
    """The gate carries the fields that handoff-gate.md requires."""
    gate = _handoff_gate()
    options = _gate_options()

    assert gate["source_skill"] == "/melt"
    assert gate["id"] == "post-melt-next-step"
    assert gate["prompt"]
    assert gate["multi"] is False
    assert gate["recommended"] in [option["id"] for option in options]

    for option in options:
        assert option["label"]
        assert option["description"]
        actions = [key for key in ("dispatch", "continue") if key in option]
        assert actions in (["dispatch"], ["continue"]), option["id"]


def test_handoff_gate_carries_the_standard_tail() -> None:
    """The gate appends Plate it, Checkpoint and stop, and Stop."""
    options = {option["id"]: option for option in _gate_options()}

    assert options["plate-it"]["dispatch"] == "/plate"
    assert options["checkpoint-and-stop"]["dispatch"] == "/wheypoint"
    assert options["stop"]["dispatch"] == "none"


def test_handoff_does_not_repeat_continuation() -> None:
    gate = _handoff_gate()
    options = {option["id"]: option for option in _gate_options()}

    assert gate["recommended"] == "rerun-upstream"
    assert "resume-operation" not in options
    assert "continuation" not in str(options["plate-it"])
    assert "continue" not in str(options["plate-it"])
    assert "Handoff only when status is `complete`" in SKILL.read_text()


def test_frontmatter_targets_conflict_requests_only() -> None:
    frontmatter = SKILL.read_text().split("---", 2)[1]
    description = cast("dict[str, str]", yaml.safe_load(frontmatter))["description"].lower()

    for phrase in ("merge", "rebase", "cherry-pick", "pull", "conflict", "unmerged paths"):
        assert phrase in description
    assert re.search(r"needs merge.*unmerged path", description)
    assert ", needs merge," not in description
    assert "clean git operations" in description
    assert "review-only" in description
    assert "mergiraf" not in description