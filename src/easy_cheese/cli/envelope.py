"""The shared CLI reply envelope: exit codes, usage errors, and JSON emission.

Every wheypoint-family command reports one line of JSON on stdout, success or
refusal, under a four-code exit ladder (``ok``/``refused``/``usage``/
``internal``). This module is the single owner of that ladder and its
argparse/emit/refuse plumbing, so no caller keeps a second copy.
"""

from __future__ import annotations

import argparse
import json
from typing import NoReturn, TextIO

from typing_extensions import override

EXIT_OK = 0
EXIT_REFUSED = 1
EXIT_USAGE = 2
EXIT_INTERNAL = 3


class BadUsage(Exception):
    """argparse's complaint, raised instead of printed so it can be JSON."""


class Parser(argparse.ArgumentParser):
    @override
    def error(self, message: str) -> NoReturn:
        raise BadUsage(message)


class Refused(Exception):
    """A command that has an error shape to report rather than a payload."""

    def __init__(
        self, code: str, message: str, extra: dict[str, object] | None = None
    ) -> None:
        super().__init__(message)
        self.code: str = code
        self.extra: dict[str, object] = {} if extra is None else extra


def emit(stdout: TextIO, payload: dict[str, object]) -> None:
    _ = stdout.write(json.dumps(payload, sort_keys=True) + "\n")


def refuse(
    stdout: TextIO,
    command: str,
    code: str,
    message: str,
    status: int,
    extra: dict[str, object] | None = None,
) -> int:
    emit(
        stdout,
        {
            "ok": False,
            "command": command,
            "error": {"code": code, "message": message, **(extra or {})},
        },
    )
    return status
