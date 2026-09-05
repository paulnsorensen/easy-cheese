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


def test_cascade_does_not_depend_on_hidden_git_configuration() -> None:
    """Stage 2 and stage 3 declare a preflight and an explicit tool."""
    skill = SKILL.read_text()

    assert "git config --get rerere.enabled" in skill
    assert "git config --get merge.tool" in skill
    assert "git config --global rerere.enabled true" in skill
    assert "git mergetool --tool=kdiff3" in skill
    assert "\ngit mergetool\n" not in skill


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


def test_plate_option_requires_a_complete_git_operation() -> None:
    """Prose states the precondition that makes the Plate dispatch safe."""
    skill = SKILL.read_text()

    assert "Run the continuation command first for `plate-it`." in skill
    assert "no unmerged paths and no interrupted operation" in skill