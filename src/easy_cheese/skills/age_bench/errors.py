"""Shared error base for the age-bench judge/scoreboard/cases slice."""

from __future__ import annotations

from easy_cheese.shared import cli


class AgeBenchError(cli.CliError):
    """Base error for producers in the age-bench judge/scoreboard/cases slice."""
