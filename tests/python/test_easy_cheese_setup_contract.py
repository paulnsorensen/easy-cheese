"""Contract tests for the Easy Cheese setup skill prose and command surface."""

from __future__ import annotations

import re
from pathlib import Path
from typing import cast

from easy_cheese.shared.bundle_commands import command_map, validate_command_surface
from easy_cheese.shared.hallouminate_setup import BEGIN, END
from easy_cheese.skills.easy_cheese_setup import commands as setup_commands

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills/easy-cheese-setup/SKILL.md"
REFERENCE = ROOT / "skills/easy-cheese-setup/references/commands.md"


def test_skill_documents_both_exact_markers() -> None:
    text = SKILL.read_text(encoding="utf-8")
    assert f"`{BEGIN}`" in text
    assert f"`{END}`" in text


def test_skill_never_documents_an_end_marker_without_the_identifier() -> None:
    text = SKILL.read_text(encoding="utf-8")
    truncated = [
        line
        for line in text.splitlines()
        if re.search(r"#\s*<<<(?!\s*easy-cheese:cheese-durable)", line)
    ]
    assert truncated == []


def test_skill_uses_one_term_for_each_meaning() -> None:
    """Prose uses `command` and `repository`. Code identifiers stay unchanged."""
    prose = re.sub(r"`[^`]*`", "", SKILL.read_text(encoding="utf-8"))
    assert "subcommand" not in prose
    assert re.search(r"\brepos?\b", prose) is None


def test_skill_does_not_name_the_configuration_path_as_universal() -> None:
    text = SKILL.read_text(encoding="utf-8")
    assert "config_path()" in text
    assert "HALLOUMINATE_CONFIG" in text


def test_command_surface_declares_exactly_the_three_legs() -> None:
    validate_command_surface(setup_commands, setup_commands.COMMANDS)
    assert sorted(command_map(setup_commands.COMMANDS)) == ["doctor", "global", "local"]


def test_every_command_target_resolves_to_the_shared_leg() -> None:
    for command in setup_commands.COMMANDS:
        module, _, attribute = command.target.partition(":")
        assert module == setup_commands.__name__
        handler = cast(object, getattr(setup_commands, attribute))
        assert callable(handler)


def test_generated_reference_matches_every_command_summary() -> None:
    text = REFERENCE.read_text(encoding="utf-8")
    for command in setup_commands.COMMANDS:
        assert f"| `{command.name}` | {command.summary} |" in text
