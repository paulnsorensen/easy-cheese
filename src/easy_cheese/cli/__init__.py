"""``easy_cheese.cli``: the single owner of the shared CLI reply envelope.

A phase or bundle command that speaks the one-line-JSON-on-stdout contract
imports its exit codes, usage exception, and emit/refuse helpers from here
rather than keeping a second copy.
"""

from __future__ import annotations

from easy_cheese.cli.envelope import (
    EXIT_INTERNAL,
    EXIT_OK,
    EXIT_REFUSED,
    EXIT_USAGE,
    BadUsage,
    Parser,
    Refused,
    emit,
    refuse,
)

__all__ = [
    "EXIT_INTERNAL",
    "EXIT_OK",
    "EXIT_REFUSED",
    "EXIT_USAGE",
    "BadUsage",
    "Parser",
    "Refused",
    "emit",
    "refuse",
]
