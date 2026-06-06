#!/usr/bin/env python3
"""Render /affinage phase timings as a durable Markdown report section."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Mapping, Sequence
from typing import Any

_SENSITIVE_REPLACEMENTS = (
    (re.compile(r"(?i)(authorization:\s*(?:bearer|token)\s+)[^\s|]+"), r"\1[redacted]"),
    (
        re.compile(r"(?i)\b([\w-]*(?:token|api[_-]?key|password|secret))(\s*[:=]\s*)([^\s|]+)"),
        r"\1\2[redacted]",
    ),
)


def format_duration_ms(duration_ms: Any) -> str:
    if isinstance(duration_ms, bool) or not isinstance(duration_ms, int):
        raise ValueError("duration_ms must be an integer number of milliseconds")
    if duration_ms < 0:
        raise ValueError("duration_ms must be non-negative")
    if duration_ms < 1000:
        return f"{duration_ms}ms"

    seconds = round(duration_ms / 1000)
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}h{minutes:02d}m{seconds:02d}s"
    if minutes:
        return f"{minutes}m{seconds:02d}s"
    return f"{seconds}s"


def _clean_cell(value: Any) -> str:
    if value is None:
        return "-"
    text = " ".join(str(value).replace("\r", " ").replace("\n", " ").split())
    if not text:
        return "-"
    for pattern, replacement in _SENSITIVE_REPLACEMENTS:
        text = pattern.sub(replacement, text)
    return text.replace("|", r"\|")


def _format_attempts(value: Any) -> str:
    if value is None:
        return "1"
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("attempts must be an integer")
    if value < 0:
        raise ValueError("attempts must be non-negative")
    return str(value)


def _format_items(phase: Mapping[str, Any]) -> str:
    seen = phase.get("items_seen")
    actionable = phase.get("items_actionable")
    if seen is None and actionable is None:
        return "-"
    parts: list[str] = []
    if seen is not None:
        parts.append(f"{_format_count(seen)} seen")
    if actionable is not None:
        parts.append(f"{_format_count(actionable)} actionable")
    return " / ".join(parts)


def _format_count(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("item counts must be integers")
    if value < 0:
        raise ValueError("item counts must be non-negative")
    return str(value)


def _phase_name(phase: Mapping[str, Any]) -> str:
    name = phase.get("phase")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("phase is required")
    return _clean_cell(name)


def _iter_phases(payload: Mapping[str, Any] | Sequence[Any]) -> Sequence[Any]:
    phases = payload.get("phases") if isinstance(payload, Mapping) else payload
    if not isinstance(phases, Sequence) or isinstance(phases, (str, bytes)):
        raise ValueError("timing payload must contain a phases list")
    if not phases:
        raise ValueError("phases list must not be empty")
    return phases


def render_timing_section(payload: Mapping[str, Any] | Sequence[Any]) -> str:
    rows = [
        "## Timing",
        "",
        "| Phase | Duration | Attempts | Status | Items | Notes |",
        "| --- | ---: | ---: | --- | --- | --- |",
    ]
    for raw_phase in _iter_phases(payload):
        if not isinstance(raw_phase, Mapping):
            raise ValueError("each phase must be an object")
        row = (
            f"| {_phase_name(raw_phase)} "
            f"| {format_duration_ms(raw_phase.get('duration_ms'))} "
            f"| {_format_attempts(raw_phase.get('attempts'))} "
            f"| {_clean_cell(raw_phase.get('status', 'ok'))} "
            f"| {_format_items(raw_phase)} "
            f"| {_clean_cell(raw_phase.get('notes'))} |"
        )
        rows.append(row)
    return "\n".join(rows) + "\n"


def _load_json(path: str) -> Any:
    if path == "-":
        raw = sys.stdin.read()
    else:
        with open(path, encoding="utf-8") as handle:
            raw = handle.read()
    return json.loads(raw)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Render /affinage phase timing JSON as Markdown.",
    )
    parser.add_argument(
        "path",
        nargs="?",
        default="-",
        help="JSON file to render, or '-' / omitted for stdin",
    )
    args = parser.parse_args(argv)

    try:
        sys.stdout.write(render_timing_section(_load_json(args.path)))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        sys.stderr.write(f"timing: {exc}\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
