"""Render safe timestamped timing sections for workflow artifacts."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cli


_SENSITIVE_REPLACEMENTS = (
    (re.compile(r"(?i)(authorization:\s*(?:bearer|token)\s+)[^\s|]+"), r"\1[redacted]"),
    (
        re.compile(
            r"(?i)\b([\w-]*(?:token|api[_-]?key|password|secret))"
            r"(\s*[:=]\s*)([^\s|]+)"
        ),
        r"\1\2[redacted]",
    ),
)


def utc_now() -> str:
    """Return the current UTC wall-clock time at whole-second precision."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def format_duration_ms(duration_ms: Any) -> str:
    if isinstance(duration_ms, bool) or not isinstance(duration_ms, int):
        raise ValueError("duration_ms must be an integer number of milliseconds")
    if duration_ms < 0:
        raise ValueError("duration_ms must be non-negative")
    if duration_ms < 1_000:
        return f"{duration_ms}ms"

    seconds = round(duration_ms / 1_000)
    hours, remainder = divmod(seconds, 3_600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}h{minutes:02d}m{seconds:02d}s"
    if minutes:
        return f"{minutes}m{seconds:02d}s"
    return f"{seconds}s"


def _timestamp(payload: Mapping[str, Any], key: str) -> datetime:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be an ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{key} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{key} must include a UTC offset")
    return parsed.astimezone(timezone.utc)


def _format_timestamp(value: datetime) -> str:
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def _clean_cell(value: Any) -> str:
    if value is None:
        return "-"
    text = " ".join(str(value).replace("\r", " ").replace("\n", " ").split())
    if not text:
        return "-"
    for pattern, replacement in _SENSITIVE_REPLACEMENTS:
        text = pattern.sub(replacement, text)
    return text.replace("|", r"\|")


def _non_negative_integer(value: Any, field: str, *, default: int | None = None) -> str:
    if value is None and default is not None:
        value = default
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field} must be an integer")
    if value < 0:
        raise ValueError(f"{field} must be non-negative")
    return str(value)


def _format_items(phase: Mapping[str, Any]) -> str:
    items = [
        f"{_non_negative_integer(phase[key], key)} {label}"
        for key, label in (("items_seen", "seen"), ("items_actionable", "actionable"))
        if phase.get(key) is not None
    ]
    return " / ".join(items) or "-"


def _phase_name(phase: Mapping[str, Any]) -> str:
    name = phase.get("phase")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("phase is required")
    return _clean_cell(name)


def _phases(payload: Mapping[str, Any]) -> Sequence[Any]:
    phases = payload.get("phases")
    if not isinstance(phases, Sequence) or isinstance(phases, (str, bytes)):
        raise ValueError("timing payload must contain a phases list")
    if not phases:
        raise ValueError("phases list must not be empty")
    return phases


def render_timing_section(payload: Mapping[str, Any]) -> str:
    started_at = _timestamp(payload, "started_at")
    ended_at = _timestamp(payload, "ended_at")
    if ended_at < started_at:
        raise ValueError("ended_at must not precede started_at")

    rows = [
        "## Timing",
        "",
        f"- Started: `{_format_timestamp(started_at)}`",
        f"- Ended: `{_format_timestamp(ended_at)}`",
        "",
        "| Phase | Duration | Attempts | Status | Items | Notes |",
        "| --- | ---: | ---: | --- | --- | --- |",
    ]
    for raw_phase in _phases(payload):
        if not isinstance(raw_phase, Mapping):
            raise ValueError("each phase must be an object")
        rows.append(
            f"| {_phase_name(raw_phase)} "
            f"| {format_duration_ms(raw_phase.get('duration_ms'))} "
            f"| {_non_negative_integer(raw_phase.get('attempts'), 'attempts', default=1)} "
            f"| {_clean_cell(raw_phase.get('status', 'ok'))} "
            f"| {_format_items(raw_phase)} "
            f"| {_clean_cell(raw_phase.get('notes'))} |"
        )
    return "\n".join(rows) + "\n"


def _load_payload(path: str) -> Mapping[str, Any]:
    if path == "-":
        raw = sys.stdin.read()
    else:
        raw = Path(path).read_text(encoding="utf-8")
    payload = json.loads(raw)
    if not isinstance(payload, Mapping):
        raise ValueError("timing payload must be an object")
    return payload


def _cmd_now(_: argparse.Namespace) -> None:
    cli.emit(utc_now())


def _cmd_render(args: argparse.Namespace) -> None:
    try:
        sys.stdout.write(render_timing_section(_load_payload(args.path)))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise cli.CliError(f"timing: {exc}") from exc


def _setup(parser: argparse.ArgumentParser) -> None:
    parser.description = "Create UTC timestamps and render workflow timing Markdown."
    sub = parser.add_subparsers(dest="cmd")
    now = sub.add_parser("now", help="print the current ISO-8601 UTC timestamp")
    now.set_defaults(func=_cmd_now)
    render = sub.add_parser("render", help="render timing JSON as Markdown")
    render.add_argument("path", nargs="?", default="-", help="JSON path; default: stdin")
    render.set_defaults(func=_cmd_render)


if __name__ == "__main__":
    cli.run(_setup)
